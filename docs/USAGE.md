# Using the workbench

This guide runs the commands that exist in version `0.0.0`. The program is the headless console `prw`. Command names and flags are unfrozen. They are not a stable interface. The project format is still [Q-ENG-01](OPEN_QUESTIONS.md#q-eng-01).

Terms are defined in the [glossary](DATA_MODEL.md#glossary). A ranked row is a hypothesis. The first row is the highest score in that list.

Work on a synthetic leaf in a disposable directory outside the checkout. Real scans stay out of Git. See [Security and privacy](SECURITY_AND_PRIVACY.md).

## Before you start

Install [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer. From the checkout root, `uv run` selects this project. `uv run prw` and `uv run python -m prw.cli` call the same function.

```bash
cd /path/to/parchment-reconstruction
export CODE DEMO IMAGES BENCHMARKS
CODE=$(git rev-parse HEAD)
DEMO="${TMPDIR:-/tmp}/prw-demo"
IMAGES="$DEMO/images"
BENCHMARKS="$DEMO/benchmarks"
mkdir -p "$DEMO"
```

`$CODE` is the checkout's HEAD. A dirty worktree does not change that SHA. Use an empty `$DEMO`. Keep it outside the repository.

`generate` refuses a destination whose path contains a component named `originals`, `observations`, `runs`, `validations`, or `exports`. It also refuses a destination inside a directory that already holds `manifest.json`. Both refusals happen before any file is created. The first message is `Fixture files are not written into a project evidence database.`

The leaf below uses missing-fragment percentage `0`, edge erosion `0`, rotation `0`, lighting variation `0`, and random seed `3`. The same parameters write the same page bytes. These synthetic images are segmented at foreground threshold `1`.

Stdout of each command below is one JSON object, with sorted keys and no insignificant whitespace. Pipe that stdout through `uv run python -m json.tool` when you want to read it. `prw --help` is plain text.

## 1. See the commands

```bash
uv run prw --help
```

The help text names these thirteen commands: `agree`, `assemble`, `assembly-rank`, `edge`, `frame`, `generate`, `join-presence`, `placement-error`, `provenance`, `rank`, `recall`, `segment`, `verify`.

## 2. Generate a synthetic leaf

```bash
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

Exit `0`. `provenance.algorithm_name` is `synthetic_tear`. `provenance.random_seed` is `3`. `provenance.parameter_hash` starts with `sha256:`. The `images` array includes an object with `name` `page.tif` and `role` `page`.

These paths exist afterward:

- `$IMAGES/page.tif`
- `$IMAGES/image_manifest.json`
- four `$IMAGES/fragment-*.tif` files
- `$BENCHMARKS/labels.json`
- `$BENCHMARKS/provenance.json`

`$BENCHMARKS/manifest.json` does not exist. `$DEMO/originals` does not exist.

`labels.json` is the BenchmarkLabel store. Leave it unread as a judge of a printed ranking. The report commands below are the comparison, and each one writes a new file beside that store.

Bind the page, two fragment files, and their recorded hashes. The walkthrough uses the first and third fragment names in sorted order:

```bash
eval "$(uv run python - <<'PY'
import json
import os
import shlex
from pathlib import Path

images = Path(os.environ["IMAGES"])
manifest = json.loads((images / "image_manifest.json").read_text())
entries = manifest["images"]
page = next(item for item in entries if item["role"] == "page")
fragments = sorted(
    (item for item in entries if item["role"] == "fragment"),
    key=lambda item: item["name"],
)
if len(fragments) != 4:
    raise SystemExit("These parameters write four fragment files.")
chosen = (fragments[0], fragments[2])

def emit(name: str, value: object) -> None:
    print(f"{name}={shlex.quote(str(value))}")

emit("PAGE", images / page["name"])
emit("PAGE_HASH", page["content_hash"])
emit("PAGE_BYTES", page["byte_length"])
emit("PIECE_A", images / chosen[0]["name"])
emit("PIECE_B", images / chosen[1]["name"])
emit("PIECE_A_HASH", chosen[0]["content_hash"])
emit("PIECE_B_HASH", chosen[1]["content_hash"])
emit("PIECE_A_ID", chosen[0]["fragment_id"])
emit("PIECE_B_ID", chosen[1]["fragment_id"])
PY
)"
```

`PIECE_A_ID` and `PIECE_B_ID` are the fixture fragment ids from the manifest. They are the ids in the file names `fragment-<id>.tif`.

## 3. Verify a source image

Match the recorded page hash:

```bash
uv run prw verify "$PAGE" --expected "$PAGE_HASH"
```

Exit `0`. `record` is `VerifiedBytes`. `content_hash` equals `$PAGE_HASH`. `byte_length` equals `$PAGE_BYTES`. `media_type` is `image/tiff`.

A different expected hash prints a completed failure and leaves the TIFF bytes in place:

```bash
uv run prw verify "$PAGE" --expected "sha256:abababababababababababababababababababababababababababababababab"
uv run python -c 'import hashlib, sys; from pathlib import Path; print("sha256:" + hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())' "$PAGE"
```

The verify process exits `1`. `record` is `IntegrityFailure`. `presented_hash` equals `$PAGE_HASH`. `expected_hash` is the digest you passed. The Python line prints `$PAGE_HASH` again. `IntegrityFailure` `id` and `timestamp` change on every mismatch. Compare the two hashes.

A file that is not a TIFF is a different failure:

```bash
printf 'not-a-tiff\n' > "$DEMO/not-a-tiff.txt"
uv run prw verify "$DEMO/not-a-tiff.txt"
```

Exit `1`. `record` is `UnsupportedMediaType`. `byte_length` is `11`.

A path that is not in the image directory exits `2`, prints no JSON, and lists the fragment file names from the sibling manifest. `fragment-0.tif` is not a generated name:

```bash
uv run prw verify "$IMAGES/fragment-0.tif"
```

Stderr contains that path and the text `Fragment files:`.

## 4. Segment a fragment

Pixel outline:

```bash
uv run prw segment "$PIECE_A" \
  --label shelf-4 \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --expected "$PIECE_A_HASH"
```

Exit `0`. `record` is `FragmentOutlineRevision`. `epistemic_class` is `interpretation`. `producer` is `machine`. `frame` is `source_pixels`. `polygon` has at least three positions. `envelope.algorithm_name` is `fragment_outline`. `envelope.algorithm_version` is `1`. `envelope.model_hash` is `absent`. The envelope omits `random_seed`. The label `shelf-4` is a name for this call. It is not a field of the printed outline.

The same file in millimetres. Supply `--pixels-per-mm` and `--uncertainty` together:

```bash
uv run prw segment "$PIECE_A" \
  --label shelf-4 \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --expected "$PIECE_A_HASH" \
  --pixels-per-mm 10 \
  --uncertainty 0.1
```

Exit `0`. `frame` is `fragment_local_mm`. `epistemic_class` is `interpretation`. `producer` is `machine`. `envelope.algorithm_name` is `caller_supplied_scale`.

One scale flag without the other exits `2`. Stdout is empty. Stderr contains `pixels_per_mm and uncertainty are supplied together.`

A checksum mismatch prints `IntegrityFailure` and no polygon:

```bash
uv run prw segment "$PIECE_A" \
  --label shelf-4 \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --expected "sha256:abababababababababababababababababababababababababababababababab"
```

Exit `1`. `record` is `IntegrityFailure`. The object has no `polygon` key.

## 5. Name a millimetre frame

This command reads no image. The square is four vertices in order:

```bash
uv run prw frame --polygon 0,0 2,0 2,2 0,2
```

Exit `0`. `kind` is `fragment_local_mm`. `origin` is `[1.0, 1.0]`. `axis_x_direction` is `+x right`. `axis_y_direction` is `+y down`. `unit` is `mm`. `origin_description` is `first-outline centroid`.

## 6. Trace chord edges

```bash
uv run prw edge "$PIECE_A" \
  --label shelf-4 \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1
```

Exit `0`. `record` is `ChordEdges`. `edges` is non-empty. Each `epistemic_class` is `interpretation`. `envelope.algorithm_name` is `edge_chord`. `envelope.model_hash` is `absent`. The envelope omits `random_seed`.

The same command without the scale pair exits `1`. `record` is `FailedEdgeChord`. `status` is `failed`.

## 7. Rank joins

A pool image is one repeated flag: `--image LABEL PATH`. The label is a name you choose for this invocation. Pass two different fragment files:

```bash
uv run prw rank \
  --image piece-a "$PIECE_A" \
  --image piece-b "$PIECE_B" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1
```

Exit `0`. `record` is `physical_join_order`. This leaf and this pair print 32 joins. Each `score` is less than or equal to the previous score. Every `epistemic_class` is `hypothesis`. Every `channel` is `physical`. `envelope.algorithm_name` is `pairwise_rigid_join`. The envelope omits `random_seed`. The first row is the highest physical score in this list. It is a hypothesis.

`$BENCHMARKS/labels.json` is byte-identical to the file `generate` wrote.

Omit the scale pair and the process exits `1` with `record` `FailedPairwiseJoin` and `status` `failed`. That object has no `joins` key. Passing the label file as an image exits `2`, prints no JSON, and writes `A BenchmarkLabel join file is not a rank path.` on stderr:

```bash
uv run prw rank \
  --image piece-a "$BENCHMARKS/labels.json" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1
```

## 8. Write join recall

Recall writes a new report under the benchmarks directory. It reads `labels.json` only for that comparison. `--k` is the prefix length you declare before the run.

Map each pool label to the fixture fragment id from the manifest. The label is the same word you passed to `--image`:

```bash
uv run prw recall \
  --image piece-a "$PIECE_A" \
  --image piece-b "$PIECE_B" \
  --benchmarks "$BENCHMARKS" \
  --k 1 \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1 \
  --correspondence "piece-a=$PIECE_A_ID" \
  --correspondence "piece-b=$PIECE_B_ID"
```

Exit `0`. `k` is `1`. `metric` is `join_recall_at_k`. `algorithm_name` is `pairwise_rigid_join`. `recall` is `0.0`. `recall_list` has four entries, and every `status` is `absent`. `reference` is `frozen kind: join row`. `does_not_measure` is `a historical join on real parchment`. `previous_report` is `absent` on the first report. The new file is `$BENCHMARKS/join_recall/join-recall-0001.json`. `labels.json` and `provenance.json` are byte-identical to the files `generate` wrote. The TIFF files are unchanged.

`recall` is the fraction of frozen synthetic joins that appear in the top K. These two fragment files are not one of those frozen pairs, so the fraction is zero. That zero is the measurement for this pool.

A later recall writes `$BENCHMARKS/join_recall/join-recall-0002.json` and leaves `join-recall-0001.json` in place.

Omit `--correspondence` and the report is still written. Every `status` is `absent` and `recall` is `0.0`, because the ranked ids were not mapped onto the fixture ids. The mapped command above also prints `0.0`, because this pair is not a frozen join.

## 9. Search assemblies

Assembly search uses the same pool flags, a predeclared N, two pose tolerances, a minimum edge length, and a page rectangle in millimetres:

```bash
uv run prw assemble \
  --image piece-a "$PIECE_A" \
  --image piece-b "$PIECE_B" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1 \
  --minimum-edge-length-mm 6 \
  --n 2 \
  --translation-tolerance-mm 1 \
  --rotation-tolerance-radians 1 \
  --min-width-mm 0 \
  --max-width-mm 1000 \
  --min-height-mm 0 \
  --max-height-mm 1000
```

Exit `0`. `record` is `AssemblySearch`. This leaf and this pair keep two assemblies. `screening` is non-empty, and each event has `gate` `physical`. `envelope.algorithm_name` is `rigid_assembly_search`. `labels.json` stays byte-identical.

The same command without `--n` exits `1`. `record` is `FailedAssemblySearch`. `status` is `failed`. The object has no `assemblies` key. Omitting the four page-bound flags does the same.

Rank the assemblies that the search kept, in the physical channel:

```bash
uv run prw assembly-rank \
  --image piece-a "$PIECE_A" \
  --image piece-b "$PIECE_B" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1 \
  --minimum-edge-length-mm 6 \
  --n 2 \
  --translation-tolerance-mm 1 \
  --rotation-tolerance-radians 1 \
  --min-width-mm 0 \
  --max-width-mm 1000 \
  --min-height-mm 0 \
  --max-height-mm 1000
```

Exit `0`. `record` is `physical_assembly_order`. `assemblies` has the same two rows, in physical order. Scores do not increase as you go down the list. Every `epistemic_class` is `hypothesis`. `envelope.algorithm_name` is `rigid_assembly_search`.

## 10. Write assembly reports

Add `--benchmarks` to the assembly flags. Placement error and end-to-end join presence each write one new file:

```bash
uv run prw placement-error \
  --image piece-a "$PIECE_A" \
  --image piece-b "$PIECE_B" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1 \
  --minimum-edge-length-mm 6 \
  --n 2 \
  --translation-tolerance-mm 1 \
  --rotation-tolerance-radians 1 \
  --min-width-mm 0 \
  --max-width-mm 1000 \
  --min-height-mm 0 \
  --max-height-mm 1000 \
  --benchmarks "$BENCHMARKS"

uv run prw join-presence \
  --image piece-a "$PIECE_A" \
  --image piece-b "$PIECE_B" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 10 \
  --uncertainty 0.1 \
  --minimum-edge-length-mm 6 \
  --n 2 \
  --translation-tolerance-mm 1 \
  --rotation-tolerance-radians 1 \
  --min-width-mm 0 \
  --max-width-mm 1000 \
  --min-height-mm 0 \
  --max-height-mm 1000 \
  --benchmarks "$BENCHMARKS"
```

Both exit `0`. The placement report has `metric` `placement_error`, `n` `2`, `reference` `frozen kind: placement row`, and `does_not_measure` `warped or shrunken real parchment`. Its file is `$BENCHMARKS/placement_error/placement-error-0001.json`.

The join-presence report has `metric` `assembly_join_presence`, `n` `2`, `reference` `frozen kind: join row`, and `does_not_measure` `a historical join on real parchment`. Its file is `$BENCHMARKS/assembly_join_presence/assembly-join-presence-0001.json`.

On each first report, `previous_report` is `absent`. `labels.json`, `provenance.json`, and the TIFF files stay byte-identical. Neither command creates `$DEMO/originals` or `$BENCHMARKS/manifest.json`.

## 11. Print a provenance envelope

A deterministic call omits `random_seed`:

```bash
uv run prw provenance \
  --algorithm-name demo \
  --algorithm-version 1 \
  --code-version "$CODE" \
  --parameter edge_erosion=0.25
```

Exit `0`. The object omits `random_seed`. `parameter_hash` starts with `sha256:`. `parameter_blob` is `{"edge_erosion":0.25}`. `model_hash`, `decoder_name`, and `decoder_version` are `absent`. `source_hashes` is `[]`. `code_version` equals `$CODE`.

Run the same command again. The second stdout matches the first, including `id`.

`--parameter` takes one `name=json` value. `edge_erosion=0.25` is a JSON number. `edge_erosion="0.25"` is a JSON string. `edge_erosion=quarter` exits `2` with an empty stdout and stderr `A parameter value is JSON.`

Add `--random-seed 7` when the algorithm used randomness. That envelope records `random_seed` `7`, and its stdout differs from the deterministic envelope.

## Exit codes

| Exit | Meaning |
| --- | --- |
| `0` | A result JSON object. |
| `1` | A completed failure record: `IntegrityFailure`, `UnsupportedMediaType`, `FailedEdgeChord`, `FailedPairwiseJoin`, or `FailedAssemblySearch`. |
| `2` | A usage error. Stdout is empty. Stderr is the message, with no traceback. |

## Further command

`prw agree` scores a segmented outline against a polygon you supply. Repeat `--reference X,Y` for each vertex. `--frame` must be the frame of that segmentation: `source_pixels`, or `fragment_local_mm` when you also pass the scale pair. The other flags match `segment`: the TIFF path, `--label`, `--foreground-threshold`, `--code-version`, and an optional `--expected` hash. The report is a new file under `$BENCHMARKS/outline_agreement/`. `labels.json` stays unchanged.

`generate` does not print a reference polygon. This guide does not supply coordinates. A polygon you pass is your reference for that report.

Run `uv run prw agree --help` for the flag list.

## What this build leaves for later

[Roadmap](ROADMAP.md) phases after the current CLI are still ahead:

- Ancient Greek HTR, and the `language` score channel.
- The Qt validation window. Detection, search, and later HTR are specified to run off the UI thread. This build has no window.
- Scholarly export.
- A stored project. The CLI does not write `manifest.json` or `originals/`.

Human outline correction is a stored record in [ADR-0013](adr/0013-human-outline-correction.md). This CLI has no command that writes one. Validation decisions are specified in the [product requirements](PRD.md). This CLI has no command that records accept, reject, or defer.

## When you are done

Remove the disposable directory:

```bash
rm -rf "$DEMO"
```

Design documents, in the order the repository lists them, start at the [README](../README.md#reading-order).
