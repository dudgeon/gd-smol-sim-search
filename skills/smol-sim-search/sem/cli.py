"""Command-line interface. See references/cli.md for the full reference."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from importlib import metadata
from pathlib import Path

from . import __version__
from .env import (SemError, default_model_key, get_paths, install_network_guard, load_install_info,
                  load_registry, log, model_spec, network_guard_active)


class Ctx:
    def __init__(self, args, paths):
        self.args = args
        self.paths = paths
        self._embedders: dict = {}

    def default_model(self) -> str:
        return getattr(self.args, "model", None) or default_model_key()

    def embedder(self, key: str):
        if key not in self._embedders:
            from .embed import load_embedder
            self._embedders[key] = load_embedder(self.paths, key)
        return self._embedders[key]



# --- helpers -----------------------------------------------------------------------

def _open(ctx: Ctx, check_model: bool = True):
    from .indexer import check_model_compat
    from .store import open_index
    idx = open_index(ctx.paths, ctx.args.index)
    if check_model:
        check_model_compat(idx.manifest, getattr(ctx.args, "model", None), ctx.paths)
    return idx


def _query_vec(ctx: Ctx, idx, text: str, kind: str = "query"):
    emb = ctx.embedder(idx.model_key)
    return emb.encode([text], kind)[0]


def _fmt_hit(i: int, h: dict) -> str:
    head = f"{i:>2}. {h['score']:.3f}  " if "score" in h else f"{i:>2}. "
    head += f"{h['path']} {h['locator']}  [{h['chunk_id']}]"
    if h.get("heading"):
        head += f"\n    § {h['heading']}"
    body = "\n".join("    " + ln for ln in h["text"].splitlines()[:8])
    return head + ("\n" + body if body else "")


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def _dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


# --- commands ----------------------------------------------------------------------

def cmd_doctor(ctx: Ctx) -> tuple[dict, str, int]:
    paths = ctx.paths
    problems, warnings = [], []
    info = load_install_info(paths)
    rt = paths.runtime
    if not rt or not rt.exists():
        problems.append("runtime not found; run ./setup.sh from the smol-sim-search repo in your terminal")
    elif not info:
        problems.append(f"runtime at {rt} has no install.json; re-run ./setup.sh")

    def ver(pkg):
        try:
            return metadata.version(pkg)
        except metadata.PackageNotFoundError:
            return None

    pkgs = {p: ver(p) for p in ("onnxruntime", "tokenizers", "numpy", "pypdf")}
    for p in pkgs:
        if pkgs[p] is None:
            problems.append(f"python package '{p}' is missing from the runtime; re-run ./setup.sh")

    reg = load_registry()
    models = {}
    from .embed import installed_revision
    for key, spec in reg["models"].items():
        if spec.get("hidden"):
            continue
        rev = installed_revision(paths, key) if paths.models_dir else None
        if rev:
            models[key] = {"revision": rev, "pinned": spec["revision"], "ok": rev == spec["revision"],
                           "repo_id": spec["repo_id"]}
            if rev != spec["revision"]:
                warnings.append(f"model {key} installed at {rev[:10]}, registry pins {spec['revision'][:10]}")
    dflt = default_model_key()
    if dflt not in models and not model_spec(dflt).get("backend") == "hash":
        problems.append(f"default model '{dflt}' is not installed; run ./setup.sh")

    # cwd writable (ensure_sem_home already created .sem; verify a real write)
    writable = True
    try:
        t = paths.tmp / f"doctor-{os.getpid()}"
        t.write_text("ok")
        t.unlink()
    except OSError as e:
        writable = False
        problems.append(f"cannot write to {paths.sem_home}: {e}")

    # env: every cache/tmp must point into ./.sem
    home_env = {}
    for var in ("TMPDIR", "XDG_CACHE_HOME"):
        home_env[var] = os.environ.get(var)
    for var in ("TMPDIR", "XDG_CACHE_HOME"):
        v = os.environ.get(var)
        if not v or not Path(v).resolve().is_relative_to(paths.sem_home.resolve()):
            warnings.append(f"{var} is not inside {paths.sem_home} (run sem through its bin/sem wrapper)")

    net = {"guard_active": network_guard_active()}


    load = None
    if ctx.args.full and not problems:
        t0 = time.time()
        try:
            e = ctx.embedder(dflt)
            v = e.encode(["hello world"], "document")
            load = {"ok": bool(abs(float((v[0] ** 2).sum()) - 1.0) < 1e-3), "seconds": round(time.time() - t0, 2)}
        except Exception as ex:  # report, don't crash
            load = {"ok": False, "error": f"{type(ex).__name__}: {ex}"}
            problems.append(f"model load failed: {load['error']}")

    out = {
        "ok": not problems,
        "sem_version": __version__,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        "runtime": str(rt) if rt else None,
        "install": info,
        "packages": pkgs,
        "models": models,
        "default_model": dflt,
        "sem_home": str(paths.sem_home),
        "cwd_writable": writable,
        "env": home_env,
        "network": net,
        "model_load": load,
        "problems": problems,
        "warnings": warnings,
    }
    lines = [f"sem {__version__} — {'OK' if not problems else 'PROBLEMS FOUND'}",
             f"  runtime:   {rt}",
             f"  python:    {out['python']}   onnxruntime {pkgs['onnxruntime']}   tokenizers {pkgs['tokenizers']}",
             f"  models:    " + (", ".join(f"{k}@{v['revision'][:10]}" for k, v in models.items()) or "none"),
             f"  default:   {dflt}",
             f"  index dir: {paths.sem_home} (writable: {writable})",
             f"  network:   {'blocked (socket guard on)' if net['guard_active'] else 'guard OFF'}"]
    if load:
        lines.append(f"  model load: {'ok' if load.get('ok') else 'FAILED'}")
    lines += [f"  ! {p}" for p in problems] + [f"  ~ {w}" for w in warnings]
    return out, "\n".join(lines), 0 if not problems else 1


def cmd_index(ctx: Ctx):
    from .indexer import run_index
    from .ingest import MAX_BYTES_DEFAULT, ReaderOpts
    a = ctx.args
    opts = ReaderOpts(text_field=a.text_field, id_field=a.id_col,
                      text_cols=[c.strip() for c in a.text_cols.split(",")] if a.text_cols else None)
    res = run_index(ctx.paths, ctx, a.index, a.paths, a.model, a.include or [], a.exclude or [], opts,
                    a.chunk_tokens, a.overlap, a.rebuild,
                    int(a.max_mb * 1024 * 1024) if a.max_mb else MAX_BYTES_DEFAULT, not a.no_gitignore)
    lines = [f"index '{res['index']}' ({res['model']}): {res['files_seen']} files seen, "
             f"{len(res['added'])} added, {len(res['changed'])} changed, {len(res['removed'])} removed, "
             f"{res['unchanged']} unchanged; {res['chunks_embedded']} chunks embedded in {res['seconds']}s"]
    for label in ("added", "changed", "removed"):
        items = res[label]
        if items and len(items) <= 20:
            lines.append(f"  {label}: " + ", ".join(items))
    if res["skipped"]:
        lines.append("  skipped: " + ", ".join(res["skipped"][:20]))
    if res["compacted"]:
        lines.append("  (compacted tombstoned rows)")
    return res, "\n".join(lines), 0


def cmd_search(ctx: Ctx):
    from .analyze import ranked
    a = ctx.args
    idx = _open(ctx)
    q = _query_vec(ctx, idx, a.query)
    hits = ranked(idx, q, a.k, a.min_score, a.path_glob, a.group_by_file, snip=a.snippet)
    res = {"index": idx.name, "model": idx.model_key, "query": a.query, "results": hits}
    human = "\n".join(_fmt_hit(i + 1, h) for i, h in enumerate(hits)) or "no results"
    return res, human, 0


def cmd_similar(ctx: Ctx):
    from .analyze import similar
    a = ctx.args
    idx = _open(ctx)
    res = similar(idx, a.item, a.k, a.group_by_file, a.snippet, a.path_glob)
    res = {"index": idx.name, "model": idx.model_key, **res}
    human = f"nearest to {res['item']}:\n" + ("\n".join(_fmt_hit(i + 1, h) for i, h in enumerate(res["results"]))
                                              or "no results")
    return res, human, 0


def cmd_compare(ctx: Ctx):
    from .analyze import compare_vecs, resolve_item
    a = ctx.args
    if a.text:
        key = a.model
        idx = None
        if key is None:
            from .store import read_manifest
            m = read_manifest(ctx.paths, a.index)
            key = m["model"]["key"] if m else default_model_key()
        emb = ctx.embedder(key)
        v = emb.encode([a.a, a.b], "document")
        res = {"model": key, "a": a.a, "b": a.b, "score": round(float(v[0] @ v[1]), 4)}
        return res, f"{res['score']:.4f}  cosine ({key})", 0
    idx = _open(ctx)
    ia, ib = resolve_item(idx, a.a), resolve_item(idx, a.b)
    res = {"index": idx.name, "model": idx.model_key, **compare_vecs(idx, ia, ib, a.pairs, a.snippet)}
    lines = [f"{res['score']:.4f}  {res['a']}  <->  {res['b']}"]
    for p in res.get("best_chunk_pairs", []):
        lines.append(f"  {p['score']:.3f}  {p['a']['locator']}  <->  {p['b']['locator']}")
    return res, "\n".join(lines), 0


def cmd_dupes(ctx: Ctx):
    from .analyze import dupes
    a = ctx.args
    idx = _open(ctx)
    thr = a.threshold if a.threshold is not None else float(model_spec(idx.model_key)["dupe_threshold"])
    res = {"index": idx.name, "model": idx.model_key,
           **dupes(idx, thr, a.across_files_only, a.limit, a.snippet)}
    lines = [f"{res['total_pairs']} pair(s) at cosine >= {thr}" +
             (f" (showing {res['shown']})" if res["shown"] < res["total_pairs"] else "")]
    for p in res["pairs"]:
        lines.append(f"  {p['score']:.4f}  {p['a']['path']} {p['a']['locator']}  <->  "
                     f"{p['b']['path']} {p['b']['locator']}")
    return res, "\n".join(lines), 0


def cmd_cluster(ctx: Ctx):
    from .analyze import cluster
    a = ctx.args
    idx = _open(ctx)
    res = {"index": idx.name, "model": idx.model_key,
           **cluster(idx, a.level, a.k, a.seed, a.sample, a.max_members, a.reps, a.snippet)}
    lines = [f"{res['k']} clusters over {res['items']} {a.level}s"]
    for c in res["clusters"]:
        lines.append(f"\n[{c['cluster']}] size {c['size']}, cohesion {c['cohesion']:.3f}")
        for r in c["representatives"]:
            if "chunk_id" in r:
                first = r["text"].splitlines()[0][:100] if r["text"] else ""
                lines.append(f"   * {r['path']} {r['locator']}: {first}")
            else:
                lines.append(f"   * {r['path']}")
        extra = c["members"][len(c["representatives"]):][:10]
        if extra:
            lines.append("     also: " + "; ".join(extra) + (" …" if c["size"] > len(c["representatives"]) + 10 else ""))
    return res, "\n".join(lines), 0


def cmd_outliers(ctx: Ctx):
    from .analyze import outliers
    a = ctx.args
    idx = _open(ctx)
    res = {"index": idx.name, "model": idx.model_key,
           **outliers(idx, a.level, a.neighbors, a.n, a.snippet)}
    lines = [f"least typical {a.level}s (mean similarity to {res['neighbors']} nearest; "
             f"median {res['median_mean_neighbor_score']:.3f}):"]
    for r in res["results"]:
        loc = f" {r['locator']}" if "locator" in r else ""
        lines.append(f"  {r['mean_neighbor_score']:.3f}  {r['path']}{loc}")
    return res, "\n".join(lines), 0


def cmd_embed(ctx: Ctx):
    a = ctx.args
    key = a.model or default_model_key()
    emb = ctx.embedder(key)
    v = emb.encode([a.text], "query" if a.query else "document")[0]
    res = {"model": key, "dim": int(v.shape[0]), "kind": "query" if a.query else "document",
           "vector": [round(float(x), 6) for x in v]}
    return res, " ".join(f"{x:.6f}" for x in v), 0


def cmd_info(ctx: Ctx):
    idx = _open(ctx, check_model=False)
    m = idx.manifest
    dead = m["rows"] - m["alive"]
    res = {"index": idx.name, "model": m["model"], "chunking": m["chunking"], "reader_opts": m.get("reader_opts"),
           "roots": m.get("roots"), "files": m["files"], "chunks": m["alive"], "tombstoned": dead,
           "size_bytes": _dir_size(idx.dir), "created": m["created"], "updated": m["updated"],
           "path": str(idx.dir)}
    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(m["updated"]))
    human = (f"index '{idx.name}': {m['files']} files, {m['alive']} chunks ({dead} tombstoned), "
             f"{_human_size(res['size_bytes'])}\n  model: {m['model']['key']}@{str(m['model']['revision'])[:10]} "
             f"dim {m['model']['dim']}\n  chunking: {m['chunking']['chunk_tokens']} tokens, overlap "
             f"{m['chunking']['overlap']}\n  roots: {', '.join(m.get('roots') or [])}\n  updated: {ts}")
    return res, human, 0


def cmd_list(ctx: Ctx):
    from .store import list_indexes, read_manifest
    out = []
    for name in list_indexes(ctx.paths):
        m = read_manifest(ctx.paths, name)
        out.append({"index": name, "model": m["model"]["key"], "files": m["files"], "chunks": m["alive"],
                    "updated": m["updated"]})
    human = "\n".join(f"{d['index']:<20} {d['model']:<12} {d['files']:>6} files {d['chunks']:>8} chunks"
                      for d in out) or f"no indexes in {ctx.paths.indexes}"
    return {"indexes": out}, human, 0


def cmd_drop(ctx: Ctx):
    from .store import drop_index
    ok = drop_index(ctx.paths, ctx.args.name)
    if not ok:
        raise SemError(f"no index named '{ctx.args.name}'")
    return {"dropped": ctx.args.name}, f"dropped index '{ctx.args.name}'", 0


# --- parser ------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--index", default=os.environ.get("SEM_INDEX", "default"), help="index name (default: default)")
    common.add_argument("--json", action="store_true", help="emit one JSON document on stdout")
    common.add_argument("--model", help="model key (fixed per index)")
    common.add_argument("--snippet", type=int, default=300, help="max chars of text per hit (0 = full)")

    p = argparse.ArgumentParser(prog="sem", description="Local semantic search and similarity analysis.")
    p.add_argument("--version", action="version", version=f"sem {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")

    s = sub.add_parser("doctor", parents=[common], help="check the runtime and sandbox fit")
    s.add_argument("--full", action="store_true", help="also load the default model and embed a test string")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("index", parents=[common], help="build or incrementally update an index")
    s.add_argument("paths", nargs="+")
    s.add_argument("--include", action="append", help="glob to include (repeatable)")
    s.add_argument("--exclude", action="append", help="glob to exclude (repeatable)")
    s.add_argument("--text-field", help="JSON/JSONL: dot.path of the text to embed")
    s.add_argument("--text-cols", help="CSV/TSV: comma-separated columns to embed")
    s.add_argument("--id-col", "--id-field", dest="id_col", help="CSV column / JSON field used as record id")
    s.add_argument("--chunk-tokens", type=int)
    s.add_argument("--overlap", type=int)
    s.add_argument("--rebuild", action="store_true", help="ignore incremental state and rebuild")
    s.add_argument("--max-mb", type=float, help="skip files larger than this (default 50)")
    s.add_argument("--no-gitignore", action="store_true", help="do not apply .gitignore rules")
    s.set_defaults(fn=cmd_index)

    s = sub.add_parser("search", parents=[common], help="top-k chunks for a query")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=10)
    s.add_argument("--min-score", type=float)
    s.add_argument("--path-glob")
    s.add_argument("--group-by-file", action="store_true", help="best chunk per file")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("similar", parents=[common], help="nearest neighbours of an indexed item")
    s.add_argument("item", help="chunk id, file path, or path:line")
    s.add_argument("-k", type=int, default=10)
    s.add_argument("--path-glob")
    s.add_argument("--group-by-file", action="store_true")
    s.set_defaults(fn=cmd_similar)

    s = sub.add_parser("compare", parents=[common], help="cosine similarity of two items or strings")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--text", action="store_true", help="treat a and b as literal strings")
    s.add_argument("--pairs", type=int, default=5, help="best chunk pairs to show for two files")
    s.set_defaults(fn=cmd_compare)

    s = sub.add_parser("dupes", parents=[common], help="near-duplicate chunk pairs")
    s.add_argument("--threshold", type=float, help="cosine threshold (default: model-specific)")
    s.add_argument("--across-files-only", action="store_true")
    s.add_argument("--limit", type=int, default=50, help="max pairs to print (0 = all)")
    s.set_defaults(fn=cmd_dupes)

    s = sub.add_parser("cluster", parents=[common], help="k-means clusters of chunks or files")
    s.add_argument("--level", choices=["chunk", "file"], default="chunk")
    s.add_argument("--k", default="auto", help="number of clusters or 'auto'")
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--sample", type=int, default=20000, help="max items used to fit centroids")
    s.add_argument("--max-members", type=int, default=50, help="members listed per cluster (0 = all)")
    s.add_argument("--reps", type=int, default=3, help="representatives per cluster")
    s.set_defaults(fn=cmd_cluster)

    s = sub.add_parser("outliers", parents=[common], help="least typical items")
    s.add_argument("--level", choices=["chunk", "file"], default="chunk")
    s.add_argument("--neighbors", type=int, default=5)
    s.add_argument("-n", type=int, default=10)
    s.set_defaults(fn=cmd_outliers)

    s = sub.add_parser("embed", parents=[common], help="print the vector for a text")
    s.add_argument("text")
    s.add_argument("--query", action="store_true", help="embed as a query (applies the query prompt)")
    s.set_defaults(fn=cmd_embed)

    s = sub.add_parser("info", parents=[common], help="index statistics")
    s.set_defaults(fn=cmd_info)

    s = sub.add_parser("list", parents=[common], help="list indexes")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("drop", parents=[common], help="delete an index")
    s.add_argument("name")
    s.set_defaults(fn=cmd_drop)
    return p


def main(argv: list[str] | None = None) -> int:
    install_network_guard()
    args = build_parser().parse_args(argv)
    try:
        paths = get_paths()
        ctx = Ctx(args, paths)
        res, human, code = args.fn(ctx)
    except SemError as e:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "command": args.cmd, "error": str(e)}))
        log(f"sem: error: {e}")
        return e.code
    except KeyboardInterrupt:
        log("sem: interrupted")
        return 130
    try:
        return _emit(args, ctx, res, human, code)
    except BrokenPipeError:  # e.g. `sem ... | head`
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        return code


def _emit(args, ctx, res, human, code) -> int:
    if args.json:
        doc = {"ok": code == 0, "command": args.cmd}
        doc.update(res)
        print(json.dumps(doc, ensure_ascii=False, indent=None))
    else:
        print(human)
    return code
