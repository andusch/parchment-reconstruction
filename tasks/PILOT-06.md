# Task ticket

- Status: Done
- Phase: Pilot, after the review window

A **yes** on any stop-and-ask field means the ticket waits until an ADR and an explicit decision exist. Open questions are indexed in [OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md). The glossary is in [DATA_MODEL.md](../docs/DATA_MODEL.md#glossary).

## Title

Record a synthetic multi-fragment pool whose rank list has join hypotheses, and the `prw-review` flags that load it.

## Phase

Pilot. `prw generate`, `prw rank`, and `prw-review` already exist. [PILOT-04](PILOT-04.md) recorded one public leaf whose rank list is empty. [PILOT-05](PILOT-05.md) is the window.

## Problem

The Cleveland run is one pool image, so its join list is empty. An operator who wants a list with join hypotheses has the synthetic commands in [USAGE.md](../docs/USAGE.md), and no worked note that names the two files, the hashes, and the review flags together.

## User or scientific outcome

An operator can generate the leaf outside the checkout, rank the first and third sorted fragment files, read a `physical_join_order` of 32 hypotheses, and open that pair in `prw-review`.

## Epistemic-class impact

no. An outline stays `interpretation`. A join stays a hypothesis. A non-empty list is the rank for this pool.

## Stop and ask

- Changes a public API: no
- Changes the project format: no
- Changes the privacy policy ([SECURITY_AND_PRIVACY.md](../docs/SECURITY_AND_PRIVACY.md)): no
- Changes evidence semantics (text status, epistemic class, or the meaning of a hypothesis): no

## Schema impact

none.

## Algorithm and benchmark impact

none. The leaf is written under a disposable `benchmarks/` directory outside the checkout. No BenchmarkLabel row in the repository is added or edited. Rank does not read that store.

## New dependencies

none. The review window already uses PySide6-Essentials in the `ui` group.

## Acceptance criteria

- [x] `prw generate` with missing-fragment percentage `0`, edge erosion `0`, rotation `0`, lighting variation `0`, and random seed `3` writes four fragment files outside the checkout. The first and third names in sorted order are two distinct rasters.
- [x] `prw verify`, `segment`, `edge`, and `rank` on that pair succeed. `rank` prints `physical_join_order` with 32 joins, each `epistemic_class` `hypothesis`.
- [x] [pilot-multi-fragment-pool.md](../docs/pilot-multi-fragment-pool.md) records the parameters, the hashes, the commands, the decoder name, and that the rows are hypotheses.
- [x] The same two paths are the `prw-review` `--image` flags. `Load synthetic pair` selects those two files.
- [x] The diff contains no image bytes.

## Tests

No new test. The run is an operator transcript. Existing synthetic tests already rank this pair, and the offscreen window test loads the first and third sorted fragment files. No read of `data/`, `scans/`, or `real_data/`.

## Provenance effects

The CLI printed the envelopes it already builds. `decoder_name` was `synthetic_uncompressed_tiff` and `decoder_version` was `1`. `random_seed` was recorded on `generate` and omitted on `segment`, `edge`, and `rank`. This ticket writes no second envelope.

## Non-goals

- HTR, a worker process, a project store, and the rest of P7.
- A museum download, a find-site, a language, a reading, or an accuracy claim.
- Changing which pairs the ranker accepts. Two copies of one raster still exit `2`.
- Scoring the list against `benchmarks/labels.json`.

## Open questions this depends on

[Q-ENG-06](../docs/OPEN_QUESTIONS.md#q-eng-06), [Q-ENG-01](../docs/OPEN_QUESTIONS.md#q-eng-01), and [Q-SCI-15](../docs/OPEN_QUESTIONS.md#q-sci-15) stay open.
