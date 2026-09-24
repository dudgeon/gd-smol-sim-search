from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "smol-sim-search"
FIXTURES = REPO / "tests" / "fixtures"
sys.path.insert(0, str(SKILL))
sys.path.insert(0, str(REPO / "tests"))

# (query, expected path suffix) — used by the hash-model and real-model golden tests
GOLDEN = [
    ("why are there two high tides every day", "docs/tides.md"),
    ("feeding a sourdough starter with flour and water", "docs/sourdough.md"),
    ("horizontal pod autoscaler adds replicas", "docs/kubernetes.md"),
    ("retry a request with exponential backoff", "code/http_retry.py"),
    ("customer credit card charged twice", "data/tickets.jsonl"),
    ("magma erupts from a volcano", "papers/volcanoes.pdf"),
    ("growing tomato seedlings in sunlight", "notes/garden.txt"),
]
DUPE_PAIR = ("fx/docs/tides.md", "fx/notes/moon-notes.md")


def assemble_vendored_model(dest: Path) -> Path:
    """Join the vendored model pieces (as setup.sh does) into dest/<key>/ and verify the hash."""
    import hashlib
    src = next(p for p in (REPO / "vendor" / "models").iterdir() if p.is_dir())
    meta = json.loads((src / "model.json").read_text())
    out = dest / src.name
    out.mkdir(parents=True, exist_ok=True)
    for name, want in meta["files_sha256"].items():
        parts = sorted(src.glob(f"{name}.part*")) or [src / name]
        data = b"".join(p.read_bytes() for p in parts)
        assert hashlib.sha256(data).hexdigest() == want, f"{name} does not match upstream hash"
        (out / name).write_bytes(data)
    (out / ".sem-revision").write_text(meta["revision"] + "\n")
    return dest


class Sem:
    """Runs `python -m sem` in a project directory, like bin/sem does."""

    def __init__(self, project: Path, env: dict):
        self.project = project
        self.env = env

    def __call__(self, *args: str, check: bool = True, env: dict | None = None, python: str | None = None):
        e = dict(self.env)
        if env:
            e.update(env)
        proc = subprocess.run([python or sys.executable, "-P", "-m", "sem", *args], cwd=self.project,
                              env=e, capture_output=True, text=True, timeout=600)
        if check and proc.returncode != 0:
            raise AssertionError(f"sem {' '.join(args)} failed ({proc.returncode}):\n{proc.stderr}\n{proc.stdout}")
        return proc

    def json(self, *args: str, check: bool = True, env: dict | None = None) -> dict:
        proc = self(*args, "--json", check=check, env=env)
        return json.loads(proc.stdout)


def base_env(project: Path) -> dict:
    sem_home = project / ".sem"
    env = {k: v for k, v in os.environ.items() if not k.startswith("SEM_")}
    env.update({
        "PYTHONPATH": str(SKILL),
        "PYTHONDONTWRITEBYTECODE": "1",
        "SEM_HOME": str(sem_home),
        "TMPDIR": str(sem_home / "tmp"),
        "XDG_CACHE_HOME": str(sem_home / "cache"),
        "SEM_QUIET": "1",
    })
    return env


@pytest.fixture
def project(tmp_path) -> Path:
    p = tmp_path / "proj"
    p.mkdir()
    shutil.copytree(FIXTURES, p / "fx")
    return p


@pytest.fixture
def sem(project) -> Sem:
    """sem with the dependency-free hash test model."""
    env = base_env(project)
    env["SEM_MODEL"] = "hash-test"
    env["SEM_DEVICE"] = "cpu"
    return Sem(project, env)
