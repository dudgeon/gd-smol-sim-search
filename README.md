<div align="center">
  <img src="assets/logo.svg" width="250" alt="Clawd the crab in a sandbox, holding a magnifying glass">
  <h1>smol-sim-search</h1>
  <p><strong>A tiny search engine that never leaves the sandbox.</strong><br>
  Local embeddings for Claude Code — simple, lightweight, zero external dependencies.</p>
  <p><sub>stays in the sandbox &nbsp;·&nbsp; nothing to download &nbsp;·&nbsp; pail included</sub></p>
</div>

A [Claude Code skill](https://code.claude.com/docs/en/skills) that lets Claude embed a local dataset and work with
meaning instead of exact text: semantic search, nearest neighbours, pairwise comparison, near-duplicates, clusters
and outliers. Claude does the summarising; the `sem` CLI finds the relevant pieces. Everything runs **in-process
and offline** on your Mac. There are no servers, API keys, or network access, **including during install**.

```bash
git clone https://github.com/dudgeon/gd-smol-sim-search
cd gd-smol-sim-search
./setup.sh
```

That's the whole install. Start a new Claude Code session in any project and ask; Claude picks up the skill on
its own. It covers two kinds of question:

**Search** — find things by meaning, not exact text:

- "find the notes where we discussed retry policies"
- "where in this repo do we talk about rate limiting?"
- "which tickets mention being charged twice, however they phrased it?"

**Similarity analysis** — characterise a dataset without a query:

- "group the records in `data/feedback.csv` by theme and name the themes"
- "which of these support tickets are duplicates of each other?"
- "what are the outliers in this folder of meeting notes — anything unusual?"
- "how similar are these two specs, and which sections overlap?"
- "what else in the repo is most related to this file?"

Works over Markdown, plain text, source code, CSV/TSV, JSON/JSONL (one record per item) and PDF. The worked
workflows behind the analysis questions are in
[`skills/smol-sim-search/references/recipes.md`](skills/smol-sim-search/references/recipes.md).

## Requirements

- macOS **14 (Sonoma) or later** on **Apple Silicon**. The vendored onnxruntime and numpy wheels need macOS 14.
- `bash`, `tar` and `shasum`, which every Mac has. No Homebrew, system Python, Xcode, Docker or Ollama.
- About 190 MB for the clone and about 400 MB for the installed runtime.

## Nothing is downloaded at install time

Corporate proxies, firewalls and sandboxes can't break the install, because it downloads nothing. Everything
`sem` runs on is committed in [`vendor/`](vendor/):

| File(s) | What | Source (checked against its upstream checksum when vendored) |
|---|---|---|
| `vendor/python/cpython-3.12.14+20260901-aarch64-apple-darwin-install_only_stripped.tar.gz` | Standalone CPython 3.12.14 (25 MB) | [python-build-standalone](https://github.com/astral-sh/python-build-standalone) release `SHA256SUMS` |
| `vendor/wheels/*.whl` | onnxruntime 1.30.0, numpy 2.5.3, tokenizers 0.23.2, pypdf 6.19.0 (30 MB) | PyPI sha256 digests |
| `vendor/models/bge-small/model.onnx.part00..02` | [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) @ `5c38ec7c`, official fp32 ONNX export (133 MB, split into pieces under GitHub's 50 MB limit) | Hugging Face LFS sha256 `828e1496…` |
| `vendor/models/bge-small/tokenizer.json`, `MODEL_CARD.md` | Tokenizer and model card (MIT license) | Hugging Face git blob ids |

`vendor/PROVENANCE.json` records every source URL and upstream hash. `vendor/SHA256SUMS` covers every vendored
file. The repo contains no Git LFS files, so a plain `git clone` gets everything.

`setup.sh` then:

1. Checks for macOS arm64 14+ and verifies **every vendored file against `vendor/SHA256SUMS`**.
2. Unpacks Python into the runtime directory.
3. Installs the four wheels with `pip --no-index --no-deps` (no package index, no dependency resolution).
4. Joins the model pieces and checks the result against **Hugging Face's published SHA-256**.
5. Precompiles bytecode, because the runtime and skill directories are read-only at runtime.
6. Copies the skill to `~/.claude/skills/smol-sim-search/`, replacing any existing copy in one swap.
7. Runs a self-test: indexes the test fixtures, runs a search, and checks the results.

Re-running it only verifies what's installed. It doesn't modify `~/.claude/settings.json` or any sandbox settings.

| Flag | Effect |
|---|---|
| `--update` | Force-refresh the runtime and skill files from `vendor/` even when they look up to date. |
| `--link` | Dev mode: symlink the skill to this repo. The runtime goes to `~/.local/share/smol-sim-search/runtime`. |
| `--runtime-dir DIR` | Put the runtime (Python, packages, model) somewhere else. |
| `--uninstall [--yes]` | Remove the skill and runtime after confirmation. Project `./.sem/` folders are left alone. |

## Updating

The clone is the distribution, so updating is a `git pull` — never a download by the tool itself:

```bash
cd gd-smol-sim-search
git pull
./setup.sh        # refreshes only what changed; --update forces a full refresh
```

- **There is deliberately no self-updater.** `sem` refuses all network access at runtime, so an installed copy
  cannot fetch anything — updates always flow through the clone, in your own terminal.
- `setup.sh` is idempotent: after a pull it re-verifies `vendor/` and refreshes exactly what changed (the
  runtime when the vendored files changed, the skill files when they differ). A no-op re-run takes seconds.
- `sem doctor` shows which clone and commit an install came from, and prints the update command.
- Deleted the clone? Re-clone and run `./setup.sh` — your projects' `./.sem/` indexes are untouched either way.
- If an update pins a **new model revision**, existing indexes refuse to load until you `sem index --rebuild`.
  That's intentional: vectors from different model revisions must never mix.

## How it stays inside the sandbox

| Sandbox rule | How `sem` complies |
|---|---|
| Writes only under the current directory | Indexes, caches and temp files live in `./.sem/`, and the wrapper points `TMPDIR` and `XDG_CACHE_HOME` into it. The skill and runtime directories are only read (bytecode is precompiled and `PYTHONDONTWRITEBYTECODE=1`). `./.sem/` gets its own `.gitignore` (`*`). |
| No network | The model loads from a local file, and the Python process refuses every non-local socket connection (`sem doctor` reports it). onnxruntime's macOS build ships Microsoft telemetry that phones home from native code; `sem` disables it before the library loads (`ORT_DISABLE_TELEMETRY=1`), verified by a before/after listing of `~/Library/Caches`. |
| No GPU / IOKit access needed | Embedding runs on the CPU with ONNX Runtime. There's no Metal, so nothing depends on what the sandbox allows for the GPU. bge-small is small enough that the CPU is fast. |
| No escapes | No `dangerouslyDisableSandbox`, no excluded commands, no settings edits. |

If the current directory isn't writable, `sem` says so and asks you to `cd` into a project, rather than writing
elsewhere.

## Using it directly

Claude runs it for you, but `sem` also works on its own:

```bash
SEM=~/.claude/skills/smol-sim-search/bin/sem
$SEM doctor
$SEM index docs/ src/                        # incremental: only changed files are re-embedded
$SEM search "how do we retry failed uploads" -k 5
$SEM similar src/upload/retry.py --group-by-file
$SEM compare docs/a.md docs/b.md             # plus the best-matching chunk pairs
$SEM dupes --across-files-only
$SEM cluster --level file --k auto
$SEM outliers --level file
$SEM index tickets.jsonl --index tickets --text-field body.text --id-field id
```

For record data, pick the columns and id at index time — each row becomes one item, addressable in every result:

```bash
$SEM index data/feedback.csv --text-cols title,comment --id-col id
$SEM cluster --level chunk --k auto      # cluster the records
$SEM similar data/feedback.csv:2971      # neighbours of the record on line 2971
```

Every command takes `--json` (one JSON document on stdout, logs on stderr) and `--index NAME` (separate corpora,
separate indexes). The full option reference is in
[`skills/smol-sim-search/references/cli.md`](skills/smol-sim-search/references/cli.md); end-to-end analysis
workflows are in [`references/recipes.md`](skills/smol-sim-search/references/recipes.md); reading cosine scores is
covered in [`references/interpreting-scores.md`](skills/smol-sim-search/references/interpreting-scores.md).

Binary files, `.git`, `node_modules`, virtualenvs and files over 50 MB are skipped, and `.gitignore` rules apply.

## Model

**bge-small-en-v1.5** (384 dimensions, MIT), English. It is fast on CPU and well suited to short entries: records,
notes, tickets, paragraphs. Long documents are split into chunks of up to 300 tokens (the model's limit is 512).
The model and its revision are part of every index's identity; `sem` refuses to mix indexes built with different
models. See [`references/interpreting-scores.md`](skills/smol-sim-search/references/interpreting-scores.md) for
reading scores.

This ONNX Runtime setup produces the same vectors as the sentence-transformers/PyTorch reference implementation
(cosine ≥ 0.9999999 on the test corpus). Scores match to 4 decimals.

## Performance

Measured on an Apple Silicon Mac (macOS 26):

| Operation | Result |
|---|---|
| Index with bge-small | about 34 chunks/s on dense 300-token chunks (8,000 in 235 s); short entries are much faster (the 19-chunk test fixtures index in 0.8 s) |
| One `search` command, start to finish, including model load | about 0.25 s |
| `dupes` over 8,000 chunks | about 2 s |
| Commands that don't embed text (`similar`, `dupes`, `cluster`, `outliers`, `info`) | about 0.15 s; they load no model |

On a 4-vCPU Linux dev box: search over 100k chunks takes 0.15 s after load, and `dupes` over 100k chunks
(tiled, bounded memory) about 29 s.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `sem: runtime not found` | Run `./setup.sh` in your own terminal (not from Claude). |
| `vendored files failed checksum verification` | The clone is incomplete or was modified. Re-clone. |
| `cannot create …/.sem` | The current directory isn't writable. `cd` into your project. |
| `built with model 'A' and cannot be used with 'B'`, or a revision mismatch | `sem index --rebuild …` |
| Self-test failed during setup | Re-run `./setup.sh`. If it still fails, open an issue with the output. |

To uninstall, run `./setup.sh --uninstall`. It removes the skill and runtime. Your project `./.sem/` folders are
left alone; delete them if you like.

## Open questions

- **Runtime location.** The default stays at `~/.claude/skills/smol-sim-search/runtime/`. Skill discovery only
  reads each skill's `SKILL.md`, so the runtime's size shouldn't matter, but that hasn't been measured. If it does,
  use `--runtime-dir ~/.local/share/smol-sim-search/runtime`.
- **Chunking.** Tuned for short English entries for now. A dedicated chunking strategy for long documents is a
  planned follow-up.

## Development

See [CLAUDE.md](CLAUDE.md) for the repo layout, tests, updating the vendored files, and the Linux dev hooks.
