# Interpreting similarity scores

All scores are **cosine similarities of L2-normalised embeddings**, in [-1, 1]. In practice they fall in a narrow,
model-specific band, so:

1. **Rank, don't threshold.** The order of results is meaningful. The absolute number means little on its own.
2. **Look for gaps.** A drop from 0.78 to 0.62 between hit 2 and hit 3 usually marks the edge of what's relevant.
3. **Compare against the corpus.** `sem outliers` prints `median_mean_neighbor_score`, the typical similarity of
   an item to its nearest neighbours in *this* corpus. Hits well above it are notable.
4. **Scores from different models or indexes are not comparable.** Every index records its model, and `sem`
   refuses to mix them.
5. **Chunk vs file.** A file vector is the mean of its chunk vectors. File-to-file scores are smoother (and usually
   higher) than the best chunk-to-chunk match. For "where exactly do these overlap", use `compare A B`, which
   lists `best_chunk_pairs`.

## bge-small (`BAAI/bge-small-en-v1.5`, default)

These numbers were measured on this repo's `tests/fixtures`, a small corpus on unrelated topics (bread, tides,
Kubernetes, gardening, code, recipes, support tickets, volcanoes):

| Situation | Typical cosine |
|---|---|
| Unrelated chunks (cross-file pairs, 10th–90th percentile) | 0.37 – 0.58 (median 0.48) |
| Unrelated short sentences ("the cat sat on the mat" vs "quarterly revenue grew 8 percent") | ~0.37 |
| Paraphrase ("the cat sat on the mat" vs "a feline rested on the rug") | ~0.75 |
| Good query → passage match (with the query prompt) | 0.70 – 0.80 |
| Near-duplicate paragraph (one word changed) | ~0.99 |

- bge scores are compressed upwards: almost nothing scores below 0.3, and **0.5 means "unrelated"**, not "half
  relevant".
- Default `dupes` threshold is **0.95**. Use 0.90 to catch heavier rewording (and expect some false positives).
  Use 0.98+ for copies with trivial edits only.
- Queries use the prompt "Represent this sentence for searching relevant passages: ". Query→passage scores are
  therefore a bit lower than passage→passage scores for the same content. Don't compare `search` scores with
  `similar` scores directly.

## qwen3-0.6b (`Qwen/Qwen3-Embedding-0.6B`, optional)

- Uses an instruction prompt for queries (the model's built-in `query` prompt). Documents are embedded as-is.
- Its score range has **not yet been measured in this repo** (the build environment could not download it). Don't
  reuse the bge numbers above. Calibrate from score gaps and the corpus median, as described below.
- Default `dupes` threshold is **0.92**.
- Multilingual: a query in one language can match passages in another, usually at a somewhat lower score than
  a same-language match.

## Picking thresholds for a specific corpus

1. Run `sem outliers --json` and note `median_mean_neighbor_score`.
2. Run `sem dupes --threshold 0.9 --limit 20` and inspect the pairs near the bottom of the list. Raise the
   threshold until the false positives stop.
3. For `search --min-score`, run a few queries whose answer you know, and set the cutoff just below the lowest
   correct hit.
