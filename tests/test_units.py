"""Unit tests: .gitignore, discovery, readers, chunking, k-means, store recovery, network guard."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from conftest import SKILL
from sem import analyze, chunk, ingest
from sem.embed import HashEmbedder
from sem.env import model_spec


@pytest.fixture
def hashemb():
    return HashEmbedder(model_spec("hash-test"))


def test_gitignore_rules():
    rules = ingest.parse_gitignore("""
# comment
*.log
build/
/root-only.txt
docs/**/draft*.md
!keep.log
""")
    st = ingest.IgnoreStack()
    st.layers.append((Path("/p"), rules))
    assert st.ignored(Path("/p/a/x.log"), False)
    assert not st.ignored(Path("/p/a/keep.log"), False)
    assert st.ignored(Path("/p/a/build"), True)
    assert not st.ignored(Path("/p/a/build"), False)  # dir-only rule
    assert st.ignored(Path("/p/root-only.txt"), False)
    assert not st.ignored(Path("/p/sub/root-only.txt"), False)
    assert st.ignored(Path("/p/docs/a/b/draft-1.md"), False)
    assert st.ignored(Path("/p/docs/draft.md"), False)


def test_discover_excludes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("secret/\n*.tmp\n")
    for rel in ["a.md", "b.tmp", "secret/s.md", "node_modules/m.js", ".git/config", "img.png", "sub/c.py"]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("hello")
    (tmp_path / "big.txt").write_bytes(b"x" * 2048)
    files, skipped = ingest.discover(["."], [], [], max_bytes=1024)
    rels = sorted(ingest.display_path(f) for f in files)
    assert rels == [".gitignore", "a.md", "sub/c.py"]
    assert any("big.txt" in s for s in skipped)
    files, _ = ingest.discover(["."], ["*.py"], [], max_bytes=1024)
    assert [ingest.display_path(f) for f in files] == ["sub/c.py"]
    files, _ = ingest.discover(["."], [], ["sub/*"], max_bytes=1024, use_gitignore=False)
    rels = sorted(ingest.display_path(f) for f in files)
    assert "sub/c.py" not in rels and "secret/s.md" in rels and "b.tmp" in rels


def test_binary_and_encoding(tmp_path):
    b = tmp_path / "blob.dat"
    b.write_bytes(b"abc\x00def")
    assert ingest.read_file(b, ingest.ReaderOpts()) is None
    latin = tmp_path / "latin.txt"
    latin.write_bytes("café au lait".encode("latin-1"))
    kind, segs = ingest.read_file(latin, ingest.ReaderOpts())
    assert "caf" in segs[0].units[0].text


def test_markdown_sections_and_heading_trail():
    text = "# Title\n\n## A\n\npara a1\n\npara a2\n\n## B\n\n```\n# not a heading\n```\n\npara b\n"
    segs = ingest.read_markdown(text)
    assert [s.heading for s in segs] == ["Title > A", "Title > B"]
    # the heading-only "# Title" section is folded into the next section
    assert segs[0].units[0].text == "# Title"
    assert "# not a heading" in "\n".join(u.text for u in segs[1].units)


def test_chunk_budget_overlap_and_lines(hashemb):
    paras = [f"paragraph {i} " + " ".join(f"w{i}x{j}" for j in range(20)) for i in range(10)]
    text = "\n\n".join(paras)
    segs = ingest.read_code(text)
    chunks = chunk.chunk_segments(segs, hashemb, budget=50, overlap=22)
    assert len(chunks) > 3
    for c in chunks:
        assert hashemb.count_tokens([c.text])[0] <= 50
        assert c.locator.startswith("L")
    # consecutive chunks overlap by one paragraph
    assert chunks[0].text.split("\n\n")[-1] == chunks[1].text.split("\n\n")[0]
    assert chunks[0].start_line == 1


def test_long_unit_is_split(hashemb):
    long = " ".join(f"tok{i}" for i in range(500))
    segs = [chunk.Segment([chunk.Unit(long, 1, 1)], "\n", record_id="r1")]
    chunks = chunk.chunk_segments(segs, hashemb, budget=100, overlap=10)
    assert len(chunks) >= 5
    assert chunks[0].locator == "rec:r1#1" and chunks[1].locator == "rec:r1#2"
    assert all(hashemb.count_tokens([c.text])[0] <= 100 for c in chunks)
    joined = " ".join(c.text for c in chunks)
    assert "tok0" in joined and "tok499" in joined


def test_kmeans_separates_blobs():
    rng = np.random.default_rng(0)
    centers = analyze._normalize(rng.normal(size=(3, 16)).astype(np.float32))
    X = analyze._normalize(np.concatenate([c + 0.05 * rng.normal(size=(40, 16)) for c in centers]).astype(np.float32))
    C, labels, _ = analyze.spherical_kmeans(X, 3, seed=0)
    for b in range(3):
        assert len(set(labels[b * 40:(b + 1) * 40])) == 1
    k, _ = analyze.choose_k(X, seed=0)
    assert k == 3


def test_store_recovers_interrupted_swap(tmp_path):
    from sem.env import Paths, ensure_sem_home
    from sem import store
    paths = Paths(sem_home=tmp_path / ".sem", runtime=None)
    ensure_sem_home(paths.sem_home)
    old = paths.indexes / ".x.old"
    old.mkdir(parents=True)
    (old / "manifest.json").write_text("{}")
    store.recover(paths, "x")  # crash after old->.old but before new->x
    assert (paths.indexes / "x" / "manifest.json").exists() and not old.exists()


def test_invalid_index_names():
    from sem import store
    from sem.env import SemError
    for bad in ["", "../x", ".hidden", "a/b"]:
        with pytest.raises(SemError):
            store.valid_name(bad)


def test_network_guard_blocks_connections():
    code = (
        "import socket, sem.env as e; e.install_network_guard()\n"
        "try:\n    socket.create_connection(('127.0.0.1', 9))\nexcept e.NetworkBlocked: print('blocked1')\n"
        "s = socket.socket()\n"
        "try:\n    s.connect(('1.1.1.1', 443))\nexcept e.NetworkBlocked: print('blocked2')\n"
        "try:\n    socket.getaddrinfo('example.com', 443)\nexcept e.NetworkBlocked: print('blocked3')\n"
        "print(e.network_guard_active())\n"
    )
    env = {**os.environ, "PYTHONPATH": str(SKILL)}
    env.pop("SEM_ALLOW_NETWORK", None)
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout
    assert out.split() == ["blocked1", "blocked2", "blocked3", "True"]


def test_unicode_line_separators_do_not_drop_jsonl_records():
    # issue #1: U+2028 etc. are valid inside JSON strings but str.splitlines() breaks on them
    import json as _json
    recs = [{"id": "A", "text": "first"},
            {"id": "B", "text": "one two"},
            {"id": "C", "text": "three four\x85five"},
            {"id": "D", "text": "last"}]
    text = "\n".join(_json.dumps(r, ensure_ascii=False) for r in recs) + "\n"
    segs = ingest.read_jsonl(text, ingest.ReaderOpts(text_field="text", id_field="id"))
    assert [s.record_id for s in segs] == ["A", "B", "C", "D"]
    assert [s.units[0].start_line for s in segs] == [1, 2, 3, 4]
    assert segs[1].units[0].text == "one two"  # content kept verbatim


def test_unicode_line_separators_do_not_shift_line_numbers():
    segs = ingest.read_code("alpha beta\n\ngamma")
    units = [(u.text, u.start_line, u.end_line) for s in segs for u in s.units]
    assert units == [("alpha beta", 1, 1), ("gamma", 3, 3)]
    md = ingest.read_markdown("# T\n\npara one\n\n## S\n\npara two\n")
    all_units = [(u.text, u.start_line) for s in md for u in s.units]
    assert ("para one", 3) in all_units
    assert ("para two", 7) in all_units


def test_blocked_topk_matches_brute_force():
    rng = np.random.default_rng(7)
    X = analyze._normalize(rng.normal(size=(53, 16)).astype(np.float32))
    S = X @ X.T
    np.fill_diagonal(S, -np.inf)
    for rb, cb in [(7, 11), (53, 53), (64, 8)]:
        scores, pos = analyze._blocked_topk(53, 5, lambda a, b: X[a:b],
                                            row_block=rb, col_block=cb)
        for i in range(53):
            want = np.sort(S[i])[::-1][:5]
            assert np.allclose(scores[i], want, atol=1e-6), (rb, cb, i)
            # returned positions really carry the returned scores, no self
            assert i not in pos[i]
            assert np.allclose(S[i][pos[i]], scores[i], atol=1e-6)
            assert list(scores[i]) == sorted(scores[i], reverse=True)


def test_blocked_topk_group_exclusion_and_padding():
    rng = np.random.default_rng(1)
    X = analyze._normalize(rng.normal(size=(12, 8)).astype(np.float32))
    groups = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2])
    scores, pos = analyze._blocked_topk(12, 8, lambda a, b: X[a:b], groups,
                                        row_block=5, col_block=4)
    for i in range(12):
        valid = pos[i][pos[i] >= 0]
        assert all(groups[j] != groups[i] for j in valid)
        # the lone member of group 2 has 11 cross-group candidates; group 0 members have 7
        expect = (groups != groups[i]).sum()
        assert len(valid) == min(8, expect)
        # padding sits at the end with -inf scores
        assert all(s == -np.inf for s, p in zip(scores[i], pos[i]) if p < 0)
