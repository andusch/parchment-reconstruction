#!/bin/sh
# Materialize the seed-3 synthetic leaf outside the checkout.
set -eu

root=$(git rev-parse --show-toplevel)
cd "$root"

dest=${1:-${TMPDIR:-/tmp}/prw-sample-leaf}

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
        "Write the sample outside the checkout. TIFF files are gitignored, "
        "and this leaf is not a scan to commit.",
        file=sys.stderr,
    )
    raise SystemExit(2)
if set(dest.parts) & blocked:
    print("That destination is a project data path.", file=sys.stderr)
    raise SystemExit(2)
print(dest)
PY
)

mkdir -p "$dest"
code=$(git rev-parse HEAD)

uv run prw generate \
  --benchmarks "$dest/benchmarks" \
  --images "$dest/images" \
  --missing-fragment-percentage 0 \
  --edge-erosion 0 \
  --rotation 0 \
  --lighting-variation 0 \
  --random-seed 3 \
  --code-version "$code"

DEST="$dest" CODE="$code" uv run python - <<'PY'
import json
import os
import shlex
from pathlib import Path

dest = Path(os.environ["DEST"])
code = os.environ["CODE"]
images = dest / "images"
manifest = json.loads((images / "image_manifest.json").read_text(encoding="utf-8"))
fragments = sorted(
    (item for item in manifest["images"] if item["role"] == "fragment"),
    key=lambda item: item["name"],
)
if len(fragments) != 4:
    raise SystemExit("These parameters write four fragment files.")
chosen = (fragments[0], fragments[2])
if chosen[0]["content_hash"] == chosen[1]["content_hash"]:
    raise SystemExit("The first and third fragment files share one hash.")
piece_a = images / chosen[0]["name"]
piece_b = images / chosen[1]["name"]
print(f"sample: {dest}")
print(f"images: {images}")
print(f"piece_a: {piece_a}")
print(f"piece_b: {piece_b}")
print("piece_a and piece_b are the first and third fragment names in sorted order.")
rank = " ".join(
    [
        "uv",
        "run",
        "prw",
        "rank",
        "--image",
        "piece-a",
        shlex.quote(str(piece_a)),
        "--image",
        "piece-b",
        shlex.quote(str(piece_b)),
        "--foreground-threshold",
        "1",
        "--code-version",
        shlex.quote(code),
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
    ]
)
review = rank.replace("uv run prw rank", "uv run prw-review", 1)
print("rank:")
print(rank)
print("review:")
print(review)
PY
