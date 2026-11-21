# Ragged synthetic demo

- Status: Working note. One synthetic leaf with non-zero edge erosion, rotation, and lighting variation. The measured record is join recall at K=1 and K=3, and placement error at N=2.
- Algorithms: `synthetic_tear` version `1`, `edge_chord` version `1`, `pairwise_rigid_join` version `1`, and `rigid_assembly_search` version `1`. The length-difference record is commit `1989e7766792018b7b878b277e38da6bf4dfd13e` (merge of PR #31). The curve-and-overlap record is commit `8a6c2e569ed8107cd47848e29005e528ec397a8e`. `git rev-parse 8a6c2e569ed8107cd47848e29005e528ec397a8e:src/prw` is `f18269ba46ce7c03c9d79cc6cb15da92b7702b3f`. The exterior-side record is commit `2fe603838c5e160c3a1e3d6a65a3d487d8f1b28b`. `git rev-parse 2fe603838c5e160c3a1e3d6a65a3d487d8f1b28b:src/prw` is `bd4a0645c85e71186cd6c2bdad51fccf870baf34`. The shared-cut record is commit `5b668f1ffdb78d4fbe5781c09a006038db29ecae`. `git rev-parse 5b668f1ffdb78d4fbe5781c09a006038db29ecae:src/prw` is `b4cc2267b83594f68b9ec884669c0ba57cdfd2c7`.
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

Stdout names the checkout SHA and the code version passed to `prw`. The default code version is `5b668f1ffdb78d4fbe5781c09a006038db29ecae`. Set `PRW_CODE_VERSION` to pass a different string. The measured record below is for the default string. The exterior-side record used `2fe603838c5e160c3a1e3d6a65a3d487d8f1b28b`. The curve-and-overlap record used `8a6c2e569ed8107cd47848e29005e528ec397a8e`. The length-difference record used `1989e7766792018b7b878b277e38da6bf4dfd13e`.

Hypothesis ids include that string. Equal physical scores are ordered by those ids. On this leaf the two best physical scores are both `0.0`, so the order of those two rows follows the hypothesis ids and can change when another string is passed. The other ten scores are distinct. The parameter hashes change with the string. Remeasure when `src/prw` differs from `b4cc2267b83594f68b9ec884669c0ba57cdfd2c7`.

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
CODE=5b668f1ffdb78d4fbe5781c09a006038db29ecae
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

## Previous measured record

This object is what the script printed when `code_version` was `1989e7766792018b7b878b277e38da6bf4dfd13e` and the physical score was `negative_absolute_length_difference`. It is kept so the failure stays visible. The script no longer prints it. Image files stay outside Git.

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

## Reading the previous record

These paragraphs describe the length-difference record above. They are not the script's current output.

Join recall at 1 is `0.25`. Join recall at 3 is `0.5`. `recall_at_1_is_1` is false. Recall at 1 is the fraction of the four frozen joins that appear in the top 1 of the `physical` channel. One frozen join is present, so the fraction is `0.25`. Recall at 3 is two of the four, so the fraction is `0.5`.

The present row at K=1 is `719df390-2c7b-5e85-a27b-6419e6187ba7`. Its fixture fragments are `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `f42a0d5c-25a4-5358-8d70-d1619f920839`. Rank 1 is that pair. `rank_1_score` is `0.0`. `rank_channel` is `physical`. `rank_epistemic_class` is `hypothesis`. `score_name` is `negative_absolute_length_difference`. The twelve scores are four `0.0` values followed by eight `-1.0` values.

`8f61ea40-e4e9-509e-a6ed-48fdd2d0064e` is the other score-`0.0` frozen join, fragments `96ec4566-67eb-5ba6-be11-29b71e58fd06` and `a739e88b-81cd-5678-a266-4b8fb4fe6b9c`. It is present at K=3 and absent at K=1. The surviving chords on those two pairs are 15 mm with 15 mm, and 16 mm with 16 mm.

The channel that this recall measures is `physical`. The score in the join envelope is `negative_absolute_length_difference`. This run leaves `htr` uncomputed and leaves `language` uncomputed.

The other two frozen joins, `6f5b0df5-3e56-5028-b283-e22aa0009db3` and `c4a29850-b170-575b-80f1-57049eb67782`, have physical score `-1.0`. The two fragment pairs with no frozen join row also have physical score `-1.0`. Erosion moves each vertex toward that fragment's centroid, so the two sides of a cut can leave the 6 mm census with lengths that differ by 1 mm. The length-difference score then ties those frozen joins with the pairs that have no frozen join row. That is the `physical` failure for recall at 1. Top 1 can hold one fragment pair, and this leaf has four frozen joins, so a single present join is the fraction `0.25`.

Placement error at N=2 lists four scored RMSE values, in report order: `60.391038285989595`, `90.98557180260953`, `54.39613642940002`, and `90.98557180260954` page millimetres. Four rows are `unplaced` and carry no RMSE. `placement_page_origin` is `minimum_corner`. The report states that the error includes the difference between that page-origin rule and the generator's absolute rotation. `does_not_measure` on the report is warped or shrunken real parchment. [Q-SCI-03](ALGORITHM.md#q-sci-03), [Q-SCI-15](EVALUATION.md#q-sci-15), and [Q-SCI-20](ALGORITHM.md#q-sci-20) stay open.

Both kept assemblies are hypotheses on the `physical` channel with score `-1.0`. The first places `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `a739e88b-81cd-5678-a266-4b8fb4fe6b9c`, which is frozen join `c4a29850-b170-575b-80f1-57049eb67782`, absent from recall at 3. The second places `a739e88b-81cd-5678-a266-4b8fb4fe6b9c` and `f42a0d5c-25a4-5358-8d70-d1619f920839`, which has no frozen join row. Rank 1's fragment pair is not the pair in either assembly. `placement_scored_pairs_are_frozen_joins` is false.

Lighting variation `0.25` is in the generator parameter blob and in the image hashes. Foreground threshold `1` keeps every painted sample of this leaf, so the outline census is the painted support. The physical score reads chord length.

Rotation `0.3` radians is what breaks each side into the short runs counted above. The 6 mm minimum keeps one chord per fragment. The physical channel scores those four chords.

## Curve-and-overlap measured record

This object is what the script printed when `code_version` was `8a6c2e569ed8107cd47848e29005e528ec397a8e` and the stored pose was still the chord alignment. It is kept so that measurement stays visible. The script no longer prints it. Image files stay outside Git.

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
      "score": -2.534184847034281
    },
    {
      "channel": "physical",
      "epistemic_class": "hypothesis",
      "fixture_fragment_ids": [
        "486d4093-d4a4-5cb2-88e2-8e0987316ed5",
        "96ec4566-67eb-5ba6-be11-29b71e58fd06"
      ],
      "score": -3.287256112754977
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
  "placement_parameter_hash": "sha256:06049beaadcbdd38fbdc3b484698ee52cc1a8fd163897986760af0d9b64090a2",
  "placement_previous_report": "absent",
  "placement_rmse_mm": [
    60.391038285989595,
    90.98557180260953,
    55.22061929928718,
    60.39103828598959
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
        "486d4093-d4a4-5cb2-88e2-8e0987316ed5",
        "96ec4566-67eb-5ba6-be11-29b71e58fd06"
      ],
      "frozen_join": false,
      "rmse_mm": [
        55.22061929928718,
        60.39103828598959
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
  "rank_1_score": -1.3307021639425243,
  "rank_algorithm_name": "pairwise_rigid_join",
  "rank_algorithm_version": "1",
  "rank_channel": "physical",
  "rank_epistemic_class": "hypothesis",
  "rank_parameter_hash": "sha256:d20da1a0d6117865f23b5c078044687fe0eab8b70f2b3346c2105edc632d50d1",
  "rank_scores": [
    -1.3307021639425243,
    -1.622827447048656,
    -2.5272957282049,
    -2.534184847034281,
    -3.287256112754977,
    -3.351844452597036,
    -49.02354646604126,
    -49.41495779301704,
    -49.56887903679135,
    -50.11408151802765,
    -50.448573959965486,
    -51.1712077120198
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
  "recall_at_3": 0.75,
  "recall_at_3_previous_report": "join-recall-0001.json",
  "recall_at_3_status": [
    {
      "id": "6f5b0df5-3e56-5028-b283-e22aa0009db3",
      "status": "present"
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
  "recall_parameter_hash": "sha256:d20da1a0d6117865f23b5c078044687fe0eab8b70f2b3346c2105edc632d50d1",
  "score_name": "negative_chord_gap_plus_curve_and_overlap",
  "surviving_chord_mm": {
    "486d4093-d4a4-5cb2-88e2-8e0987316ed5": 15.0,
    "96ec4566-67eb-5ba6-be11-29b71e58fd06": 16.0,
    "a739e88b-81cd-5678-a266-4b8fb4fe6b9c": 16.0,
    "f42a0d5c-25a4-5358-8d70-d1619f920839": 15.0
  }
}
```

## Reading the curve-and-overlap record

These paragraphs describe the curve-and-overlap record above. They are not the script's current output.

Join recall at 1 is `0.25`. Join recall at 3 is `0.75`. `recall_at_1_is_1` is false. Recall at 1 is the fraction of the four frozen joins that appear in the top 1 of the `physical` channel. One frozen join is present, so the fraction is `0.25`. Recall at 3 is three of the four, so the fraction is `0.75`.

The present row at K=1 is `719df390-2c7b-5e85-a27b-6419e6187ba7`. Its fixture fragments are `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `f42a0d5c-25a4-5358-8d70-d1619f920839`. Rank 1 is that pair. `rank_1_score` is `-1.3307021639425243`. `rank_channel` is `physical`. `rank_epistemic_class` is `hypothesis`. `score_name` is `negative_chord_gap_plus_curve_and_overlap`. The twelve scores are distinct. The first six are the separated chord orientations. The last six are the reversed orientations, near `-50`.

`8f61ea40-e4e9-509e-a6ed-48fdd2d0064e` and `6f5b0df5-3e56-5028-b283-e22aa0009db3` are present at K=3 and absent at K=1. `c4a29850-b170-575b-80f1-57049eb67782` is absent at both. That fourth frozen join is rank 4. Its score is `-2.534184847034281`, which is below rank 3 at `-2.5272957282049`. K=3 stops before it.

The channel that this recall measures is `physical`. The score in the join envelope is `negative_chord_gap_plus_curve_and_overlap`. `curve_samples` is `8`. This run leaves `htr` uncomputed and leaves `language` uncomputed.

The chord term is still the absolute length difference of the one chord at or above 6 mm. On this leaf those chords are 15 mm or 16 mm. They are the long axis-aligned runs of the rotated raster, one per fragment, not the two sides of a cut. Erosion scales every side of a fragment by `0.85` about that fragment's centroid, so the two sides of one cut stay the same length in the generator polygon. The 1 mm census gap is the pixel run, not that homothety.

The curve term fits a minimum-area rectangle to each outline and samples each side at 8 equal steps. True neighbors share one recovered side. The closest sides of a diagonal pair differ by about 0.6 mm. The overlap term is the intersection area of those rectangles under the chord pose, divided by the square root of the smaller area. The reversed chord orientation overlaps by about 50 mm of thickness. The separated orientation overlaps by about 1.3 mm to 1.6 mm. That orders the four frozen pairs ahead of the two pairs with no frozen join row.

Recall at 1 stays `0.25` because the prefix of length 1 holds one fragment pair and this leaf has four frozen joins. Recall at 1 is not `1.0` on this metric. K and the label file were not changed to make it so.

Placement error at N=2 lists four scored RMSE values, in report order: `60.391038285989595`, `90.98557180260953`, `55.22061929928718`, and `60.39103828598959` page millimetres. Four rows are `unplaced` and carry no RMSE. `placement_page_origin` is `minimum_corner`. The report states that the error includes the difference between that page-origin rule and the generator's absolute rotation. `does_not_measure` on the report is warped or shrunken real parchment. [Q-SCI-03](ALGORITHM.md#q-sci-03), [Q-SCI-15](EVALUATION.md#q-sci-15), and [Q-SCI-20](ALGORITHM.md#q-sci-20) stay open.

The kept assemblies are hypotheses on the `physical` channel. The first places `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `a739e88b-81cd-5678-a266-4b8fb4fe6b9c`, frozen join `c4a29850-b170-575b-80f1-57049eb67782`, with score `-2.534184847034281`. The second places `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `96ec4566-67eb-5ba6-be11-29b71e58fd06`, which has no frozen join row, with score `-3.287256112754977`. `placement_scored_pairs_are_frozen_joins` is false. Rank 1 is not either assembly. The join pose still aligns the 15 mm and 16 mm chords. Assembly search drops a pose whose raster outlines have positive overlap. The rectangle thickness used in the rank is not that raster test, so the highest join scores are not the assemblies that survive.

Lighting variation `0.25` is in the generator parameter blob and in the image hashes. Foreground threshold `1` keeps every painted sample of this leaf. Rotation `0.3` radians breaks each straight side into short pixel runs. The 6 mm minimum still keeps one chord per fragment. The curve term reads the outline those runs came from.

## Exterior-side measured record

The script prints this object on the `record` line when `code_version` is `2fe603838c5e160c3a1e3d6a65a3d487d8f1b28b`. Image files stay in `$DEST/images/` and are not committed.

```json
{
  "assembly_rank": [
    {
      "channel": "physical",
      "epistemic_class": "hypothesis",
      "fixture_fragment_ids": [
        "486d4093-d4a4-5cb2-88e2-8e0987316ed5",
        "f42a0d5c-25a4-5358-8d70-d1619f920839"
      ],
      "score": 0.0
    },
    {
      "channel": "physical",
      "epistemic_class": "hypothesis",
      "fixture_fragment_ids": [
        "96ec4566-67eb-5ba6-be11-29b71e58fd06",
        "a739e88b-81cd-5678-a266-4b8fb4fe6b9c"
      ],
      "score": 0.0
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
  "placement_parameter_hash": "sha256:72ea3a57a881188dffa8a1aef6f0b23458d4cc9616bfce6f292ea56c7ee77c8f",
  "placement_previous_report": "absent",
  "placement_rmse_mm": [
    72.29919571303537,
    75.97087636887031,
    19.127628841908624,
    17.694371869745904
  ],
  "placement_scored_assemblies": [
    {
      "fixture_fragment_ids": [
        "486d4093-d4a4-5cb2-88e2-8e0987316ed5",
        "f42a0d5c-25a4-5358-8d70-d1619f920839"
      ],
      "frozen_join": true,
      "rmse_mm": [
        72.29919571303537,
        75.97087636887031
      ]
    },
    {
      "fixture_fragment_ids": [
        "96ec4566-67eb-5ba6-be11-29b71e58fd06",
        "a739e88b-81cd-5678-a266-4b8fb4fe6b9c"
      ],
      "frozen_join": true,
      "rmse_mm": [
        19.127628841908624,
        17.694371869745904
      ]
    }
  ],
  "placement_scored_pairs_are_frozen_joins": true,
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
  "rank_parameter_hash": "sha256:208dd26cb23fda5dbf8e39d3dbfad8208f639adf00db8171c7c29c8474a50542",
  "rank_scores": [
    0.0,
    0.0,
    -1.0008409837349252,
    -1.0620163000557326,
    -1.7887320483671032,
    -1.8515893321577614,
    -49.02354646604126,
    -49.41495779301704,
    -49.56887903679135,
    -50.11408151802765,
    -50.448573959965486,
    -51.1712077120198
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
  "recall_at_3": 0.75,
  "recall_at_3_previous_report": "join-recall-0001.json",
  "recall_at_3_status": [
    {
      "id": "6f5b0df5-3e56-5028-b283-e22aa0009db3",
      "status": "present"
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
  "recall_parameter_hash": "sha256:208dd26cb23fda5dbf8e39d3dbfad8208f639adf00db8171c7c29c8474a50542",
  "score_name": "negative_chord_gap_plus_curve_and_overlap",
  "surviving_chord_mm": {
    "486d4093-d4a4-5cb2-88e2-8e0987316ed5": 15.0,
    "96ec4566-67eb-5ba6-be11-29b71e58fd06": 16.0,
    "a739e88b-81cd-5678-a266-4b8fb4fe6b9c": 16.0,
    "f42a0d5c-25a4-5358-8d70-d1619f920839": 15.0
  }
}
```

## Reading the exterior-side record

These paragraphs describe the exterior-side record above. They are not the script's current output.

Join recall at 1 is `0.25`. Join recall at 3 is `0.75`. `recall_at_1_is_1` is false. Recall at 1 is the fraction of the four frozen joins that appear in the top 1 of the `physical` channel. One frozen join is present, so the fraction is `0.25`. Recall at 3 is three of the four, so the fraction is `0.75`. K and the label file were not changed.

The present row at K=1 is `719df390-2c7b-5e85-a27b-6419e6187ba7`. Its fixture fragments are `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `f42a0d5c-25a4-5358-8d70-d1619f920839`. Rank 1 is that pair. `rank_1_score` is `0.0`. `rank_channel` is `physical`. `rank_epistemic_class` is `hypothesis`. `score_name` is `negative_chord_gap_plus_curve_and_overlap`. The parameter blob records `seat` `exterior_side` and `curve_samples` `8`.

The twelve scores begin with two `0.0` values. Those two rows are the left column and the right column. Their order follows the hypothesis ids, which include the code-version string, so another string can swap them. The next four scores are the separated orientations of the remaining pairs, near `-1.0` and `-1.8`. The last six are the reversed chord orientations, near `-50`. `8f61ea40-e4e9-509e-a6ed-48fdd2d0064e` and `6f5b0df5-3e56-5028-b283-e22aa0009db3` are present at K=3 and absent at K=1. `c4a29850-b170-575b-80f1-57049eb67782` is absent at both. It is rank 4.

The channel is `physical`. This run leaves `htr` uncomputed and leaves `language` uncomputed.

The chord term is still the absolute length difference of the one chord at or above 6 mm. On this leaf those chords are 15 mm or 16 mm, the long axis-aligned runs of the rotated raster. Aligning them still overlaps each pair of minimum-area rectangles by about 1.3 mm to 1.6 mm, and the raster outlines of that alignment overlap too. For that pairing the stored pose is no longer the chord alignment. It seats the best-matched rectangle sides so the rectangles touch on the exterior and the fragment is not turned over. The direction of the seat is the one most opposed to the flat's translation. The overlap term is the thickness under that stored pose, which is zero for these seats. The reversed pairing keeps the chord pose, and its rectangles still overlap by about 50 mm.

Both columns have chord gap `0` and a matched side of equal length, so both score `0.0`. The two horizontal frozen joins have chord gap `1` mm, so they score near `-1`. The diagonals score near `-1.8`. Recall at 1 stays `0.25` because the prefix of length 1 holds one fragment pair.

Placement error at N=2 lists four scored RMSE values, in report order: `72.29919571303537`, `75.97087636887031`, `19.127628841908624`, and `17.694371869745904` page millimetres. Four rows are `unplaced` and carry no RMSE. `placement_page_origin` is `minimum_corner`. The report states that the error includes the difference between that page-origin rule and the generator's absolute rotation. `does_not_measure` on the report is warped or shrunken real parchment. [Q-SCI-03](ALGORITHM.md#q-sci-03), [Q-SCI-15](EVALUATION.md#q-sci-15), and [Q-SCI-20](ALGORITHM.md#q-sci-20) stay open.

Both kept assemblies are hypotheses on the `physical` channel with score `0.0`. `placement_scored_pairs_are_frozen_joins` is true. Assembly search is unchanged: a pose whose raster outlines have positive area is still dropped. These two seats do not overlap, so the two score-`0.0` joins are the assemblies that survive.

The first assembly places `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `f42a0d5c-25a4-5358-8d70-d1619f920839`, frozen join `719df390-2c7b-5e85-a27b-6419e6187ba7`, which is rank 1. Its RMSE values are `72.29919571303537` and `75.97087636887031`. That pair is the right column. Each outline's minimum-area rectangle has two short sides of 44.26 mm, so the shared cut and the two outer borders are the same length. Both exterior seats have no rectangle overlap, and neither seat's raster outlines overlap. The flat's translation picks the outer borders. The outlines do not mark which of those equal sides is the cut. The overlap rule was not loosened, and the labels were not changed, to force the other seat.

The second assembly places `96ec4566-67eb-5ba6-be11-29b71e58fd06` and `a739e88b-81cd-5678-a266-4b8fb4fe6b9c`, frozen join `8f61ea40-e4e9-509e-a6ed-48fdd2d0064e`. Its RMSE values are `19.127628841908624` and `17.694371869745904`. That pair is the left column. The seat meets the matched sides of length 40.66 mm, which are the shared cut, and the raster outlines do not overlap. The error is the rigid fit of those sides, not the 55 mm to 90 mm left by aligning the long flats. It is not zero. The observed outline is already the rotated raster, with page-parallel axes and its centroid at the origin. The label applies another `0.3` rad to those vertices and translates by the generator centroid. The assembly anchor has rotation `0`, and the pair is then shifted so its minimum corner is the origin. Erosion `0.15` leaves a gap in the generator; the seat closes that gap by putting the matched sides on one line. Those differences are the residual.

Lighting variation `0.25` is in the generator parameter blob and in the image hashes. Foreground threshold `1` keeps every painted sample of this leaf. Rotation `0.3` radians breaks each straight side into short pixel runs. The 6 mm minimum still keeps one chord per fragment. The seat reads the minimum-area rectangle of the outline those runs came from.

## Measured record

The script prints this object on the `record` line when `code_version` is `5b668f1ffdb78d4fbe5781c09a006038db29ecae`. Image files stay in `$DEST/images/` and are not committed.

```json
{
  "assembly_rank": [
    {
      "channel": "physical",
      "epistemic_class": "hypothesis",
      "fixture_fragment_ids": [
        "96ec4566-67eb-5ba6-be11-29b71e58fd06",
        "a739e88b-81cd-5678-a266-4b8fb4fe6b9c"
      ],
      "score": 0.0
    },
    {
      "channel": "physical",
      "epistemic_class": "hypothesis",
      "fixture_fragment_ids": [
        "486d4093-d4a4-5cb2-88e2-8e0987316ed5",
        "f42a0d5c-25a4-5358-8d70-d1619f920839"
      ],
      "score": 0.0
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
  "placement_parameter_hash": "sha256:0ded32551e39237fcf8fe42724f0b12d7b26e2520bce9f5746f64138063bc16d",
  "placement_previous_report": "absent",
  "placement_rmse_mm": [
    19.127628841908624,
    17.694371869745904,
    28.33419097479096,
    46.94693565494972
  ],
  "placement_scored_assemblies": [
    {
      "fixture_fragment_ids": [
        "96ec4566-67eb-5ba6-be11-29b71e58fd06",
        "a739e88b-81cd-5678-a266-4b8fb4fe6b9c"
      ],
      "frozen_join": true,
      "rmse_mm": [
        19.127628841908624,
        17.694371869745904
      ]
    },
    {
      "fixture_fragment_ids": [
        "486d4093-d4a4-5cb2-88e2-8e0987316ed5",
        "f42a0d5c-25a4-5358-8d70-d1619f920839"
      ],
      "frozen_join": true,
      "rmse_mm": [
        28.33419097479096,
        46.94693565494972
      ]
    }
  ],
  "placement_scored_pairs_are_frozen_joins": true,
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
  "rank_parameter_hash": "sha256:81c5da9af69a209a06d10b5d796c349bb9a4914f07f70040d9585a55e0baf060",
  "rank_scores": [
    0.0,
    0.0,
    -1.0008409837349252,
    -1.0620163000557326,
    -1.7887320483671032,
    -1.8515893321577614,
    -49.02354646604126,
    -49.41495779301704,
    -49.56887903679135,
    -50.11408151802765,
    -50.448573959965486,
    -51.1712077120198
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
  "recall_at_3": 0.75,
  "recall_at_3_previous_report": "join-recall-0001.json",
  "recall_at_3_status": [
    {
      "id": "6f5b0df5-3e56-5028-b283-e22aa0009db3",
      "status": "present"
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
  "recall_parameter_hash": "sha256:81c5da9af69a209a06d10b5d796c349bb9a4914f07f70040d9585a55e0baf060",
  "score_name": "negative_chord_gap_plus_curve_and_overlap",
  "surviving_chord_mm": {
    "486d4093-d4a4-5cb2-88e2-8e0987316ed5": 15.0,
    "96ec4566-67eb-5ba6-be11-29b71e58fd06": 16.0,
    "a739e88b-81cd-5678-a266-4b8fb4fe6b9c": 16.0,
    "f42a0d5c-25a4-5358-8d70-d1619f920839": 15.0
  }
}
```

## Reading the record

Join recall at 1 is `0.25`. Join recall at 3 is `0.75`. `recall_at_1_is_1` is false. Recall at 1 is the fraction of the four frozen joins that appear in the top 1 of the `physical` channel. One frozen join is present, so the fraction is `0.25`. Recall at 3 is three of the four, so the fraction is `0.75`. K and the label file were not changed.

The present row at K=1 is `719df390-2c7b-5e85-a27b-6419e6187ba7`. Its fixture fragments are `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `f42a0d5c-25a4-5358-8d70-d1619f920839`. Rank 1 is that pair. `rank_1_score` is `0.0`. `rank_channel` is `physical`. `rank_epistemic_class` is `hypothesis`. `score_name` is `negative_chord_gap_plus_curve_and_overlap`. The parameter blob records `seat` `exterior_side` and `curve_samples` `8`.

The twelve scores begin with two `0.0` values. For this code version the first of those rows is the right column and the second is the left column. Another string can swap them. The next four scores are the separated orientations of the remaining pairs, near `-1.0` and `-1.8`. The last six are the reversed chord orientations, near `-50`. `8f61ea40-e4e9-509e-a6ed-48fdd2d0064e` and `6f5b0df5-3e56-5028-b283-e22aa0009db3` are present at K=3 and absent at K=1. `c4a29850-b170-575b-80f1-57049eb67782` is absent at both. It is rank 4.

The channel is `physical`. This run leaves `htr` uncomputed and leaves `language` uncomputed.

The chord term is still the absolute length difference of the one chord at or above 6 mm. On this leaf those chords are 15 mm or 16 mm, the long axis-aligned runs of the rotated raster. Aligning them still overlaps each pair of minimum-area rectangles by about 1.3 mm to 1.6 mm, and the raster outlines of that alignment overlap too. For that pairing the stored pose seats the best-matched rectangle sides so the rectangles touch on the exterior and the fragment is not turned over. Both flats of a column sit off center toward the same end of the rectangle. The left-column flats sit below the rectangle center, so the reference stays the flat's translation and the seat is the shared cut kept by the exterior-side record. The right-column flats sit above the rectangle center. A clockwise outline stores that flat pointing down, and opposing the flat seats the outer borders. The reference is reversed, and the seat meets the other pair of equal short sides, the shared cut. The overlap term is the thickness under the stored pose, which is zero. The reversed pairing keeps the chord pose, and its rectangles still overlap by about 50 mm.

Both columns have chord gap `0` and a matched side of equal length, so both score `0.0`. The two horizontal frozen joins have chord gap `1` mm, so they score near `-1`. The diagonals score near `-1.8`. Recall at 1 stays `0.25` because the prefix of length 1 holds one fragment pair.

Placement error at N=2 lists four scored RMSE values, in report order: `19.127628841908624`, `17.694371869745904`, `28.33419097479096`, and `46.94693565494972` page millimetres. Report order follows assembly rank. Join rank lists the right column first, and assembly rank lists the left column first. The two orders use different hypothesis ids. Four rows are `unplaced` and carry no RMSE. `placement_page_origin` is `minimum_corner`. The report states that the error includes the difference between that page-origin rule and the generator's absolute rotation. `does_not_measure` on the report is warped or shrunken real parchment. [Q-SCI-03](ALGORITHM.md#q-sci-03), [Q-SCI-15](EVALUATION.md#q-sci-15), and [Q-SCI-20](ALGORITHM.md#q-sci-20) stay open.

Both kept assemblies are hypotheses on the `physical` channel with score `0.0`. `placement_scored_pairs_are_frozen_joins` is true. Assembly search is unchanged: a pose whose raster outlines have positive area is still dropped. These two seats do not overlap, so the two score-`0.0` joins are the assemblies that survive.

The first assembly places `96ec4566-67eb-5ba6-be11-29b71e58fd06` and `a739e88b-81cd-5678-a266-4b8fb4fe6b9c`, frozen join `8f61ea40-e4e9-509e-a6ed-48fdd2d0064e`. Its RMSE values are `19.127628841908624` and `17.694371869745904`. That pair is the left column. The seat meets the matched sides of length 40.66 mm, which are the shared cut, and the raster outlines do not overlap. Those RMSE values are the exterior-side record's values for this pair.

The second assembly places `486d4093-d4a4-5cb2-88e2-8e0987316ed5` and `f42a0d5c-25a4-5358-8d70-d1619f920839`, frozen join `719df390-2c7b-5e85-a27b-6419e6187ba7`, which is join rank 1. Its RMSE values are `28.33419097479096` and `46.94693565494972`. That pair is the right column. Each outline's minimum-area rectangle has two short sides of 44.26 mm, so the shared cut and the two outer borders are the same length. The exterior-side record seated the outer borders and reported `72.29919571303537` and `75.97087636887031`. This seat meets the shared cut. The overlap rule was not loosened, and the labels were not changed. The label file hash is `sha256:a837cb997ea892862275e853fa21c2e0172b34495f56e65ee8a17a6f381d48ac`.

The error on the shared cut is not zero. The observed outline is already the rotated raster, with page-parallel axes and its centroid at the origin. The label applies another `0.3` rad to those vertices and translates by the generator centroid. The assembly anchor has rotation `0`, and the pair is then shifted so its minimum corner is the origin. Erosion `0.15` leaves a gap in the generator; the seat closes that gap by putting the matched sides on one line. Those differences are the residual.

Lighting variation `0.25` is in the generator parameter blob and in the image hashes. Foreground threshold `1` keeps every painted sample of this leaf. Rotation `0.3` radians breaks each straight side into short pixel runs. The 6 mm minimum still keeps one chord per fragment. The seat reads the minimum-area rectangle of the outline those runs came from.
