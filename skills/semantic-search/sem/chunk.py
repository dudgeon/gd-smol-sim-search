"""Chunking: pack reader units into token-budgeted chunks with overlap.

Readers (see ingest.py) turn a file into *segments*; a segment is a run of
units (paragraphs, code blocks, lines, a record) that may be packed together.
Chunks never cross segment boundaries (a Markdown section, a PDF page, a
record), so every chunk has a single, precise locator.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Unit:
    text: str
    start_line: int | None = None
    end_line: int | None = None
    tokens: int = 0


@dataclass
class Segment:
    units: list[Unit]
    joiner: str = "\n\n"
    page: int | None = None
    record_id: str | None = None
    heading: str | None = None


@dataclass
class Chunk:
    text: str
    locator: str
    start_line: int | None = None
    end_line: int | None = None
    page: int | None = None
    record_id: str | None = None
    heading: str | None = None
    sha256: str = field(default="")

    def __post_init__(self):
        if not self.sha256:
            self.sha256 = hashlib.sha256(self.text.encode("utf-8", "replace")).hexdigest()


def _locator(start_line, end_line, page, record_id, part, nparts) -> str:
    if record_id is not None:
        loc = f"rec:{record_id}"
    elif page is not None:
        loc = f"p{page}"
        if start_line is not None:
            loc += f":L{start_line}-{end_line}"
    elif start_line is not None:
        loc = f"L{start_line}-{end_line}"
    else:
        loc = "all"
    if nparts > 1 and record_id is not None:
        loc += f"#{part + 1}"
    return loc


def _split_long(unit: Unit, budget: int, overlap: int, embedder) -> list[Unit]:
    """Cut a unit that exceeds the budget at token boundaries."""
    spans = embedder.token_spans(unit.text)
    if len(spans) <= budget:
        return [unit]
    step = max(1, budget - overlap)
    out = []
    for s in range(0, len(spans), step):
        window = spans[s: s + budget]
        a, b = window[0][0], window[-1][1]
        if s + budget < len(spans):
            b = spans[s + budget][0]  # keep trailing whitespace/punctuation up to the next token
        text = unit.text[a:b].strip()
        if not text:
            continue
        sl = el = None
        if unit.start_line is not None:
            sl = unit.start_line + unit.text.count("\n", 0, a)
            el = unit.start_line + unit.text.count("\n", 0, b)
        out.append(Unit(text, sl, el, len(window)))
        if s + budget >= len(spans):
            break
    return out


def chunk_segments(segments: list[Segment], embedder, budget: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    # count all unit tokens for the file in one tokenizer call
    all_units = [u for seg in segments for u in seg.units]
    counts = embedder.count_tokens([u.text for u in all_units])
    for u, c in zip(all_units, counts):
        u.tokens = c

    for seg in segments:
        units: list[Unit] = []
        for u in seg.units:
            if not u.text.strip():
                continue
            units.extend(_split_long(u, budget, overlap, embedder) if u.tokens > budget else [u])
        groups: list[list[Unit]] = []
        cur: list[Unit] = []
        cur_tok = 0
        for u in units:
            if cur and cur_tok + u.tokens > budget:
                groups.append(cur)
                # carry trailing units into the next chunk as overlap
                carry: list[Unit] = []
                ct = 0
                for prev in reversed(cur):
                    if ct + prev.tokens > overlap or ct + prev.tokens + u.tokens > budget:
                        break
                    carry.insert(0, prev)
                    ct += prev.tokens
                cur, cur_tok = carry, ct
            cur.append(u)
            cur_tok += u.tokens
        if cur:
            groups.append(cur)
        for i, g in enumerate(groups):
            text = seg.joiner.join(u.text for u in g).strip()
            if not text:
                continue
            lines = [x for u in g for x in (u.start_line, u.end_line) if x is not None]
            sl, el = (min(lines), max(lines)) if lines else (None, None)
            chunks.append(Chunk(
                text=text,
                locator=_locator(sl, el, seg.page, seg.record_id, i, len(groups)),
                start_line=sl, end_line=el, page=seg.page,
                record_id=seg.record_id, heading=seg.heading,
            ))
    return chunks
