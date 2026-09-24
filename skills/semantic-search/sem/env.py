"""Path and environment resolution, plus the runtime's sandbox guarantees.

Everything sem writes lives under ``$SEM_HOME`` (``./.sem`` in the current
working directory). The runtime directory (Python, venv, model weights) is
only ever read.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
MODELS_JSON = SKILL_DIR / "models.json"


class SemError(Exception):
    """An expected, user-facing error. Printed without a traceback."""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


@dataclass
class Paths:
    sem_home: Path
    runtime: Path | None

    @property
    def indexes(self) -> Path:
        return self.sem_home / "indexes"

    @property
    def tmp(self) -> Path:
        return self.sem_home / "tmp"

    @property
    def cache(self) -> Path:
        return self.sem_home / "cache"

    @property
    def models_dir(self) -> Path | None:
        override = os.environ.get("SEM_MODELS_DIR")
        if override:
            return Path(override)
        return self.runtime / "models" if self.runtime else None


def ensure_sem_home(sem_home: Path) -> None:
    """Create ./.sem (with a catch-all .gitignore) and its subdirectories."""
    fresh = not sem_home.exists()
    try:
        sem_home.mkdir(parents=True, exist_ok=True)
        for sub in ("tmp", "cache", "indexes"):
            (sem_home / sub).mkdir(exist_ok=True)
        gi = sem_home / ".gitignore"
        if fresh or not gi.exists():
            gi.write_text("*\n")
    except OSError as e:
        raise SemError(
            f"cannot create {sem_home}: {e.strerror or e}.\n"
            "sem stores indexes in the project directory (./.sem). "
            "cd into a project directory you can write to and retry."
        ) from e


def get_paths() -> Paths:
    sem_home = Path(os.environ.get("SEM_HOME") or (Path.cwd() / ".sem"))
    rt = os.environ.get("SEM_RUNTIME")
    paths = Paths(sem_home=sem_home, runtime=Path(rt) if rt else None)
    ensure_sem_home(sem_home)
    return paths


def load_install_info(paths: Paths) -> dict:
    if not paths.runtime:
        return {}
    p = paths.runtime / "install.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def load_registry() -> dict:
    # SEM_REGISTRY lets tests point at an alternate registry (e.g. a tiny local model)
    return json.loads(Path(os.environ.get("SEM_REGISTRY") or MODELS_JSON).read_text())


def model_spec(key: str) -> dict:
    reg = load_registry()
    if key not in reg["models"]:
        visible = [k for k, v in reg["models"].items() if not v.get("hidden")]
        raise SemError(f"unknown model '{key}'. Known models: {', '.join(visible)}")
    spec = dict(reg["models"][key])
    spec["key"] = key
    return spec


def default_model_key() -> str:
    return os.environ.get("SEM_MODEL") or load_registry()["default"]


# --- network guard -----------------------------------------------------------

class NetworkBlocked(OSError):
    pass


def install_network_guard() -> None:
    """Refuse any non-local socket connection for the life of the process.

    The sandbox already blocks the network; this makes the "no network at
    runtime" promise explicit and independent of sandbox configuration.
    Unix-domain sockets (used by nothing in sem, but harmless) are allowed.
    """
    if os.environ.get("SEM_ALLOW_NETWORK") == "1":  # tests of the guard itself
        return

    def _deny(*_a, **_k):
        raise NetworkBlocked("sem runs offline: network access is disabled at runtime")

    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex

    def connect(self, address):
        if self.family == getattr(socket, "AF_UNIX", None):
            return orig_connect(self, address)
        _deny()

    def connect_ex(self, address):
        if self.family == getattr(socket, "AF_UNIX", None):
            return orig_connect_ex(self, address)
        _deny()

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.create_connection = _deny  # type: ignore[assignment]
    socket.getaddrinfo = _deny  # type: ignore[assignment]


def network_guard_active() -> bool:
    try:
        socket.getaddrinfo("localhost", 80)
    except NetworkBlocked:
        return True
    except OSError:
        return False
    return False


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
