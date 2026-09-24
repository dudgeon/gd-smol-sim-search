"""bin/sem: environment, runtime discovery, project-local state."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SKILL

WRAPPER = SKILL / "bin" / "sem"


@pytest.fixture
def fake_runtime(tmp_path):
    rt = tmp_path / "rt"
    rt.mkdir()
    (rt / "models").mkdir()
    (rt / "venv").symlink_to(Path(sys.prefix))  # the venv running the tests
    (rt / "install.json").write_text("{}")
    return rt


def run(cwd, rt, *args, extra=None):
    env = {"PATH": os.environ["PATH"], "HOME": str(cwd), "SEM_RUNTIME": str(rt), "SEM_MODEL": "hash-test",
           "SEM_QUIET": "1", **(extra or {})}
    return subprocess.run([str(WRAPPER), *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=120)


def test_wrapper_sets_project_local_env(tmp_path, fake_runtime):
    proj = tmp_path / "p"
    proj.mkdir()
    p = run(proj, fake_runtime, "doctor", "--json")
    doc = json.loads(p.stdout)
    sem_home = proj / ".sem"
    assert doc["sem_home"] == str(sem_home)
    assert doc["env"]["TMPDIR"] == str(sem_home / "tmp")
    assert doc["env"]["XDG_CACHE_HOME"] == str(sem_home / "cache")
    assert doc["env"]["TORCH_HOME"] == str(sem_home / "cache" / "torch")
    assert doc["env"]["HF_HOME"] == str(fake_runtime / "models")
    assert doc["network"] == {"guard_active": True, "offline_env": True}
    assert (sem_home / ".gitignore").read_text() == "*\n"
    # no bytecode written into the skill dir
    assert not list((SKILL / "sem").glob("__pycache__/*.cpython-*.pyc.*"))


def test_wrapper_follows_symlinks(tmp_path, fake_runtime):
    link = tmp_path / "skills" / "semantic-search"
    link.parent.mkdir()
    link.symlink_to(SKILL)
    proj = tmp_path / "p"
    proj.mkdir()
    p = subprocess.run([str(link / "bin" / "sem"), "list", "--json"], cwd=proj, capture_output=True, text=True,
                       env={"PATH": os.environ["PATH"], "HOME": str(tmp_path), "SEM_RUNTIME": str(fake_runtime)})
    assert json.loads(p.stdout)["indexes"] == []


def test_wrapper_without_runtime(tmp_path):
    p = subprocess.run([str(WRAPPER), "doctor"], cwd=tmp_path, capture_output=True, text=True,
                       env={"PATH": os.environ["PATH"], "HOME": str(tmp_path)})
    assert p.returncode == 3 and "setup.sh" in p.stderr


def test_project_sem_package_does_not_shadow(tmp_path, fake_runtime):
    proj = tmp_path / "p"
    (proj / "sem").mkdir(parents=True)
    (proj / "sem" / "__init__.py").write_text("raise SystemExit('shadowed!')")
    (proj / "sem" / "__main__.py").write_text("raise SystemExit('shadowed!')")
    p = run(proj, fake_runtime, "list", "--json")
    assert p.returncode == 0, p.stderr
    assert "shadowed" not in p.stderr


def test_wrapper_unwritable_cwd(tmp_path, fake_runtime):
    ro = tmp_path / "ro"
    ro.mkdir()
    os.chmod(ro, 0o555)
    try:
        if os.access(ro, os.W_OK):
            pytest.skip("running as root")
        p = run(ro, fake_runtime, "doctor")
        assert p.returncode == 3 and "cd into a project directory" in p.stderr
    finally:
        os.chmod(ro, 0o755)
