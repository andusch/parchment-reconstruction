# Open questions

- Status: Draft for review
- Phase: P0
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)

This index lists every question that is still open, and it records questions that have been closed. The owning document holds the same decision or the same options; if the two diverge, the owning document is the one to amend in the same change as this index.

Closing a question that touches evidence semantics, project format, public API, or privacy policy requires an ADR and an explicit decision. Questions without that decision stay open.

Renaming the stored status `ocr_inferred` to `htr_inferred` is an evidence-semantics change. It has no separate ID. It stays forbidden until an explicit decision, as stated in the [data model](DATA_MODEL.md#text-status-and-epistemic-class).

## Product

### Q-PRD-01

- **Owning document.** [PRD.md](PRD.md#q-prd-01)
- **Question.** Are scholar, imaging operator, and benchmark operator separate roles in v1, or one operator?
- **Why it matters.** Separate accounts change the validation record and the export rules for operator names. One shared operator is enough for a single-user desktop tool.
- **Options.** One local operator with a role label on each action; three distinct local profiles; no role field at all.
- **Blocks.** Role-specific UI in P7. P1 can store a single actor string under the labeled assumption of one local operator. Pilot-05 stores the actor string `local-operator` and does not define roles. This question stays open.

### Q-PRD-02

- **Owning document.** [PRD.md](PRD.md#q-prd-02)
- **Question.** Is a project one leaf, one manuscript, or a pool with many hypothesized pages?
- **Why it matters.** The choice fixes the manifest, the fragment pool, and what an assembly is allowed to contain.
- **Options.** One leaf; one manuscript with many leaves; a pool of fragments and many hypothesized pages, which is the working assumption; a multi-manuscript collection.
- **Blocks.** Closing the project-shape decision. P1 may follow the working assumption only while this question stays open and the assumption stays labeled.

### Q-PRD-03

- **Owning document.** [PRD.md](PRD.md#q-prd-03)
- **Question.** Do recto and verso constrain the first assembly model?
- **Why it matters.** Face identity changes which outlines may meet and which readings may be scored together.
- **Options.** Capture both faces and ignore face in assembly; capture both faces and forbid joins across opposite faces; model a leaf as a front-and-back pair.
- **Blocks.** Face constraints in P4. Capture of both faces can proceed under the scan protocol.

### Q-PRD-04

- **Owning document.** [PRD.md](PRD.md#q-prd-04)
- **Question.** Are multi-fragment group scans a supported ingest mode?
- **Why it matters.** Group scans change detection, scale confidence, and the acceptance checklist.
- **Options.** One fragment per frame only; group scans allowed, recorded as `group_scan` on the source image, and not treated as metrologically equivalent; group scans treated as equivalent to one-fragment frames.
- **Blocks.** P1 ingest rules for group scans. The provisional protocol flags group scans and does not treat them as metrologically equivalent.

### Q-PRD-05

- **Status.** Closed by [ADR-0012](adr/0012-export-types.md).
- **Owning document.** [PRD.md](PRD.md#q-prd-05)
- **Decision.** An audit export includes master bytes or rendered composites and recomputable hashes. A metadata-only export is labeled non-auditable. Both state whether they contain every hypothesis or a top-N cut of one type and one channel. Leiden-style markers are the editorial convention. The marker text is filled at export time.
- **Blocks.** Nothing further for the export type. P8 remains blocked by the privacy questions.

### Q-PRD-06

- **Owning document.** [PRD.md](PRD.md#q-prd-06)
- **Question.** Is macOS the only first desktop target?
- **Why it matters.** Qt can target more than one operating system. The first tested platform still has to be chosen.
- **Options.** macOS only; macOS and Linux; macOS, Linux, and Windows.
- **Blocks.** P7 packaging claims. Documentation in P0 is platform-neutral. Pilot-05 does not choose a desktop target. This question stays open.

### Q-PRD-07

- **Owning document.** [PRD.md](PRD.md#q-prd-07)
- **Question.** What fragment count and page count must a project handle?
- **Why it matters.** Search cost and UI density depend on the bound.
- **Options.** Tens of fragments and one page; low hundreds of fragments and a handful of pages; a larger bound stated with a number before P3.
- **Blocks.** Performance targets for P3 and P4. P0 states no capacity number.

### Q-PRD-08

- **Status.** Closed by [ADR-0013](adr/0013-human-outline-correction.md).
- **Owning document.** [PRD.md](PRD.md#q-prd-08)
- **Decision.** A human correction of a machine outline is a new `FragmentOutlineRevision` in class `interpretation` with `producer: human`. `run_id` is null. `operator_id` and `session_id` are set. There is no machine envelope. `supersedes_id` cites the machine revision, which stays. Source bytes stay. The correction is not a `FragmentExtent`. Acceptance does not re-type the machine outline. The row is not benchmark ground truth.
- **Blocks.** Nothing for the evidence class of the correction. [P2-06](../tasks/P2-06.md) may store that row. An accuracy claim against human outlines stays blocked by [Q-SCI-17](EVALUATION.md#q-sci-17).

### Q-PRD-09

- **Owning document.** [PRD.md](PRD.md#q-prd-09)
- **Question.** Is a working reconstruction a named selection, or only a set of validation decisions?
- **Why it matters.** A named selection can be mistaken for the original page if the UI labels it poorly.
- **Options.** Validation decisions only; a named selection that cites hypothesis ids and keeps its epistemic class as scholarly restoration; a mutable canvas that edits placements in place.
- **Blocks.** The P7 working-set UI, and any project-format field for a preferred reconstruction. Pilot-05 records validation decisions only and does not name a reconstruction. This question stays open.

### Q-PRD-10

- **Owning document.** [PRD.md](PRD.md#q-prd-10)
- **Question.** Are ruling, pricking, and hair/flesh side in the first product?
- **Why it matters.** These physical features can constrain joins. They also widen capture and the data model.
- **Options.** Out of the first product; recorded as optional observations and unused by search; used as additional `physical` features.
- **Blocks.** Feature work in P2 and P3. The first algorithm contract does not require them. Hair/flesh side as a join constraint is also [Q-SCI-19](ALGORITHM.md#q-sci-19).

## Scientific

### Q-SCI-01

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-01)
- **Question.** Codex leaves only, or also rolls and irregular sheets?
- **Why it matters.** The page frame is a rectangle in [ADR-0008](adr/0008-rigid-rectangular-page.md). A roll or a badly irregular sheet does not fit that frame.
- **Options.** Rectangular leaves only, which is the working assumption of the first geometric discussion; leaves and irregular sheets still forced into a rectangle; a later roll model.
- **Blocks.** Any scientific claim about rolls or non-rectangular supports. P4 claims beyond a rectangular synthetic leaf wait on this question.

### Q-SCI-02

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-02)
- **Question.** How are the shared page frame's width and height ranges chosen?
- **Why it matters.** The project has one `PageFrame`. Width and height are ranges, not a point size, and not a size owned by one assembly. Treating an estimated size as the historical page overstates the evidence.
- **Options.** Ranges taken from a catalogue record; ranges set by an explicit prior; ranges left wide until a later measurement.
- **Blocks.** A P4 scientific claim beyond the synthetic fixture. On that fixture the generator's page size is a `BenchmarkLabel`, and it is ground truth for the fixture only.

### Q-SCI-03

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-03)
- **Question.** Rigid placement only, or must the first algorithm model shrinkage, cockling, and gaps between edges?
- **Why it matters.** Real parchment often fails to meet in a rigid plane.
- **Options.** Rigid placements and edges that must meet; rigid placements that allow a recorded gap; a non-rigid warp.
- **Blocks.** A P4 scientific claim on real parchment. The synthetic fixture can follow the rigid proposal. Anisotropic shrinkage is [Q-SCI-20](ALGORITHM.md#q-sci-20).

### Q-SCI-04

- **Status.** Closed by [ADR-0010](adr/0010-local-greek-htr-runtime.md) and [P5-01](../tasks/P5-01.md).
- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-04)
- **Decision.** One model covers all polytonic Greek. Separate majuscule and minuscule models are not used. Nomina sacra, abbreviations, and mixed-script pages are recorded under their own `script` or `language` tag and left unscored. Storage is unchanged. A reading carries `script` and `language`. Stored text is Unicode NFC. Comparison and matching may strip accents and normalize final sigma. Storage never does those stripping steps. PP-OCRv6 medium emits Unicode NFD. An implementation normalizes that output to NFC before storage. That step is an adapter. It is not a change to the storage rule, and this close-out does not implement it. [P5-02](../tasks/P5-02.md) normalizes model output to NFC before storage. The PP-OCR card does not say "polytonic" and does not claim majuscule, papyrus, or inscription coverage. The product scope remains one model for all polytonic Greek, and this is the chosen model.
- **Blocks.** Nothing further for the hand scope or for storing those pages. Scoring that expands abbreviations or flattens nomina sacra stays out. [Q-SCI-16](EVALUATION.md#q-sci-16) is closed by [P5-03](../tasks/P5-03.md). The abbreviation policy is frozen. [P5-04](../tasks/P5-04.md) reports character error rate on a frozen synthetic line fixture. The scored total is edit distance 1 over reference length 22. That number is a synthetic-fixture result. It does not measure Ancient Greek handwriting, scholarly acceptability, or the model card. The card's cited Ancient Greek CER 7.21% and WER 44.03% stay citations only and are not compared with this figure. P5's official exit criteria are met. [Q-SCI-06](DATA_MODEL.md#q-sci-06) and [Q-SCI-13](DATA_MODEL.md#q-sci-13) stay open and do not block that exit. [Q-SCI-15](EVALUATION.md#q-sci-15) still blocks an accuracy claim on a real manuscript.

### Q-SCI-05

- **Status.** Closed by [P6-01](../tasks/P6-01.md). No ADR: the question does not touch evidence semantics, project format, a public API, or privacy policy. Supplied text already has epistemic class `hypothesis` on a scholarly restoration. This scoring treatment does not re-type a grapheme. Andu approved the policy on 2026-11-15 (Asia/Hong_Kong), in the Elon · Coding chat, after [P5-04](../tasks/P5-04.md) (PR #28) merged to master.
- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-05)
- **Decision.** Yes, include supplied text with an explicit label and a recorded treatment. Language scoring may use supplied letters only with that label and treatment. Language still does not create a join that geometry rejected. Training on scholarly restoration stays out of scope. The language scorer remains unimplemented.
- **Blocks.** Nothing further for this policy. The language scorer remains unimplemented.

### Q-SCI-06

- **Owning document.** [DATA_MODEL.md](DATA_MODEL.md#q-sci-06)
- **Question.** How are bleed-through and show-through represented?
- **Why it matters.** Ink from the opposite face can be segmented as text. The representation decides whether that ink is a reading on this face, a link to the other face, or a flagged region with no reading.
- **Options.** Ignore show-through in the first reading model and treat it as a known failure; store a region flagged as possible show-through without a reading; register the two faces and attribute the ink to one of them.
- **Blocks.** The P5 reading model for opposite-face ink. The first algorithm contract names bleed-through as a failure mode and does not represent it as a reading.

### Q-SCI-07

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-07)
- **Question.** Are joins pairwise only, or may three fragments meet in one hypothesis?
- **Why it matters.** Tear corners often involve more than two pieces. The hypothesis shape has to say so, or the pairwise poses have to imply the meeting.
- **Options.** Pairwise joins only, with a triple point emerging from consistent pairs; an explicit three-fragment hypothesis type.
- **Blocks.** Adding a triple-fragment type before P3. P3 may implement pairwise joins under this labeled proposal.

### Q-SCI-08

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-08)
- **Question.** What makes two assemblies distinct inside top-N?
- **Why it matters.** Without a diversity rule, the top of the list can be the same placement with tiny pose changes. A diversity rule chosen after seeing results is evaluation leakage.
- **Options.** A minimum pose distance in page millimetres; a minimum difference in the set of joins; no diversity filter, so top-N is the N highest assembly scores on the `physical` channel.
- **Blocks.** A diversity claim in P4. Until the question closes, the search applies no near-duplicate filter.

### Q-SCI-09

- **Status.** Closed by [ADR-0009](adr/0009-separate-score-channels.md), accepted as option 2, and by [P6-01](../tasks/P6-01.md). Andu accepted the ADR on 2026-11-15 (Asia/Hong_Kong), in the Elon · Coding chat, after [P5-04](../tasks/P5-04.md) (PR #28) merged to master.
- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-09)
- **Decision.** Store `physical`, `htr`, and `language` as separate channels, and also allow a declared weighted sum in the parameter blob as the default sort. This close-out does not pick weight values and does not write a fused value. Accepting option 2 is an algorithm change. The later implementation needs a benchmark comparison on the frozen fixture. This close-out does not write that comparison. Language scoring may annotate only hypotheses the physical search already admitted. It does not create joins. Scores remain uncalibrated ranking features. They are not probabilities.
- **Blocks.** Nothing further for the fusion policy. The declared weighted sum remains unimplemented.

### Q-SCI-10

- **Owning document.** [SCAN_PROTOCOL.md](SCAN_PROTOCOL.md#q-sci-10)
- **Question.** Which calibration target and scale-error bound are required?
- **Why it matters.** Join ranking in millimetres is only as good as the scale observation. A number stated too early becomes a false standard.
- **Options.** A ruler; a dot grid or checker target; an institution-specific target. Separately, the scale-error bound may be unset until a study, or set to a percent before P1 calibration tests. A file-header resolution is not an option. It never populates calibration.
- **Blocks.** Treating any numeric imaging threshold as validated. Blocks P1 calibration acceptance tests that would enforce a specific target or error bound. Lossless TIFF is already required at ingest and is not part of this question. A scale target in frame and at least 600 ppi at object scale remain a provisional bar, not a decision.

### Q-SCI-11

- **Status.** Closed by [ADR-0011](adr/0011-frame-conventions.md).
- **Owning document.** [ADR-0011](adr/0011-frame-conventions.md)
- **Decision.** `fragment_local_mm` origin is the centroid of the outline revision cited by `CoordinateFrame.establishing_outline_revision_id`. That citation is the mask, it is fixed when the frame is created, and a later revision does not move it. Axes are `+x` right, `+y` down, millimetres. `page_global_mm` origin is the corner with the smallest x and the smallest y, at coordinate (0, 0), with the same axes. Width and height ranges are measured from that origin. `source_pixels` uses those axes with its origin at the top-left pixel. Stored frames repeat that convention as redundancy.
- **Blocks.** Nothing. The synthetic generator writes coordinates in this convention.

### Q-SCI-12

- **Status.** Closed by [ADR-0011](adr/0011-frame-conventions.md).
- **Owning document.** [ADR-0011](adr/0011-frame-conventions.md)
- **Decision.** Same decision as Q-SCI-11. The fragment-local origin is the centroid of the cited outline revision and does not move when that revision is superseded. The page origin is the corner with the smallest x and the smallest y, at coordinate (0, 0).
- **Blocks.** Nothing.

### Q-SCI-13

- **Owning document.** [DATA_MODEL.md](DATA_MODEL.md#q-sci-13)
- **Question.** What does a `GapRegion` denote: absent support, absent ink, or an editorial lacuna?
- **Why it matters.** `missing` is not a grapheme status. A gap is a `GapRegion` on a page hypothesis. The three situations remain different, and the stored schema does not store a separate label for each.
- **Options.** Leave the `GapRegion` unlabeled as to which of the three it denotes; store that distinction on the `GapRegion`.
- **Blocks.** Storing the distinction. P5 and P8 need a closed question before they emit lacunae as a distinct label. They do not emit a grapheme status `missing`.

### Q-SCI-14

- **Status.** Closed by [ADR-0010](adr/0010-local-greek-htr-runtime.md) and [P5-01](../tasks/P5-01.md).
- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-14)
- **Decision.** The model is PP-OCRv6 medium, file `medium.safetensors`, by Benjamin Kiessling, ALMAnaCH, Inria Paris, published 4 August 2026, v1. The canonical record is <https://zenodo.org/records/21788410> and <https://doi.org/10.5281/zenodo.21788410> (`10.5281/zenodo.21788410`). An unofficial Hub mirror is not canonical. The license is Apache License 2.0 (<https://www.apache.org/licenses/LICENSE-2.0>). Attribution and notices are required. Some training datasets are private and not redistributable. That does not change the Apache-2.0 grant on the published weights. Zenodo does not publish a SHA-256 for `medium.safetensors`. This record does not supply one. The Zenodo MD5 is `e3411a453ce3b9e9efae3f8631d85762`. That MD5 is not a provenance `model_hash`. The record states 63.8 MB. Official use on the card is Kraken >= 7.1.0, `ocr -m medium.safetensors`. Ancient Greek training sources listed on the card are EPARCHOS, HPGTR, HTR_CPgr23 (Palatinus graecus 23), and Stavronikita Monastery collections 53, 79, and 114, plus private datasets and synthetic augmentation. The card cites Ancient Greek CER 7.21% and WER 44.03% on 451 lines, greedy CTC, NFD and whitespace. Those figures are the card's. Weights are supplied from a local path in the default process. A network download is allowed only after a later, separate implementation approval. [ADR-0001](adr/0001-local-only-processing.md) stays in force. This close-out does not fetch the file and does not add it to Git. The model was chosen because it is the licensed multi-corpus Ancient Greek handwriting model. Licensed alternatives that were found are also Kraken models. The only native `.pt` candidate found had no license on its model card.
- **Blocks.** Nothing further for the named model, its license, or the local-path rule. A download remains a separate implementation approval. [Q-SCI-16](EVALUATION.md#q-sci-16) is closed by [P5-03](../tasks/P5-03.md). The abbreviation policy is frozen. [P5-04](../tasks/P5-04.md) reports character error rate on a frozen synthetic line fixture. The scored total is edit distance 1 over reference length 22. That number is a synthetic-fixture result. It does not measure Ancient Greek handwriting, scholarly acceptability, or the model card. The card's cited Ancient Greek CER 7.21% and WER 44.03% stay citations only and are not compared with this figure. P5's official exit criteria are met. [Q-SCI-06](DATA_MODEL.md#q-sci-06) and [Q-SCI-13](DATA_MODEL.md#q-sci-13) stay open and do not block that exit. [Q-SCI-15](EVALUATION.md#q-sci-15) still blocks an accuracy claim on a real manuscript.

### Q-SCI-15

- **Status.** Partially answered on 8 November 2026 for one candidate set. The license review is [pilot-public-corpus.md](pilot-public-corpus.md). The operator steps for a local file, a checksum, and a scale note are [pilot-import-path.md](pilot-import-path.md). One worked file is [pilot-first-run.md](pilot-first-run.md). The question stays open for every other corpus and for any accuracy claim on real manuscripts.
- **Owning document.** [EVALUATION.md](EVALUATION.md#q-sci-15)
- **Question.** Which evaluation corpora are permitted, and under what license?
- **Why it matters.** Real manuscript images are culturally sensitive and often unpublished or licensed. Synthetic tears cannot stand in for them.
- **Options.** Synthetic tears only, including in the repository; published images stored outside Git under a named license and cited by hash; no real-image claims until a separate license review.
- **Blocks.** Any accuracy claim on real manuscripts. In-repo benchmark material stays synthetic. The partial answer covers local storage and checksums for the named sources only.

### Q-SCI-16

- **Status.** Closed by [P5-03](../tasks/P5-03.md). No ADR: the question does not touch evidence semantics, project format, a public API, or privacy policy. Andu approved the policy on 2026-11-14 (Asia/Hong_Kong), after [P5-02](../tasks/P5-02.md) merged to master.
- **Owning document.** [EVALUATION.md](EVALUATION.md#q-sci-16)
- **Decision.** Lines the operator tags as a nomen sacrum, an abbreviation, or mixed-script stay unscored and are excluded from the character-error set. Every other scored line is compared as written. Abbreviations are not expanded. [ADR-0010](adr/0010-local-greek-htr-runtime.md) already records that abbreviation expansion can be unpredictable. Storage stays Unicode NFC. This close-out does not change the storage rule. Comparison may still strip accents and normalize final sigma, as the data model already allows. Storage never does those stripping steps. The policy is frozen before any reportable run. The PP-OCRv6 medium model card's cited Ancient Greek CER 7.21% and WER 44.03% stay citations only. This close-out reports no workbench character-error number. [P5-04](../tasks/P5-04.md) later reports the synthetic-fixture rate. The scored total is edit distance 1 over reference length 22. That number does not measure Ancient Greek handwriting, scholarly acceptability, or the model card, and it is not compared with the card's cited 7.21% CER or 44.03% WER.
- **Blocks.** Nothing further for the abbreviation policy. [P5-04](../tasks/P5-04.md) reports character error rate on a frozen synthetic line fixture. The scored total is edit distance 1 over reference length 22. That number is a synthetic-fixture result. It does not measure Ancient Greek handwriting, scholarly acceptability, or the model card. P5's official exit criteria are met. The report is what makes the synthetic-fixture number reportable under the frozen policy. [Q-SCI-06](DATA_MODEL.md#q-sci-06) and [Q-SCI-13](DATA_MODEL.md#q-sci-13) stay open and do not block that exit. [Q-SCI-15](EVALUATION.md#q-sci-15) still blocks an accuracy claim on a real manuscript.

### Q-SCI-17

- **Owning document.** [EVALUATION.md](EVALUATION.md#q-sci-17)
- **Question.** Is a human outline the ground truth for fragment detection, and what is the annotator protocol?
- **Why it matters.** A single corrected outline can be one expert's trace. Calling it ground truth needs a protocol.
- **Options.** One expert outline is the reference; two annotators and a stated agreement rule; synthetic generator polygons are the only reference until a protocol exists.
- **Blocks.** A P2 accuracy claim against human outlines. Synthetic outline agreement against generator polygons can proceed without this question. A corrected outline is `interpretation` under [ADR-0013](adr/0013-human-outline-correction.md), which closed [Q-PRD-08](PRD.md#q-prd-08). This question still blocks an accuracy claim against human outlines.

### Q-SCI-18

- **Owning document.** [SCAN_PROTOCOL.md](SCAN_PROTOCOL.md#q-sci-18)
- **Question.** Are multispectral or other modalities in scope later?
- **Why it matters.** Extra bands change the source-image model, the checksum story, and what a capture of a fragment is.
- **Options.** Visible-light captures only, including later phases; a later phase for registered multispectral or other bands; a single source file that already stacks bands.
- **Blocks.** Any ingest path for non-visible modalities. The first product lists multispectral capture as a non-goal in the [PRD](PRD.md#non-goals).

### Q-SCI-19

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-19)
- **Question.** Is hair side versus flesh side a join constraint?
- **Why it matters.** Skin side is sometimes visible and can rule out a contact. It is also easy to misread.
- **Options.** Unused; recorded and shown, not scored; a hard constraint; a feature inside the `physical` channel.
- **Blocks.** Using hair or flesh side in P3. Whether the first product records it at all is [Q-PRD-10](PRD.md#q-prd-10).

### Q-SCI-20

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-20)
- **Question.** Is anisotropic shrinkage residual error or a modeled transform?
- **Why it matters.** A single uniform scale cannot represent different shrinkage along the two skin directions. Fitting a richer transform can absorb the wrong join.
- **Options.** Report shrinkage as residual error and do not fit it; keep the single uniform scale that already lives on `CalibrationTransform` and do not add a second axis; fit a two-axis scale; fit a richer warp.
- **Blocks.** A shrinkage model. The ADR-0008 proposal leaves shrinkage as residual error until this question closes. See also [Q-SCI-03](ALGORITHM.md#q-sci-03).

## Privacy

### Q-PRI-01

- **Owning document.** [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md#q-pri-01)
- **Question.** Should the app warn when the project directory is inside a cloud-sync folder?
- **Why it matters.** A warning can prevent an accidental upload. Detecting sync roots is platform-specific and can be wrong.
- **Options.** Warn when the path is under a known sync root; document the risk and do not detect it; refuse to create a project in a detected sync root.
- **Blocks.** A P7 warning or refusal. The risk stands in P0 as an operator responsibility. Pilot-05 writes no project directory and does not detect a sync folder. This question stays open.

### Q-PRI-02

- **Owning document.** [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md#q-pri-02)
- **Question.** Must exports be able to omit operator names?
- **Why it matters.** Names in decisions and sidecars identify who recorded evidence. They are also personal data in a bundle that may be shared.
- **Options.** Exports include actor strings; exports have a switch that omits them; actor strings are never stored.
- **Blocks.** P8. Until it closes, the data model allows an actor field and the privacy policy treats the name as optional personal data.

### Q-PRI-03

- **Owning document.** [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md#q-pri-03)
- **Question.** Do museum or archive agreements need an access-restriction field on a project?
- **Why it matters.** Some captures may be stored locally and still be contractually barred from export or from being shown to a wider group.
- **Options.** No field, with restrictions handled outside the tool; a free-text restriction note that export must display; a structured flag that blocks export until the operator confirms.
- **Blocks.** Any P8 access-control behavior. P0 stores no restriction field.

## Engineering

### Q-ENG-01

- **Owning document.** [ARCHITECTURE.md](ARCHITECTURE.md#q-eng-01)
- **Question.** Content-addressed files, SQLite, or both?
- **Why it matters.** The store is the project format. Changing it later requires a migration and stop-and-ask.
- **Options.** A directory of content-addressed files plus JSON records; a single SQLite database with originals stored as files beside it; SQLite for records and content-addressed files for originals, which is the layout sketched in the architecture.
- **Blocks.** Accepting a project format. P1 implements a store only after this question is closed, or keeps the implementation behind a decision that answers it. Pilot-05 keeps the review session in memory and writes no project directory. This question stays open.

### Q-ENG-02

- **Status.** Closed by [P1-01](../tasks/P1-01.md). No ADR: the question does not touch evidence semantics, project format, a public API, or privacy policy.
- **Owning document.** [ARCHITECTURE.md](ARCHITECTURE.md#q-eng-02)
- **Decision.** Minimum Python is 3.12. The layout is `src/`. The distribution name is `parchment-workbench`. The import package is `prw`.
- **Blocks.** Nothing further for packaging.

### Q-ENG-03

- **Status.** Closed by [ADR-0010](adr/0010-local-greek-htr-runtime.md) and [P5-01](../tasks/P5-01.md).
- **Owning document.** [ARCHITECTURE.md](ARCHITECTURE.md#q-eng-03)
- **Decision.** The product-facing HTR runtime is Kraken >= 7.1.0. This supersedes an earlier lean toward PyTorch with local weights. Kraken uses PyTorch underneath. A first-party `torch.load` trainer is not the runtime. Weights are the local file `medium.safetensors` (PP-OCRv6 medium). The default process does not download them. [P5-02](../tasks/P5-02.md) adds Kraken >= 7.1.0 in the optional `htr` group and the unfrozen `recognize` command. The group is not a default group. The Kraken package license is Apache-2.0, recorded on that ticket. A weight download remains a separate approval. The weight license is Apache-2.0, recorded in the ADR. The model was chosen because it is the licensed multi-corpus Ancient Greek handwriting model. Licensed alternatives that were found are also Kraken models. The only native `.pt` candidate found had no license on its model card.
- **Blocks.** Nothing further for the runtime choice. [Q-SCI-16](EVALUATION.md#q-sci-16) is closed by [P5-03](../tasks/P5-03.md). The abbreviation policy is frozen. [P5-04](../tasks/P5-04.md) reports character error rate on a frozen synthetic line fixture. The scored total is edit distance 1 over reference length 22. That number is a synthetic-fixture result. It does not measure Ancient Greek handwriting, scholarly acceptability, or the model card. P5's official exit criteria are met. [Q-SCI-06](DATA_MODEL.md#q-sci-06) and [Q-SCI-13](DATA_MODEL.md#q-sci-13) stay open and do not block that exit.

### Q-ENG-04

- **Owning document.** [ARCHITECTURE.md](ARCHITECTURE.md#q-eng-04)
- **Question.** Geometry library versus an in-house implementation, including license?
- **Why it matters.** Join and assembly geometry need robust polygons. A library adds a license obligation.
- **Options.** An in-house implementation of the rigid operations the algorithm contract needs; a documented geometry library chosen with its license at implementation time.
- **Blocks.** P3 and P4 implementation choices. The algorithm contract does not name a library.

### Q-ENG-05

- **Status.** Closed by [ADR-0014](adr/0014-stdlib-lossless-tiff.md) and [PILOT-03](../tasks/PILOT-03.md).
- **Owning document.** [ADR-0014](adr/0014-stdlib-lossless-tiff.md)
- **Decision.** No new runtime dependency. `struct` and `zlib` from the Python standard library read classic lossless TIFF. The synthetic fixture layout keeps decoder `synthetic_uncompressed_tiff` version `1`. Every other accepted master records `lossless_tiff` version `1`. Epistemic class is unchanged. Header resolution is not `pixels_per_mm`.
- **Blocks.** Nothing further for the TIFF library. Refused layouts are in the ADR. A project format remains [Q-ENG-01](ARCHITECTURE.md#q-eng-01).

### Q-ENG-06

- **Owning document.** [ARCHITECTURE.md](ARCHITECTURE.md#q-eng-06)
- **Question.** Worker thread or worker process for expensive jobs?
- **Why it matters.** [ADR-0005](adr/0005-qt-shell-and-headless-core.md) requires work off the UI thread and does not choose the isolation mechanism. A process crash can leave the shell up. A thread shares memory and needs a stricter cancellation story.
- **Options.** A worker thread; a worker process that calls the same use-case entry points as the CLI; either, chosen per job class.
- **Blocks.** P7 worker implementation. P1 CLI work can run in the foreground process. Pilot-05 runs one rank on a Qt thread inside the review window and does not choose thread versus process for P7. This question stays open. See [ADR-0015](adr/0015-thin-review-window.md).
