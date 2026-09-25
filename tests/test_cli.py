"""End-to-end CLI tests with the hash test model (no model files)."""

from __future__ import annotations

import json
import os
import time

import pytest

from conftest import DUPE_PAIR, GOLDEN


def test_index_and_json_contract(sem, project):
    res = sem.json("index", "fx")
    assert res["ok"] and res["command"] == "index"
    assert res["files_seen"] == 10
    assert len(res["added"]) == 10
    assert res["chunks_embedded"] > 10
    assert (project / ".sem" / ".gitignore").read_text() == "*\n"
    for f in ("manifest.json", "vectors.f16.npy", "meta.sqlite"):
        assert (project / ".sem" / "indexes" / "default" / f).exists()


@pytest.mark.parametrize("query,expected", GOLDEN)
def test_golden_top3(sem, query, expected):
    sem("index", "fx")
    res = sem.json("search", query, "-k", "3")
    paths = [r["path"] for r in res["results"]]
    assert any(p.endswith(expected) for p in paths), (query, paths)


def test_search_options(sem):
    sem("index", "fx")
    res = sem.json("search", "tides moon", "-k", "5", "--group-by-file")
    paths = [r["path"] for r in res["results"]]
    assert len(paths) == len(set(paths))
    res = sem.json("search", "tides moon", "-k", "5", "--path-glob", "*.py")
    assert all(r["path"].endswith(".py") for r in res["results"])
    res = sem.json("search", "tides moon", "--min-score", "0.99")
    assert res["results"] == []
    res = sem.json("search", "tides moon", "-k", "1", "--snippet", "10")
    assert len(res["results"][0]["text"]) <= 12


def test_dupes_finds_planted_pair(sem):
    sem("index", "fx")
    res = sem.json("dupes", "--across-files-only")
    pairs = {tuple(sorted((p["a"]["path"], p["b"]["path"]))) for p in res["pairs"]}
    assert DUPE_PAIR in pairs
    assert res["total_pairs"] >= 1


def test_similar_file_chunk_and_line(sem):
    sem("index", "fx")
    res = sem.json("similar", "fx/docs/tides.md", "-k", "3", "--group-by-file")
    assert res["item_kind"] == "file"
    assert res["results"][0]["path"] == "fx/notes/moon-notes.md"
    assert all(r["path"] != "fx/docs/tides.md" for r in res["results"])

    cid = res["results"][0]["chunk_id"]
    res2 = sem.json("similar", cid, "-k", "2")
    assert res2["item_kind"] == "chunk"
    assert all(r["chunk_id"] != cid for r in res2["results"])

    res3 = sem.json("similar", "fx/docs/tides.md:10", "-k", "1")
    assert res3["item_kind"] == "chunk"
    assert res3["results"][0]["path"] == "fx/notes/moon-notes.md"


def test_similar_unknown_item(sem):
    sem("index", "fx")
    res = sem.json("similar", "nope/missing.md", check=False)
    assert res["ok"] is False and "not a chunk id" in res["error"]


def test_compare(sem):
    sem("index", "fx")
    res = sem.json("compare", "fx/docs/tides.md", "fx/notes/moon-notes.md")
    assert res["score"] > 0.5
    assert res["best_chunk_pairs"][0]["score"] > 0.85
    far = sem.json("compare", "fx/docs/tides.md", "fx/code/fib.py")
    assert far["score"] < res["score"]
    t = sem.json("compare", "--text", "spring tides at full moon", "spring tides at new moon")
    assert 0 < t["score"] <= 1.0001


def test_cluster_and_outliers(sem):
    sem("index", "fx")
    res = sem.json("cluster", "--level", "file", "--k", "3")
    assert res["k"] == 3
    assert sum(c["size"] for c in res["clusters"]) == 10
    together = [c for c in res["clusters"] if "fx/docs/tides.md" in c["members"]][0]
    assert "fx/notes/moon-notes.md" in together["members"]
    auto = sem.json("cluster", "--level", "chunk", "--k", "auto")
    assert auto["k"] >= 2 and auto["k_search"]
    out = sem.json("outliers", "-n", "3")
    assert len(out["results"]) == 3
    scores = [r["mean_neighbor_score"] for r in out["results"]]
    assert scores == sorted(scores)
    out_f = sem.json("outliers", "--level", "file", "-n", "2")
    assert "path" in out_f["results"][0]


def test_embed_info_list_drop(sem):
    v = sem.json("embed", "hello world")
    assert v["dim"] == len(v["vector"]) == 2048
    sem("index", "fx")
    sem("index", "fx/docs", "--index", "docs")
    info = sem.json("info")
    assert info["files"] == 10 and info["chunks"] > 0 and info["model"]["key"] == "hash-test"
    names = [d["index"] for d in sem.json("list")["indexes"]]
    assert names == ["default", "docs"]
    sem("drop", "docs")
    assert [d["index"] for d in sem.json("list")["indexes"]] == ["default"]
    assert sem.json("drop", "docs", check=False)["ok"] is False


def test_incremental_reembeds_only_changed_file(sem, project):
    sem("index", "fx")
    again = sem.json("index", "fx")
    assert again["chunks_embedded"] == 0 and again["unchanged"] == 10

    # touch without content change: no re-embed
    f = project / "fx" / "docs" / "kubernetes.md"
    os.utime(f, (time.time() + 5, time.time() + 5))
    res = sem.json("index", "fx")
    assert res["chunks_embedded"] == 0 and res["changed"] == []

    f = project / "fx" / "docs" / "tides.md"
    f.write_text(f.read_text() + "\n## Tidal bores\n\nSome rivers see a tidal bore when the tide rushes upstream.\n")
    res = sem.json("index", "fx")
    assert res["changed"] == ["fx/docs/tides.md"]
    assert res["added"] == [] and res["removed"] == []
    n_tides_chunks = res["chunks_embedded"]
    assert n_tides_chunks >= 1

    hits = sem.json("search", "tidal bore rushing up a river", "-k", "1")
    assert hits["results"][0]["path"] == "fx/docs/tides.md"

    (project / "fx" / "notes" / "garden.txt").unlink()
    res = sem.json("index", "fx")
    assert res["removed"] == ["fx/notes/garden.txt"] and res["chunks_embedded"] == 0
    info = sem.json("info")
    assert info["files"] == 9


def test_compaction(sem, project):
    sem("index", "fx")
    f = project / "fx" / "docs" / "sourdough.md"
    for i in range(6):
        f.write_text(f.read_text() + f"\n\nExtra note {i} about crust colour.\n")
        res = sem.json("index", "fx")
    info = sem.json("info")
    # rewrites tombstone the file's old rows; compaction keeps them under 20 %
    assert info["tombstoned"] <= 0.2 * (info["chunks"] + info["tombstoned"]) + 1
    hits = sem.json("search", "extra note about crust colour", "-k", "1")
    assert hits["results"][0]["path"] == "fx/docs/sourdough.md"


def test_model_mismatch_is_a_clear_error(sem):
    sem("index", "fx")
    for cmd in (["search", "tides"], ["index", "fx"], ["similar", "fx/docs/tides.md"]):
        res = sem.json(*cmd, "--model", "bge-small", check=False)
        assert res["ok"] is False
        assert "built with model 'hash-test'" in res["error"]


def test_chunking_change_requires_rebuild(sem):
    sem("index", "fx")
    res = sem.json("index", "fx", "--chunk-tokens", "50", check=False)
    assert res["ok"] is False and "--rebuild" in res["error"]
    ok = sem.json("index", "fx", "--chunk-tokens", "50", "--rebuild")
    assert ok["chunks_embedded"] > 0


def test_structured_records(sem):
    res = sem.json("index", "fx/data/tickets.jsonl", "--index", "t", "--text-field", "body.text",
                   "--id-field", "id")
    assert res["chunks_embedded"] == 3
    hit = sem.json("search", "charged twice on my card", "--index", "t", "-k", "1")["results"][0]
    assert hit["locator"] == "rec:T-101"
    assert hit["text"].startswith("My credit card")
    res = sem.json("index", "fx/data/recipes.csv", "--index", "r", "--text-cols", "title,description",
                   "--id-col", "id")
    assert res["chunks_embedded"] == 3
    hit = sem.json("search", "kidney beans and chili powder", "--index", "r", "-k", "1")["results"][0]
    assert hit["locator"] == "rec:r2" and "minutes" not in hit["text"]
    bad = sem.json("index", "fx/data/recipes.csv", "--index", "r2", "--text-cols", "nope", check=False)
    assert bad["ok"] is False and "not found" in bad["error"]


def test_pdf_pages(sem):
    sem("index", "fx/papers")
    hit = sem.json("search", "earthquake magnitude seismometer", "-k", "1")["results"][0]
    assert hit["path"].endswith("volcanoes.pdf") and hit["locator"] == "p2"


def test_missing_index_and_bad_path(sem):
    res = sem.json("search", "x", check=False)
    assert res["ok"] is False and "no index named 'default'" in res["error"]
    res = sem.json("index", "does-not-exist", check=False)
    assert res["ok"] is False and "path not found" in res["error"]


def test_human_output(sem):
    sem("index", "fx")
    p = sem("search", "tides")
    assert "fx/docs/tides.md" in p.stdout


def test_nothing_written_outside_sem_home(sem, project, tmp_path):
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*") if ".sem" not in p.parts)
    sem("index", "fx")
    sem("search", "tides")
    sem("dupes")
    sem("cluster")
    after = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*") if ".sem" not in p.parts)
    assert before == after


def test_unwritable_cwd(project, sem):
    ro = project / "ro"
    ro.mkdir()
    os.chmod(ro, 0o555)
    try:
        if os.access(ro, os.W_OK):
            pytest.skip("running as a user that can write anywhere (root)")
        from conftest import Sem, base_env
        s = Sem(ro, {**base_env(ro), "SEM_MODEL": "hash-test"})
        p = s("doctor", check=False)
        assert p.returncode != 0 and "cd into a project directory" in p.stderr
    finally:
        os.chmod(ro, 0o755)


def test_neighbors_bulk(sem):
    sem("index", "fx")
    info = sem.json("info")
    res = sem.json("neighbors", "-k", "3")
    assert res["level"] == "chunk" and res["k"] == 3
    assert res["items_total"] == len(res["items"]) == info["chunks"]
    for it in res["items"]:
        ids = [nb["chunk_id"] for nb in it["neighbors"]]
        assert it["chunk_id"] not in ids and len(ids) == len(set(ids)) == 3
        scores = [nb["score"] for nb in it["neighbors"]]
        assert scores == sorted(scores, reverse=True)
        assert "text" not in it and all("text" not in nb for nb in it["neighbors"])
    # the planted near-duplicates are each other's top neighbour
    tides = next(i for i in res["items"] if i["path"] == "fx/docs/tides.md" and i["locator"] == "L9-13")
    moon = next(i for i in res["items"] if i["path"] == "fx/notes/moon-notes.md")
    assert tides["neighbors"][0]["chunk_id"] == moon["chunk_id"]
    assert moon["neighbors"][0]["chunk_id"] == tides["chunk_id"]


def test_neighbors_matches_similar(sem):
    sem("index", "fx")
    res = sem.json("neighbors", "-k", "4")
    it = next(i for i in res["items"] if i["path"] == "fx/docs/sourdough.md")
    sim = sem.json("similar", it["chunk_id"], "-k", "4")
    assert [n["chunk_id"] for n in it["neighbors"]] == [h["chunk_id"] for h in sim["results"]]
    assert [n["score"] for n in it["neighbors"]] == [h["score"] for h in sim["results"]]


def test_neighbors_options(sem, project):
    sem("index", "fx")
    afo = sem.json("neighbors", "-k", "2", "--across-files-only")
    for it in afo["items"]:
        assert all(nb["path"] != it["path"] for nb in it["neighbors"])
    filt = sem.json("neighbors", "-k", "5", "--min-score", "0.5")
    nonempty = [i for i in filt["items"] if i["neighbors"]]
    assert {i["path"] for i in nonempty} == {"fx/docs/tides.md", "fx/notes/moon-notes.md"}
    snip = sem.json("neighbors", "-k", "1", "--snippet", "30")
    assert all(len(nb["text"]) <= 32 for i in snip["items"] for nb in i["neighbors"])
    files = sem.json("neighbors", "--level", "file", "-k", "2")
    assert files["items_total"] == 10
    assert {"path", "neighbors"} == set(files["items"][0].keys())
    # single-file index refuses --across-files-only with a clear error
    sem("index", "fx/docs/tides.md", "--index", "one")
    err = sem.json("neighbors", "--across-files-only", "--index", "one", check=False)
    assert err["ok"] is False and "single file" in err["error"]
