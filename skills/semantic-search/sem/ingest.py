"""File discovery (globs, default excludes, simple .gitignore) and readers."""

from __future__ import annotations

import csv
import fnmatch
import io
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .chunk import Segment, Unit
from .env import SemError

MAX_BYTES_DEFAULT = 50 * 1024 * 1024
DEFAULT_EXCLUDE_DIRS = {".git", ".sem", ".venv", "venv", "node_modules", "__pycache__",
                        ".hg", ".svn", ".mypy_cache", ".pytest_cache", ".tox", ".idea"}
DEFAULT_EXCLUDE_FILES = {".DS_Store"}

CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".swift", ".c", ".h",
            ".cc", ".cpp", ".hpp", ".m", ".mm", ".rb", ".php", ".cs", ".scala", ".sh", ".bash", ".zsh",
            ".sql", ".lua", ".r", ".jl", ".pl", ".ex", ".exs", ".erl", ".hs", ".ml", ".clj", ".dart",
            ".vue", ".svelte", ".css", ".scss", ".html", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
MD_EXT = {".md", ".markdown", ".mdx", ".rst", ".txt", ".text", ".org", ".adoc"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff", ".heic", ".mp3", ".mp4",
              ".mov", ".avi", ".wav", ".flac", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
              ".tar", ".dmg", ".pkg", ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".class", ".jar",
              ".pyc", ".whl", ".npy", ".npz", ".safetensors", ".bin", ".pt", ".onnx", ".sqlite",
              ".db", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".psd", ".sketch", ".key", ".numbers",
              ".pages", ".docx", ".xlsx", ".pptx", ".parquet", ".arrow", ".feather"}


@dataclass
class ReaderOpts:
    text_field: str | None = None
    id_field: str | None = None
    text_cols: list[str] | None = None

    def as_dict(self) -> dict:
        return {"text_field": self.text_field, "id_field": self.id_field, "text_cols": self.text_cols}


# --- .gitignore ---------------------------------------------------------------

def _glob_to_regex(pat: str) -> str:
    i, out = 0, []
    while i < len(pat):
        c = pat[i]
        if c == "*":
            if pat[i: i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if pat[i: i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = pat.find("]", i + 1)
            if j == -1:
                out.append(re.escape(c))
            else:
                cls = pat[i + 1: j].replace("\\", "\\\\")
                if cls.startswith("!"):
                    cls = "^" + cls[1:]
                out.append(f"[{cls}]")
                i = j
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


@dataclass
class IgnoreRule:
    regex: re.Pattern
    negate: bool
    dir_only: bool


def parse_gitignore(text: str) -> list[IgnoreRule]:
    rules = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        neg = line.startswith("!")
        if neg:
            line = line[1:]
        if line.startswith("\\"):
            line = line[1:]
        dir_only = line.endswith("/")
        line = line.rstrip("/")
        if not line:
            continue
        anchored = "/" in line
        line = line.lstrip("/")
        body = _glob_to_regex(line)
        rx = ("^" if anchored else "^(?:.*/)?") + body + "$"
        rules.append(IgnoreRule(re.compile(rx), neg, dir_only))
    return rules


class IgnoreStack:
    """Applies .gitignore files found from the walk root downwards."""

    def __init__(self):
        self.layers: list[tuple[Path, list[IgnoreRule]]] = []

    def push_dir(self, d: Path) -> bool:
        gi = d / ".gitignore"
        if gi.is_file():
            try:
                self.layers.append((d, parse_gitignore(gi.read_text(errors="replace"))))
                return True
            except OSError:
                pass
        return False

    def pop(self):
        self.layers.pop()

    def ignored(self, p: Path, is_dir: bool) -> bool:
        result = False
        for base, rules in self.layers:
            try:
                rel = p.relative_to(base).as_posix()
            except ValueError:
                continue
            for r in rules:
                if r.dir_only and not is_dir:
                    continue
                if r.regex.match(rel):
                    result = not r.negate
        return result


# --- discovery ----------------------------------------------------------------

def _match_any(rel: str, name: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(name, g) for g in globs)


def display_path(p: Path) -> str:
    """Path as stored in the index: relative to cwd when inside it."""
    p = p.resolve() if not p.is_absolute() else p
    try:
        return p.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def discover(roots: list[str], include: list[str], exclude: list[str],
             max_bytes: int = MAX_BYTES_DEFAULT, use_gitignore: bool = True) -> tuple[list[Path], list[str]]:
    """Return (files, skipped_notes)."""
    files: list[Path] = []
    skipped: list[str] = []
    seen: set[Path] = set()

    def consider(f: Path, explicit: bool):
        rp = f.resolve()
        if rp in seen:
            return
        name = f.name
        rel = display_path(rp)
        if name in DEFAULT_EXCLUDE_FILES and not explicit:
            return
        if exclude and _match_any(rel, name, exclude):
            return
        if include and not explicit and not _match_any(rel, name, include):
            return
        try:
            size = rp.stat().st_size
        except OSError:
            return
        if size > max_bytes:
            skipped.append(f"{rel} (over {max_bytes // (1024 * 1024)} MB)")
            return
        if f.suffix.lower() in BINARY_EXT:
            return
        seen.add(rp)
        files.append(rp)

    for root in roots:
        rp = Path(root).expanduser()
        if not rp.exists():
            raise SemError(f"path not found: {root}")
        if rp.is_file():
            consider(rp, explicit=True)
            continue
        rp = rp.resolve()
        stack = IgnoreStack()
        # honour .gitignore files between cwd and the root, when the root is inside cwd
        if use_gitignore:
            cwd = Path.cwd().resolve()
            try:
                parts = rp.relative_to(cwd).parts
                d = cwd
                stack.push_dir(d)
                for part in parts[:-1] if parts else []:
                    d = d / part
                    stack.push_dir(d)
            except ValueError:
                pass

        def walk(d: Path):
            pushed = stack.push_dir(d) if use_gitignore else False
            try:
                entries = sorted(os.scandir(d), key=lambda e: e.name)
            except OSError:
                entries = []
            for e in entries:
                p = Path(e.path)
                try:
                    is_dir = e.is_dir(follow_symlinks=False)
                    is_file = e.is_file()
                except OSError:
                    continue
                if is_dir:
                    if e.name in DEFAULT_EXCLUDE_DIRS:
                        continue
                    if use_gitignore and stack.ignored(p, True):
                        continue
                    rel = display_path(p)
                    if exclude and _match_any(rel, e.name, exclude):
                        continue
                    walk(p)
                elif is_file:
                    if use_gitignore and stack.ignored(p, False):
                        continue
                    consider(p, explicit=False)
            if pushed:
                stack.pop()

        walk(rp)
    return files, skipped


# --- readers ------------------------------------------------------------------

def read_text(path: Path) -> str | None:
    """Decode a file as text; None if it looks binary."""
    data = path.read_bytes()
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _paragraph_units(lines: list[str], first_line: int) -> list[Unit]:
    units, buf, start = [], [], None
    for i, line in enumerate(lines):
        ln = first_line + i
        if line.strip():
            if start is None:
                start = ln
            buf.append(line)
        elif buf:
            units.append(Unit("\n".join(buf), start, ln - 1))
            buf, start = [], None
    if buf:
        units.append(Unit("\n".join(buf), start, first_line + len(lines) - 1))
    return units


def read_markdown(text: str) -> list[Segment]:
    lines = text.splitlines()
    segments: list[Segment] = []
    trail: list[tuple[int, str]] = []
    sec_start, in_fence = 0, False

    carry: list[Unit] = []  # heading-only sections are folded into the next section

    def flush(end: int):
        nonlocal carry
        if end > sec_start:
            units = _paragraph_units(lines[sec_start:end], sec_start + 1)
            if units and all(_HEADING.match(ln) for u in units for ln in u.text.splitlines()):
                carry.extend(units)
                return
            if units:
                heading = " > ".join(t for _, t in trail) or None
                segments.append(Segment(carry + units, "\n\n", heading=heading))
                carry = []

    for i, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            flush(i)
            level = len(m.group(1))
            trail = [(lv, t) for lv, t in trail if lv < level] + [(level, m.group(2))]
            sec_start = i
    flush(len(lines))
    if carry:
        segments.append(Segment(carry, "\n\n", heading=" > ".join(t for _, t in trail) or None))
    return segments


def read_code(text: str) -> list[Segment]:
    # blank-line separated blocks; packing keeps them aligned to blank lines
    units = _paragraph_units(text.splitlines(), 1)
    return [Segment(units, "\n\n")] if units else []


def _get_path(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def _record_text(rec, opts: ReaderOpts) -> str:
    if opts.text_field:
        v = _get_path(rec, opts.text_field)
        if v is None:
            return ""
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    if isinstance(rec, dict):
        parts = []
        for k, v in rec.items():
            if opts.id_field and k == opts.id_field:
                continue
            if isinstance(v, (str, int, float)) and str(v).strip():
                parts.append(f"{k}: {v}")
            elif isinstance(v, (list, dict)):
                parts.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        return "\n".join(parts)
    return rec if isinstance(rec, str) else json.dumps(rec, ensure_ascii=False)


AUTO_ID_KEYS = ("id", "_id", "ID", "Id", "uuid", "key")


def _auto_id(rec) -> str | None:
    if isinstance(rec, dict):
        for k in AUTO_ID_KEYS:
            v = rec.get(k)
            if isinstance(v, (str, int)) and str(v).strip():
                return str(v)
    return None


def _record_segments(records, opts: ReaderOpts, line_of=None) -> list[Segment]:
    segs = []
    for i, rec in enumerate(records):
        rid = None
        if opts.id_field and isinstance(rec, dict):
            v = _get_path(rec, opts.id_field)
            rid = str(v) if v is not None else None
        elif not opts.id_field:
            rid = _auto_id(rec)
        if rid is None:
            rid = str(i + 1)
        text = _record_text(rec, opts).strip()
        if not text:
            continue
        ln = line_of(i) if line_of else None
        segs.append(Segment([Unit(text, ln, ln)], "\n", record_id=rid))
    return segs


def read_jsonl(text: str, opts: ReaderOpts) -> list[Segment]:
    records, lines_of = [], []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
            lines_of.append(n)
        except ValueError:
            continue
    return _record_segments(records, opts, lambda i: lines_of[i])


def read_json(text: str, opts: ReaderOpts) -> list[Segment] | None:
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if isinstance(data, list):
        return _record_segments(data, opts)
    if isinstance(data, dict):
        # a single object: index it as prose-ish text
        return [Segment([Unit(_record_text(data, opts))], "\n", record_id="1")]
    return None


def read_csv(text: str, delimiter: str, opts: ReaderOpts) -> list[Segment]:
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    cols = opts.text_cols
    if cols and reader.fieldnames:
        missing = [c for c in cols if c not in reader.fieldnames]
        if missing:
            raise SemError(f"--text-cols: column(s) not found: {', '.join(missing)} "
                           f"(have: {', '.join(reader.fieldnames)})")
    segs = []
    for i, row in enumerate(reader):
        rid = (row.get(opts.id_field) if opts.id_field else _auto_id(row)) or str(i + 1)
        if cols:
            text = "\n".join(f"{c}: {row.get(c) or ''}" for c in cols if (row.get(c) or "").strip())
        else:
            text = "\n".join(f"{k}: {v}" for k, v in row.items()
                             if k is not None and k != opts.id_field and v and str(v).strip())
        if text.strip():
            segs.append(Segment([Unit(text, i + 2, i + 2)], "\n", record_id=str(rid)))
    return segs


def read_pdf(path: Path) -> list[Segment]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    segs = []
    for n, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        units = [Unit(u.text) for u in _paragraph_units(text.splitlines(), 1)]
        if units:
            segs.append(Segment(units, "\n\n", page=n))
    return segs


def read_file(path: Path, opts: ReaderOpts) -> tuple[str, list[Segment]] | None:
    """Return (kind, segments), or None when the file is binary/unreadable."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf", read_pdf(path)
    text = read_text(path)
    if text is None:
        return None
    if ext in (".jsonl", ".ndjson"):
        return "jsonl", read_jsonl(text, opts)
    if ext == ".json":
        segs = read_json(text, opts)
        if segs is not None:
            return "json", segs
        return "code", read_code(text)
    if ext in (".csv", ".tsv"):
        return "csv", read_csv(text, "\t" if ext == ".tsv" else ",", opts)
    if ext in CODE_EXT:
        return "code", read_code(text)
    if ext in (".md", ".markdown", ".mdx"):
        return "markdown", read_markdown(text)
    return "text", read_markdown(text) if ext in MD_EXT else read_code(text)
