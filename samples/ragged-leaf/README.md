# Ragged synthetic leaf

One command generates a synthetic leaf with non-zero edge erosion, rotation, and lighting variation, freezes `benchmarks/labels.json`, and writes join recall at K=1 and K=3 plus placement error at N=2. The TIFF bytes stay in the destination directory. They are not committed.

The measured numbers, the command list, and the physical-channel diagnosis are [Ragged synthetic demo](../../docs/ragged-synthetic-demo.md).

## Run

From the checkout root, with [uv](https://docs.astral.sh/uv/) on `PATH`:

```bash
./samples/ragged-leaf/run.sh
```

Pass an empty directory outside the checkout as the first argument to write somewhere else. The default directory is `${TMPDIR:-/tmp}/prw-ragged-leaf/`. A path inside the checkout, or a destination that already holds a file, exits `2`.

The default `--code-version` is `2fe603838c5e160c3a1e3d6a65a3d487d8f1b28b`. The note's measured record is for that string. The curve-and-overlap record and the length-difference record are kept in the same note. Joins stay hypotheses.
