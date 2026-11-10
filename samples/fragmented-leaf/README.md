# Sample fragmented leaf

A newcomer can materialize one synthetic leaf, rank two of its fragment files, and open that pair in `prw-review`. The TIFF bytes are not in Git. `*.tif` is gitignored, and this leaf is not a scan.

The pixels come from `prw generate` (`synthetic_tear`). There is no publisher image and no third-party license. The recorded hashes, the 32-join transcript, and the review flags are [Multi-fragment pool](../../docs/pilot-multi-fragment-pool.md). [Using the workbench](../../docs/USAGE.md) is the longer walkthrough.

## Generate

From the checkout root, with [uv](https://docs.astral.sh/uv/) on `PATH`:

```bash
./samples/fragmented-leaf/generate.sh
```

That writes `${TMPDIR:-/tmp}/prw-sample-leaf/`. Pass another directory outside the checkout as the first argument. A path inside the checkout, or a path with a component `originals`, `observations`, `runs`, `validations`, `exports`, `data`, `scans`, or `real_data`, is refused before `generate` runs.

The parameters are missing-fragment percentage `0`, edge erosion `0`, rotation `0`, lighting variation `0`, and random seed `3`. The same parameters write the same TIFF bytes. Four `fragment-*.tif` files land in `images/`. `benchmarks/labels.json` is the BenchmarkLabel store. Leave it unread as a judge of the ranking.

Lighting variation `0` paints two rasters and writes each one twice. Sorted by file name, the first and second files are one raster. The script selects the first and third names. Those two hashes differ. `Load synthetic pair` in the review window selects that same pair.

## Rank

The script prints a `prw rank` command for that pair. Exit `0`. `record` is `physical_join_order`. `joins` has 32 rows. Every `epistemic_class` is `hypothesis`. Every `channel` is `physical`. The first row is the highest physical score in this list. It is a hypothesis.

Ranking the first and second sorted names exits `2`. Stderr is `A join cites two distinct edge ids.`

## Review

The script prints the same flags for `prw-review`. The window needs a display and the `ui` group (`uv sync` installs it). The list labels every row `hypothesis`, including rank 1. Reject hypothesis, Keep as hypothesis, and Defer append a decision. The other rows stay.

`benchmarks/labels.json` is not an image path. The window does not write a project directory.
