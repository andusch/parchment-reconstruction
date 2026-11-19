# Ragged synthetic demo

- Status: Working note. One synthetic leaf with non-zero edge erosion, rotation, and lighting variation. The measured record is join recall at K=1 and K=3, and placement error at N=2.
- Algorithms: `synthetic_tear` version `1`, `edge_chord` version `1`, `pairwise_rigid_join` version `1`, and `rigid_assembly_search` version `1`, as of commit `1989e7766792018b7b878b277e38da6bf4dfd13e` (merge of PR #31).
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)
- Evaluation: [EVALUATION.md](EVALUATION.md)

The leaf is synthetic. The program generates it. Nothing is downloaded. The Cleveland `1999.137` cuttings are not inputs, and this note does not treat them as torn mates. [Q-SCI-15](EVALUATION.md#q-sci-15) stays open. These numbers are a synthetic-fixture result. They do not measure a historical join on real parchment. `400` ppi stays a claim. These commands do not pass `--claimed-ppi`.

A row in `physical_join_order` is a hypothesis. Rank 1 is the highest physical score in that list. It is a hypothesis. This note does not name a reconstruction.

## One command

From the checkout root, with [uv](https://docs.astral.sh/uv/) on `PATH`:

```bash
./samples/ragged-leaf/run.sh
```

That writes `${TMPDIR:-/tmp}/prw-ragged-leaf/`. Pass another empty directory outside the checkout as the first argument. A path inside the checkout, a path whose components include `originals`, `observations`, `runs`, `validations`, `exports`, `data`, `scans`, or `real_data`, or a destination that already contains a file, exits `2` before `generate` runs. Stdout is empty on that refusal.

The script's exit code is `0` when every `prw` command below exits `0` and `labels.json` is byte-identical after scoring. A label-byte change exits `1`.

Stdout names the checkout SHA and the code version passed to `prw`. The default code version is `1989e7766792018b7b878b277e38da6bf4dfd13e`. Set `PRW_CODE_VERSION` to pass a different string. The measured record below is for the default string.

Hypothesis ids include that string. Equal physical scores are ordered by those ids. Passing another string can change which tied join is rank 1 and can change the placement RMSE list. Remeasure and replace the record when `src/prw` differs from that commit.

## Parameters, frozen before scoring

| Parameter | Value |
| --- | --- |
| `--missing-fragment-percentage` | `0` |
| `--edge-erosion` | `0.15` |
| `--rotation` | `0.3` |
| `--lighting-variation` | `0.25` |
| `--random-seed` | `3` |
| `--foreground-threshold` | `1` |
| `--pixels-per-mm` | `1` |
| `--uncertainty` | `0.1` |
| `--minimum-edge-length-mm` on `rank`, `recall`, `placement-error`, and `assembly-rank` | `6` |
| `--k` | `1`, then `3` |
| `--n` | `2` |
| `--translation-tolerance-mm` | `1` |
| `--rotation-tolerance-radians` | `1` |
| Page bounds, millimetres | width `0` to `1000`, height `0` to `1000` |

`generate` writes `benchmarks/labels.json` and `benchmarks/provenance.json`. The script copies both to `$DEST/frozen/` before `rank`, `recall`, `placement-error`, and `assembly-rank`. Those later commands read `labels.json` only inside `recall` and `placement-error`, which are the comparison commands. `rank` and `assembly-rank` do not read it. After scoring, the script compares the bytes. The freeze identifier is the `sha256:` digest of `labels.json`.

The generator's scale is `1` millimetre per pixel, so `--pixels-per-mm` is `1`. `--uncertainty 0.1` is the caller-supplied uncertainty. It is not a scale the algorithm recovered. K and N were fixed before the reports in the measured record were written.

`prw edge` with `--minimum-edge-length-mm 0` runs before those reports. On this leaf each fragment has 106 to 112 chords. One chord on each fragment is 15 or 16 mm. Every other chord is shorter than 6 mm. Assembly search enumerates every subset of admitted joins, so the unfiltered chord set is not a search this command can finish. The minimum stays `6` mm, the value the assembly walkthrough already uses, applied here at the generator scale. It was not changed after recall or placement error was known.

Missing-fragment percentage `0` keeps all four pieces. The label file has four `kind: join` rows. A missing fragment would be an omitted piece of the page. It would not be grapheme status `missing`.

## Commands

`CODE` below is the default code version. `DEST` is a new empty directory. Each `prw` command exits `0`. Stdout is one JSON object. Use a destination path with no spaces. The `eval` lines split on spaces. `samples/ragged-leaf/run.sh` quotes its arguments and is the command to run when the path may contain spaces.

```bash
export CODE DEST
CODE=1989e7766792018b7b878b277e38da6bf4dfd13e
DEST="${TMPDIR:-/tmp}/prw-ragged-leaf-hand"
mkdir -p "$DEST"

uv run prw generate \
  --benchmarks "$DEST/benchmarks" \
  --images "$DEST/images" \
  --missing-fragment-percentage 0 \
  --edge-erosion 0.15 \
  --rotation 0.3 \
  --lighting-variation 0.25 \
  --random-seed 3 \
  --code-version "$CODE"
```

Exit `0`. `provenance.algorithm_name` is `synthetic_tear`. `provenance.algorithm_version` is `1`. `provenance.random_seed` is `3`. `provenance.parameter_blob` is `{"edge_erosion":0.15,"lighting_variation":0.25,"missing_fragment_percentage":0.0,"rotation":0.3}`. `provenance.parameter_hash` is `sha256:fb1cae07ef9d8c8558acd9bec77a8c3ede97637785567ff6c48fdfaa567c86cb`. `provenance.decoder_name` is `synthetic_uncompressed_tiff`. `provenance.decoder_version` is `1`. `provenance.model_hash` is `absent`.

Copy the label file, then bind the four fragment files. The pool label is the fixture fragment id from the manifest. The correspondence uses that same id on both sides. `recall` maps the project fragment id created for that label onto the fixture id. The project id is not the fixture id.

```bash
mkdir -p "$DEST/frozen"
cp "$DEST/benchmarks/labels.json" "$DEST/frozen/labels.json"
cp "$DEST/benchmarks/provenance.json" "$DEST/frozen/provenance.json"

eval "$(DEST="$DEST" uv run python - <<'PY'
import json
import os
import shlex
from pathlib import Path

dest = Path(os.environ["DEST"])
manifest = json.loads((dest / "images" / "image_manifest.json").read_text())
fragments = [item for item in manifest["images"] if item["role"] == "fragment"]
if len(fragments) != 4:
    raise SystemExit("These parameters write four fragment files.")
images = []
correspondence = []
for item in fragments:
    fixture_id = str(item["fragment_id"])
    path = dest / "images" / item["name"]
    images.extend(["--image", fixture_id, str(path)])
    correspondence.extend(["--correspondence", f"{fixture_id}={fixture_id}"])

def emit(name: str, args: list[str]) -> None:
    print(f"{name}={shlex.quote(' '.join(shlex.quote(arg) for arg in args))}")

emit("IMAGES", images)
emit("CORR", correspondence)
PY
)"
```

Edge census, minimum length `0`. Exit `0` for each file. `record` is `ChordEdges`.

```bash
eval "set -- $IMAGES"
uv run prw edge "$3" --label "$2" --foreground-threshold 1 \
  --code-version "$CODE" --pixels-per-mm 1 --uncertainty 0.1 \
  --minimum-edge-length-mm 0
uv run prw edge "$6" --label "$5" --foreground-threshold 1 \
  --code-version "$CODE" --pixels-per-mm 1 --uncertainty 0.1 \
  --minimum-edge-length-mm 0
uv run prw edge "$9" --label "$8" --foreground-threshold 1 \
  --code-version "$CODE" --pixels-per-mm 1 --uncertainty 0.1 \
  --minimum-edge-length-mm 0
uv run prw edge "$12" --label "$11" --foreground-threshold 1 \
  --code-version "$CODE" --pixels-per-mm 1 --uncertainty 0.1 \
  --minimum-edge-length-mm 0
```

Rank, then recall, then placement error, then assembly rank:

```bash
eval "set -- $IMAGES"
uv run prw rank "$@" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 1 \
  --uncertainty 0.1 \
  --minimum-edge-length-mm 6

eval "set -- $IMAGES $CORR"
uv run prw recall "$@" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 1 \
  --uncertainty 0.1 \
  --minimum-edge-length-mm 6 \
  --benchmarks "$DEST/benchmarks" \
  --k 1

uv run prw recall "$@" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 1 \
  --uncertainty 0.1 \
  --minimum-edge-length-mm 6 \
  --benchmarks "$DEST/benchmarks" \
  --k 3

uv run prw placement-error "$@" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 1 \
  --uncertainty 0.1 \
  --minimum-edge-length-mm 6 \
  --benchmarks "$DEST/benchmarks" \
  --n 2 \
  --translation-tolerance-mm 1 \
  --rotation-tolerance-radians 1 \
  --min-width-mm 0 \
  --max-width-mm 1000 \
  --min-height-mm 0 \
  --max-height-mm 1000

eval "set -- $IMAGES"
uv run prw assembly-rank "$@" \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --pixels-per-mm 1 \
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

Exit `0` for each command. `rank` prints `record` `physical_join_order`. `recall` writes `$DEST/benchmarks/join_recall/join-recall-0001.json` and then `join-recall-0002.json`. `placement-error` writes `$DEST/benchmarks/placement_error/placement-error-0001.json`. `assembly-rank` prints `record` `physical_assembly_order` and writes no report file.

`cmp` of `$DEST/frozen/labels.json` and `$DEST/benchmarks/labels.json` reports no difference. The same is true of `provenance.json`. The TIFF bytes and `image_manifest.json` are unchanged. `$DEST/benchmarks/manifest.json` does not exist. `$DEST/originals` does not exist.

The first recall report has `previous_report` `absent`. This fixture had no earlier join-recall file. The second report's `previous_report` is `join-recall-0001.json`. The placement report's `previous_report` is `absent`. There is no earlier placement-error file on this fixture.

## Measured record

The script prints this object on the `record` line when `code_version` is the default. Image files stay in `$DEST/images/` and are not committed.

```json
{
  "assembly_rank": [
    {
      "channel": "physical",
      "epistemic_class": "hypothesis",
      "fixture_fragment_ids": [
        "486d4093-d4a4-5cb2-88e2-8e0987316ed5",
        "a739e88b-81cd-5678-a266-4b8fb4fe6b9c"
      ],
      "score": -1.0
    },
    {
      "channel": "physical",
      "epistemic_class": "hypothesis",
      "fixture_fragment_ids": [
        "a739e88b-81cd-5678-a266-4b8fb4fe6b9c",
        "f42a0d5c-25a4-5358-8d70-d1619f920839"
      ],
      "score": -1.0
    }
  ],
  "chord_count_at_minimum_0": {
    "486d4093-d4a4-5cb2-88e2-8e0987316ed5": 112,
    "96ec4566-67eb-5ba6-be11-29b71e58fd06": 106,
    "a739e88b-81cd-5678-a266-4b8fb4fe6b9c": 107,
    "f42a0d5c-25a4-5358-8d70-d1619f920839": 112
  },
  "decoder_name": "synthetic_uncompressed_tiff",
  "decoder_version": "1",
  "generator_algorithm_name": "synthetic_tear",
  "generator_algorithm_version": "1",
  "generator_parameter_blob": "{\"edge_erosion\":0.15,\"lighting_variation\":0.25,\"missing_fragment_percentage\":0.0,\"rotation\":0.3}",
  "generator_parameter_hash": "sha256:fb1cae07ef9d8c8558acd9bec77a8c3ede97637785567ff6c48fdfaa567c86cb",
  "images": [
    {
      "byte_length": 14122,
      "content_hash": "sha256:734beb89077706044883ae7e1d1d9954caf4e49b3fc926946bd7366d8764f267",
      "height": 140,
      "name": "page.tif",
      "role": "page",
      "width": 100
    },
    {
      "byte_length": 3710,
      "content_hash": "sha256:2b90816cb6d6286d67deb05effea388328e0af6404cd49696537a70052937a17",
      "height": 69,
      "name": "fragment-96ec4566-67eb-5ba6-be11-29b71e58fd06.tif",
      "role": "fragment",
      "width": 52
    },
    {
      "byte_length": 4042,
      "content_hash": "sha256:033220bd0a9831b373c5f39082e760a6ac6f044bee7e2fc82430bd57072bde4d",
      "height": 70,
      "name": "fragment-f42a0d5c-25a4-5358-8d70-d1619f920839.tif",
      "role": "fragment",
      "width": 56
    },
    {
      "byte_length": 3658,
      "content_hash": "sha256:40958b854251051de241547ac134c44c261dbfc88bab20233d55f5e9ddc0fb1c",
      "height": 68,
      "name": "fragment-a739e88b-81cd-5678-a266-4b8fb4fe6b9c.tif",
      "role": "fragment",
      "width": 52
    },
    {
      "byte_length": 3986,
      "content_hash": "sha256:e8456c78fc6fefa9da11f83d068a359df34cf75908b5dc266718806f9545a96c",
      "height": 69,
      "name": "fragment-486d4093-d4a4-5cb2-88e2-8e0987316ed5.tif",
      "role": "fragment",
      "width": 56
    }
  ],
  "join_count": 12,
  "label_file_hash": "sha256:a837cb997ea892862275e853fa21c2e0172b34495f56e65ee8a17a6f381d48ac",
  "labels_unchanged": true,
  "model_hash": "absent",
  "placement_algorithm_name": "rigid_assembly_search",
  "placement_algorithm_version": "1",
  "placement_n": 2,
  "placement_page_origin": "minimum_corner",
  "placement_parameter_hash": "sha256:405bd27ccae86aa684151a0b628d34afb0e900fc093e48632195786e5f2cddb0",
  "placement_previous_report": "absent",
  "placement_rmse_mm": [
    60.391038285989595,
    90.98557180260953,
    54.39613642940002,
    90.98557180260954
  ],
  "placement_scored_assemblies": [
    {
      "fixture_fragment_ids": [
        "486d4093-d4a4-5cb2-88e2-8e0987316ed5",
        "a739e88b-81cd-5678-a266-4b8fb4fe6b9c"
      ],
      "frozen_join": true,
      "rmse_mm": [
        60.391038285989595,
        90.98557180260953
      ]
    },
    {
      "fixture_fragment_ids": [
        "a739e88b-81cd-5678-a266-4b8fb4fe6b9c",
        "f42a0d5c-25a4-5358-8d70-d1619f920839"
      ],
      "frozen_join": false,
      "rmse_mm": [
        54.39613642940002,
        90.98557180260954
      ]
    }
  ],
  "placement_scored_pairs_are_frozen_joins": false,
  "placement_unplaced_count": 4,
  "random_seed": 3,
  "rank_1_fixture_fragment_ids": [
    "486d4093-d4a4-5cb2-88e2-8e0987316ed5",
    "f42a0d5c-25a4-5358-8d70-d1619f920839"
  ],
  "rank_1_is_frozen_join": true,
  "rank_1_score": 0.0,
  "rank_algorithm_name": "pairwise_rigid_join",
  "rank_algorithm_version": "1",
  "rank_channel": "physical",
  "rank_epistemic_class": "hypothesis",
  "rank_parameter_hash": "sha256:fc32c1d4d03761ecc94b6c0f1dec7594760af56b9349fa3d2a98c2d67dc96b82",
  "rank_scores": [
    0.0,
    0.0,
    0.0,
    0.0,
    -1.0,
    -1.0,
    -1.0,
    -1.0,
    -1.0,
    -1.0,
    -1.0,
    -1.0
  ],
  "recall_algorithm_name": "pairwise_rigid_join",
  "recall_algorithm_version": "1",
  "recall_at_1": 0.25,
  "recall_at_1_is_1": false,
  "recall_at_1_previous_report": "absent",
  "recall_at_1_status": [
    {
      "id": "6f5b0df5-3e56-5028-b283-e22aa0009db3",
      "status": "absent"
    },
    {
      "id": "719df390-2c7b-5e85-a27b-6419e6187ba7",
      "status": "present"
    },
    {
      "id": "8f61ea40-e4e9-509e-a6ed-48fdd2d0064e",
      "status": "absent"
    },
    {
      "id": "c4a29850-b170-575b-80f1-57049eb67782",
      "status": "absent"
    }
  ],
  "recall_at_3": 0.5,
  "recall_at_3_previous_report": "join-recall-0001.json",
  "recall_at_3_status": [
    {
      "id": "6f5b0df5-3e56-5028-b283-e22aa0009db3",
      "status": "absent"
    },
    {
      "id": "719df390-2c7b-5e85-a27b-6419e6187ba7",
      "status": "present"
    },
    {
      "id": "8f61ea40-e4e9-509e-a6ed-48fdd2d0064e",
      "status": "present"
    },
    {
      "id": "c4a29850-b170-575b-80f1-57049eb67782",
      "status": "absent"
    }
  ],
  "recall_parameter_hash": "sha256:fc32c1d4d03761ecc94b6c0f1dec7594760af56b9349fa3d2a98c2d67dc96b82",
  "score_name": "negative_absolute_length_difference",
  "surviving_chord_mm": {
    "486d4093-d4a4-5cb2-88e2-8e0987316ed5": 15.0,
    "96ec4566-67eb-5ba6-be11-29b71e58fd06": 16.0,
    "a739e88b-81cd-5678-a266-4b8fb4fe6b9c": 16.0,
    "f42a0d5c-25a4-5358-8d70-d1619f920839": 15.0
  }
}
```

## Reading the record

Join recall at 1 is `0.25`. Join recall at 3 is `0.5`. `recall_at_1_is_1` is false. Recall at 1 is the fraction of the four frozen joins that appear in the top 1 of the `physical` channel. One frozen join is present, so the fraction is `0.25`. Recall at 3 is two of the four, so the fraction is `0.5`.

The present row at K=1 is `719df390-2c7b-5e85-a27b-6419e6187ba7`. Its fixture fragments are `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `f42a0d5c-25a4-5358-8d70-d1619f920839`. Rank 1 is that pair. `rank_1_score` is `0.0`. `rank_channel` is `physical`. `rank_epistemic_class` is `hypothesis`. `score_name` is `negative_absolute_length_difference`. The twelve scores are four `0.0` values followed by eight `-1.0` values.

`8f61ea40-e4e9-509e-a6ed-48fdd2d0064e` is the other score-`0.0` frozen join, fragments `96ec4566-67eb-5ba6-be11-29b71e58fd06` and `a739e88b-81cd-5678-a266-4b8fb4fe6b9c`. It is present at K=3 and absent at K=1. The surviving chords on those two pairs are 15 mm with 15 mm, and 16 mm with 16 mm.

The channel that this recall measures is `physical`. The score in the join envelope is `negative_absolute_length_difference`. This run leaves `htr` uncomputed and leaves `language` uncomputed.

The other two frozen joins, `6f5b0df5-3e56-5028-b283-e22aa0009db3` and `c4a29850-b170-575b-80f1-57049eb67782`, have physical score `-1.0`. The two fragment pairs with no frozen join row also have physical score `-1.0`. Erosion moves each vertex toward that fragment's centroid, so the two sides of a cut can leave the 6 mm census with lengths that differ by 1 mm. The length-difference score then ties those frozen joins with the pairs that have no frozen join row. That is the `physical` failure for recall at 1. Top 1 can hold one fragment pair, and this leaf has four frozen joins, so a single present join is the fraction `0.25`.

Placement error at N=2 lists four scored RMSE values, in report order: `60.391038285989595`, `90.98557180260953`, `54.39613642940002`, and `90.98557180260954` page millimetres. Four rows are `unplaced` and carry no RMSE. `placement_page_origin` is `minimum_corner`. The report states that the error includes the difference between that page-origin rule and the generator's absolute rotation. `does_not_measure` on the report is warped or shrunken real parchment. [Q-SCI-03](ALGORITHM.md#q-sci-03), [Q-SCI-15](EVALUATION.md#q-sci-15), and [Q-SCI-20](ALGORITHM.md#q-sci-20) stay open.

Both kept assemblies are hypotheses on the `physical` channel with score `-1.0`. The first places `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `a739e88b-81cd-5678-a266-4b8fb4fe6b9c`, which is frozen join `c4a29850-b170-575b-80f1-57049eb67782`, absent from recall at 3. The second places `a739e88b-81cd-5678-a266-4b8fb4fe6b9c` and `f42a0d5c-25a4-5358-8d70-d1619f920839`, which has no frozen join row. Rank 1's fragment pair is not the pair in either assembly. `placement_scored_pairs_are_frozen_joins` is false.

Lighting variation `0.25` is in the generator parameter blob and in the image hashes. Foreground threshold `1` keeps every painted sample of this leaf, so the outline census is the painted support. The physical score reads chord length.

Rotation `0.3` radians is what breaks each side into the short runs counted above. The 6 mm minimum keeps one chord per fragment. The physical channel scores those four chords.
