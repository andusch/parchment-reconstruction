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
- **Failure.** On mismatch or unreadable bytes, stop for that file. Do not emit outlines, joins, or readings. The failure is an `IntegrityFailure`, not observed evidence. The bytes are not repaired in place. Ingest accepts lossless TIFF only. After ingest, the `originals/` copy is the byte source the later stages read. The decoder name and version go into the provenance envelope.



### 2. Estimate scale

- **Inputs.** A verified source image and a scale target or a human measurement.
- **Outputs.** A `CalibrationObservation` in `source_pixels`, with uncertainty, epistemic class `observed`, and a `CalibrationTransform` for that image only. Producer is `human`, `machine`, or `imported`, and the class stays `observed`.
- **Failure.** When no scale evidence exists, do not emit millimetre placements. A claimed resolution in the file header never becomes `pixels_per_mm`. The importer warns and leaves calibration absent. Pixel-space observations may still be recorded in `source_pixels`.

The target type and the acceptable scale error are [Q-SCI-10](SCAN_PROTOCOL.md#q-sci-10).

### 3. Segment fragments

- **Inputs.** A verified source image.
- **Outputs.** One or more `FragmentOutlineRevision` rows, epistemic class `interpretation`, producer `machine`, grouped by an `AlgorithmRun`.
- **Failure.** When segmentation fails, record the failed run under its own id, not the id a later completed run of the same inputs would take. Do not invent an outline. A group scan is `SourceImage.group_scan` from the [scan protocol](SCAN_PROTOCOL.md). It is not a confidence value, and it is not treated as metrologically equivalent to a one-fragment frame.



### 4. Build edge descriptors

- **Inputs.** An outline and, when scale exists, the transform into `fragment_local_mm`.
- **Outputs.** `EdgeArc` rows in `fragment_local_mm`, scoped to that outline revision, and the descriptors the join stage will consume. Descriptors are epistemic class `interpretation`, producer `machine`, and travel inside the run's provenance.
- **Failure.** An outline with no usable edge yields no join that names that outline. The outline itself remains. Superseding the outline revision invalidates its edge arcs and the join candidates that cite them. Those rows stay stored and leave the rank list.

Descriptor choice and numeric parameters are part of the parameter blob. P0 does not set them.

### 5. Propose pairwise rigid joins

- **Inputs.** Edge descriptors for a fragment pool, and the calibration observations those edges depend on.
- **Outputs.** `JoinHypothesis` rows with a rigid relative pose and a `physical` score. Rank follows the `physical` channel.
- **Failure.** When millimetre calibration is missing, do not emit a millimetre pose. The stage may refuse to rank rather than rank in mixed units.

Joins in this contract are pairwise. Three fragments meeting at a point are [Q-SCI-07](#q-sci-07). Hair side and flesh side are [Q-SCI-19](#q-sci-19).

### 6. Search top-N assemblies

- **Inputs.** Join hypotheses and fragment outlines admitted by the physical stage, plus the project's `PageFrame`. A `ScreeningEvent` with gate `physical` records each admission or exclusion.
- **Outputs.** Up to N `AssemblyHypothesis` rows. Placements are rigid transforms into the project's one `page_global_mm` frame. Each assembly records `join_ids` and `unplaced_fragment_ids`. Fragments do not overlap. Scores include the `physical` channel and its `score_context`. N is a recorded parameter. A rigid penalty against the page frame's dimension ranges is a known limitation.
- **Failure.** When the search finds no non-overlapping placement, the run completes with an empty hypothesis list and an explicit empty result. It does not fabricate a placement.

Page size is [Q-SCI-02](#q-sci-02). Gaps, shrinkage, and cockling are [Q-SCI-03](#q-sci-03). Distinctness inside top-N is [Q-SCI-08](#q-sci-08). Until Q-SCI-08 closes, the stage does not drop assemblies as near-duplicates. Top-N means the N highest `physical` scores among assemblies. It is not an order mixed with joins or readings. Equal scores break ties by content-derived id, ascending.

### 7. Detect text lines

- **Inputs.** A verified image and a fragment outline.
- **Outputs.** `TextLineHypothesis` rows: a baseline and a region in `fragment_local_mm`, epistemic class `interpretation`, producer `machine`. Order is a `TextLineOrder`: a ranked list of alternative sequences of those line ids. A line row has no order index.
- **Failure.** No line yields no HTR call for that fragment. The physical hypotheses remain.



### 8. Local Ancient Greek HTR

- **Inputs.** A line image derived for the recognizer, the line geometry, and a local model identified by hash.
- **Outputs.** `ReadingHypothesis` and `GraphemeHypothesis` rows with text status `ocr_inferred`, epistemic class `interpretation`, producer `machine`, script and language tags, text stored in Unicode NFC, and an `htr` score channel.
- **Failure.** A missing model, a license block, or a runtime error fails the HTR stage for that run. Physical hypotheses remain. The stage does not call a network.

Script, period, and abbreviation scope are [Q-SCI-04](#q-sci-04). The model, its license, its weight hash, and any download are [Q-SCI-14](#q-sci-14). No model is approved in P0. Show-through is [Q-SCI-06](DATA_MODEL.md#q-sci-06).

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
- **Script mismatch.** An HTR model for a different hand or period emits `ocr_inferred` text. That text stays `interpretation`. It is not the original reading.
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

Storage is already decided. Readings carry `script` and `language`. Stored text is Unicode NFC. Comparison and matching may strip accents and normalize final sigma. Storage never does those steps. A page is never forced through a Greek-only reading. The full Greek-policy ADR is Phase 5. HTR and language scoring are only meaningful inside a declared corpus of hands and conventions.

- Options: a named subset chosen before P5; all polytonic Greek in one model; separate models for majuscule and minuscule. Separately, for nomina sacra, abbreviations, and mixed-script pages: record them under their own script or language tag and leave them unscored; or defer a representation until the Phase 5 ADR.
- Blocks: P5 model choice, and any scoring that would expand abbreviations or flatten nomina sacra.



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

Weights are code-like, licensed, and large. A downloader is a network call.

- Options: a named local model, reviewed license, and a recorded weight hash, with weights provided from a local path; no model in the first releases; a download only after a separate implementation approval.
- Blocks: P5. P0 approves no model, no weight file, and no download. See [ADR-0010](adr/0010-local-greek-htr-runtime.md).



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

