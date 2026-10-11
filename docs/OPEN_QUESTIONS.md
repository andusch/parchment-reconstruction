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
- **Blocks.** Role-specific UI in P7. P1 can store a single actor string under the labeled assumption of one local operator.

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
- **Blocks.** P7 packaging claims. Documentation in P0 is platform-neutral.

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
- **Blocks.** The P7 working-set UI, and any project-format field for a preferred reconstruction.

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

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-04)
- **Question.** Which Greek hands and periods are in scope, and how are nomina sacra, abbreviations, and mixed-script pages stored?
- **Why it matters.** Storage is already decided: readings carry `script` and `language`, stored text is Unicode NFC, and comparison may strip accents and normalize final sigma. Storage never does those steps. A page is never forced through a Greek-only reading. HTR and language scoring are only meaningful inside a declared corpus of hands and conventions. The full ADR is Phase 5.
- **Options.** A named subset chosen before P5; all polytonic Greek in one model; separate models for majuscule and minuscule. Separately, for nomina sacra, abbreviations, and mixed-script pages: record them under their own script or language tag and leave them unscored; or defer a representation until the Phase 5 ADR.
- **Blocks.** P5 model choice, and any scoring that would expand abbreviations or flatten nomina sacra.

### Q-SCI-05

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-05)
- **Question.** May language scoring cross a physical gap using supplied letters?
- **Why it matters.** Supplied letters are scholarly restoration. Scoring them as if they were observed ink feeds the editorial guess back into the ranking.
- **Options.** No, score only `human_read`, `unclear`, and `ocr_inferred` text; yes, include `supplied` text with an explicit label and a recorded treatment; yes, with no distinction.
- **Blocks.** P6. Until the question closes, the language stage excludes `supplied` text.

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

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-09)
- **Question.** May score channels be fused for a default sort, and by which policy?
- **Why it matters.** A single sort key can hide a strong physical join with a weak language score, or the reverse.
- **Options.** Do not fuse, and let the scholar choose the sort channel; a declared weighted sum stored in the parameter blob; a learned fusion after a separate study.
- **Blocks.** A fused default sort in P6. [ADR-0009](adr/0009-separate-score-channels.md) recommends separate channels until this question closes.

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

- **Owning document.** [ALGORITHM.md](ALGORITHM.md#q-sci-14)
- **Question.** Which local HTR model, license, and weight hash are required, and is a download ever allowed?
- **Why it matters.** Weights are code-like, licensed, and large. A downloader is a network call.
- **Options.** A named local model, reviewed license, and a recorded weight hash, with weights provided from a local path; no model in the first releases; a download only after a separate implementation approval.
- **Blocks.** P5. P0 approves no model, no weight file, and no download. See [ADR-0010](adr/0010-local-greek-htr-runtime.md).

### Q-SCI-15

- **Owning document.** [EVALUATION.md](EVALUATION.md#q-sci-15)
- **Question.** Which evaluation corpora are permitted, and under what license?
- **Why it matters.** Real manuscript images are culturally sensitive and often unpublished or licensed. Synthetic tears cannot stand in for them.
- **Options.** Synthetic tears only, including in the repository; published images stored outside Git under a named license and cited by hash; no real-image claims until a separate license review.
- **Blocks.** Any accuracy claim on real manuscripts. In-repo benchmark material stays synthetic.

### Q-SCI-16

- **Owning document.** [EVALUATION.md](EVALUATION.md#q-sci-16)
- **Question.** What abbreviation policy applies to character error rate?
- **Why it matters.** Storage is Unicode NFC. Comparison and matching may strip accents and normalize final sigma, and storage never does. Abbreviations still change the character count. A policy chosen after scoring changes the metric.
- **Options.** Abbreviations scored as written; abbreviations expanded before scoring; a written policy that freezes one of these before the first reportable run.
- **Blocks.** Reporting character error rate. P5 writes no character-error number until the abbreviation policy is frozen. NFC storage does not by itself make the number reportable.

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
- **Blocks.** A P7 warning or refusal. The risk stands in P0 as an operator responsibility.

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
- **Blocks.** Accepting a project format. P1 implements a store only after this question is closed, or keeps the implementation behind a decision that answers it.

### Q-ENG-02

- **Status.** Closed by [P1-01](../tasks/P1-01.md). No ADR: the question does not touch evidence semantics, project format, a public API, or privacy policy.
- **Owning document.** [ARCHITECTURE.md](ARCHITECTURE.md#q-eng-02)
- **Decision.** Minimum Python is 3.12. The layout is `src/`. The distribution name is `parchment-workbench`. The import package is `prw`.
- **Blocks.** Nothing further for packaging.

### Q-ENG-03

- **Owning document.** [ARCHITECTURE.md](ARCHITECTURE.md#q-eng-03)
- **Question.** HTR runtime: ONNX Runtime, PyTorch, or an external local binary?
- **Why it matters.** The runtime is a dependency with a license, a distribution size, and a possible network installer. No runtime is approved.
- **Options.** ONNX Runtime; PyTorch; an external local binary invoked without a network call; defer HTR until P5.
- **Blocks.** P5, together with [Q-SCI-14](ALGORITHM.md#q-sci-14). See [ADR-0010](adr/0010-local-greek-htr-runtime.md).

### Q-ENG-04

- **Owning document.** [ARCHITECTURE.md](ARCHITECTURE.md#q-eng-04)
- **Question.** Geometry library versus an in-house implementation, including license?
- **Why it matters.** Join and assembly geometry need robust polygons. A library adds a license obligation.
- **Options.** An in-house implementation of the rigid operations the algorithm contract needs; a documented geometry library chosen with its license at implementation time.
- **Blocks.** P3 and P4 implementation choices. The algorithm contract does not name a library.

### Q-ENG-05

- **Owning document.** [ARCHITECTURE.md](ARCHITECTURE.md#q-eng-05)
- **Question.** Which TIFF and image libraries are allowed, including license?
- **Why it matters.** Source images are lossless TIFF. Reading them without rewriting bytes is an ingest requirement.
- **Options.** The Python standard library where it is sufficient; a documented TIFF library chosen with its license at implementation time.
- **Blocks.** P1 image ingest. P0 does not select a library.

### Q-ENG-06

- **Owning document.** [ARCHITECTURE.md](ARCHITECTURE.md#q-eng-06)
- **Question.** Worker thread or worker process for expensive jobs?
- **Why it matters.** [ADR-0005](adr/0005-qt-shell-and-headless-core.md) requires work off the UI thread and does not choose the isolation mechanism. A process crash can leave the shell up. A thread shares memory and needs a stricter cancellation story.
- **Options.** A worker thread; a worker process that calls the same use-case entry points as the CLI; either, chosen per job class.
- **Blocks.** P7 worker implementation. P1 CLI work can run in the foreground process.
