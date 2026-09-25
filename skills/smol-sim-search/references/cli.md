# `sem` command reference

```
sem <command> [options]
```

## Common options (all commands)

| Option | Meaning |
|---|---|
| `--index NAME` | Index to use (default `default`, env `SEM_INDEX`). Indexes live in `./.sem/indexes/NAME/`. |
| `--json` | Print exactly one JSON document on stdout; progress and logs go to stderr. |
| `--model KEY` | Model key (only `bge-small` ships). Fixed per index: a different one for an existing index is an error. |
| `--snippet N` | Max characters of chunk text per result (default 300; `0` = full text). |

Every JSON document has `ok` (bool) and `command`. Errors: `{"ok": false, "command": ..., "error": "..."}` with a non-zero exit.

A **result item** (hit) looks like:

```json
{"score": 0.8123, "chunk_id": "3f2a9c01be77", "path": "docs/tides.md", "locator": "L9-13",
 "heading": "Ocean tides > Spring and neap tides", "text": "When the Sun, Moon and Earth line up ..."}
```

`locator` formats: `L9-13` (line range), `p3` (PDF page), `rec:T-101` (record id; `rec:T-101#2` for the 2nd
chunk of a long record). `heading` is the Markdown heading trail, when there is one.

## Items

`similar` and `compare` accept an **item**:

- a `chunk_id` from any result,
- an indexed **file path** (relative to the project, as shown in results). Its vector is the normalised mean of its chunk vectors,
- `path:line`, meaning the chunk of that file covering that line. This also addresses one record of a CSV/JSONL
  file: use the record's line number in the file (a CSV header is line 1, so the first data row is line 2).

`rec:<id>` locators shown in results are labels, not lookup keys — address a record by `path:line` or `chunk_id`.

## `sem doctor [--full]`

Reports runtime paths, versions, the installed model, whether `./.sem` is writable, and whether the network guard
is active. Exits 1 on a blocking
problem (missing runtime, missing default model, unwritable directory). `--full` also loads the default model and
embeds a test string.

## `sem index PATHS... [options]`

Builds or incrementally updates an index. Only files whose content hash changed are re-embedded. Files that were
deleted, or that are now excluded under a directory being indexed, are removed.

| Option | Meaning |
|---|---|
| `--model KEY` | Model for a new index (default `bge-small`). |
| `--include GLOB` / `--exclude GLOB` | Repeatable. Matched against the project-relative path and the file name. |
| `--text-field DOT.PATH` | JSON/JSONL: the field to embed (e.g. `body.text`). Default: all scalar fields as `key: value` lines. |
| `--text-cols a,b` | CSV/TSV: columns to embed. Default: all columns as `col: value` lines. |
| `--id-col NAME` / `--id-field NAME` | CSV column / JSON field used as the record id. Default: a column/field named `id`, `_id`, `ID`, `Id`, `uuid` or `key` if present, else the row number. |
| `--chunk-tokens N` | Token budget per chunk (default 300; bge-small's limit is 512). |
| `--overlap N` | Tokens of overlap between consecutive chunks (default 15%). |
| `--rebuild` | Ignore existing state; required to change model, chunking or reader options. |
| `--max-mb N` | Skip files larger than N MB (default 50). |
| `--no-gitignore` | Don't apply `.gitignore` rules. |

Always skipped: `.git`, `.sem`, `.venv`, `venv`, `node_modules`, `__pycache__`, and similar tool directories, plus
binary files (by extension or NUL bytes). `.gitignore` files between the project root and each indexed file apply
(basic syntax: globs, `**`, `!negation`, trailing `/`, leading `/`).

Readers:

| Files | Chunking | Locator |
|---|---|---|
| Markdown / text | Split at headings, then paragraphs, packed to the token budget | `L<a>-<b>` + `heading` |
| Source code / config | Blank-line-separated blocks packed to the budget | `L<a>-<b>` |
| CSV / TSV / JSONL / JSON arrays | One record per item; long records are split | `rec:<id>` |
| PDF (`pypdf`) | Per page, paragraphs packed to the budget | `p<n>` |

JSON output: `added`, `changed`, `removed` (paths), `unchanged` (count), `chunks_embedded`, `skipped`
(too-large files), `empty_files`, `compacted`, `seconds`.

## `sem search "QUERY"`

| Option | Meaning |
|---|---|
| `-k N` | Results (default 10). |
| `--min-score X` | Drop hits below X. |
| `--path-glob GLOB` | Only chunks whose path (or file name) matches. |
| `--group-by-file` | Best chunk per file. |

The query is embedded with the model's query prompt (bge: "Represent this sentence for searching relevant
passages: "). Documents are embedded without one.

## `sem similar ITEM`

Nearest neighbours of an item. It excludes the item itself (for a file, all of that file's chunks). Options: `-k`
(default 10), `--path-glob` (restrict where neighbours may come from), `--group-by-file` (best chunk per file —
use it for "which *files* are related"). JSON output: `item`, `item_kind` (`chunk` or `file`), `results`.

## `sem neighbors`

Ranked top-k neighbours for **every** item in one pass — the bulk form of `similar`, for building a similarity
graph or precomputing related-item lists. Exact (no approximation): a blocked computation streams tiles of the
memory-mapped vectors and keeps a running top-k per row, so memory stays bounded at any corpus size (100k chunks:
about a minute and about 1 GB; 12k chunks: under 2 s). `outliers` runs on the same core.

| Option | Meaning |
|---|---|
| `--level chunk\|file` | Neighbour lists per chunk/record (default) or per file. |
| `-k N` | Neighbours per item (default 10). |
| `--min-score X` | Drop neighbours below X; lists may then be shorter than k. |
| `--across-files-only` | Chunk level: exclude neighbours from the item's own file. Use for prose indexed with overlap (adjacent chunks of one file are trivially similar). Leave off for record files — a CSV/JSONL corpus is one file. |
| `--snippet N` | **For this command the default is 0 = no text** (identity + score only, keeping n×k output compact). Pass a positive N to include snippets; fetch full text via `chunk_id` with `similar` or the source file. |

JSON: `items` is one entry per item — `{chunk_id, path, locator, heading?, neighbors: [{score, chunk_id, path,
locator, ...}]}` (file level: `{path, neighbors: [{score, path}]}`), neighbours sorted by descending score.
`k` in the output is the effective k (capped at items−1). Human output prints one line per item.

## `sem compare A B [--text] [--pairs N]`

Cosine similarity of two items. With `--text`, A and B are literal strings, both embedded as documents (no query
prompt) — this needs no index and works before anything is indexed. For the model it uses the index's model if the
index exists, otherwise `--model` or the default. For two files, it also returns `best_chunk_pairs`: the N most
similar chunk pairs across the two files, which answer "where exactly do these overlap?".

## `sem dupes`

Near-duplicate chunk pairs at cosine ≥ `--threshold` (default 0.95 for bge-small).
Tiled matrix multiply, so memory stays bounded. `--across-files-only` ignores pairs within one file. `--limit N`
controls how many pairs are printed (default 50; `total_pairs` always has the full count).

## `sem cluster`

Spherical k-means (cosine, k-means++ init, best of 3 restarts). Deterministic for a given `--seed`.

| Option | Meaning |
|---|---|
| `--level chunk\|file` | Cluster chunks or files (file = mean of its chunks). |
| `--k N\|auto` | `auto` picks k in 2..15 by silhouette on a sample of up to 2000 items (`k_search` lists scores). |
| `--sample N` | Fit centroids on at most N items (default 20000), then assign every item. |
| `--max-members N` | Members listed per cluster (default 50; `0` = all). |
| `--reps N` | Representatives per cluster: the items nearest the centroid (default 3). |
| `--seed N` | Random seed (default 0). Results are deterministic for a given seed. |

Each cluster has `size`, `cohesion` (mean similarity of members to the centroid), `representatives`, and `members`.

## `sem outliers`

Items with the lowest mean similarity to their `--neighbors` (default 5) nearest neighbours. `--level chunk|file`,
`-n` results. The output also has `median_mean_neighbor_score` for comparison.

## `sem embed "TEXT" [--query]`

Prints the normalised vector (JSON: `vector`, `dim`). `--query` applies the query prompt.

## `sem info` · `sem list` · `sem drop NAME`

Index statistics (model and revision, dim, chunking, files, chunks, tombstoned rows, size on disk, roots, last
update) · all indexes in `./.sem` · delete an index.

## Environment

| Variable | Effect |
|---|---|
| `SEM_INDEX` | Default index name. |
| `SEM_MODEL` | Default model key for new indexes and `embed`. |
| `SEM_BATCH_SIZE` | Embedding batch size (default 32). |
| `SEM_THREADS` | ONNX Runtime threads (default: all cores). |
| `SEM_QUIET=1` | No progress output. |

The wrapper sets `SEM_HOME=./.sem` and points `TMPDIR` and `XDG_CACHE_HOME` into it. Embedding runs on the CPU
with ONNX Runtime. The process refuses non-local socket connections.

## On-disk format (`.sem/indexes/<name>/`)

`manifest.json` (schema version, model key and revision, dim, chunking, reader options, counts, times),
`vectors.f16.npy` (float16, L2-normalised, memory-mapped), and `meta.sqlite` (`files`, `chunks`). Updates that
change vectors are built in `.sem/tmp/` and swapped in by rename. An index is compacted automatically when more
than 20% of its rows are tombstoned.
