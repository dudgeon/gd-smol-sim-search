"""Tests on the real torch / sentence-transformers path.

* tiny-bert: a random-weight model built locally, so these always run when torch is available.
* bge-small golden tests: run when a real runtime is installed (``./setup.sh``), found at the default
  locations or via ``SEM_TEST_RUNTIME``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("torch")
pytest.importorskip("sentence_transformers")

from conftest import DUPE_PAIR, GOLDEN, Sem, base_env, find_runtime  # noqa: E402
from tiny_model import build_tiny_model, tiny_registry  # noqa: E402

FIXTURES_DIR = __import__("conftest").FIXTURES


@pytest.fixture(scope="session")
def tiny_runtime(tmp_path_factory):
    rt = tmp_path_factory.mktemp("tiny-rt")
    (rt / "models").mkdir()
    build_tiny_model(rt / "models", FIXTURES_DIR)
    tiny_registry(rt / "registry.json")
    return rt


@pytest.fixture
def tiny_sem(project, tiny_runtime):
    env = base_env(project)
    env.update({"SEM_REGISTRY": str(tiny_runtime / "registry.json"),
                "SEM_MODELS_DIR": str(tiny_runtime / "models")})
    return Sem(project, env)


def test_tiny_model_end_to_end(tiny_sem):
    res = tiny_sem.json("index", "fx", "--device", "cpu")
    assert res["model"] == "tiny-bert" and res["device"] == "cpu"
    assert res["chunks_embedded"] > 10
    for cmd in (["search", "tides"], ["similar", "fx/docs/tides.md"], ["compare", "fx/docs/tides.md", "fx/code/fib.py"],
                ["dupes"], ["cluster", "--k", "3"], ["outliers"], ["embed", "hello", "--query"]):
        out = tiny_sem.json(*cmd, "--device", "cpu")
        assert out["ok"] and out["device"] == "cpu", cmd


@pytest.mark.parametrize("mode", ["fail", "crash"])
def test_every_command_works_when_metal_probe_fails(tiny_sem, mode):
    env = {"SEM_PROBE_SIMULATE": mode, "SEM_PROBE_TIMEOUT": "5"}
    res = tiny_sem.json("index", "fx", env=env)
    assert res["device"] == "cpu" and res["chunks_embedded"] > 0
    for cmd in (["search", "tides"], ["compare", "--text", "a", "b"], ["embed", "x"]):
        out = tiny_sem.json(*cmd, env=env)
        assert out["ok"] and out["device"] == "cpu"
        assert "Metal unavailable" in out["device_note"]


def test_token_budget_respected(tiny_sem, project):
    tiny_sem("index", "fx", "--device", "cpu", "--chunk-tokens", "40", "--overlap", "5")
    from sentence_transformers import SentenceTransformer
    import sqlite3
    conn = sqlite3.connect(project / ".sem/indexes/default/meta.sqlite")
    texts = [t for (t,) in conn.execute("SELECT text FROM chunks WHERE deleted=0")]
    tok = SentenceTransformer(tiny_sem.env["SEM_MODELS_DIR"] + "/tiny-bert", device="cpu").tokenizer
    over = [t for t in texts if len(tok(t, add_special_tokens=False)["input_ids"]) > 40]
    assert not over


def test_revision_mismatch_is_an_error(tiny_sem, tiny_runtime, project):
    tiny_sem("index", "fx", "--device", "cpu")
    rev = tiny_runtime / "models" / "tiny-bert" / ".sem-revision"
    old = rev.read_text()
    try:
        rev.write_text("something-else\n")
        res = tiny_sem.json("search", "tides", check=False)
        assert res["ok"] is False and "Rebuild" in res["error"]
    finally:
        rev.write_text(old)


# --- real model --------------------------------------------------------------------

REAL_RT = find_runtime()
real = pytest.mark.skipif(REAL_RT is None or not (REAL_RT / "models" / "bge-small").exists(),
                          reason="bge-small runtime not installed (run ./setup.sh)")


@pytest.fixture(scope="module")
def bge_project(tmp_path_factory):
    import shutil
    p = tmp_path_factory.mktemp("bge") / "proj"
    p.mkdir()
    shutil.copytree(FIXTURES_DIR, p / "fx")
    env = base_env(p)
    env.update({"SEM_RUNTIME": str(REAL_RT)})
    s = Sem(p, env)
    s("index", "fx")
    return s


@real
@pytest.mark.parametrize("query,expected", GOLDEN)
def test_bge_golden(bge_project, query, expected):
    res = bge_project.json("search", query, "-k", "3")
    paths = [r["path"] for r in res["results"]]
    assert paths[0].endswith(expected), (query, paths)


@real
def test_bge_dupes_and_similar(bge_project):
    d = bge_project.json("dupes", "--across-files-only")
    assert {tuple(sorted((p["a"]["path"], p["b"]["path"]))) for p in d["pairs"]} == {DUPE_PAIR}
    s = bge_project.json("similar", "fx/docs/tides.md", "--group-by-file", "-k", "1")
    assert s["results"][0]["path"] == "fx/notes/moon-notes.md"


@real
def test_bge_other_model_rejected(bge_project):
    res = bge_project.json("search", "x", "--model", "qwen3-0.6b", check=False)
    assert res["ok"] is False and "built with model 'bge-small'" in res["error"]
