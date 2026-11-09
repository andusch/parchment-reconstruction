# Multi-fragment pool

- Status: Working note. One operator run of `prw generate`, then `segment` and `rank` on two fragment files from that leaf, then the `prw-review` flags that load the same pair.
- Run: 9 November 2026, checkout `7518379cb2d35171c6419241e6d8a8b6ce02648b` (merge of PR #16). Command names and flags are unfrozen.
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)

The leaf is synthetic. It stays outside the clone. [Using the workbench](USAGE.md) uses the same parameters. [First public-leaf run](pilot-first-run.md) is one publisher TIFF and an empty join list. This note is the pool that prints join hypotheses.

Every join in a `physical_join_order` is a hypothesis. Rank 1 is the highest physical score in that list. The list is the rank for this pool. This note does not score it against `benchmarks/labels.json`.

## Source

`prw generate` writes the files. The program does not download them. [ADR-0001](adr/0001-local-only-processing.md) still forbids a network call from the program. There is no publisher, no license string, and no attribution line. The bytes are the fixture writer.

From the checkout root. `CODE` is `git rev-parse HEAD`. On this run it was `7518379cb2d35171c6419241e6d8a8b6ce02648b`. `DEMO` is a new directory outside the checkout.

```bash
export CODE DEMO IMAGES BENCHMARKS
CODE=$(git rev-parse HEAD)
DEMO="${TMPDIR:-/tmp}/prw-multi-fragment"
IMAGES="$DEMO/images"
BENCHMARKS="$DEMO/benchmarks"
mkdir -p "$DEMO"
uv run prw generate \
  --benchmarks "$BENCHMARKS" \
  --images "$IMAGES" \
  --missing-fragment-percentage 0 \
  --edge-erosion 0 \
  --rotation 0 \
  --lighting-variation 0 \
  --random-seed 3 \
  --code-version "$CODE"
```

Exit `0`. `provenance.algorithm_name` is `synthetic_tear`. `provenance.algorithm_version` is `1`. `provenance.random_seed` is `3`. `provenance.decoder_name` is `synthetic_uncompressed_tiff`. `provenance.decoder_version` is `1`. `provenance.model_hash` is `absent`. `provenance.parameter_blob` is `{"edge_erosion":0.0,"lighting_variation":0.0,"missing_fragment_percentage":0.0,"rotation":0.0}`. `provenance.parameter_hash` is `sha256:7bfcf5bdecd927a501a2fd8a9b1ff8026683742da0450bf7d885f8e29011bd6e`.

These paths exist afterward:

- `$IMAGES/page.tif`
- `$IMAGES/image_manifest.json`
- four `$IMAGES/fragment-*.tif` files
- `$BENCHMARKS/labels.json`
- `$BENCHMARKS/provenance.json`

`$DEMO/originals` does not exist. `$BENCHMARKS/manifest.json` does not exist. `labels.json` is the BenchmarkLabel store. Leave it unread as a judge of the ranking below.

The same parameters write the same TIFF bytes. A second generate with a different `--code-version` reprints the hashes in the next section. The code version is stored on the provenance object. It is not painted into the rasters.

The page file is 100 by 140, `14122` bytes, `sha256:78d1e0716f07a04c7c0a25c780922dd3a3c40b40d203aa84afe2c0a85d98fe24`.

## Which two files

Lighting variation `0` paints every fragment at one gray level. Two fragments with the same width and height are the same TIFF bytes. This leaf writes four files and two rasters.

Sorted by file name:

| File | Pixels | Bytes | `content_hash` |
| --- | --- | --- | --- |
| `fragment-1ff770d6-b967-513e-a5cb-e8386ba1727c.tif` | 48 by 70 | `3482` | `sha256:29eb01c09fde531d69778b68d02c6e7da24ad40a126892a310715e3a39e81534` |
| `fragment-5de72798-c696-5211-b0f1-201995d5896e.tif` | 48 by 70 | `3482` | `sha256:29eb01c09fde531d69778b68d02c6e7da24ad40a126892a310715e3a39e81534` |
| `fragment-82ee214b-5d6c-56ce-b454-b926130e8601.tif` | 52 by 70 | `3762` | `sha256:d7434daad654155fb4d4077108c561a43f7b220497b6df063d46db87d2d9676f` |
| `fragment-d7a93980-e44f-5af1-b04e-662485e17740.tif` | 52 by 70 | `3762` | `sha256:d7434daad654155fb4d4077108c561a43f7b220497b6df063d46db87d2d9676f` |

The pool is the first and the third name. Those two hashes differ. `Load synthetic pair` in `prw-review` selects the same two files. The ids in the file names are the fixture fragment ids.

Bind them from the manifest:

```bash
eval "$(uv run python - <<'PY'
import json
import os
import shlex
from pathlib import Path

images = Path(os.environ["IMAGES"])
manifest = json.loads((images / "image_manifest.json").read_text())
fragments = sorted(
    (item for item in manifest["images"] if item["role"] == "fragment"),
    key=lambda item: item["name"],
)
if len(fragments) != 4:
    raise SystemExit("These parameters write four fragment files.")
chosen = (fragments[0], fragments[2])
if chosen[0]["content_hash"] == chosen[1]["content_hash"]:
    raise SystemExit("The first and third fragment files share one hash.")

def emit(name: str, value: object) -> None:
    print(f"{name}={shlex.quote(str(value))}")

emit("PIECE_A", images / chosen[0]["name"])
emit("PIECE_B", images / chosen[1]["name"])
emit("PIECE_A_HASH", chosen[0]["content_hash"])
emit("PIECE_B_HASH", chosen[1]["content_hash"])
PY
)"
```

On this run `PIECE_A` is `fragment-1ff770d6-b967-513e-a5cb-e8386ba1727c.tif` and `PIECE_B` is `fragment-82ee214b-5d6c-56ce-b454-b926130e8601.tif`.

Passing both files of one hash exits `2`. Stdout is empty. Stderr is `A join cites two distinct edge ids.` The same exit happens when all four files are one pool: the ranker pairs the two copies of each raster, and a join cites two distinct edge ids. Chord edge ids are content-derived from the outline of that raster. This note leaves that rule in place.

## Commands

```bash
uv run prw verify "$PIECE_A" --expected "$PIECE_A_HASH"
uv run prw verify "$PIECE_B" --expected "$PIECE_B_HASH"
```

Both exited `0`. `record` is `VerifiedBytes`. `media_type` is `image/tiff`. For the first file, `content_hash` is `sha256:29eb01c09fde531d69778b68d02c6e7da24ad40a126892a310715e3a39e81534`, `byte_length` is `3482`, and `id` is `49b0732c-fde5-59fb-9fc2-254bd82be912`. For the third file, `content_hash` is `sha256:d7434daad654155fb4d4077108c561a43f7b220497b6df063d46db87d2d9676f`, `byte_length` is `3762`, and `id` is `00f8601d-0bda-510e-a61d-00501463d448`.

```bash
uv run prw segment "$PIECE_A" \
  --label piece-a \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --expected "$PIECE_A_HASH"
uv run prw segment "$PIECE_B" \
  --label piece-b \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --expected "$PIECE_B_HASH"
```

Both exited `0`. `record` is `FragmentOutlineRevision`. `epistemic_class` is `interpretation`. `producer` is `machine`. `frame` is `source_pixels`. `envelope.algorithm_name` is `fragment_outline`, `algorithm_version` is `1`, `decoder_name` is `synthetic_uncompressed_tiff`, `decoder_version` is `1`, `model_hash` is `absent`. The envelope omits `random_seed`. `parameter_blob` is `{"foreground_threshold":1}`. The first polygon is `[[0.0,0.0],[47.0,0.0],[47.0,69.0],[0.0,69.0]]`, the corners of the 48 by 70 raster. The third polygon is `[[0.0,0.0],[51.0,0.0],[51.0,69.0],[0.0,69.0]]`, the corners of the 52 by 70 raster. `--foreground-threshold 1` kept each raster as one component. Each outline is an interpretation of that threshold.

```bash
uv run prw edge "$PIECE_A" \
  --label piece-a \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1
```

Exit `0`. `record` is `ChordEdges`. `edges` has four rows. Each `epistemic_class` is `interpretation`. `envelope.algorithm_name` is `edge_chord`. The envelope omits `random_seed`.

```bash
uv run prw rank \
  --image piece-a "$PIECE_A" \
  --image piece-b "$PIECE_B" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1
```

Exit `0`. `record` is `physical_join_order`. `joins` has 32 rows. The first `score` is `0.0`. The last `score` is `-2.2`. Each score is less than or equal to the previous score. Every `epistemic_class` is `hypothesis`. Every `channel` is `physical`. `envelope.algorithm_name` is `pairwise_rigid_join`. `envelope.algorithm_version` is `1`. `decoder_name` is `synthetic_uncompressed_tiff`. `decoder_version` is `1`. `model_hash` is `absent`. The envelope omits `random_seed`. `parameter_blob` records `score` `negative_absolute_length_difference` and the edge, fragment, and frame ids of this run. `parameter_hash` starts with `sha256:`. `source_hashes` are the two fragment digests above, in sorted order. The labels `piece-a` and `piece-b` are names for this invocation. The fragment ids in the JSON are those pool ids.

`--pixels-per-mm 10` and `--uncertainty 0.1` are the scale the review window fills in. They are caller-supplied. The fixture page label records `millimetres_per_pixel` `1` inside `benchmarks/labels.json`. This rank does not read that file.

After these commands the two fragment lengths and the two digests above were unchanged. `labels.json` was not a rank path.

## Open the pool in prw-review

`uv sync` from the checkout installs the `ui` group, which holds PySide6-Essentials. The headless `prw` console does not import it. See [ADR-0015](adr/0015-thin-review-window.md).

The window needs a display. It imports PySide6 when it starts, including for `--help`. A missing platform library is an import error on stderr. The checks in this repository run the window on the offscreen Qt platform. An operator session uses a display.

```bash
uv run prw-review \
  --image piece-a "$PIECE_A" \
  --image piece-b "$PIECE_B" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1
```

Those flags are the rank above. The window ranks once when it opens. The list labels every row `hypothesis`, including rank 1. The banner says these joins are hypotheses, and that rank 1 is the first row of the physical score sort. The sketch draws the two outlines in fragment-local millimetres. Reject hypothesis, Keep as hypothesis, and Defer append a validation decision. The other rows stay. The actor string is `local-operator`. The window does not ask for a person's name, and it does not write a project directory.

`Load synthetic pair` writes another leaf under a temporary directory outside the checkout, with the parameters in the generate command, and ranks the first and third sorted fragment files. It does not read `benchmarks/labels.json`. The code-version field in the window is the value passed to `--code-version`, or `0.0.0` when that flag is omitted.

## What stays open

[Q-SCI-15](OPEN_QUESTIONS.md#q-sci-15) stays open. This leaf is synthetic, and the 32 rows are hypotheses about this pool. [Q-ENG-01](OPEN_QUESTIONS.md#q-eng-01) stays open. [Q-ENG-06](OPEN_QUESTIONS.md#q-eng-06) stays open: one rank runs on a Qt thread, and there is no worker process. Full P7 stays deferred. This note does not add HTR, a project store, or a second validation UI.
