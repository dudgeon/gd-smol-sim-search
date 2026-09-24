"""Device selection: Metal (mps) when it demonstrably works, CPU otherwise.

The Metal probe always runs in a *subprocess*: a Seatbelt profile that blocks
IOKit/GPU access can make Metal initialisation hang or abort the process, and
we never want that to take down the caller. Any failure, timeout or signal in
the probe means CPU.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

from .env import SemError

PROBE_TIMEOUT = float(os.environ.get("SEM_PROBE_TIMEOUT", "20"))

# Runs in a fresh interpreter. Prints one JSON line on success.
_PROBE = r"""
import json, os, sys
sim = os.environ.get("SEM_PROBE_SIMULATE", "")
if sim == "crash":
    os.abort()
if sim == "hang":
    import time; time.sleep(3600)
if sim == "fail":
    print(json.dumps({"ok": False, "reason": "simulated probe failure"})); sys.exit(0)
import torch
if not torch.backends.mps.is_available():
    built = torch.backends.mps.is_built()
    print(json.dumps({"ok": False, "reason": "torch.backends.mps.is_available() is False"
                      + ("" if built else " (torch built without MPS)")}))
    sys.exit(0)
torch.manual_seed(0)
a = torch.randn(64, 64)
b = torch.randn(64, 64)
ref = a @ b
got = (a.to("mps") @ b.to("mps")).to("cpu")
torch.mps.synchronize()
err = float((ref - got).abs().max())
ok = err < 1e-2
print(json.dumps({"ok": ok, "reason": "matmul matches cpu" if ok else f"mps matmul mismatch (max err {err:.3g})"}))
"""


def _os_version() -> str:
    mac = platform.mac_ver()[0]
    return f"macos-{mac}" if mac else f"{platform.system().lower()}-{platform.release()}"


def _torch_version() -> str | None:
    try:
        return metadata.version("torch")
    except metadata.PackageNotFoundError:
        return None


def run_probe() -> dict:
    env = dict(os.environ)
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _PROBE],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT, env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": f"probe timed out after {PROBE_TIMEOUT:.0f}s"}
    except OSError as e:
        return {"ok": False, "reason": f"probe could not start: {e}"}
    elapsed = round(time.time() - t0, 2)
    if proc.returncode < 0:
        return {"ok": False, "reason": f"probe killed by signal {-proc.returncode}", "seconds": elapsed}
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or ["no output"]
        return {"ok": False, "reason": f"probe exited {proc.returncode}: {tail[0][:200]}", "seconds": elapsed}
    try:
        line = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")][-1]
        res = json.loads(line)
    except (IndexError, ValueError):
        return {"ok": False, "reason": "probe produced no result", "seconds": elapsed}
    res["seconds"] = elapsed
    return res


def probe_mps(cache_file: Path, reprobe: bool = False) -> dict:
    """Return the (possibly cached) probe result."""
    key = {"torch": _torch_version(), "os": _os_version(),
           "simulate": os.environ.get("SEM_PROBE_SIMULATE", "")}
    if not reprobe and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if cached.get("key") == key:
                cached["result"]["cached"] = True
                return cached["result"]
        except (OSError, ValueError, KeyError):
            pass
    if key["torch"] is None:
        res = {"ok": False, "reason": "torch is not installed"}
    elif platform.system() != "Darwin" and not key["simulate"]:
        res = {"ok": False, "reason": "Metal is only available on macOS"}
    else:
        res = run_probe()
    try:
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"key": key, "result": res, "probed_at": time.time()}))
        os.replace(tmp, cache_file)
    except OSError:
        pass
    res = dict(res)
    res["cached"] = False
    return res


def select_device(requested: str | None, cache_file: Path, reprobe: bool = False) -> tuple[str, dict]:
    """Resolve 'auto' | 'cpu' | 'mps' to a concrete device. Returns (device, info)."""
    req = (requested or os.environ.get("SEM_DEVICE") or "auto").lower()
    if req not in ("auto", "cpu", "mps"):
        raise SemError(f"invalid device '{req}'; use auto, cpu or mps")
    if req == "cpu":
        return "cpu", {"requested": "cpu", "reason": "cpu requested"}
    probe = probe_mps(cache_file, reprobe=reprobe)
    if probe.get("ok"):
        return "mps", {"requested": req, "reason": "Metal probe passed", "probe": probe}
    info = {"requested": req, "reason": f"Metal unavailable ({probe.get('reason')}); using CPU",
            "probe": probe, "fallback": req == "mps" or platform.system() == "Darwin"}
    return "cpu", info
