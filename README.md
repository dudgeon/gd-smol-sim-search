# semantic-search: local embeddings for Claude Code, inside the sandbox

A [Claude Code skill](https://code.claude.com/docs/en/skills) that lets Claude embed any local dataset and work with
meaning instead of exact text: semantic search, nearest neighbours, pairwise comparison, near-duplicates, clusters
and outliers. Everything runs **in-process and offline** on your Mac. There are no servers, daemons, API keys or
network access at runtime. It works with Claude Code's sandbox **on and at its default settings**.

```bash
git clone https://github.com/dudgeon/gd-smol-sim-search
cd gd-smol-sim-search
./setup.sh
```

That's the whole install. Start a new Claude Code session in any project and ask something like *"find the notes
where we discussed retry policies"*, *"which of these tickets are duplicates?"* or *"group these docs by theme"*.
Claude picks up the skill on its own.

## Requirements

- macOS **14 (Sonoma) or later** on **Apple Silicon** (M1–M4). The pinned PyTorch 2.14 wheels need macOS 14.
- Nothing else: `setup.sh` uses only `bash`, `curl`, `shasum` and `tar`, which every Mac has. It does **not** use
  Homebrew, the system Python, Xcode, Docker or Ollama.
- About 1.5 GB of disk for the runtime plus about 130 MB for the default model (qwen3-0.6b adds about 1.2 GB).

## What `setup.sh` does

`setup.sh` is the only step that uses the network, and you run it in your own terminal, outside the sandbox.

1. Checks for macOS arm64 and free disk space.
2. Downloads **uv 0.12.18** for `aarch64-apple-darwin` from GitHub releases and verifies its **SHA-256**.
3. Uses uv to install **CPython 3.12.14** into the runtime directory (uv verifies the download).
4. Creates a venv and installs packages from `requirements.lock` with **`--require-hashes`**: every wheel is pinned
   and hash-checked.
5. Downloads the model at a **pinned Hugging Face commit** (inference files only), then checks each weight file
   against the SHA-256 that Hugging Face publishes for that commit.
6. Precompiles bytecode, because the skill directory is read-only at runtime.
7. Copies the skill to `~/.claude/skills/semantic-search/`, replacing any existing copy in one swap.
8. Runs a self-test in a temporary directory: `sem doctor`, then it indexes the test fixtures, runs a search and
   checks the results.

Re-running it only verifies what's installed. It doesn't modify `~/.claude/settings.json` or any sandbox settings.

| Flag | Effect |
|---|---|
| `--model qwen3-0.6b` | Also install the optional model (repeatable). |
| `--update` | Re-sync packages and re-copy skill files. Downloaded models are kept. |
| `--link` | Dev mode: symlink the skill to this repo. The runtime goes to `~/.local/share/semantic-search/runtime`, so the repo never holds a venv or weights. |
| `--runtime-dir DIR` | Put the runtime (uv, Python, venv, models) somewhere else. |
| `--uninstall [--yes]` | Remove the skill and runtime after confirmation. Project `./.sem/` folders are left alone. |

## How it stays inside the sandbox

| Sandbox rule | How `sem` complies |
|---|---|
| Writes only under the current directory | Indexes, caches, temp files and the device-probe cache all live in `./.sem/`. The wrapper points `TMPDIR`, `XDG_CACHE_HOME`, `TORCH_HOME` and the HF module caches into it. The skill and runtime directories are only read (bytecode is precompiled and `PYTHONDONTWRITEBYTECODE=1`). `./.sem/` gets its own `.gitignore` (`*`). |
| No network | `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, models load from a local path, and the Python process refuses every non-local socket connection. `sem doctor` reports both. |
| No escapes | No `dangerouslyDisableSandbox`, no excluded commands, no settings edits. If something can't run, `sem` falls back or explains; it never works around the sandbox. |
| Metal may be blocked | The GPU probe runs in a **subprocess** with a 20 s timeout. It checks `torch.backends.mps.is_available()` and runs a matmul on `mps` against CPU. Any failure, hang or crash (including SIGABRT) means CPU. The result is cached in `.sem/device.json`, keyed on the torch and macOS versions. |

If the current directory isn't writable, `sem` says so and asks you to `cd` into a project, rather than writing
elsewhere.

## Using it directly

Claude runs it for you, but `sem` also works on its own:

```bash
SEM=~/.claude/skills/semantic-search/bin/sem
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

Every command takes `--json` (one JSON document on stdout, logs on stderr), `--index NAME` and `--device
auto|cpu|mps`. The full reference is in [`skills/semantic-search/references/cli.md`](skills/semantic-search/references/cli.md).

Supported inputs: Markdown and text (split at headings and paragraphs), source code (blank-line-aligned line
windows), CSV/TSV, JSON and JSONL (one record per chunk, keeping its id) and PDF (per page, via `pypdf`). Binary
files, `.git`, `node_modules`, virtualenvs and files over 50 MB are skipped, and `.gitignore` rules apply.

## Models

| Key | Model | Dim | License | Notes |
|---|---|---|---|---|
| `bge-small` (default) | [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) @ `5c38ec7c` | 384 | MIT | Small, fast, good on CPU. English. |
| `qwen3-0.6b` | [`Qwen/Qwen3-Embedding-0.6B`](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) @ `c54f2e6e` | 1024 | Apache-2.0 | Higher quality, multilingual, long context. Much slower on CPU. |

The model is part of an index's identity. An index built with one model can't be queried with another; `sem`
refuses with a clear error. Use a separate `--index` or `--rebuild`. Score interpretation per model is in
[`references/interpreting-scores.md`](skills/semantic-search/references/interpreting-scores.md).

## Performance

These figures were measured on the development machine (Linux x86-64, 4 vCPU, CPU only), **not** yet on an M-series
Mac:

| Operation | Result |
|---|---|
| Index with bge-small, CPU | about 32 chunks/s with dense 300-token chunks (8,000 chunks in 253 s). Ordinary prose chunks are often shorter and faster. |
| Search over 100k chunks (after model load) | 0.15 s (0.19 s with `--group-by-file`) |
| `dupes` over 100k chunks (tiled, bounded memory) | 29 s |
| Model load and torch import per embedding command | about 5–6 s. Commands that don't embed text (`similar`, `dupes`, `cluster`, `outliers`, `info`) never import torch and start in about 0.2 s. |

## Open questions and findings

- **Does Claude Code's Seatbelt profile allow Metal?** Not yet verified; this was built in an environment without
  macOS. Either way, `sem` works: run `sem doctor` inside a sandboxed Claude Code session and the `device:` line
  shows `mps` or `cpu (Metal unavailable: …)`. If it's CPU, expect indexing at roughly the CPU speeds above. Please
  record the result here.
- **Runtime location.** The default stays at `~/.claude/skills/semantic-search/runtime/` as specified. Skill
  discovery only reads each skill's `SKILL.md`, so the runtime's size shouldn't matter, but that hasn't been
  measured. If discovery turns out slow, use `--runtime-dir ~/.local/share/semantic-search/runtime`; the wrapper
  follows a pointer file.
- **When is qwen3-0.6b worth it?** Its CPU throughput isn't measured yet (the build environment couldn't reach
  Hugging Face). Expect it to be several times slower than bge-small per chunk (about 18× the parameters). Prefer
  it for non-English or mixed-language corpora, and for long, technical passages where bge-small's recall is poor.
  Measure with `time sem index <dir> --index q --model qwen3-0.6b`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `sem: runtime not found` | Run `./setup.sh` in your own terminal (not from Claude). |
| `model 'X' is not installed` | `./setup.sh --model X` |
| `cannot create …/.sem` | The current directory isn't writable. `cd` into your project. |
| `built with model 'A' and cannot be used with 'B'` | Use a separate `--index` or `sem index --rebuild --model B …`. |
| Device shows `cpu` on a Mac | Metal is blocked or unavailable in this context. Everything still works, just slower. `sem doctor --reprobe` re-tests. |
| Self-test failed during setup | Re-run `./setup.sh`. If it still fails, open an issue with the output. |

To uninstall, run `./setup.sh --uninstall`. It removes the skill and runtime. Your project `./.sem/` folders are
left alone; delete them if you like.

## Development

See [CLAUDE.md](CLAUDE.md) for the repo layout, running tests, updating pins, and the Linux dev hooks.
