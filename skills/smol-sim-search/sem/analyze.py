"""search, similar, compare, dupes, cluster, outliers — brute-force NumPy.

Vectors are L2-normalised float16 on disk; every computation upcasts one
block at a time to float32, so memory stays bounded by the block size.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

import numpy as np

from .env import SemError
from .ingest import display_path
from .progress import Progress
from .store import Index

BLOCK = 8192


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return v / n


def snippet(text: str, n: int) -> str:
    if n <= 0 or len(text) <= n:
        return text
    return text[:n].rstrip() + " …"


def _item(c: dict, score: float | None, snip: int) -> dict:
    d = {"chunk_id": c["chunk_id"], "path": c["path"], "locator": c["locator"]}
    if score is not None:
        d = {"score": round(float(score), 4), **d}
    if c.get("heading"):
        d["heading"] = c["heading"]
    d["text"] = snippet(c["text"], snip)
    return d


def scores_for(idx: Index, rows: np.ndarray, q: np.ndarray) -> np.ndarray:
    out = np.empty(len(rows), dtype=np.float32)
    for s in range(0, len(rows), BLOCK):
        out[s: s + BLOCK] = idx.block(rows[s: s + BLOCK]) @ q
    return out


def _alive_paths(idx: Index) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """(rows, path_code per row, path list) for all alive rows, ordered by row."""
    rows, codes, names, lookup = [], [], [], {}
    for r, p in idx.conn.execute("SELECT row, path FROM chunks WHERE deleted=0 ORDER BY row"):
        if p not in lookup:
            lookup[p] = len(names)
            names.append(p)
        rows.append(r)
        codes.append(lookup[p])
    return np.asarray(rows, dtype=np.int64), np.asarray(codes, dtype=np.int64), names


def ranked(idx: Index, q: np.ndarray, k: int, min_score: float | None = None,
           path_glob: str | None = None, group_by_file: bool = False,
           exclude_rows: set[int] | None = None, exclude_path: str | None = None,
           snip: int = 300) -> list[dict]:
    rows, codes, names = _alive_paths(idx)
    if len(rows) == 0:
        return []
    mask = np.ones(len(rows), dtype=bool)
    if path_glob:
        ok = np.array([fnmatch.fnmatch(n, path_glob) or fnmatch.fnmatch(os.path.basename(n), path_glob)
                       for n in names], dtype=bool)
        mask &= ok[codes]
    if exclude_path is not None and exclude_path in names:
        mask &= codes != names.index(exclude_path)
    if exclude_rows:
        mask &= ~np.isin(rows, np.fromiter(exclude_rows, dtype=np.int64))
    rows, codes = rows[mask], codes[mask]
    if len(rows) == 0:
        return []
    sc = scores_for(idx, rows, q.astype(np.float32))
    if min_score is not None:
        keep = sc >= min_score
        rows, codes, sc = rows[keep], codes[keep], sc[keep]
    if group_by_file:
        best: dict[int, int] = {}
        order = np.argsort(-sc, kind="stable")
        for i in order:
            c = int(codes[i])
            if c not in best:
                best[c] = int(i)
                if len(best) >= k:
                    break
        top = list(best.values())
    else:
        m = min(k, len(sc))
        top = np.argpartition(-sc, m - 1)[:m] if m else []
        top = sorted(top, key=lambda i: -sc[i])
    info = idx.chunks(rows[top])
    return [_item(info[int(rows[i])], sc[i], snip) for i in top]


# --- item resolution --------------------------------------------------------------

_PATH_LINE = re.compile(r"^(.*):(\d+)$")


def _norm_path(s: str) -> str:
    p = Path(s).expanduser()
    if p.exists():
        return display_path(p.resolve())
    return s[2:] if s.startswith("./") else s


def resolve_item(idx: Index, item: str) -> dict:
    """Resolve a chunk id, file path, or path:line to a vector + description."""
    rows = idx.rows_by_chunk_id(item)
    if rows:
        r = rows[0]
        c = idx.chunk(r)
        return {"kind": "chunk", "vec": idx.block(np.array([r]))[0], "rows": [r], "path": c["path"],
                "label": f"{c['path']} {c['locator']} [{c['chunk_id']}]"}
    m = _PATH_LINE.match(item)
    if m and not Path(item).exists():
        path, line = _norm_path(m.group(1)), int(m.group(2))
        r = idx.row_at_line(path, line)
        if r is None:
            if not idx.rows_for_path(path):
                raise SemError(f"'{path}' is not in index '{idx.name}'")
            raise SemError(f"no chunk in '{path}' covers line {line}")
        c = idx.chunk(r)
        return {"kind": "chunk", "vec": idx.block(np.array([r]))[0], "rows": [r], "path": path,
                "label": f"{path} {c['locator']} [{c['chunk_id']}]"}
    path = _norm_path(item)
    rows = idx.rows_for_path(path)
    if rows:
        v = _normalize(idx.block(np.array(rows)).mean(axis=0))
        return {"kind": "file", "vec": v, "rows": rows, "path": path, "label": path}
    raise SemError(f"'{item}' is not a chunk id, indexed file, or path:line in index '{idx.name}'. "
                   "Run `sem index` on it first, or use `sem search` for free text.")


def similar(idx: Index, item: str, k: int, group_by_file: bool, snip: int,
            path_glob: str | None = None) -> dict:
    it = resolve_item(idx, item)
    res = ranked(idx, it["vec"], k, group_by_file=group_by_file, path_glob=path_glob,
                 exclude_rows=set(it["rows"]) if it["kind"] == "chunk" else None,
                 exclude_path=it["path"] if it["kind"] == "file" else None, snip=snip)
    return {"item": it["label"], "item_kind": it["kind"], "results": res}


def compare_vecs(idx: Index, a: dict, b: dict, pairs: int, snip: int) -> dict:
    out = {"a": a["label"], "b": b["label"], "score": round(float(a["vec"] @ b["vec"]), 4)}
    if a["kind"] == "file" and b["kind"] == "file":
        A = idx.block(np.array(a["rows"]))
        B = idx.block(np.array(b["rows"]))
        S = A @ B.T
        flat = np.argsort(-S, axis=None)[:pairs]
        info = idx.chunks(list(a["rows"]) + list(b["rows"]))
        out["score_kind"] = "cosine of mean chunk vectors"
        out["best_chunk_pairs"] = [
            {"score": round(float(S[i, j]), 4),
             "a": _item(info[a["rows"][i]], None, snip), "b": _item(info[b["rows"][j]], None, snip)}
            for i, j in (np.unravel_index(f, S.shape) for f in flat)]
    return out


# --- dupes ------------------------------------------------------------------------

def dupes(idx: Index, threshold: float, across_files_only: bool, limit: int, snip: int,
          tile: int = 4096) -> dict:
    rows, codes, names = _alive_paths(idx)
    n = len(rows)
    found: list[tuple[float, int, int]] = []
    nt = (n + tile - 1) // tile
    bar = Progress(nt * (nt + 1) // 2, "comparing")
    for i in range(0, n, tile):
        A = idx.block(rows[i: i + tile])
        for j in range(i, n, tile):
            B = A if j == i else idx.block(rows[j: j + tile])
            S = A @ B.T
            if j == i:
                S = np.triu(S, k=1)
            ii, jj = np.nonzero(S >= threshold)
            if across_files_only and len(ii):
                keep = codes[i + ii] != codes[j + jj]
                ii, jj = ii[keep], jj[keep]
            found.extend(zip(S[ii, jj].tolist(), (i + ii).tolist(), (j + jj).tolist()))
            bar.update()
    bar.close()
    found.sort(key=lambda t: -t[0])
    total = len(found)
    shown = found[:limit] if limit > 0 else found
    info = idx.chunks({int(rows[a]) for _, a, _ in shown} | {int(rows[b]) for _, _, b in shown})
    pairs = [{"score": round(s, 4), "a": _item(info[int(rows[a])], None, snip),
              "b": _item(info[int(rows[b])], None, snip)} for s, a, b in shown]
    return {"threshold": threshold, "total_pairs": total, "shown": len(pairs), "pairs": pairs}


# --- vectors per level --------------------------------------------------------------

def level_vectors(idx: Index, level: str) -> tuple[np.ndarray, list, np.ndarray]:
    """Return (vectors float32, labels, rows) for 'chunk' or 'file' level."""
    rows, codes, names = _alive_paths(idx)
    if level == "chunk":
        V = np.concatenate([idx.block(rows[s: s + BLOCK]) for s in range(0, len(rows), BLOCK)]) \
            if len(rows) else np.zeros((0, idx.manifest["model"]["dim"]), np.float32)
        return V, rows.tolist(), rows
    if level == "file":
        dim = idx.manifest["model"]["dim"]
        sums = np.zeros((len(names), dim), dtype=np.float64)
        counts = np.bincount(codes, minlength=len(names)).astype(np.float64)
        for s in range(0, len(rows), BLOCK):
            np.add.at(sums, codes[s: s + BLOCK], idx.block(rows[s: s + BLOCK]))
        V = _normalize((sums / np.maximum(counts, 1)[:, None]).astype(np.float32))
        return V, names, rows
    raise SemError("--level must be 'chunk' or 'file'")


# --- k-means ------------------------------------------------------------------------

def kmeans_pp(X: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    n = X.shape[0]
    C = [X[rng.integers(n)]]
    d2 = np.full(n, np.inf, dtype=np.float64)
    for _ in range(1, k):
        d2 = np.minimum(d2, np.maximum(0.0, 2.0 - 2.0 * (X @ C[-1])))
        tot = d2.sum()
        if tot <= 0:
            C.append(X[rng.integers(n)])
            continue
        C.append(X[rng.choice(n, p=d2 / tot)])
    return np.stack(C).astype(np.float32)


def spherical_kmeans(X: np.ndarray, k: int, seed: int = 0, iters: int = 50, n_init: int = 3) -> tuple[np.ndarray, np.ndarray, float]:
    """Cosine k-means on unit vectors. Returns (centroids, labels, inertia)."""
    best = None
    for t in range(n_init):
        rng = np.random.default_rng(seed + t)
        C = kmeans_pp(X, k, rng)
        labels = np.full(X.shape[0], -1)
        for _ in range(iters):
            new = np.argmax(X @ C.T, axis=1)
            if np.array_equal(new, labels):
                break
            labels = new
            for c in range(k):
                members = X[labels == c]
                if len(members):
                    C[c] = members.mean(axis=0)
                else:  # re-seed an empty cluster with the worst-fit point
                    worst = np.argmin(np.max(X @ C.T, axis=1))
                    C[c] = X[worst]
            C = _normalize(C)
        sims = np.max(X @ C.T, axis=1)
        inertia = float(np.sum(1.0 - sims))
        if best is None or inertia < best[2]:
            best = (C.copy(), labels.copy(), inertia)
    return best


def silhouette(X: np.ndarray, labels: np.ndarray) -> float:
    D = 1.0 - X @ X.T
    ks = np.unique(labels)
    if len(ks) < 2:
        return -1.0
    s = np.zeros(len(X))
    for i in range(len(X)):
        same = labels == labels[i]
        n_same = same.sum() - 1
        if n_same == 0:
            s[i] = 0.0
            continue
        a = D[i, same].sum() / n_same
        b = min(D[i, labels == c].mean() for c in ks if c != labels[i])
        s[i] = (b - a) / max(a, b) if max(a, b) > 0 else 0.0
    return float(s.mean())


def choose_k(X: np.ndarray, seed: int, kmax: int = 15) -> tuple[int, list[dict]]:
    rng = np.random.default_rng(seed)
    S = X if len(X) <= 2000 else X[rng.choice(len(X), 2000, replace=False)]
    hi = min(kmax, len(S) - 1, max(2, int(np.sqrt(len(S)))))
    scores = []
    for k in range(2, hi + 1):
        _, lab, _ = spherical_kmeans(S, k, seed=seed, n_init=2)
        scores.append({"k": k, "silhouette": round(silhouette(S, lab), 4)})
    if not scores:
        return 1, []
    best = max(scores, key=lambda d: d["silhouette"])
    return best["k"], scores


def cluster(idx: Index, level: str, k: str | int, seed: int, sample: int,
            max_members: int, reps: int, snip: int) -> dict:
    V, labels_src, rows = level_vectors(idx, level)
    n = len(V)
    if n < 2:
        raise SemError("need at least 2 items to cluster")
    tried = None
    if str(k) == "auto":
        kk, tried = choose_k(V, seed)
    else:
        kk = int(k)
        if not 1 <= kk <= n:
            raise SemError(f"--k must be between 1 and {n}")
    rng = np.random.default_rng(seed)
    fitX = V if n <= sample else V[rng.choice(n, sample, replace=False)]
    C, _, _ = spherical_kmeans(fitX, kk, seed=seed)
    assign = np.empty(n, dtype=np.int64)
    sim = np.empty(n, dtype=np.float32)
    for s in range(0, n, BLOCK):
        S = V[s: s + BLOCK] @ C.T
        assign[s: s + BLOCK] = np.argmax(S, axis=1)
        sim[s: s + BLOCK] = np.max(S, axis=1)

    chunk_info = idx.chunks(rows) if level == "chunk" else None
    clusters = []
    for c in range(kk):
        members = np.nonzero(assign == c)[0]
        if len(members) == 0:
            continue
        members = members[np.argsort(-sim[members])]
        def describe(i):
            if level == "chunk":
                return _item(chunk_info[int(labels_src[i])], float(sim[i]), snip)
            return {"score": round(float(sim[i]), 4), "path": labels_src[i]}
        cl = {
            "size": int(len(members)),
            "cohesion": round(float(sim[members].mean()), 4),
            "representatives": [describe(i) for i in members[:reps]],
        }
        shown = members if max_members <= 0 else members[:max_members]
        if level == "chunk":
            cl["members"] = [f"{chunk_info[int(labels_src[i])]['path']} "
                             f"{chunk_info[int(labels_src[i])]['locator']} "
                             f"[{chunk_info[int(labels_src[i])]['chunk_id']}]" for i in shown]
        else:
            cl["members"] = [labels_src[i] for i in shown]
        cl["members_truncated"] = len(shown) < len(members)
        clusters.append(cl)
    clusters.sort(key=lambda d: -d["size"])
    for i, cl in enumerate(clusters):
        cl["cluster"] = i
    out = {"level": level, "k": kk, "items": n, "clusters": clusters}
    if tried is not None:
        out["k_search"] = tried
    return out


# --- outliers -----------------------------------------------------------------------

def outliers(idx: Index, level: str, neighbors: int, n_out: int, snip: int) -> dict:
    V, labels_src, rows = level_vectors(idx, level)
    n = len(V)
    if n < 2:
        raise SemError("need at least 2 items to find outliers")
    kk = min(neighbors, n - 1)
    mean_sim = np.empty(n, dtype=np.float32)
    rb, cb = 2048, BLOCK
    bar = Progress((n + rb - 1) // rb, "neighbours")
    for s in range(0, n, rb):
        A = V[s: s + rb]
        best = np.full((A.shape[0], kk), -np.inf, dtype=np.float32)
        for t in range(0, n, cb):
            S = A @ V[t: t + cb].T
            # exclude self-similarity
            r = np.arange(A.shape[0])
            cols = s + r - t
            ok = (cols >= 0) & (cols < S.shape[1])
            S[r[ok], cols[ok]] = -np.inf
            both = np.concatenate([best, S], axis=1)
            best = np.partition(both, -kk, axis=1)[:, -kk:]
        mean_sim[s: s + rb] = best.mean(axis=1)
        bar.update()
    bar.close()
    order = np.argsort(mean_sim)[:n_out]
    info = idx.chunks([labels_src[i] for i in order]) if level == "chunk" else None
    res = []
    for i in order:
        if level == "chunk":
            d = _item(info[int(labels_src[i])], None, snip)
        else:
            d = {"path": labels_src[i]}
        res.append({"mean_neighbor_score": round(float(mean_sim[i]), 4), **d})
    return {"level": level, "neighbors": kk, "items": n,
            "median_mean_neighbor_score": round(float(np.median(mean_sim)), 4), "results": res}
