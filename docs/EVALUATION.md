# Evaluation

- Status: Draft for review
- Phase: P0 (measurement contract; no benchmark numbers and no fixture files)
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)
- Open-question index: [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)

This document states how a later phase may claim that an algorithm change is an improvement. P0 runs no benchmark and writes no score. Publishing a benchmark means a local write under `benchmarks/`. It is not a network publication.

## Principles

- Ground truth is a `BenchmarkLabel` record. It is frozen before scoring.
- Ground truth is not edited to make a check pass.
- The `BenchmarkLabel` store is a separate SQLite or JSON store under `benchmarks/`. It is never written into the project evidence database. It is the only place a ground-truth label is allowed. Solver code paths never read it. Agent rule 13 names this store.
- Real manuscript images stay outside Git. In-repo evaluation material is synthetic. See [Q-SCI-15](#q-sci-15).
- Synthetic tears measure geometry under the generator's cuts. They do not measure ink loss, script, or parchment warp.
- A scholar's acceptance of rank 1 is a decision record. It is not accuracy.
- Every algorithm change publishes a comparison against the previous benchmark record on the same frozen fixture.
- K, fusion weights, and the abbreviation policy are selected before the evaluation set is scored. They are not selected after seeing that set. Storage stays NFC.

## BenchmarkLabel

`BenchmarkLabel` is the legal home of benchmark ground truth.

- The store is SQLite or JSON under `benchmarks/`.
- It is never a table in the project evidence database. Solver code paths never read it.
- A label may name a fixture join, placement, or reading that the generator or a frozen protocol calls true for that fixture.
- Project entities still forbid `truth`, `correct_join`, and `original_text`.
- An algorithm change writes a comparison against the previous local record in this store. That write is what "publish a benchmark" means.

## Synthetic-tear fixture contract

Later tests may generate fixtures. P0 does not generate them and does not commit images.

Fragment-local coordinates follow [ADR-0011](adr/0011-frame-conventions.md). `fragment_local_mm` has its origin at the centroid of the establishing outline polygon, `+x` right, `+y` down, in millimetres. `page_global_mm` uses the same axes. Placements and ground-truth transforms use that convention.

A fixture includes:

- A generated page image and the generator's fragment polygons.
- The generator's cut curves, join set, and placements in `page_global_mm`.
- The generator's scale, so millimetres per pixel are known.
- A parameter blob and `random_seed`. The generator uses randomness, so `random_seed` is required. The blob is canonical JSON: sorted keys, UTF-8, no insignificant whitespace. Its hash is `sha256:` followed by the lowercase hexadecimal digest. The blob names these configurable parameters: missing-fragment percentage, edge erosion, rotation, and lighting variation.
- A manifest of SHA-256 digests for every generated image.

A missing fragment is an omitted piece of the generated page. It is not grapheme status `missing`.

Ground truth for the joins, the placements, and the generator page is written only to the [BenchmarkLabel](#benchmarklabel) store under `benchmarks/`. The contract forbids writing that ground truth into any project database. Solver code paths never read that store. A known join is a `BenchmarkLabel`. It is not a `correct_join` field on a project entity. The rows are frozen when the fixture is accepted into the benchmark set. A later algorithm may read the images and the manifest. It does not read the `BenchmarkLabel` joins during inference. Synthetic outline agreement uses the generator's polygons and does not require a human annotator.

The fixture does not authorize a claim about a real manuscript.

## Metrics

Each metric has a unit and a limit on what it means. No target threshold is set in P0.

### Checksum and protocol conformance

- **Unit.** Pass or fail per source image against the [acceptance checklist](SCAN_PROTOCOL.md#acceptance-checklist).
- **Does not measure.** Reconstruction quality, scale accuracy, or the historical correctness of a join.

### Outline agreement

- **Unit.** Intersection-over-union between a predicted polygon and a reference polygon, in a named frame.
- **Reference.** The generator polygon on a synthetic fixture. A human outline is a reference only after [Q-SCI-17](#q-sci-17).
- **Does not measure.** Whether two fragments join, or whether the reading is right.

### Scale error

- **Unit.** Percent error of recovered millimetres per pixel against the fixture's known scale.
- **Does not measure.** Local shrinkage, cockling, or the correct page size.

### Join recall at K

- **Unit.** The fraction of known synthetic joins that appear in the top K of the `physical` channel.
- **Predeclaration.** K is fixed in the benchmark record before the evaluation fixtures are scored.
- **Does not measure.** That the top-ranked join is the historical join on real parchment. The metric applies to synthetic tears.

### Placement error

- **Unit.** Root-mean-square error, in page millimetres, between placed fragment landmarks and the generator's landmarks, on synthetic tears.
- **Does not measure.** Error on warped or shrunken real parchment. See [Q-SCI-03](ALGORITHM.md#q-sci-03) and [Q-SCI-20](ALGORITHM.md#q-sci-20).

### Character error rate

- **Unit.** Character error rate after a Unicode normalization policy frozen before the run.
- **Predeclaration.** The policy is [Q-SCI-16](#q-sci-16). No character-error number is reportable until that policy is frozen.
- **Does not measure.** Scholarly acceptability, translation quality, or language-channel quality.

### Language-score quality

- **Unit.** The fraction of evaluation items on which the `language` channel ranks a known reading above a stated alternative. The known reading and the alternative are frozen with the fixture.
- **Does not measure.** Character error rate. Perplexity is not this metric and is not reported as accuracy.

### End-to-end join presence

- **Unit.** The fraction of synthetic fixtures for which a known join appears inside a predeclared top-N of assemblies.
- **Predeclaration.** N is fixed before scoring.
- **Does not measure.** Real manuscripts, reading quality, or that the rank-1 assembly is historically correct.

## Human review protocol

Human review records what a scholar decided. It does not replace the frozen fixture metrics.

- Show each hypothesis with its rank, its score channels, its epistemic class, and, for a reading, its text status.
- Record `accept`, `reject`, or `defer` as a `ValidationDecision`.
- Keep competing hypotheses.
- Report acceptance of rank 1 as a rate of decisions, beside the frozen metrics, and label it as a decision rate.

Inter-annotator agreement on outlines waits on [Q-SCI-17](#q-sci-17).

## Split discipline

Once fixtures exist, a development set and an evaluation set stay separate. Parameters, K, N, normalization, and any fusion policy are written into the benchmark record before evaluation-set scoring. A result computed after changing those choices on the evaluation set is exploratory. It is not the confirmatory comparison required for an algorithm change.

Fusion weights stay unused until [Q-SCI-09](ALGORITHM.md#q-sci-09) accepts a policy. A benchmark does not introduce a private fusion to improve a headline number.

## Reporting

A comparison report includes:

- The algorithm name, version, parameter hash, code version, model hash, and seed or its absence.
- The fixture manifest hashes and the ground-truth freeze identifier.
- The full distribution of each metric, not only the best score.
- The previous benchmark record on the same fixture, when one exists.
- The open questions that limit the claim, including any metric that is blocked above.

An algorithm change is incomplete without this comparison. See the benchmark rule in [AGENTS.md](../AGENTS.md).

## Open questions

### Q-SCI-15

Which evaluation corpora are permitted, and under what license?

Real manuscript images are culturally sensitive and often unpublished or licensed. Synthetic tears cannot stand in for them.

- Options: synthetic tears only, including in the repository; published images stored outside Git under a named license and cited by hash; no real-image claims until a separate license review.
- Blocks: any accuracy claim on real manuscripts. In-repo benchmark material stays synthetic.

### Q-SCI-16

What abbreviation policy applies to character error rate?

Storage is Unicode NFC. Comparison and matching may strip accents and normalize final sigma, and storage never does. Polytonic Greek and abbreviations still change the character count. A policy chosen after scoring changes the metric.

- Options: abbreviations scored as written; abbreviations expanded before scoring; a written policy that freezes one of these before the first reportable run.
- Blocks: reporting character error rate. P5 writes no character-error number until the abbreviation policy is frozen. NFC storage does not by itself make the number reportable.

### Q-SCI-17

Is a human outline the ground truth for fragment detection, and what is the annotator protocol?

A single corrected outline can be one expert's trace. Calling it ground truth needs a protocol.

- Options: one expert outline is the reference; two annotators and a stated agreement rule; synthetic generator polygons are the only reference until a protocol exists.
- Blocks: a P2 accuracy claim against human outlines. Synthetic outline agreement against generator polygons can proceed without this question. Whether a corrected outline is observed evidence is [Q-PRD-08](PRD.md#q-prd-08).
