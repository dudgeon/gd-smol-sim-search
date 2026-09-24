"""`sem index`: discover files, detect changes, chunk, embed, commit."""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np

from .chunk import chunk_segments
from .embed import installed_revision
from .env import Paths, SemError, log, model_spec
from .ingest import ReaderOpts, discover, display_path, read_file
from .progress import Progress
from .store import SCHEMA_VERSION, Updater, file_sha256, read_manifest

EMBED_FLUSH = 2048


def resolve_chunking(spec: dict, chunk_tokens: int | None, overlap: int | None) -> tuple[int, int]:
    limit = int(spec["max_seq_length"]) - 8
    ct = chunk_tokens or min(int(spec["default_chunk_tokens"]), limit)
    if ct > limit:
        raise SemError(f"--chunk-tokens {ct} exceeds model '{spec['key']}' limit ({limit})")
    if ct < 16:
        raise SemError("--chunk-tokens must be at least 16")
    ov = round(ct * 0.15) if overlap is None else overlap
    if not 0 <= ov < ct:
        raise SemError("--overlap must be between 0 and chunk-tokens")
    return ct, ov


def check_model_compat(manifest: dict, requested: str | None, paths: Paths) -> None:
    built = manifest["model"]["key"]
    if requested and requested != built:
        raise SemError(
            f"index '{manifest['name']}' was built with model '{built}' and cannot be used with "
            f"'{requested}'. Vectors from different models are not comparable. Use --index <other> "
            f"for a separate index, or `sem index --rebuild --model {requested} ...` to replace it.")
    have = installed_revision(paths, built)
    want = manifest["model"]["revision"]
    if have is not None and have != want:
        raise SemError(
            f"index '{manifest['name']}' was built with {built}@{want[:10]}, but the installed "
            f"model is @{have[:10]}. Rebuild with `sem index --rebuild ...`.")


def run_index(paths: Paths, ctx, name: str, roots: list[str], model: str | None,
              include: list[str], exclude: list[str], opts: ReaderOpts,
              chunk_tokens: int | None, overlap: int | None, rebuild: bool,
              max_bytes: int, use_gitignore: bool) -> dict:
    t0 = time.time()
    existing = read_manifest(paths, name)
    if existing and not rebuild:
        check_model_compat(existing, model, paths)
        key = existing["model"]["key"]
        spec = model_spec(key)
        ct0, ov0 = existing["chunking"]["chunk_tokens"], existing["chunking"]["overlap"]
        if (chunk_tokens and chunk_tokens != ct0) or (overlap is not None and overlap != ov0):
            raise SemError(f"index '{name}' uses chunk-tokens={ct0} overlap={ov0}; "
                           "pass --rebuild to change chunking")
        ct, ov = ct0, ov0
        if opts.as_dict() != existing.get("reader_opts") and any(opts.as_dict().values()):
            raise SemError(f"index '{name}' was built with reader options {existing.get('reader_opts')}; "
                           "pass --rebuild to change them")
        opts = ReaderOpts(**existing.get("reader_opts") or {})
    else:
        key = model or ctx.default_model()
        spec = model_spec(key)
        ct, ov = resolve_chunking(spec, chunk_tokens, overlap)
        rev = installed_revision(paths, key)
        if rev is None:
            raise SemError(f"model '{key}' is not installed. Run ./setup.sh --model {key} in your terminal.")

    if not roots:
        raise SemError("give one or more paths to index, e.g. `sem index docs/ notes/`")
    files, skipped = discover(roots, include, exclude, max_bytes=max_bytes, use_gitignore=use_gitignore)

    upd = Updater(paths, name, existing, rebuild)
    known = upd.existing_files()

    # removed: gone from disk, or under a directory root of this run but no longer discovered
    found = {display_path(f) for f in files}
    dir_roots = [display_path(Path(r).expanduser().resolve()) for r in roots if Path(r).expanduser().is_dir()]

    def under_run_root(p: str) -> bool:
        for r in dir_roots:
            if r in ("", "."):
                if not os.path.isabs(p):
                    return True
            elif p == r or p.startswith(r.rstrip("/") + "/"):
                return True
        return False

    removed = [p for p in known if not os.path.exists(p) or (p not in found and under_run_root(p))]

    embedder = None
    meta_only: dict[str, tuple] = {}
    new_files: list[tuple] = []
    new_chunks: list[dict] = []
    new_vecs: list[np.ndarray] = []
    pending_texts: list[str] = []
    changed, added, unchanged = [], [], 0
    empty = []

    def ensure_embedder():
        nonlocal embedder
        if embedder is None:
            embedder = ctx.embedder(key)
        return embedder

    def flush():
        if pending_texts:
            vecs = ensure_embedder().encode(pending_texts, "document", progress=True)
            new_vecs.append(vecs.astype(np.float16))
            pending_texts.clear()

    scan = Progress(len(files), "scanning")
    for f in files:
        scan.update()
        p = display_path(f)
        st = f.stat()
        prev = known.get(p)
        if prev and not rebuild:
            size, mtime, sha, kind, n = prev
            if size == st.st_size and mtime == st.st_mtime:
                unchanged += 1
                continue
            new_sha = file_sha256(f)
            if new_sha == sha:
                meta_only[p] = (st.st_size, st.st_mtime)
                unchanged += 1
                continue
            changed.append(p)
            removed.append(p)  # tombstone old rows; file row is re-inserted below
        else:
            new_sha = file_sha256(f)
            added.append(p)
        try:
            res = read_file(f, opts)
        except SemError:
            raise
        except Exception as e:  # unreadable file: record and move on
            log(f"sem: skipping {p}: {type(e).__name__}: {e}")
            res = None
        if res is None:
            new_files.append((p, st.st_size, st.st_mtime, new_sha, "skipped", 0))
            continue
        kind, segments = res
        chunks = chunk_segments(segments, ensure_embedder(), ct, ov) if segments else []
        if not chunks:
            empty.append(p)
        new_files.append((p, st.st_size, st.st_mtime, new_sha, kind, len(chunks)))
        for c in chunks:
            new_chunks.append({"path": p, "locator": c.locator, "text": c.text, "sha256": c.sha256,
                               "start_line": c.start_line, "end_line": c.end_line, "page": c.page,
                               "record_id": c.record_id, "heading": c.heading})
            pending_texts.append(c.text)
        if len(pending_texts) >= EMBED_FLUSH:
            flush()
    scan.close()
    flush()

    manifest = dict(existing) if existing and not rebuild else {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "model": {"key": key, "repo_id": spec.get("repo_id"), "revision": installed_revision(paths, key),
                  "dim": int(spec["dim"])},
        "normalization": "l2",
        "dtype": "float16",
        "chunking": {"chunk_tokens": ct, "overlap": ov, "tokenizer": key},
        "reader_opts": opts.as_dict(),
        "roots": [],
        "created": None,
    }
    manifest["roots"] = sorted(set(manifest.get("roots", [])) | {display_path(Path(r).expanduser().resolve()) for r in roots})
    removed_unique = sorted(set(removed))
    result = upd.commit(manifest, removed_unique, meta_only, new_files, new_chunks, new_vecs)
    real_removed = [p for p in removed_unique if p not in changed]
    return {
        "index": name,
        "model": key,
        "files_seen": len(files),
        "unchanged": unchanged,
        "added": added,
        "changed": changed,
        "removed": real_removed,
        "chunks_embedded": len(new_chunks),
        "empty_files": empty,
        "skipped": skipped,
        "compacted": result["compacted"],
        "seconds": round(time.time() - t0, 2),
    }
