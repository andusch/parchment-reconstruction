# Algorithms

- Status: Draft for review
- Phase: P0 (contracts only)
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)
- Geometry proposal: [ADR-0008](adr/0008-rigid-rectangular-page.md)
- Score channels: [ADR-0009](adr/0009-separate-score-channels.md)

P0 states inputs, outputs, invariants, and failure behavior. It does not implement stages, and it does not publish weights as valid.

The rigid rectangular leaf is the proposal in ADR-0008. It is not an accepted geometric model. Rolls, warps, and anisotropic shrinkage sit outside that proposal. See [Q-SCI-01](#q-sci-01), [Q-SCI-03](#q-sci-03), and [Q-SCI-20](#q-sci-20).

## Stages

Stages run in order. A later stage consumes the records the earlier stage actually wrote. It does not invent missing inputs.

### 1. Verify bytes

- **Inputs.** A source path and the stored SHA-256 and byte length, when a previous ingest stored them.
- **Outputs.** A verified `SourceImage`, or an `IntegrityFailure`. No hypothesis.
- **Failure.** On mismatch or unreadable bytes, stop for that file. Do not emit outlines, joins, or readings. The failure is an `IntegrityFailure`, not observed evidence. The bytes are not repaired in place. `prw verify` accepts classic TIFF magic. A pixel command refuses a compression that is not lossless, and that refusal is not an outline. After ingest, the `originals/` copy is the byte source the later stages read. The decoder name and version go into the provenance envelope.



### 2. Estimate scale

- **Inputs.** A verified source image and a scale target or a human measurement.
- **Outputs.** A `CalibrationObservation` in `source_pixels`, with uncertainty, epistemic class `observed`, and a `CalibrationTransform` for that image only. Producer is `human`, `machine`, or `imported`, and the class stays `observed`.
- **Failure.** When no scale evidence exists, do not emit millimetre placements. A claimed resolution in the file header never becomes `pixels_per_mm`. The importer warns and leaves calibration absent. An operator may pass that claim on `claimed_resolution_scale`. The envelope records `claimed_resolution_ppi`, evidence description `claimed resolution`, and `populates_calibration: false`. It does not write `CalibrationObservation` or `pixels_per_mm`, and it does not read the file header. Pixel-space observations may still be recorded in `source_pixels`.

The target type and the acceptable scale error are [Q-SCI-10](SCAN_PROTOCOL.md#q-sci-10).

### 3. Segment fragments

- **Inputs.** A verified source image. The optional parameter `enclosed_background_treatment` is omitted, or `fill_without_4_interior`. The optional parameter `border_mount_treatment` is omitted, or `not_above_frame_split`.
- **Outputs.** One `FragmentOutlineRevision` for a single 4-connected foreground component, epistemic class `interpretation`, producer `machine`, grouped by an `AlgorithmRun`. The implemented segmenter fails when it finds more than one component. When a treatment is omitted, that step leaves the mask unchanged. `not_above_frame_split` reclassifies as background each sample that is 4-connected to the one-pixel image frame through samples at or below the frame's Otsu split. The split is the maximum luminance of the darker class. A frame of one luminance uses that value. Samples above the split stop the flood. The reclassification runs before the enclosed-background fill, and neither treatment implies the other. `fill_without_4_interior` fills an enclosed 4-connected background component that does not contain the radius-1 structuring element (a pixel and its four edge neighbors). It does not dilate the outer boundary and it does not merge foreground components. The parameter blob names each treatment when it is used. The algorithm version stays `1`.
- **Failure.** When segmentation fails, record the failed run under its own id, not the id a later completed run of the same inputs would take. Do not invent an outline. A component that contains the structuring element stays background, and the hole check still fails. A bright sample in the mount that is not 4-connected to the cutting stays a second component. A group scan is `SourceImage.group_scan` from the [scan protocol](SCAN_PROTOCOL.md). It is not a confidence value, and it is not treated as metrologically equivalent to a one-fragment frame.



### 4. Build edge descriptors

- **Inputs.** An outline and, when scale exists, the transform into `fragment_local_mm`.
- **Outputs.** `EdgeArc` rows in `fragment_local_mm`, scoped to that outline revision, and the descriptors the join stage will consume. Descriptors are epistemic class `interpretation`, producer `machine`, and travel inside the run's provenance. The implemented algorithm `edge_chord` records descriptor `chord`: a non-millimetre outline is a failed run, and an outline with no usable side is a completed run with no edges.
- **Failure.** An outline with no usable edge yields no join that names that outline. The outline itself remains. Superseding the outline revision invalidates its edge arcs and the join candidates that cite them. Those rows stay stored and leave the rank list.

Descriptor choice and numeric parameters are part of the parameter blob. P0 does not set them.

### 5. Propose pairwise rigid joins

- **Inputs.** Edge descriptors for a fragment pool, and the calibration observations those edges depend on.
- **Outputs.** `JoinHypothesis` rows with a rigid relative pose and a `physical` score. Rank follows the `physical` channel.
- **Failure.** When millimetre calibration is missing, do not emit a millimetre pose. The stage may refuse to rank rather than rank in mixed units.

The implemented algorithm `pairwise_rigid_join` version `1` scores each candidate by `negative_absolute_length_difference`, which is not a probability and does not mean the edges meet.

Joins in this contract are pairwise. Three fragments meeting at a point are [Q-SCI-07](#q-sci-07). Hair side and flesh side are [Q-SCI-19](#q-sci-19).

### 6. Search top-N assemblies

- **Inputs.** Join hypotheses and fragment outlines admitted by the physical stage, plus the project's `PageFrame`. A `ScreeningEvent` with gate `physical` records each admission or exclusion.
- **Outputs.** Up to N `AssemblyHypothesis` rows. Placements are rigid transforms into the project's one `page_global_mm` frame. Each assembly records `join_ids` and `unplaced_fragment_ids`. Fragments do not overlap. Scores include the `physical` channel and its `score_context`. N is a recorded parameter. A rigid penalty against the page frame's dimension ranges is a known limitation.
- **Failure.** When the search finds no non-overlapping placement, the run completes with an empty hypothesis list and an explicit empty result. It does not fabricate a placement.

The implemented algorithm `rigid_assembly_search` version `1` scores each kept assembly by `join_score_sum_minus_range_penalty`; the range penalty is a known limitation of the rigid model, and the score does not recover a historical page size.

Page size is [Q-SCI-02](#q-sci-02). Gaps, shrinkage, and cockling are [Q-SCI-03](#q-sci-03). Distinctness inside top-N is [Q-SCI-08](#q-sci-08). Until Q-SCI-08 closes, the stage does not drop assemblies as near-duplicates. Top-N means the N highest `physical` scores among assemblies. It is not an order mixed with joins or readings. Equal scores break ties by content-derived id, ascending.

### 7. Detect text lines

- **Inputs.** A verified image and a fragment outline.
- **Outputs.** `TextLineHypothesis` rows: a baseline and a region in `fragment_local_mm`, epistemic class `interpretation`, producer `machine`. Order is a `TextLineOrder`: a ranked list of alternative sequences of those line ids. A line row has no order index.
- **Failure.** No line yields no HTR call for that fragment. The physical hypotheses remain.



### 8. Local Ancient Greek HTR

- **Inputs.** A line image derived for the recognizer, the line geometry, and a local model identified by hash.
- **Outputs.** `ReadingHypothesis` and `GraphemeHypothesis` rows with text status `ocr_inferred`, epistemic class `interpretation`, producer `machine`, script and language tags, text stored in Unicode NFC, and an `htr` score channel.
- **Failure.** A missing model, a license block, or a runtime error fails the HTR stage for that run. Physical hypotheses remain. The stage does not call a network.

Script and abbreviation scope are [Q-SCI-04](#q-sci-04), closed by [ADR-0010](adr/0010-local-greek-htr-runtime.md). The model, its license, the published checksum, and the download rule are [Q-SCI-14](#q-sci-14), closed by the same ADR. The runtime is [Q-ENG-03](ARCHITECTURE.md#q-eng-03). [P5-02](../tasks/P5-02.md) implements `greek_line_htr` version `1` for one operator-supplied line image and a local `medium.safetensors`. It does not detect lines. The named model emits Unicode NFD. The recognizer normalizes that output to NFC before storage. That step is an adapter. It does not change the storage rule. Kraken confidences are not stored and are not an `htr` score. No `language` score is written. Show-through is [Q-SCI-06](DATA_MODEL.md#q-sci-06). [Q-SCI-16](EVALUATION.md#q-sci-16) is closed by [P5-03](../tasks/P5-03.md). The abbreviation policy is frozen. The workbench character-error report is not implemented. A later ticket may implement that report. P5 is not complete.

### 9. Score language

- **Inputs.** Reading hypotheses whose graphemes are `human_read`, `unclear`, or `ocr_inferred`, and the assemblies or joins those readings sit on.
- **Outputs.** A `language` score channel on hypotheses the physical search already admitted, plus a `ScreeningEvent` for each gate outcome (`admitted` or `excluded`).
- **Failure.** When the stage has no eligible graphemes, it writes no language score. It does not fill the gap with generated letters. An exclusion is a `ScreeningEvent`, not a missing row that looks like a hypothesis never scored.

The stage does not create a join that geometry rejected. Supplied letters are excluded unless [Q-SCI-05](#q-sci-05) is accepted.

### 10. Present channels

- **Inputs.** The run's hypotheses and their channels.
- **Outputs.** The same records, each ranked inside its own `(run, hypothesis_type, channel)`, ready for human review. The UI shows one type and one channel at a time.
- **Failure.** A request for a cross-type total order fails presentation. The runner does not invent a fused key.

Default fusion is [Q-SCI-09](#q-sci-09). Until that question closes, presentation keeps `physical`, `htr`, and `language` separate.

## Invariants

- Never edit source pixels.
- Never invent ink. A grapheme with text is a human reading or an HTR reading, and the text status says which. A reading is `interpretation`. Supplied text is a `hypothesis` on a scholarly restoration. It is not a grapheme text status.
- Never let the language score create a join that geometry rejected.
- Never train or score language using `supplied` text unless Q-SCI-05 is accepted.
- Record every parameter in the provenance envelope. Record `random_seed` when the algorithm used randomness. Omit it when the algorithm is deterministic.
- Keep near-duplicate assemblies out of top-N only after Q-SCI-08 defines diversity. Until then, do not apply a diversity filter.
- A top-ranked hypothesis remains a hypothesis.



## Known failure modes

These modes are expected limits of the proposal. They are not solved in P0.

- **Wrong scale.** A bad calibration shifts every millimetre pose.
- **Bleed-through.** Ink from the other face is read as text on this face.
- **Warping.** Cockled or shrunken parchment violates a rigid placement.
- **Fragments from another leaf.** The pool can contain pieces that do not belong on the hypothesized page.
- **Script mismatch.** An HTR model for a different hand or period emits `ocr_inferred` text. That text stays `interpretation`. It is not the original reading. [ADR-0010](adr/0010-local-greek-htr-runtime.md) chooses one model for all polytonic Greek. The model card does not claim majuscule, papyrus, or inscription coverage.
- **A wrong top rank.** The highest score can be the wrong join or the wrong reading. Rank is not truth.



## Open questions



### Q-SCI-01

Codex leaves only, or also rolls and irregular sheets?

The page frame is a rectangle in ADR-0008. A roll or a badly irregular sheet does not fit that frame.

- Options: rectangular leaves only, which is the working assumption of the first geometric discussion; leaves and irregular sheets still forced into a rectangle; a later roll model.
- Blocks: any scientific claim about rolls or non-rectangular supports. P4 claims beyond a rectangular synthetic leaf wait on this question.



### Q-SCI-02

How are the shared page frame's width and height ranges chosen?

The project has one `PageFrame`. Width and height are ranges, not a point size, and not a size owned by one assembly. Treating an estimated size as the historical page overstates the evidence.

- Options: ranges taken from a catalogue record; ranges set by an explicit prior; ranges left wide until a later measurement.
- Blocks: a P4 scientific claim beyond the synthetic fixture. On that fixture the generator's page size is a `BenchmarkLabel`, and it is ground truth for the fixture only.



### Q-SCI-03

Rigid placement only, or must the first algorithm model shrinkage, cockling, and gaps between edges?

Real parchment often fails to meet in a rigid plane.

- Options: rigid placements and edges that must meet; rigid placements that allow a recorded gap; a non-rigid warp.
- Blocks: a P4 scientific claim on real parchment. The synthetic fixture can follow the rigid proposal. Anisotropic shrinkage is [Q-SCI-20](#q-sci-20).



### Q-SCI-04

Which Greek hands and periods are in scope, and how are nomina sacra, abbreviations, and mixed-script pages stored?

Closed by [ADR-0010](adr/0010-local-greek-htr-runtime.md) and [P5-01](../tasks/P5-01.md). One model covers all polytonic Greek. Separate majuscule and minuscule models are not used. Nomina sacra, abbreviations, and mixed-script pages are recorded under their own `script` or `language` tag and left unscored. Storage is unchanged. A reading carries `script` and `language`. Stored text is Unicode NFC. Comparison and matching may strip accents and normalize final sigma. Storage never does those stripping steps. PP-OCRv6 medium emits Unicode NFD. An implementation normalizes that output to NFC before storage. That step is an adapter. It is not a change to the storage rule, and this close-out does not implement it. [P5-02](../tasks/P5-02.md) normalizes model output to NFC before storage. The PP-OCR card does not say "polytonic" and does not claim majuscule, papyrus, or inscription coverage. The product scope remains one model for all polytonic Greek, and this is the chosen model.

- Blocks: nothing further for the hand scope or for storing those pages. Scoring that expands abbreviations or flattens nomina sacra stays out. [Q-SCI-16](EVALUATION.md#q-sci-16) is closed by [P5-03](../tasks/P5-03.md). The abbreviation policy is frozen. The workbench character-error report is not implemented. A later ticket may implement that report. P5 is not complete.



### Q-SCI-05

May language scoring cross a physical gap using supplied letters?

Supplied letters are scholarly restoration. Scoring them as if they were observed ink feeds the editorial guess back into the ranking.

- Options: no, score only `human_read`, `unclear`, and `ocr_inferred` text; yes, include `supplied` text with an explicit label and a recorded treatment; yes, with no distinction.
- Blocks: P6. Until the question closes, the language stage excludes `supplied` text.



### Q-SCI-07

Are joins pairwise only, or may three fragments meet in one hypothesis?

Tear corners often involve more than two pieces. The hypothesis shape has to say so, or the pairwise poses have to imply the meeting.

- Options: pairwise joins only, with a triple point emerging from consistent pairs; an explicit three-fragment hypothesis type.
- Blocks: adding a triple-fragment type before P3. P3 may implement pairwise joins under this labeled proposal.



### Q-SCI-08

What makes two assemblies distinct inside top-N?

Without a diversity rule, the top of the list can be the same placement with tiny pose changes. A diversity rule chosen after seeing results is evaluation leakage.

- Options: a minimum pose distance in page millimetres; a minimum difference in the set of joins; no diversity filter, so top-N is the N highest assembly scores on the `physical` channel.
- Blocks: a diversity claim in P4. Until the question closes, the search applies no near-duplicate filter.



### Q-SCI-09

May score channels be fused for a default sort, and by which policy?

A single sort key can hide a strong physical join with a weak language score, or the reverse.

- Options: do not fuse, and let the scholar choose the sort channel; a declared weighted sum stored in the parameter blob; a learned fusion after a separate study.
- Blocks: a fused default sort in P6. [ADR-0009](adr/0009-separate-score-channels.md) recommends separate channels until this question closes.



### Q-SCI-14

Which local HTR model, license, and weight hash are required, and is a download ever allowed?

Closed by [ADR-0010](adr/0010-local-greek-htr-runtime.md) and [P5-01](../tasks/P5-01.md). The model is PP-OCRv6 medium, file `medium.safetensors`, by Benjamin Kiessling, ALMAnaCH, Inria Paris, published 4 August 2026, v1. The canonical record is <https://zenodo.org/records/21788410> and <https://doi.org/10.5281/zenodo.21788410> (`10.5281/zenodo.21788410`). An unofficial Hub mirror is not canonical. The license is Apache License 2.0 (<https://www.apache.org/licenses/LICENSE-2.0>). Attribution and notices are required. Some training datasets are private and not redistributable. That does not change the Apache-2.0 grant on the published weights. Zenodo does not publish a SHA-256 for `medium.safetensors`. This record does not supply one. The Zenodo MD5 is `e3411a453ce3b9e9efae3f8631d85762`. That MD5 is not a provenance `model_hash`. The record states 63.8 MB. Official use on the card is Kraken >= 7.1.0, `ocr -m medium.safetensors`. Ancient Greek training sources listed on the card are EPARCHOS, HPGTR, HTR_CPgr23 (Palatinus graecus 23), and Stavronikita Monastery collections 53, 79, and 114, plus private datasets and synthetic augmentation. The card cites Ancient Greek CER 7.21% and WER 44.03% on 451 lines, greedy CTC, NFD and whitespace. Those figures are the card's. Weights are supplied from a local path in the default process. A network download is allowed only after a later, separate implementation approval. [ADR-0001](adr/0001-local-only-processing.md) stays in force. This close-out does not fetch the file and does not add it to Git. The model was chosen because it is the licensed multi-corpus Ancient Greek handwriting model. Licensed alternatives that were found are also Kraken models. The only native `.pt` candidate found had no license on its model card.

- Blocks: nothing further for the named model, its license, or the local-path rule. A download remains a separate implementation approval. [Q-SCI-16](EVALUATION.md#q-sci-16) is closed by [P5-03](../tasks/P5-03.md). The abbreviation policy is frozen. The workbench character-error report is not implemented. A later ticket may implement that report. P5 is not complete.



### Q-SCI-19

Is hair side versus flesh side a join constraint?

Skin side is sometimes visible and can rule out a contact. It is also easy to misread.

- Options: unused; recorded and shown, not scored; a hard constraint; a feature inside the `physical` channel.
- Blocks: using hair or flesh side in P3. Whether the first product records it at all is [Q-PRD-10](PRD.md#q-prd-10).



### Q-SCI-20

Is anisotropic shrinkage residual error or a modeled transform?

A single uniform scale cannot represent different shrinkage along the two skin directions. Fitting a richer transform can absorb the wrong join.

- Options: report shrinkage as residual error and do not fit it; keep the single uniform scale that already lives on `CalibrationTransform` and do not add a second axis; fit a two-axis scale; fit a richer warp.
- Blocks: a shrinkage model. The ADR-0008 proposal leaves shrinkage as residual error until this question closes. A rigid rank penalty is a known limitation in the meantime. See also [Q-SCI-03](#q-sci-03). The uniform scale on a calibration transform is not a placement and is not a shrinkage model.

