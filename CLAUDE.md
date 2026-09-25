# Working on this repo

This repo builds the `smol-sim-search` Claude Code skill: a local, offline embeddings CLI (`sem`) plus the installer
(`setup.sh`). `README.md` is for users; this file is for whoever develops the repo.

## Layout

```
setup.sh                         installer: fully offline, installs from vendor/
vendor/                          COMMITTED runtime for macOS arm64 (built by tools/build_vendor.py; don't hand-edit)
  python/                        python-build-standalone CPython tarball
  wheels/                        onnxruntime, numpy, tokenizers, pypdf
  models/bge-small/              official fp32 ONNX (split in <50 MB parts), tokenizer.json, model card, model.json
  SHA256SUMS, PROVENANCE.json    per-file hashes (checked by setup.sh) / upstream URLs + hashes
tools/vendor.json                pins for the vendored files (exact file names, model revision)
tools/build_vendor.py            downloads + verifies against upstream checksums, writes vendor/ (stdlib only)
tools/requirements-dev.txt       pytest + the runtime packages, for running tests on any platform
skills/smol-sim-search/
  SKILL.md                       skill entry point (keep under ~150 lines; details go in references/)
  references/{cli,interpreting-scores}.md
  bin/sem                        bash wrapper: env + exec runtime/python/bin/python3 -P -s -m sem
  models.json                    model registry (bge-small + hidden hash-test)
  sem/                           the Python package
    cli.py      argparse commands, JSON/human output, network guard install
    env.py      paths (SEM_HOME=./.sem, SEM_RUNTIME), registry, SemError, network guard
    ingest.py   discovery (.gitignore, excludes, size cap) and readers
    chunk.py    token-budget packing with overlap; segments never cross sections/pages/records
    embed.py    OnnxEmbedder (onnxruntime + tokenizers, CLS pooling) and HashEmbedder (tests)
    indexer.py  change detection (size/mtime -> sha256), model/chunking compatibility checks
    store.py    index format, tombstones, compaction, crash-safe generation swap
    analyze.py  search/similar/compare/dupes/cluster/neighbors/outliers in NumPy
                (neighbors + outliers share _blocked_topk: exact streaming top-k, bounded memory)
    progress.py stderr progress without tqdm
tests/                           pytest; fixtures/ is the golden dataset
```

## Rules that are easy to break

- **The install never touches the network.** Everything `setup.sh` installs comes from `vendor/`. It has to be
  verified against `vendor/SHA256SUMS` first, and the model against its upstream hash. Don't add downloads to
  `setup.sh`; change `tools/vendor.json` and rebuild `vendor/` instead.
- **Keep every vendored file under 50 MB** (GitHub warns at 50 MB and rejects at 100 MB). No Git LFS: a plain clone
  must work. `build_vendor.py` splits large files (`split_mb`), and `setup.sh` joins them.
- **Runtime writes only under `$SEM_HOME` (`./.sem`).** Never write to the skill dir, the runtime dir or `~`.
- **Updates flow only through the clone.** There is no self-updater and never should be: the skill cannot use
  the network, so `git pull` + `./setup.sh` is the whole update story. `setup.sh` records `source_repo` and
  `source_commit` in `install.json` so `sem doctor` can point users at the right clone.
- **No network at runtime.** `cli.main()` installs a socket guard — but that only covers Python. onnxruntime's
  macOS wheel embeds Microsoft 1DS telemetry in native code (it POSTed to mobile.events.data.microsoft.com and
  wrote `~/Library/Caches/python3/` during indexing, observed on macOS 26 / ORT 1.30). `ORT_DISABLE_TELEMETRY=1`
  must be set **before** `import onnxruntime` (embed.py does; bin/sem too); the
  `disable_telemetry_events()` API after import is too late. When bumping the onnxruntime wheel, re-run the
  `~/Library/Caches` before/after check on a Mac.
- **Keep numpy-only commands light.** Only commands that embed text (`index`, `search`, `compare --text`,
  `embed`) may import onnxruntime/tokenizers.
- **The model is part of the index identity.** `manifest.json` records key + revision. Keep
  `indexer.check_model_compat` on every path that reads an index with a model.
- **Bash 3.2.** `setup.sh` and `bin/sem` must run on macOS's stock bash 3.2: no `mapfile`, no associative arrays,
  no `${var,,}`. Guard empty arrays with `${arr[@]+"${arr[@]}"}`.
- **Runtime dependencies are exactly the four vendored wheels**, installed with `--no-deps`. Adding one means
  adding its wheel (and any of its runtime deps) to `tools/vendor.json`, with a reason recorded here.
  onnxruntime declares `flatbuffers` and `protobuf` as dependencies, but CPU inference doesn't import them;
  the test suite runs without them on purpose.

## Why ONNX Runtime and not PyTorch

The first version used sentence-transformers on PyTorch, with setup downloading uv, Python, packages and weights.
That was replaced so the install needs no network, which corporate proxies, firewalls and sandboxes can't break.
PyTorch's macOS wheel is 127 MB, more than GitHub allows in one file, and it brings about 40 transitive packages.
ONNX Runtime plus `tokenizers` runs the official ONNX export of the same model on CPU and gives identical vectors
(cosine ≥ 0.9999999 against sentence-transformers). It also removes Metal, and with it the question of whether
Seatbelt allows GPU access. The fp32 model is vendored rather than an int8 quantization, because quantizing
changed rankings in testing (6–8 of 8 golden top-1s agreed, depending on the variant). The fp32 file also stays
checkable against Hugging Face's own hash.

## Running tests

```bash
uv venv .venv-dev --python 3.12 && uv pip install --python .venv-dev/bin/python -r tools/requirements-dev.txt
.venv-dev/bin/python -m pytest tests -q
```

- `test_models.py` runs the real vendored bge-small. It assembles the model from `vendor/models` exactly as
  `setup.sh` does and checks its hash. It covers golden top-1 queries, the planted duplicate pair, known scores
  and token budgets.
- `test_cli.py` and `test_units.py` use the hidden `hash-test` model (hashed bag-of-words): fast, no model files.
- To check sandbox behaviour for real, run the acceptance checks from a Claude Code session with `/sandbox` on.
  Use a before/after listing of `~/.claude/skills/smol-sim-search`, `~/.cache` and `~/Library/Caches`.

## Updating vendored files

1. Edit `tools/vendor.json`: exact wheel file names (as on PyPI), the Python release and file name, and the model
   revision (a full commit hash; re-check the license).
2. `python3 tools/build_vendor.py`. It downloads everything, checks each file against the checksum its upstream
   publishes, and rewrites `vendor/` including `SHA256SUMS` and `PROVENANCE.json`.
3. Run the tests. Commit `vendor/` together with the `vendor.json` change.
4. A new model revision makes existing indexes refuse to load until they're rebuilt; that's intended.
   If a wheel raises its macOS floor, update `MIN_MACOS_MAJOR` in `setup.sh` and the README.

## Linux dev hooks (not for users)

`setup.sh` is macOS-only, but it can be exercised on Linux x86-64:

```bash
python3 tools/build_vendor.py --platform linux-x86_64 --out /tmp/vendor-linux
SEM_SETUP_ALLOW_LINUX=1 SEM_SETUP_VENDOR_DIR=/tmp/vendor-linux ./setup.sh
```

Also: `CLAUDE_SKILLS_DIR=dir` installs the skill elsewhere, and `--no-self-test` skips the self-test. Runtime-side
test hooks: `SEM_REGISTRY` (alternate models.json), `SEM_MODELS_DIR` (alternate models dir), and
`SEM_ALLOW_NETWORK=1` (disables the socket guard; only for testing the guard).

## Build notes

- Built and tested in a Linux container (offline install/re-run/link/uninstall cycle in a no-network namespace;
  sandbox simulated with mount + network namespaces), then verified on a real Apple Silicon Mac (macOS 26):
  fresh offline install with passing self-test, all 53 tests, golden queries, and the write-isolation check
  (before/after listings of `~/.claude/skills/smol-sim-search`, `~/.cache`, `~/Library/Caches`). That check is
  what caught the onnxruntime telemetry above — keep running it after dependency bumps.
