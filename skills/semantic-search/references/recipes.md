# Recipes: similarity analysis workflows

Worked, end-to-end flows for the analysis side of `sem` (everything that isn't plain search). All commands
support `--json`; parse that rather than scraping text. `$SEM` is `<skill dir>/bin/sem`.

## Profile an unknown dataset

The standard first pass over any corpus — see its shape before reading anything:

```bash
$SEM index data/ --json                      # 1. embed it
$SEM info --json                             # 2. how big, what got indexed
$SEM cluster --k auto --json                 # 3. what themes exist (k chosen by silhouette)
$SEM dupes --across-files-only --json        # 4. how much redundancy
$SEM outliers -n 15 --json                   # 5. what's unusual
```

Then read: cluster `representatives` name each theme; `total_pairs` from dupes quantifies redundancy;
outliers are the items worth opening by hand. Summarise those for the user instead of reading the corpus.

## Similarity analysis over a CSV / JSONL of records

Each row/record is one item. Pick the meaningful columns and a stable id:

```bash
$SEM index data/feedback.csv --index fb --text-cols title,comment --id-col id --json
```

- Without `--text-cols`, every column is embedded as `name: value` lines — fine for a first pass, but numeric
  and date columns add noise; prefer naming the text columns.
- Without `--id-col`, a column named `id`, `_id`, `ID`, `Id`, `uuid` or `key` is picked up automatically;
  otherwise the row number is used. The id shows up in every result as `rec:<id>`.
- JSONL/JSON: `--text-field body.text --id-field id` (dot paths).

Then analyse **at chunk level** (each record is a chunk):

```bash
$SEM cluster --index fb --level chunk --k auto --json     # group records by theme
$SEM dupes   --index fb --threshold 0.9 --json            # repeated / boilerplate records
$SEM outliers --index fb --level chunk -n 20 --json       # records unlike all others
$SEM similar "data/feedback.csv:2971" --index fb --json   # neighbours of the record on line 2971
```

To drill into one record: use `path:LINE` (the row's line number in the file, header = line 1), or the
`chunk_id` printed in any result. `rec:` ids are labels in output, not lookup keys.

## Deduplicate a corpus

```bash
$SEM dupes --across-files-only --limit 0 --json
```

Start at the model's default threshold (0.95); lower toward 0.9 to catch rewording, raise to 0.98 for
copy-paste-with-tweaks only. Pairs come sorted by score, so review from the bottom of the list to find where
false positives start. `--across-files-only` matters for prose: consecutive chunks of one file overlap by
design and would otherwise dominate.

## Name and use clusters

`cluster` gives sizes, `cohesion`, `representatives` (items nearest the centroid) and `members`. To label a
cluster, read its representatives (they are the most central examples) — not random members. A cluster with
low cohesion (well below the others) is usually "everything else", not a real theme; re-run with a larger
`--k`, or ignore it. Results are deterministic for a given `--seed`.

- `--level chunk`: cluster records/passages (right for CSV/JSONL, or themes inside documents).
- `--level file`: cluster whole documents (a file's vector is the mean of its chunks).

## Compare two specific things

```bash
$SEM compare docs/spec-v1.md docs/spec-v2.md --json     # one score + best-matching chunk pairs
$SEM compare "notes.md:120" "notes.md:300" --json       # two passages of one file
$SEM compare --text "first phrasing" "second phrasing"  # two literal strings; no index needed
```

For two files, `best_chunk_pairs` shows *where* they overlap — use it to answer "which parts are the same?".

## "What is this most related to?"

```bash
$SEM similar src/upload/retry.py --group-by-file -k 5 --json   # related files
$SEM similar src/upload/retry.py:88 -k 10 --json               # related to one passage
$SEM similar <chunk_id> --path-glob "docs/*" --json            # neighbours, restricted to docs/
```

`similar` excludes the item itself (for a file: all of its chunks). Chaining is the drill-down pattern:
cluster or search first, then `similar <chunk_id>` on an interesting hit.

## Two corpora in one project

Keep them in separate indexes; vectors from one index are comparable with each other, not across models:

```bash
$SEM index docs/    --index docs --json
$SEM index tickets/ --index tickets --json
```

Cross-corpus questions ("which docs answer which tickets?"): index both into **one** index instead, then
`search` with the ticket text or `similar` on a ticket's chunk with `--path-glob "docs/*"`.

## Judging significance without absolute thresholds

Scores are relative (see [interpreting-scores.md](interpreting-scores.md)). Three calibrations that work:

1. **Gaps**: a drop of ≥ 0.1 between adjacent ranked results usually marks the relevance boundary.
2. **Corpus baseline**: `outliers --json` reports `median_mean_neighbor_score` — the typical similarity in
   *this* corpus. Similarity well above it is meaningful; near it is noise.
3. **Known pairs**: `compare` two items the user says are related, and use that score as the yardstick.

## Keeping analyses current

Re-run `index` before analysing if files may have changed — it is incremental (only changed files re-embed;
check `changed` / `chunks_embedded` in the JSON). Changing chunking, reader options or model needs
`--rebuild`. `drop <name>` deletes an index; `list` shows them all.
