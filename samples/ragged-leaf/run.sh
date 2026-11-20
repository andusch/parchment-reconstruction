#!/bin/sh
# Generate one ragged synthetic leaf and score it with the current commands.
# Images stay in the destination directory. They are not committed.
set -eu

root=$(git rev-parse --show-toplevel)
cd "$root"

dest=${1:-${TMPDIR:-/tmp}/prw-ragged-leaf}

dest=$(ROOT="$root" DEST="$dest" uv run python - <<'PY'
import os
import sys
from pathlib import Path

root = Path(os.environ["ROOT"]).resolve()
dest = Path(os.environ["DEST"]).expanduser().resolve()
blocked = {
    "originals",
    "observations",
    "runs",
    "validations",
    "exports",
    "data",
    "scans",
    "real_data",
}
if dest == root or root in dest.parents:
    print(
        "Write the ragged leaf outside the checkout. TIFF files are gitignored.",
        file=sys.stderr,
    )
    raise SystemExit(2)
if set(dest.parts) & blocked:
    print("That destination is a project data path.", file=sys.stderr)
    raise SystemExit(2)
if dest.exists() and any(dest.iterdir()):
    print(
        "The destination is not empty. Pass a new directory so the label file stays the freeze.",
        file=sys.stderr,
    )
    raise SystemExit(2)
print(dest)
PY
)

mkdir -p "$dest"
# Hypothesis ids include this string. Equal physical scores are ordered by
# those ids, so the published rank-1 row and placement RMSE list are for
# this commit of the algorithms. Override PRW_CODE_VERSION only when
# remeasuring after an algorithm change.
pinned=8a6c2e569ed8107cd47848e29005e528ec397a8e
checkout=$(git rev-parse HEAD)
code=${PRW_CODE_VERSION:-$pinned}
echo "checkout $checkout"
echo "code_version $code"

uv run prw generate \
  --benchmarks "$dest/benchmarks" \
  --images "$dest/images" \
  --missing-fragment-percentage 0 \
  --edge-erosion 0.15 \
  --rotation 0.3 \
  --lighting-variation 0.25 \
  --random-seed 3 \
  --code-version "$code" \
  > "$dest/generate.json"
echo "generate_exit 0"

mkdir -p "$dest/frozen"
cp "$dest/benchmarks/labels.json" "$dest/frozen/labels.json"
cp "$dest/benchmarks/provenance.json" "$dest/frozen/provenance.json"
sha256sum "$dest"/images/*.tif "$dest"/images/image_manifest.json \
  > "$dest/frozen/images.sha256"

DEST="$dest" CODE="$code" uv run python - <<'PY'
import json
import os
import shlex
from pathlib import Path

dest = Path(os.environ["DEST"])
code = os.environ["CODE"]
images = dest / "images"
manifest = json.loads((images / "image_manifest.json").read_text(encoding="utf-8"))
fragments = [item for item in manifest["images"] if item["role"] == "fragment"]
if len(fragments) != 4:
    raise SystemExit("These parameters write four fragment files.")
pool: list[str] = []
correspondence: list[str] = []
for item in fragments:
    fixture_id = str(item["fragment_id"])
    path = images / item["name"]
    pool.extend(["--image", fixture_id, str(path)])
    correspondence.extend(["--correspondence", f"{fixture_id}={fixture_id}"])
scale = [
    "--foreground-threshold",
    "1",
    "--code-version",
    code,
    "--pixels-per-mm",
    "1",
    "--uncertainty",
    "0.1",
]
assembly = [
    "--n",
    "2",
    "--translation-tolerance-mm",
    "1",
    "--rotation-tolerance-radians",
    "1",
    "--min-width-mm",
    "0",
    "--max-width-mm",
    "1000",
    "--min-height-mm",
    "0",
    "--max-height-mm",
    "1000",
    "--benchmarks",
    str(dest / "benchmarks"),
]


def write(name: str, args: list[str]) -> None:
    text = " ".join(shlex.quote(arg) for arg in args)
    (dest / name).write_text(text + "\n", encoding="utf-8")


for index, item in enumerate(fragments):
    write(
        f"edge-{index}.args",
        [
            "edge",
            str(images / item["name"]),
            "--label",
            str(item["fragment_id"]),
            *scale,
            "--minimum-edge-length-mm",
            "0",
        ],
    )
write(
    "rank.args",
    ["rank", *pool, *scale, "--minimum-edge-length-mm", "6"],
)
write(
    "recall-1.args",
    [
        "recall",
        *pool,
        *scale,
        "--minimum-edge-length-mm",
        "6",
        "--benchmarks",
        str(dest / "benchmarks"),
        "--k",
        "1",
        *correspondence,
    ],
)
write(
    "recall-3.args",
    [
        "recall",
        *pool,
        *scale,
        "--minimum-edge-length-mm",
        "6",
        "--benchmarks",
        str(dest / "benchmarks"),
        "--k",
        "3",
        *correspondence,
    ],
)
write(
    "placement.args",
    [
        "placement-error",
        *pool,
        *scale,
        "--minimum-edge-length-mm",
        "6",
        *assembly,
        *correspondence,
    ],
)
write(
    "assembly-rank.args",
    [
        "assembly-rank",
        *pool,
        *scale,
        "--minimum-edge-length-mm",
        "6",
        "--n",
        "2",
        "--translation-tolerance-mm",
        "1",
        "--rotation-tolerance-radians",
        "1",
        "--min-width-mm",
        "0",
        "--max-width-mm",
        "1000",
        "--min-height-mm",
        "0",
        "--max-height-mm",
        "1000",
    ],
)
PY

run_prw() {
  out=$1
  args_file=$2
  # The args file is shlex-quoted by the writer above.
  eval "set -- $(cat "$args_file")"
  uv run prw "$@" > "$dest/$out.json"
  echo "${out}_exit 0"
}

index=0
while [ "$index" -lt 4 ]; do
  run_prw "edge-$index" "$dest/edge-$index.args"
  index=$((index + 1))
done
run_prw rank "$dest/rank.args"
run_prw recall-1 "$dest/recall-1.args"
run_prw recall-3 "$dest/recall-3.args"
run_prw placement "$dest/placement.args"
run_prw assembly-rank "$dest/assembly-rank.args"

if ! cmp -s "$dest/frozen/labels.json" "$dest/benchmarks/labels.json"; then
  echo "labels.json changed after scoring." >&2
  exit 1
fi
if ! cmp -s "$dest/frozen/provenance.json" "$dest/benchmarks/provenance.json"; then
  echo "provenance.json changed after scoring." >&2
  exit 1
fi
sha256sum "$dest"/images/*.tif "$dest"/images/image_manifest.json \
  > "$dest/frozen/images-after.sha256"
if ! cmp -s "$dest/frozen/images.sha256" "$dest/frozen/images-after.sha256"; then
  echo "Image bytes changed after scoring." >&2
  exit 1
fi
echo "labels_unchanged yes"

DEST="$dest" uv run python - <<'PY'
import hashlib
import json
import math
import os
from pathlib import Path

dest = Path(os.environ["DEST"])


def load(name: str) -> dict:
    return json.loads((dest / name).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def length(edge: dict) -> float:
    start, end = edge["geometry"]
    return math.hypot(end[0] - start[0], end[1] - start[1])


generate = load("generate.json")
rank = load("rank.json")
recall_1 = load("recall-1.json")
recall_3 = load("recall-3.json")
placement = load("placement.json")
assembly_rank = load("assembly-rank.json")
labels = json.loads((dest / "benchmarks" / "labels.json").read_text(encoding="utf-8"))
manifest = json.loads(
    (dest / "images" / "image_manifest.json").read_text(encoding="utf-8")
)
frozen_pairs = {
    tuple(sorted(str(item) for item in row["fragment_ids"]))
    for row in labels
    if row["kind"] == "join"
}
correspondence = {
    row["project_fragment_id"]: row["fixture_fragment_id"]
    for row in recall_1["correspondence"]
}
if correspondence != {
    row["project_fragment_id"]: row["fixture_fragment_id"]
    for row in recall_3["correspondence"]
}:
    raise SystemExit("The two recall reports name different correspondences.")
if correspondence != {
    row["project_fragment_id"]: row["fixture_fragment_id"]
    for row in placement["correspondence"]
}:
    raise SystemExit("Placement names a different correspondence.")

chords: dict[str, float] = {}
counts: dict[str, int] = {}
for index, item in enumerate(
    row for row in manifest["images"] if row["role"] == "fragment"
):
    traced = load(f"edge-{index}.json")
    if traced["record"] != "ChordEdges":
        raise SystemExit("The edge census did not return chord edges.")
    fixture_id = str(item["fragment_id"])
    counts[fixture_id] = len(traced["edges"])
    kept = [length(edge) for edge in traced["edges"] if length(edge) >= 6]
    if len(kept) != 1:
        raise SystemExit("Each fragment kept one chord at or above 6 mm.")
    chords[fixture_id] = kept[0]

joins = rank["joins"]
if not joins:
    raise SystemExit("Rank returned no join.")
channels = {join["channel"] for join in joins}
classes = {join["epistemic_class"] for join in joins}
if channels != {"physical"} or classes != {"hypothesis"}:
    raise SystemExit("Rank mixed a channel or an epistemic class.")
score_name = json.loads(rank["envelope"]["parameter_blob"])["score"]
first = joins[0]
rank_pair = tuple(
    sorted(
        (
            correspondence[str(first["fragment_a_id"])],
            correspondence[str(first["fragment_b_id"])],
        )
    )
)
present_at_1 = [
    tuple(sorted(row["fragment_ids"]))
    for row in recall_1["recall_list"]
    if row["status"] == "present"
]
if present_at_1 != [rank_pair]:
    raise SystemExit("Rank 1 and the recall-at-1 present row disagree.")

scored_assemblies: list[dict] = []
assembly_ids: list[str] = []
for row in placement["error_list"]:
    if row["status"] != "scored":
        continue
    if row["assembly_id"] not in assembly_ids:
        assembly_ids.append(row["assembly_id"])
for assembly_id in assembly_ids:
    rows = [
        row
        for row in placement["error_list"]
        if row["assembly_id"] == assembly_id and row["status"] == "scored"
    ]
    members = tuple(sorted(correspondence[row["fragment_id"]] for row in rows))
    scored_assemblies.append(
        {
            "fixture_fragment_ids": list(members),
            "frozen_join": members in frozen_pairs,
            "rmse_mm": [row["rmse_mm"] for row in rows],
        }
    )
ranked_assemblies = []
for row in assembly_rank["assemblies"]:
    placed = tuple(sorted(correspondence[item] for item in row["placements"]))
    ranked_assemblies.append(
        {
            "fixture_fragment_ids": list(placed),
            "score": row["score"],
            "channel": row["channel"],
            "epistemic_class": row["epistemic_class"],
        }
    )
if [item["fixture_fragment_ids"] for item in ranked_assemblies] != [
    item["fixture_fragment_ids"] for item in scored_assemblies
]:
    raise SystemExit("Assembly rank and placement error name different pairs.")

record = {
    "generator_algorithm_name": generate["provenance"]["algorithm_name"],
    "generator_algorithm_version": generate["provenance"]["algorithm_version"],
    "generator_parameter_hash": generate["provenance"]["parameter_hash"],
    "generator_parameter_blob": generate["provenance"]["parameter_blob"],
    "random_seed": generate["provenance"]["random_seed"],
    "decoder_name": generate["provenance"]["decoder_name"],
    "decoder_version": generate["provenance"]["decoder_version"],
    "model_hash": generate["provenance"]["model_hash"],
    "images": [
        {
            "name": item["name"],
            "role": item["role"],
            "content_hash": item["content_hash"],
            "byte_length": item["byte_length"],
            "width": item["width"],
            "height": item["height"],
        }
        for item in manifest["images"]
    ],
    "label_file_hash": digest(dest / "frozen" / "labels.json"),
    "chord_count_at_minimum_0": counts,
    "surviving_chord_mm": chords,
    "join_count": len(joins),
    "rank_channel": "physical",
    "rank_epistemic_class": "hypothesis",
    "score_name": score_name,
    "rank_algorithm_name": rank["envelope"]["algorithm_name"],
    "rank_algorithm_version": rank["envelope"]["algorithm_version"],
    "rank_parameter_hash": rank["envelope"]["parameter_hash"],
    "rank_scores": [join["score"] for join in joins],
    "rank_1_score": first["score"],
    "rank_1_fixture_fragment_ids": list(rank_pair),
    "rank_1_is_frozen_join": rank_pair in frozen_pairs,
    "recall_at_1": recall_1["recall"],
    "recall_at_3": recall_3["recall"],
    "recall_at_1_is_1": recall_1["recall"] == 1.0,
    "recall_algorithm_name": recall_1["algorithm_name"],
    "recall_algorithm_version": recall_1["algorithm_version"],
    "recall_parameter_hash": recall_1["parameter_hash"],
    "recall_at_1_previous_report": recall_1["previous_report"],
    "recall_at_3_previous_report": recall_3["previous_report"],
    "recall_at_1_status": [
        {"id": row["id"], "status": row["status"]} for row in recall_1["recall_list"]
    ],
    "recall_at_3_status": [
        {"id": row["id"], "status": row["status"]} for row in recall_3["recall_list"]
    ],
    "placement_algorithm_name": placement["algorithm_name"],
    "placement_algorithm_version": placement["algorithm_version"],
    "placement_parameter_hash": placement["parameter_hash"],
    "placement_previous_report": placement["previous_report"],
    "placement_n": placement["n"],
    "placement_page_origin": placement["page_origin"],
    "placement_rmse_mm": [
        row["rmse_mm"] for row in placement["error_list"] if row["status"] == "scored"
    ],
    "placement_unplaced_count": sum(
        1 for row in placement["error_list"] if row["status"] == "unplaced"
    ),
    "placement_scored_assemblies": scored_assemblies,
    "placement_scored_pairs_are_frozen_joins": all(
        item["frozen_join"] for item in scored_assemblies
    ),
    "assembly_rank": ranked_assemblies,
    "labels_unchanged": True,
}
text = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
print("record " + text)
PY
