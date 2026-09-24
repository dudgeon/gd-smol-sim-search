"""Device selection: CPU fallback on every kind of Metal probe failure."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("torch")

from sem import device  # noqa: E402


@pytest.mark.parametrize("mode,reason", [
    ("fail", "simulated probe failure"),
    ("crash", "signal"),       # os.abort() -> SIGABRT, as MLX/Metal can do under Seatbelt
    ("hang", "timed out"),
])
def test_probe_failures_fall_back_to_cpu(tmp_path, monkeypatch, mode, reason):
    monkeypatch.setenv("SEM_PROBE_SIMULATE", mode)
    monkeypatch.setattr(device, "PROBE_TIMEOUT", 3.0)
    dev, info = device.select_device("auto", tmp_path / "device.json")
    assert dev == "cpu"
    assert reason in info["reason"]


def test_explicit_cpu_skips_probe(tmp_path, monkeypatch):
    monkeypatch.setenv("SEM_PROBE_SIMULATE", "hang")
    dev, info = device.select_device("cpu", tmp_path / "device.json")
    assert dev == "cpu" and not (tmp_path / "device.json").exists()


def test_env_var_selects_cpu(tmp_path, monkeypatch):
    monkeypatch.setenv("SEM_DEVICE", "cpu")
    assert device.select_device(None, tmp_path / "d.json")[0] == "cpu"


def test_probe_result_is_cached_and_keyed(tmp_path, monkeypatch):
    monkeypatch.setenv("SEM_PROBE_SIMULATE", "fail")
    cache = tmp_path / "device.json"
    r1 = device.probe_mps(cache)
    assert r1["cached"] is False
    r2 = device.probe_mps(cache)
    assert r2["cached"] is True
    data = json.loads(cache.read_text())
    assert set(data["key"]) == {"torch", "os", "simulate"}
    # a different torch version invalidates the cache
    data["key"]["torch"] = "0.0.0"
    cache.write_text(json.dumps(data))
    assert device.probe_mps(cache)["cached"] is False
    assert device.probe_mps(cache, reprobe=True)["cached"] is False


def test_invalid_device(tmp_path):
    from sem.env import SemError
    with pytest.raises(SemError):
        device.select_device("gpu", tmp_path / "d.json")
