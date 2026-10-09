# Scan protocol

- Status: Draft for review
- Phase: P0 (capture contract for later ingest, not a scanner manual)
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)
- Open-question index: [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)

This protocol states how a source image becomes usable evidence. P0 does not operate a scanner and does not add sample images to the repository.

## Purpose

A source image supports fragment outlines, millimetre placements, and later readings only when the bytes are intact, a scale reference is present, and the file name does not smuggle a reconstruction conclusion. The protocol is the capture contract that later ingest will check.

## Handling limits

Conservation handling stays with the holding institution. This protocol does not authorize humidification, flattening under pressure beyond the institution's own practice, or any other treatment. The imaging operator records the face that was presented and any constraint the institution imposed.

## Source-of-record file rules

These rules are already decided:

- The original file is immutable. Later steps read it and write only new files.
- SHA-256 of the original bytes is recorded outside the pixels, in the sidecar or the project record. The hash is not written into the image.
- A lossy derivative is never the source of record.
- Cropping, tonal change, or other enhancement creates a new derived file with a provenance envelope. The derived file cites the source hash and does not replace it.

Lossless TIFF is the required master. Ingest enforces that media type and rejects anything else. After ingest, the `originals/` copy is the authoritative byte source. The decoder name and version are recorded in provenance.

The imaging bar below, other than the TIFF rule, is a working assumption, not a validated standard. It retires with [Q-SCI-10](#q-sci-10).

- A scale target is visible in the frame and does not cover the fragment.
- Sampling is at least 600 ppi at object scale.

Bit depth, scanner versus camera, and the specific calibration target remain open under Q-SCI-10. A claimed resolution in the file header is never copied into calibration. When that claim is the only scale information, the importer warns and leaves calibration absent.

## Scale and color targets

Scale evidence is what later code converts between `source_pixels` and millimetre frames. Until a calibration observation exists, millimetre placements are not emitted. See [ALGORITHM.md](ALGORITHM.md).

Color control matters because fragment segmentation and ink detection use color and luminance. P0 does not mandate a named color chart. The sidecar records whether a color target was in frame and whether any tonal edit was baked into a derivative rather than the source.

A claimed resolution in the file header is a claim. The calibration observation is the measurement that later geometry uses. The importer never fills `pixels_per_mm` from the claim.

## One-fragment frames and group scans

The preferred frame contains one fragment and the scale target. A group scan contains more than one fragment. Whether group scans are a supported ingest mode is [Q-PRD-04](PRD.md#q-prd-04).

Until that question closes, a group scan may be stored. `SourceImage.group_scan` records that more than one fragment is in the frame. It is a fact about the capture, not a confidence value, and it does not have an epistemic class of its own. A group scan is not treated as metrologically equivalent to a one-fragment frame.

## Recto and verso identity

When both faces exist, both are captured. Face is `SourceImage.face`: `recto`, `verso`, or `unknown`. A fragment has no face field. Two captures of one fragment are two `SourceImage` rows with the same `fragment_id` and their own `face`. The label is the operator's identification of the physical face. It is not a join decision.

How face identity constrains assembly is [Q-PRD-03](PRD.md#q-prd-03). Opposite-face show-through is [Q-SCI-06](DATA_MODEL.md#q-sci-06).

## Naming

File names and fragment labels identify the capture. They use an inventory number or another opaque label. They do not encode a proposed join, a page number in a reconstruction, or a reading.

Content-addressed storage by SHA-256 is the persistence proposal in [ADR-0007](adr/0007-project-persistence.md). The capture name and the content hash are different fields.

## Sidecar metadata

Each source image has a sidecar, or equivalent project fields, recorded outside the pixels:

- SHA-256 and byte length
- Capture time
- Operator name, which is optional personal data under [Q-PRI-02](SECURITY_AND_PRIVACY.md#q-pri-02)
- Face label as recorded by the operator: `recto`, `verso`, or `unknown`
- Protocol version
- Claimed resolution in ppi, which is not calibration
- `color_profile_ref`, a reference to the color-profile sidecar, when one exists
- Whether a scale target and a color target were in frame
- Group-scan flag when more than one fragment is in frame
- Protocol exceptions

## Checksum procedure

1. Compute SHA-256 over the original file bytes before any derivative is written.
2. Store the digest and the byte length outside the image.
3. Before any later read, recompute the digest and compare it.
4. On mismatch, refuse the file as usable evidence and record an `IntegrityFailure`. Do not repair the bytes in place. `IntegrityFailure` is not observed evidence. `IntegrityFailure` and `ProtocolException` are both protocol events. Neither enters the evidence pool.

FR-1 in the [PRD](PRD.md) is this rule as a product requirement.

## Acceptance checklist

A capture is acceptable for later millimetre work when all of the following hold:

- The file is a lossless TIFF master, and its SHA-256 is stored outside the pixels.
- The fragment lies fully in frame, with its edges visible against the background.
- A scale target is in frame and unobstructed.
- The face label is recorded.
- The file name does not state a reconstruction conclusion.
- Any deviation is stored as a protocol exception.

Ingest rejects any media type other than lossless TIFF. A capture that fails a checklist item other than the master can still be imported. Ingest then stores the exception and withholds millimetre claims that the missing item would have supported.

## Protocol exceptions

A deviation is a `ProtocolException` on the source image. See the [data model](DATA_MODEL.md#protocolexception). The exception names the rule, the operator, and the time. It does not rewrite pixels, and it does not delete the source. Later algorithms read the exception before they emit millimetre measurements.

## Open questions

### Q-SCI-10

Which calibration target and scale-error bound are required?

Join ranking in millimetres is only as good as the scale observation. A number stated too early becomes a false standard.

- Options: a ruler; a dot grid or checker target; an institution-specific target. Separately, the scale-error bound may be unset until a study, or set to a percent before P1 calibration tests. Scale is not taken from the file header.
- Lossless TIFF is already required at ingest. This question does not reopen the media type. A scale target in frame and at least 600 ppi at object scale remain a provisional bar, not a decision. Bit depth and scanner-versus-camera stay inside this question.
- Blocks: treating any numeric imaging threshold as validated. Blocks P1 calibration acceptance tests that would enforce a specific target or error bound.

### Q-SCI-18

Are multispectral or other modalities in scope later?

Extra bands change the source-image model, the checksum story, and what "the" capture of a fragment is.

- Options: visible-light captures only, including later phases; a later phase for registered multispectral or other bands; a single source file that already stacks bands.
- Blocks: any ingest path for non-visible modalities. The first product lists multispectral capture as a non-goal in the [PRD](PRD.md#non-goals).
