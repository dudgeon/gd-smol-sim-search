# Working on this repo

This repo builds the `semantic-search` Claude Code skill: a local, offline embeddings CLI (`sem`) plus the installer
(`setup.sh`). `README.md` is for users; this file is for whoever develops the repo.

## Layout

```
setup.sh                         installer (the only thing that uses the network)
tools/fetch_model.py             setup-time model download + SHA-256 verification (run by setup.sh)
tools/requirements.in            direct runtime deps (input to the lock)
tools/requirements-dev.txt       pytest (dev only; never in the runtime lock)
skills/semantic-search/
  SKILL.md                       skill entry point (keep under ~150 lines; details go in references/)
  references/{cli,interpreting-scores}.md
  bin/sem                        bash wrapper: env + exec runtime python -P -s -m sem
  models.json                    model registry with pinned revisions
  requirements.lock              hashed lock for macOS 14+ arm64 / CPython 3.12
  sem/                           the Python package
    cli.py      argparse commands, JSON/human output, network guard install
    env.py      paths (SEM_HOME=./.sem, SEM_RUNTIME), registry, SemError, network guard
    device.py   subprocess Metal probe (+ SEM_PROBE_SIMULATE), cache in .sem/device.json
    ingest.py   discovery (.gitignore, excludes, size cap) and readers
    chunk.py    token-budget packing with overlap; segments never cross sections/pages/records
    embed.py    HashEmbedder (tests) and STEmbedder (sentence-transformers), OOM backoff
    indexer.py  change detection (size/mtime -> sha256), model/chunking compatibility checks
    store.py    index format, tombstones, compaction, crash-safe generation swap
    analyze.py  search/similar/compare/dupes/cluster/outliers in NumPy
    progress.py stderr progress without tqdm
tests/                           pytest; fixtures/ is the golden dataset
```

## Rules that are easy to break

- **Runtime writes only under `$SEM_HOME` (`./.sem`).** Never write to the skill dir, the runtime dir or `~`.
  Anything new that caches (a library, a temp file) must be pointed into `./.sem` by `bin/sem`.
- **No network at runtime.** `cli.main()` installs a socket guard. Don't add code paths that fetch anything; model
  downloads belong in `tools/fetch_model.py`.
- **Import torch/transformers lazily.** Only commands that embed text may import them. `similar`, `dupes`,
  `cluster`, `outliers`, `info` and `list` must stay fast (NumPy + sqlite only).
- **Never probe Metal in-process.** Always use `device.run_probe()` (subprocess).
- **The model is part of the index identity.** `manifest.json` records key + revision. Keep
  `indexer.check_model_compat` on every path that reads an index with a model.
- **Bash 3.2.** `setup.sh` and `bin/sem` must run on macOS's stock bash 3.2: no `mapfile`, no associative arrays,
  no `${var,,}`. Guard empty arrays with `${arr[@]+"${arr[@]}"}`.
- Dependencies are `torch`, `sentence-transformers`, `transformers`, `numpy`, `pypdf` and `huggingface_hub`
  (setup-time). Adding anything else needs a reason recorded here. Transitive deps pulled in by
  sentence-transformers (scikit-learn, scipy, …) are accepted as-is.

## Running tests

```bash
# any Python 3.12 venv with the runtime deps + pytest works; e.g.
uv venv .venv-dev --python 3.12 && uv pip install --python .venv-dev/bin/python -r tools/requirements.in -r tools/requirements-dev.txt
.venv-dev/bin/python -m pytest tests -q
```

- `test_cli.py` and `test_units.py` use the built-in `hash-test` model (hashed bag-of-words; hidden in the
  registry). They need no torch and no download.
- `test_models.py` builds a tiny random BERT locally to exercise the real sentence-transformers path, including the
  simulated Metal crash/fail fallback. Its bge-small golden tests run when a real runtime is installed (default
  locations, or `SEM_TEST_RUNTIME=<runtime dir>`).
- `test_device.py` covers the probe: `SEM_PROBE_SIMULATE=fail|crash|hang`.
- To check sandbox behaviour for real, run the acceptance checks from a Claude Code session with `/sandbox` on.
  Use a before/after listing of `~/.claude/skills/semantic-search`, `~/.cache` and `~/Library/Caches`.

## Updating pins

1. **uv**: bump `UV_VERSION` in `setup.sh` and paste the new `.sha256` files from the GitHub release
   (`uv-aarch64-apple-darwin.tar.gz.sha256`; the Linux one is for dev only).
2. **Python**: bump `PYTHON_VERSION` to a build that uv lists (`uv python list 3.12 --all-versions`).
3. **Packages**: edit `tools/requirements.in`, then regenerate the lock for the target platform:
   ```bash
   MACOSX_DEPLOYMENT_TARGET=14.0 uv pip compile tools/requirements.in \
     --python-platform aarch64-apple-darwin --python-version 3.12 --generate-hashes --no-header \
     -o skills/semantic-search/requirements.lock
   ```
   Re-add the two header comment lines. If a torch release raises its macOS floor, update `MIN_MACOS_MAJOR` and
   the README.
4. **Models**: set `revision` in `models.json` to a full commit hash from the model's Hugging Face history, and
   re-check the license. A new revision makes existing indexes refuse to load until they're rebuilt; that's
   intended.

## Linux dev hooks (not for users)

`setup.sh` is macOS-only, but it can be exercised on Linux x86-64 for development:

| Env var | Effect |
|---|---|
| `SEM_SETUP_ALLOW_LINUX=1` | Skip the macOS check and use the Linux uv tarball (pinned hash). |
| `SEM_SETUP_LOCKFILE=path` | Use a different lock (e.g. one compiled with `--python-platform x86_64-unknown-linux-gnu`). |
| `SEM_SETUP_UV_CACHE_DIR=dir` | Reuse a uv cache instead of the one inside the runtime dir. |
| `SEM_SETUP_MODELS_FROM=dir` | Copy `<dir>/<key>/` instead of downloading. Its `.sem-revision` must equal the pin. Also useful for air-gapped installs. |
| `CLAUDE_SKILLS_DIR=dir` | Install the skill somewhere other than `~/.claude/skills`. |
| `--no-self-test` | Skip step 10. |

Runtime-side test hooks: `SEM_REGISTRY` (alternate models.json), `SEM_MODELS_DIR` (alternate models dir),
`SEM_PROBE_SIMULATE`, `SEM_ALLOW_NETWORK=1` (disables the socket guard; only for testing the guard).

## Build notes

- The first version was built in a Linux container with no macOS and no access to huggingface.co. Everything below
  the device probe was exercised there, including a full `setup.sh` install/update/link/uninstall cycle with a
  Linux lock and a locally mirrored copy of bge-small. The mirror was a test-only stand-in; installs download
  from Hugging Face and verify hashes. The sandbox was simulated with a mount + network namespace (read-only home,
  writable project, no network). What remains to verify on a real Mac: Metal under Seatbelt, the macOS lock
  installing cleanly, and qwen3-0.6b.
