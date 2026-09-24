"""On-disk index format and incremental, crash-safe updates.

Layout of ``.sem/indexes/<name>/``::

    manifest.json      schema, model identity, chunking params, counts, times
    vectors.f16.npy    float16, L2-normalised, one row per chunk (memory-mapped)
    meta.sqlite        files(...) and chunks(...) tables

A row is never reused: changed or deleted files have their rows tombstoned
(``chunks.deleted = 1``) and new rows are appended. When tombstones exceed
20 % the index is compacted.

Any update that changes rows is built as a complete new generation under
``.sem/tmp/`` and swapped in with two renames (old -> ``.<name>.old``,
new -> ``<name>``); ``recover()`` repairs an interrupted swap. Updates that
only touch file metadata run as a single SQLite transaction in place.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .env import Paths, SemError

SCHEMA_VERSION = 1
COMPACT_RATIO = 0.20
_BLOCK = 65536

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY, size INTEGER, mtime REAL, sha256 TEXT, kind TEXT, nchunks INTEGER
);
CREATE TABLE IF NOT EXISTS chunks (
    row INTEGER PRIMARY KEY, chunk_id TEXT, path TEXT, locator TEXT, text TEXT, sha256 TEXT,
    start_line INTEGER, end_line INTEGER, page INTEGER, record_id TEXT, heading TEXT,
    deleted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS chunks_path ON chunks(path);
CREATE INDEX IF NOT EXISTS chunks_id ON chunks(chunk_id);
"""

CHUNK_COLS = ("row", "chunk_id", "path", "locator", "text", "sha256", "start_line", "end_line",
              "page", "record_id", "heading")


def valid_name(name: str) -> str:
    if not name or name.startswith(".") or "/" in name or "\\" in name or len(name) > 100:
        raise SemError(f"invalid index name '{name}'")
    return name


def index_dir(paths: Paths, name: str) -> Path:
    return paths.indexes / valid_name(name)


def recover(paths: Paths, name: str) -> None:
    d = index_dir(paths, name)
    old = paths.indexes / f".{name}.old"
    if old.exists():
        if d.exists():
            shutil.rmtree(old, ignore_errors=True)
        else:
            os.replace(old, d)


def list_indexes(paths: Paths) -> list[str]:
    if not paths.indexes.exists():
        return []
    out = []
    for p in sorted(paths.indexes.iterdir()):
        if p.name.startswith("."):
            continue
        if (p / "manifest.json").exists():
            out.append(p.name)
    return out


def drop_index(paths: Paths, name: str) -> bool:
    recover(paths, name)
    d = index_dir(paths, name)
    if not d.exists():
        return False
    trash = paths.tmp / f"drop-{name}-{uuid.uuid4().hex[:8]}"
    os.replace(d, trash)
    shutil.rmtree(trash, ignore_errors=True)
    return True


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def make_chunk_id(path: str, locator: str, sha: str) -> str:
    return hashlib.sha1(f"{path}\0{locator}\0{sha}".encode()).hexdigest()[:12]


@dataclass
class Index:
    name: str
    dir: Path
    manifest: dict
    vectors: np.ndarray  # (rows, dim) float16 memmap
    conn: sqlite3.Connection

    @property
    def model_key(self) -> str:
        return self.manifest["model"]["key"]

    def alive_rows(self) -> np.ndarray:
        rows = [r for (r,) in self.conn.execute("SELECT row FROM chunks WHERE deleted=0 ORDER BY row")]
        return np.asarray(rows, dtype=np.int64)

    def chunk(self, row: int) -> dict | None:
        cur = self.conn.execute(f"SELECT {','.join(CHUNK_COLS)} FROM chunks WHERE row=?", (int(row),))
        r = cur.fetchone()
        return dict(zip(CHUNK_COLS, r)) if r else None

    def chunks(self, rows) -> dict[int, dict]:
        rows = [int(r) for r in rows]
        out: dict[int, dict] = {}
        for i in range(0, len(rows), 900):
            part = rows[i: i + 900]
            q = f"SELECT {','.join(CHUNK_COLS)} FROM chunks WHERE row IN ({','.join('?' * len(part))})"
            for r in self.conn.execute(q, part):
                d = dict(zip(CHUNK_COLS, r))
                out[d["row"]] = d
        return out

    def row_paths(self, rows: np.ndarray) -> list[str]:
        m = dict(self.conn.execute("SELECT row, path FROM chunks WHERE deleted=0"))
        return [m[int(r)] for r in rows]

    def rows_for_path(self, path: str) -> list[int]:
        return [r for (r,) in self.conn.execute(
            "SELECT row FROM chunks WHERE path=? AND deleted=0 ORDER BY row", (path,))]

    def rows_by_chunk_id(self, cid: str) -> list[int]:
        return [r for (r,) in self.conn.execute(
            "SELECT row FROM chunks WHERE chunk_id=? AND deleted=0", (cid,))]

    def row_at_line(self, path: str, line: int) -> int | None:
        r = self.conn.execute(
            "SELECT row FROM chunks WHERE path=? AND deleted=0 AND start_line<=? AND end_line>=? "
            "ORDER BY (end_line-start_line) LIMIT 1", (path, line, line)).fetchone()
        return r[0] if r else None

    def paths(self) -> list[str]:
        return [p for (p,) in self.conn.execute("SELECT path FROM files WHERE nchunks>0 ORDER BY path")]

    def block(self, rows: np.ndarray) -> np.ndarray:
        """Upcast selected rows to float32."""
        return np.asarray(self.vectors[rows], dtype=np.float32)

    def close(self):
        self.conn.close()


def read_manifest(paths: Paths, name: str) -> dict | None:
    recover(paths, name)
    f = index_dir(paths, name) / "manifest.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())


def open_index(paths: Paths, name: str) -> Index:
    m = read_manifest(paths, name)
    if m is None:
        existing = list_indexes(paths)
        hint = f" Existing indexes: {', '.join(existing)}." if existing else " Run `sem index <paths>` first."
        raise SemError(f"no index named '{name}' in {paths.indexes}.{hint}")
    if m.get("schema_version") != SCHEMA_VERSION:
        raise SemError(f"index '{name}' has schema {m.get('schema_version')}, this sem expects "
                       f"{SCHEMA_VERSION}. Rebuild it with `sem index --rebuild ...`.")
    d = index_dir(paths, name)
    vf = d / "vectors.f16.npy"
    vectors = np.load(vf, mmap_mode="r") if m["rows"] > 0 else np.zeros((0, m["model"]["dim"]), np.float16)
    conn = sqlite3.connect(f"file:{d / 'meta.sqlite'}?mode=ro", uri=True)
    if vectors.shape[0] != m["rows"]:
        raise SemError(f"index '{name}' is inconsistent (vectors {vectors.shape[0]} != manifest "
                       f"{m['rows']}). Rebuild with `sem index --rebuild`.")
    return Index(name, d, m, vectors, conn)


# --- updates ------------------------------------------------------------------

@dataclass
class FileState:
    path: str
    abspath: Path
    size: int
    mtime: float


def _new_db(p: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(p)
    conn.executescript(SCHEMA)
    return conn


def _copy_vectors(src: np.ndarray | None, keep: np.ndarray | None, new: list[np.ndarray],
                  out: Path, dim: int) -> int:
    n_old = 0 if src is None else (len(keep) if keep is not None else src.shape[0])
    n_new = sum(a.shape[0] for a in new)
    total = n_old + n_new
    if total == 0:
        np.save(out, np.zeros((0, dim), dtype=np.float16))
        return 0
    mm = np.lib.format.open_memmap(out, mode="w+", dtype=np.float16, shape=(total, dim))
    pos = 0
    if src is not None and n_old:
        idx = keep if keep is not None else None
        for s in range(0, n_old, _BLOCK):
            blk = src[idx[s: s + _BLOCK]] if idx is not None else src[s: s + _BLOCK]
            mm[pos: pos + blk.shape[0]] = blk
            pos += blk.shape[0]
    for a in new:
        mm[pos: pos + a.shape[0]] = a.astype(np.float16)
        pos += a.shape[0]
    mm.flush()
    del mm
    return total


class Updater:
    """Stages one index update. Use ``plan()`` then ``commit()``."""

    def __init__(self, paths: Paths, name: str, manifest: dict | None, rebuild: bool):
        self.paths = paths
        self.name = name
        self.dir = index_dir(paths, name)
        self.old_manifest = None if rebuild else manifest
        self.rebuild = rebuild

    def existing_files(self) -> dict[str, tuple]:
        if not self.old_manifest:
            return {}
        conn = sqlite3.connect(f"file:{self.dir / 'meta.sqlite'}?mode=ro", uri=True)
        try:
            return {r[0]: r[1:] for r in conn.execute("SELECT path,size,mtime,sha256,kind,nchunks FROM files")}
        finally:
            conn.close()

    def commit(self, manifest: dict, removed_paths: list[str], meta_only: dict[str, tuple],
               new_files: list[tuple], new_chunks: list[dict], new_vecs: list[np.ndarray]) -> dict:
        """Apply the update.

        removed_paths: paths whose chunks are tombstoned and file rows deleted
        meta_only:     path -> (size, mtime) where content hash is unchanged
        new_files:     (path, size, mtime, sha256, kind, nchunks) for (re)indexed files
        new_chunks:    chunk dicts (without row) for the new vectors, in order
        """
        dim = manifest["model"]["dim"]
        now = time.time()
        rows_change = bool(removed_paths or new_files or self.rebuild or not self.old_manifest)

        if not rows_change:
            if meta_only:
                conn = sqlite3.connect(self.dir / "meta.sqlite")
                with conn:
                    conn.executemany("UPDATE files SET size=?, mtime=? WHERE path=?",
                                     [(s, m, p) for p, (s, m) in meta_only.items()])
                conn.close()
            return {"compacted": False, "rewritten": False}

        stage = self.paths.tmp / f"stage-{self.name}-{uuid.uuid4().hex[:8]}"
        stage.mkdir(parents=True)
        try:
            db_path = stage / "meta.sqlite"
            old_vecs = None
            if self.old_manifest:
                shutil.copy2(self.dir / "meta.sqlite", db_path)
                if self.old_manifest["rows"] > 0:
                    old_vecs = np.load(self.dir / "vectors.f16.npy", mmap_mode="r")
            conn = _new_db(db_path)
            with conn:
                for p in removed_paths:
                    conn.execute("UPDATE chunks SET deleted=1 WHERE path=?", (p,))
                    conn.execute("DELETE FROM files WHERE path=?", (p,))
                conn.executemany("UPDATE files SET size=?, mtime=? WHERE path=?",
                                 [(s, m, p) for p, (s, m) in meta_only.items()])
                conn.executemany("INSERT OR REPLACE INTO files(path,size,mtime,sha256,kind,nchunks) "
                                 "VALUES (?,?,?,?,?,?)", new_files)
                base = self.old_manifest["rows"] if self.old_manifest else 0
                seen_ids: set[str] = set()
                rows = []
                for i, c in enumerate(new_chunks):
                    cid = make_chunk_id(c["path"], c["locator"], c["sha256"])
                    while cid in seen_ids:
                        cid = hashlib.sha1(cid.encode()).hexdigest()[:12]
                    seen_ids.add(cid)
                    rows.append((base + i, cid, c["path"], c["locator"], c["text"], c["sha256"],
                                 c.get("start_line"), c.get("end_line"), c.get("page"),
                                 c.get("record_id"), c.get("heading")))
                conn.executemany(f"INSERT INTO chunks({','.join(CHUNK_COLS)}) VALUES "
                                 f"({','.join('?' * len(CHUNK_COLS))})", rows)

            total = base + len(new_chunks)
            dead = conn.execute("SELECT COUNT(*) FROM chunks WHERE deleted=1").fetchone()[0]
            compact = total > 0 and dead / total > COMPACT_RATIO
            keep = None
            if compact:
                old_alive = [r for (r,) in conn.execute(
                    "SELECT row FROM chunks WHERE deleted=0 AND row<? ORDER BY row", (base,))]
                keep = np.asarray(old_alive, dtype=np.int64)
                with conn:
                    conn.execute("DELETE FROM chunks WHERE deleted=1")
                    for new_row, (old_row,) in enumerate(conn.execute(
                            "SELECT row FROM chunks ORDER BY row").fetchall()):
                        if new_row != old_row:
                            conn.execute("UPDATE chunks SET row=? WHERE row=?", (new_row, old_row))
                conn.execute("VACUUM")
            alive = conn.execute("SELECT COUNT(*) FROM chunks WHERE deleted=0").fetchone()[0]
            nfiles = conn.execute("SELECT COUNT(*) FROM files WHERE nchunks>0").fetchone()[0]
            conn.close()

            rows_written = _copy_vectors(old_vecs, keep, new_vecs, stage / "vectors.f16.npy", dim)
            del old_vecs
            manifest = dict(manifest)
            manifest.update(rows=rows_written, alive=alive, files=nfiles, updated=now)
            if not manifest.get("created"):
                manifest["created"] = now
            (stage / "manifest.json").write_text(json.dumps(manifest, indent=2))

            # swap
            old = self.paths.indexes / f".{self.name}.old"
            if old.exists():
                shutil.rmtree(old)
            if self.dir.exists():
                os.replace(self.dir, old)
            os.replace(stage, self.dir)
            shutil.rmtree(old, ignore_errors=True)
            return {"compacted": compact, "rewritten": True}
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
