"""Tests with the real, vendored bge-small model (ONNX Runtime on CPU).

The model is assembled from vendor/models/ exactly as setup.sh does, so these always run
when onnxruntime and tokenizers are installed (see tools/requirements-dev.txt).
"""

from __future__ import annotations

import shutil
import sqlite3

import pytest

pytest.importorskip("onnxruntime")
pytest.importorskip("tokenizers")

from conftest import DUPE_PAIR, FIXTURES, GOLDEN, Sem, assemble_vendored_model, base_env  # noqa: E402


@pytest.fixture(scope="session")
def models_dir(tmp_path_factory):
    return assemble_vendored_model(tmp_path_factory.mktemp("models"))


@pytest.fixture(scope="module")
def bge(tmp_path_factory, models_dir):
    p = tmp_path_factory.mktemp("bge") / "proj"
    p.mkdir()
    shutil.copytree(FIXTURES, p / "fx")
    env = base_env(p)
    env["SEM_MODELS_DIR"] = str(models_dir)
    s = Sem(p, env)
    s("index", "fx")
    return s


@pytest.mark.parametrize("query,expected", GOLDEN)
def test_golden_top1(bge, query, expected):
    res = bge.json("search", query, "-k", "3")
    paths = [r["path"] for r in res["results"]]
    assert paths[0].endswith(expected), (query, paths)


def test_dupes_and_similar(bge):
    d = bge.json("dupes", "--across-files-only")
    assert {tuple(sorted((p["a"]["path"], p["b"]["path"]))) for p in d["pairs"]} == {DUPE_PAIR}
    s = bge.json("similar", "fx/docs/tides.md", "--group-by-file", "-k", "1")
    assert s["results"][0]["path"] == "fx/notes/moon-notes.md"


def test_known_scores(bge):
    # regression guard: these match sentence-transformers on the same model to 4 decimals
    para = bge.json("compare", "--text", "the cat sat on the mat", "a feline rested on the rug")
    far = bge.json("compare", "--text", "the cat sat on the mat", "quarterly revenue grew 8 percent")
    assert para["score"] == pytest.approx(0.7484, abs=2e-3)
    assert far["score"] == pytest.approx(0.3728, abs=2e-3)


def test_all_commands(bge):
    for cmd in (["similar", "fx/code/fib.py:9"], ["compare", "fx/docs/tides.md", "fx/code/fib.py"],
                ["cluster", "--level", "file", "--k", "auto"], ["outliers"], ["info"], ["embed", "hi", "--query"]):
        assert bge.json(*cmd)["ok"], cmd
    v = bge.json("embed", "hello")
    assert v["dim"] == 384


def test_token_budget_respected(bge, models_dir):
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(str(models_dir / "bge-small" / "tokenizer.json"))
    tok.no_truncation()
    bge("index", "fx", "--index", "small", "--chunk-tokens", "40", "--overlap", "5")
    conn = sqlite3.connect(bge.project / ".sem/indexes/small/meta.sqlite")
    texts = [t for (t,) in conn.execute("SELECT text FROM chunks WHERE deleted=0")]
    assert texts
    assert all(len(tok.encode(t, add_special_tokens=False).ids) <= 40 for t in texts)


def test_other_model_rejected(bge):
    res = bge.json("search", "x", "--model", "hash-test", check=False)
    assert res["ok"] is False and "built with model 'bge-small'" in res["error"]


def test_revision_mismatch_is_an_error(bge, models_dir):
    rev = models_dir / "bge-small" / ".sem-revision"
    old = rev.read_text()
    try:
        rev.write_text("something-else\n")
        res = bge.json("search", "tides", check=False)
        assert res["ok"] is False and "Rebuild" in res["error"]
    finally:
        rev.write_text(old)
