"""Download one pinned model for setup.sh and verify it. Needs network; never run by sem.

    python tools/fetch_model.py <models.json> <key> <models_dir>

Downloads <repo_id>@<revision> (inference files only) into <models_dir>/<key>,
verifies each LFS file against the SHA-256 Hugging Face publishes for that
revision, then writes <models_dir>/<key>/.sem-revision. The download goes to a
.partial directory first, so an interrupted run never leaves a half model.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    registry, key, models_dir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    spec = json.loads(Path(registry).read_text())["models"][key]
    repo, rev = spec["repo_id"], spec["revision"]
    dest = models_dir / key
    marker = dest / ".sem-revision"
    if marker.exists() and marker.read_text().strip() == rev:
        print(f"  {key}: already installed at {rev[:10]}")
        return 0

    from huggingface_hub import HfApi, snapshot_download

    part = models_dir / f".{key}.partial"
    if part.exists():
        shutil.rmtree(part)
    print(f"  {key}: downloading {repo}@{rev[:10]} ({spec['license']})")
    snapshot_download(repo_id=repo, revision=rev, local_dir=str(part),
                      ignore_patterns=spec.get("ignore_patterns") or None)
    shutil.rmtree(part / ".cache", ignore_errors=True)

    info = HfApi().model_info(repo, revision=rev, files_metadata=True)
    if info.sha != rev:
        print(f"  {key}: revision mismatch: asked {rev}, got {info.sha}", file=sys.stderr)
        return 1
    checked = 0
    for s in info.siblings or []:
        lfs = getattr(s, "lfs", None)
        f = part / s.rfilename
        if not f.exists():
            continue
        want = getattr(lfs, "sha256", None) or (lfs.get("sha256") if isinstance(lfs, dict) else None)
        if want:
            got = sha256(f)
            if got != want:
                print(f"  {key}: checksum mismatch for {s.rfilename}: {got} != {want}", file=sys.stderr)
                return 1
            checked += 1
    if checked == 0:
        print(f"  {key}: no LFS checksums published; relying on the pinned revision", file=sys.stderr)
    (part / ".sem-revision").write_text(rev + "\n")
    if dest.exists():
        shutil.rmtree(dest)
    os.replace(part, dest)
    print(f"  {key}: ok ({checked} file checksum(s) verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
