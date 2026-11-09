# Public import path

- Status: Working note. Directory, checksum, and scale record for one file from the [public-corpus pilot](pilot-public-corpus.md).
- Applies to: the CLI in this checkout, version `0.0.0`. Command names and flags are unfrozen.
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)
- Open-question index: [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)

The license gates live in the corpus note. This note is how to keep one accepted file on the machine and pass its path to `prw`. The program does not download files. [ADR-0001](adr/0001-local-only-processing.md) forbids a network call from the program. The operator uses a browser.

## Directory

Keep the leaf outside the clone. A durable directory under the home directory:

```text
$HOME/prw-pilot/leaves/shelf-1/
```

The same leaf can sit beside the clone:

```text
$HOME/src/parchment-reconstruction/    # the Git checkout
$HOME/src/prw-pilot/leaves/shelf-1/    # the leaf
```

`shelf-1` is an opaque label for this capture. The directory holds the publisher's file and a text sidecar:

```text
image.tif     # unchanged TIFF bytes, when the publisher issued a TIFF
image.note    # UTF-8 text
```

`$TMPDIR/prw-pilot-corpus` in the corpus note is a one-session checksum. A leaf you will pass to `prw` again uses a durable path like the ones above.

Paths inside the checkout are out of bounds. That includes any directory named `data/`, `scans/`, or `real_data/`. [`.gitignore`](../.gitignore) ignores those three names, and it ignores `*.tif` and `*.tiff` anywhere in the checkout. An ignored path can still be force-added. Leave the leaf outside the checkout so Git never sees it. From the checkout, this command prints the rule that would hide a TIFF inside the tree:

```bash
git check-ignore -v -- data/image.tif scans/image.tif real_data/image.tif image.tif
```

`git status` in the checkout does not list `$HOME/prw-pilot`. A listing of the leaf means the leaf is inside the checkout.

The leaf directory is a plain folder. It is not named `originals`. It does not contain `manifest.json`, `image_manifest.json`, or `benchmarks/`. `prw verify` reads the path you pass and writes nothing. [Q-ENG-01](OPEN_QUESTIONS.md#q-eng-01) is open, and the CLI does not write `manifest.json` or `originals/`.

Keep the directory off a cloud-sync folder when the copy should stay on this machine. [Q-PRI-01](SECURITY_AND_PRIVACY.md#q-pri-01) is open.

## Download one file

1. Pick one source in the [public-corpus pilot](pilot-public-corpus.md): Metropolitan Museum of Art Open Access, Cleveland Museum of Art Open Access, or one Wikimedia Commons file page.
2. Re-read that source's terms URL on the day you download. When the page no longer states the license recorded in the corpus note, leave the file out.
3. Take one file that meets that source's own gate. Metropolitan: the object page shows the Open Access icon. Cleveland: the object page carries the CC0 mark and `share_license_status` is `CC0`. Commons: the file page states a public-domain tag, CC0, or CC BY. A category, a search hit, or a catalogue caption is a finding aid.
4. Save the publisher's file with the browser. When that file is a TIFF, the path is `$HOME/prw-pilot/leaves/shelf-1/image.tif`. Cleveland's API documentation describes a CC0 original asset, when the record includes one, as a TIFF. That TIFF is the file to save. Leave the bytes as the publisher sent them: no crop, no tonal edit, and no format conversion.
5. When the publisher's file is JPEG, PNG, or another non-TIFF, save it under the leaf with the publisher's extension, for example `image.jpg`. `prw verify` then reports `UnsupportedMediaType`. A TIFF wrapped around those bytes is a new file. The [scan protocol](SCAN_PROTOCOL.md) requires a lossless TIFF as the source of record, so this note leaves the wrapper out of the checksum path.

Catalogue title, culture, geography, script, and transcription stay on the institution's page. The directory name and any later `--label` are opaque. This note records no Black Sea identity, no other find-site, no language, and no reading. A join printed by a later build would be a hypothesis.

## Checksum

From the checkout root, so `uv run` selects this project. The image path is absolute and can sit outside the checkout:

```bash
cd /path/to/parchment-reconstruction
export LEAF
LEAF="$HOME/prw-pilot/leaves/shelf-1"
uv run prw verify "$LEAF/image.tif"
```

`uv run python -m prw.cli verify` calls the same function.

Exit `0` when the first four bytes are `II*\x00` or `MM\x00*`. `record` is `VerifiedBytes`. `media_type` is `image/tiff`. `content_hash` is `sha256:` and 64 lowercase hex digits. `byte_length` is the file length. Copy `content_hash` into `image.note`. The command hashes the file and checks that prefix. It does not parse an IFD, read a resolution tag, or modify the file. A file of TIFF magic plus other bytes still returns `VerifiedBytes`. Pixel commands are a separate check, below.

Run it again with the sidecar digest. The value includes the `sha256:` prefix:

```bash
uv run prw verify "$LEAF/image.tif" --expected "sha256:<64 lowercase hex digits>"
```

Exit `0` and the same `content_hash` mean the bytes still match the note. Exit `1` with `record` `IntegrityFailure` means they differ. `presented_hash` is the digest of the file now. `expected_hash` is the digest you passed. The file stays as it was. Compare the two hashes and keep the publisher's bytes. An `IntegrityFailure` is a protocol event. It has no epistemic class.

A prefix other than those four bytes exits `1`. `record` is `UnsupportedMediaType`. `presented_hash` is the digest of the unchanged bytes. `byte_length` is the file length. JPEG and PNG take this path. For the `image.jpg` saved above, the command is `uv run prw verify "$LEAF/image.jpg"`.

A missing path exits `2`. Stdout is empty. Stderr says `<path> is not a fixture image.` A directory that also holds `image_manifest.json` or files named `fragment-*.tif` appends those fragment names. Keep the public leaf in its own directory.

## Scale

`prw --help` names thirteen commands: `agree`, `assemble`, `assembly-rank`, `edge`, `frame`, `generate`, `join-presence`, `placement-error`, `provenance`, `rank`, `recall`, `segment`, and `verify`. None of them is a scale store.

Scale reaches the pixel commands as two flags supplied together: `--pixels-per-mm` and `--uncertainty`. The flags are accepted on `segment`, `edge`, `rank`, `recall`, `assemble`, `assembly-rank`, `placement-error`, and `join-presence`. One flag without the other exits `2`, stdout is empty, and stderr is `pixels_per_mm and uncertainty are supplied together.` `pixels_per_mm` is a positive finite number. `uncertainty` is zero or a positive finite number, in the same units. The caller-supplied scale records producer `human`. The number is a measurement you supply. The algorithm does not recover a scale from the file.

The CLI does not read `image.note`. The fixture decoder does not read TIFF tags 282 or 283. A resolution in a header or on a catalogue page is `claimed_resolution_ppi`. The [data model](DATA_MODEL.md#sourceimage) leaves `CalibrationObservation` empty when that claim is the only scale information. Write the claim in the sidecar when the publisher states one. Leave `pixels_per_mm` and `uncertainty` as `absent` until you have a measurement of your own. [Q-SCI-10](OPEN_QUESTIONS.md#q-sci-10) is open, so this note does not choose a calibration target or a scale-error bound. A scale target in frame and at least 600 ppi at object scale remain the scan protocol's provisional bar.

`image.note` is the corpus note's sidecar plus the scale lines. It is an operator note. It is not a provenance envelope, not a `BenchmarkLabel`, and not a project record.

```text
source_name: <name from the corpus note>
object_or_file_url: <object or file URL>
terms_url: <terms URL from the corpus note>
license: <license string copied from the terms page on the download day>
terms_read: <YYYY-MM-DD>
content_hash: sha256:<64 lowercase hex digits printed by prw verify>
attribution: <author, source, and license URL for CC BY, or absent>
claimed_resolution_ppi: <publisher or header claim, or absent>
scale_target_in_frame: <yes, no, or unknown>
pixels_per_mm: <measurement, or absent>
uncertainty: <same units as pixels_per_mm, or absent>
evidence_description: <what was measured, or absent>
```

For CC0 and for a public-domain tag, `attribution` is `absent`. Commons asks for a courtesy credit, and the corpus note records that request. For CC BY, copy the author, the source, and the license URL from the file page. An operator name is optional personal data under [Q-PRI-02](SECURITY_AND_PRIVACY.md#q-pri-02). Add a line `operator:` only when you choose to record one.

## What pixel commands do today

`segment`, `edge`, `rank`, `recall`, `assemble`, `assembly-rank`, `placement-error`, and `join-presence` read pixels with the fixture decoder `synthetic_uncompressed_tiff` version `1`. That decoder accepts one layout: magic `II*\x00`, the writer's IFD, and one uncompressed 8-bit grayscale sample per pixel. A publisher TIFF is a different file. [Q-ENG-05](OPEN_QUESTIONS.md#q-eng-05) stays open. This note does not choose a TIFF library.

On a file that `verify` accepted:

```bash
export CODE HASH
CODE=$(git rev-parse HEAD)
HASH="sha256:<64 lowercase hex digits from image.note>"
uv run prw segment "$LEAF/image.tif" \
  --label shelf-1 \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --expected "$HASH"
```

Exit `1` when the bytes are a publisher TIFF. `record` is `UnsupportedFixtureLayout`. `kind` is `different_ifd`, `compressed_strip`, `not_grayscale`, or `other_layout`. Big-endian magic `MM\x00*` is `other_layout`, because the fixture decoder requires `II*\x00`. The object has no `polygon` key. A wrong `--expected` digest returns `IntegrityFailure` before the layout check. `--pixels-per-mm` and `--uncertainty` are applied only after an outline exists, so a scale pair does not change an `UnsupportedFixtureLayout` result.

`--foreground-threshold 1` is the integer the synthetic leaf uses. It reaches the fixture reader. It is not a threshold selected for a publisher image.

A pool image is one flag and one existing path, `--image shelf-1 "$LEAF/image.tif"`. `rank`, `recall`, `assemble`, `assembly-rank`, `placement-error`, and `join-presence` take that flag and then use the same fixture reader. They stop on `UnsupportedFixtureLayout` for this file.

Millimetre `segment` and `rank` wait on a measurement in the sidecar and on a decoder that can read the file. Until both exist, `prw verify` is the command that accepts the TIFF. Leave this leaf out of any `benchmarks/` directory. It has no ground-truth label. Synthetic fixtures remain the evaluation material.

## Git

Image bytes stay outside Git, including when the license permits redistribution. The filled `image.note` stays beside the image, outside the clone. The clone's ignore rules cover a TIFF that lands inside the tree. The pilot directory stays outside the clone.
