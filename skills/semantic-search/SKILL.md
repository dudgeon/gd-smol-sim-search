---
name: semantic-search
description: Local semantic search and similarity analysis over any dataset in the current project — documents, code, notes, CSV/JSONL records, PDFs. Use this whenever the user wants to find things by meaning rather than exact text, search a large corpus that won't fit in context, find related or similar files or records, detect near-duplicates, group or cluster items by theme, find outliers, or compare how similar two things are. Runs fully offline inside the Claude Code sandbox.
---

# semantic-search

`sem` embeds files in the current project with a local model and answers
questions about meaning: search, nearest neighbours, pairwise similarity,
near-duplicates, clusters and outliers. It runs in-process, offline, and
writes only to `./.sem/` in the current directory.

Run it by its full path inside this skill's directory:

```bash
SEM="<this skill's base directory>/bin/sem"   # e.g. ~/.claude/skills/semantic-search/bin/sem
"$SEM" doctor
```

## 1. First use in a project

Run `"$SEM" doctor` once. If it prints `PROBLEMS FOUND` or exits non-zero,
show the problems to the user and stop. Don't try to fix sandbox settings,
install packages or copy models yourself. The fix is for the user to run
`./setup.sh` in their own terminal.

## 2. Workflow

1. **Index only the relevant paths**, never the whole disk or home directory:
   `"$SEM" index docs/ notes/ --json`. Indexing is incremental; re-running it
   is cheap.
2. **Query or analyse** with `--json` and parse the result. Progress and logs
   go to stderr; stdout holds exactly one JSON document. Every JSON document
   has `ok` and `command`; on failure it has `error`.
3. Use `--index <name>` to keep separate corpora apart (default `default`).

Structured data: `--text-cols title,body --id-col id` for CSV/TSV, and
`--text-field body.text --id-field id` for JSON/JSONL. Each record becomes its
own chunk, and the id appears in the locator as `rec:<id>`.

## 3. Context discipline

Use results to decide what to open. Read only the top hits' files, or just the
`path` + `locator` line ranges, with the Read tool. Don't paste a whole large
dataset into context. `--snippet N` controls how much text each hit carries
(default 300 chars; `0` = full chunk).

## 4. Choosing a command

| User intent | Command |
|---|---|
| "find where we talk about X", "search by meaning" | `search "X" -k 10` (add `--group-by-file` for one hit per file) |
| "what's related to this file / chunk / line" | `similar path/to/file.md` · `similar <chunk_id>` · `similar path.py:120` |
| "how similar are A and B" | `compare a.md b.md` (files/chunks) · `compare --text "..." "..."` |
| "find duplicates / copy-paste / redundant records" | `dupes --across-files-only` |
| "group these by theme / topics" | `cluster --level file --k auto` (or `--level chunk`, `--k 8`) |
| "what doesn't fit / unusual items" | `outliers --level file -n 10` |
| "how big is the index / which model" | `info` · `list` |
| start over / change model or chunking | `index --rebuild ...` · `drop <name>` |

Items for `similar`/`compare` are a `chunk_id` (from any result), an indexed
file path, or `path:line`. The full reference is in
[references/cli.md](references/cli.md).

## 5. Reading scores

Cosine scores are **relative and model-specific**. Rank and compare items
against each other, and don't treat a score as an absolute measure of
relevance. With `bge-small`, unrelated text often scores 0.3–0.5, so a 0.6
isn't "60% relevant". Look for gaps between scores and compare against the
corpus median (`outliers` reports it). Dupe thresholds default per model. See
[references/interpreting-scores.md](references/interpreting-scores.md).

## 6. Sandbox rules

- Indexes, caches and temp files live in `./.sem/` (which has its own
  `.gitignore`). Never write anywhere else, and never set `SEM_HOME` outside
  the project.
- Never attempt network access. Never propose disabling the sandbox,
  `dangerouslyDisableSandbox`, excluded commands, or settings edits to make
  `sem` work. If `sem` can't do something inside the sandbox, say so.
- If the cwd isn't writable, `sem` says so. Ask the user which project
  directory to work in.

## 7. Stale indexes

Before answering from an index, run `"$SEM" index <same paths> --json` again
if files may have changed. Only changed files are re-embedded (see `changed`
and `chunks_embedded` in the output). An index is tied to one model: querying
with a different model fails on purpose. Use a new `--index` name or
`--rebuild`.

## Examples

```bash
"$SEM" index docs/ src/ --json
"$SEM" search "how do we retry failed uploads" -k 5 --json
"$SEM" similar src/upload/retry.py --group-by-file -k 5 --json
"$SEM" dupes --across-files-only --json
"$SEM" cluster --level file --k auto --json
"$SEM" index data/tickets.jsonl --index tickets --text-field body.text --id-field id --json
"$SEM" search "customer charged twice" --index tickets -k 5 --json
```
