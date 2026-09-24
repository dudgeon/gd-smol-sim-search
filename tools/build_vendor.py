"""Build vendor/: everything setup.sh installs, so installs never touch the network.

    python3 tools/build_vendor.py                          # macOS arm64 -> vendor/ (committed)
    python3 tools/build_vendor.py --platform linux-x86_64 --out /tmp/vendor-linux   # dev only

Stdlib only. Downloads each pinned file from tools/vendor.json and checks it against the
checksum its upstream publishes: python-build-standalone's SHA256SUMS, PyPI's sha256
digests, and Hugging Face's LFS sha256 (or git blob id for small files). It then writes
vendor/SHA256SUMS, which setup.sh verifies before installing anything.
Large files are split into pieces under GitHub's 50 MB warning size; setup.sh joins them
and checks the joined file against the upstream hash.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "tools" / "vendor.json"


def fetch(url: str, attempts: int = 4) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "smol-sim-search-build-vendor"})
    for n in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except (OSError, http.client.HTTPException) as e:
            if n == attempts - 1:
                raise
            print(f"  retrying {url.rsplit('/', 1)[-1]} ({type(e).__name__})")
            time.sleep(2 ** (n + 1))
    raise AssertionError("unreachable")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_blob_sha1(b: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def check(name: str, got: str, want: str) -> None:
    if got != want:
        sys.exit(f"checksum mismatch for {name}: got {got}, upstream says {want}")
    print(f"  ok  {name}  {got[:16]}…")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", default="macos-arm64", choices=["macos-arm64", "linux-x86_64"])
    ap.add_argument("--out", default=str(REPO / "vendor"))
    a = ap.parse_args()
    cfg = json.loads(CONFIG.read_text())
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "python").mkdir(parents=True)
    (out / "wheels").mkdir()
    provenance: dict = {"platform": a.platform, "python": {}, "wheels": {}, "model": {}}

    # --- Python ---
    py = cfg["python"]
    fname = py["files"][a.platform]
    print(f"python {py['version']} ({py['release']})")
    sums = fetch(py["base_url"] + "SHA256SUMS").decode()
    want = next(line.split()[0] for line in sums.splitlines() if line.endswith(fname))
    data = fetch(py["base_url"] + fname.replace("+", "%2B"))
    check(fname, sha256(data), want)
    (out / "python" / fname).write_bytes(data)
    provenance["python"] = {"file": fname, "url": py["base_url"] + fname, "sha256": want}

    # --- wheels ---
    print("wheels")
    for whl in cfg["wheels"][a.platform]:
        name, version = whl.split("-")[:2]
        meta = json.loads(fetch(f"https://pypi.org/pypi/{name}/{version}/json"))
        entry = next((f for f in meta["urls"] if f["filename"] == whl), None)
        if entry is None:
            sys.exit(f"{whl} not found on PyPI")
        data = fetch(entry["url"])
        check(whl, sha256(data), entry["digests"]["sha256"])
        (out / "wheels" / whl).write_bytes(data)
        provenance["wheels"][whl] = {"url": entry["url"], "sha256": entry["digests"]["sha256"]}

    # --- model ---
    m = cfg["model"]
    print(f"model {m['repo_id']}@{m['revision'][:10]}")
    info = json.loads(fetch(f"https://huggingface.co/api/models/{m['repo_id']}/revision/{m['revision']}?blobs=true"))
    if info["sha"] != m["revision"]:
        sys.exit(f"revision mismatch: {info['sha']}")
    siblings = {s["rfilename"]: s for s in info["siblings"]}
    mdir = out / "models" / m["key"]
    mdir.mkdir(parents=True)
    model_files = {}
    for src, dst in m["files"].items():
        s = siblings[src]
        data = fetch(f"https://huggingface.co/{m['repo_id']}/resolve/{m['revision']}/{src}")
        if s.get("lfs"):
            want = s["lfs"]["sha256"]
            check(src, sha256(data), want)
        else:
            check(src + " (git blob)", git_blob_sha1(data), s["blobId"])
            want = sha256(data)
        model_files[dst] = want
        limit = m["split_mb"] * 1024 * 1024
        if len(data) > limit:
            for i in range(0, len(data), limit):
                (mdir / f"{dst}.part{i // limit:02d}").write_bytes(data[i: i + limit])
        else:
            (mdir / dst).write_bytes(data)
    (mdir / "model.json").write_text(json.dumps({
        "key": m["key"], "repo_id": m["repo_id"], "revision": m["revision"], "license": m["license"],
        "files_sha256": model_files}, indent=2) + "\n")
    provenance["model"] = {"repo_id": m["repo_id"], "revision": m["revision"], "files_sha256": model_files}

    (out / "PROVENANCE.json").write_text(json.dumps(provenance, indent=2) + "\n")
    # SHA256SUMS over every vendored file (paths relative to vendor/)
    lines = []
    for f in sorted(p for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        lines.append(f"{sha256(f.read_bytes())}  {f.relative_to(out).as_posix()}")
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    biggest = max((p.stat().st_size, p.name) for p in out.rglob("*") if p.is_file())
    print(f"wrote {out} ({total / 1e6:.1f} MB; largest file {biggest[1]} {biggest[0] / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
