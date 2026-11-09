# Task ticket

- Status: Done
- Phase: Pilot, after the review window

A **yes** on any stop-and-ask field means the ticket waits until an ADR and an explicit decision exist. Open questions are indexed in [OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md). The glossary is in [DATA_MODEL.md](../docs/DATA_MODEL.md#glossary).

## Title

Cover `prw-review` in the verify-prw feature map, and give newcomers a one-command synthetic fragment pool.

## Phase

Pilot. [PILOT-05](PILOT-05.md) is the window. [PILOT-06](PILOT-06.md) recorded the seed-3 pair whose rank list has 32 join hypotheses. This ticket does not close P7.

## Problem

The verify-prw skill drove six headless features and said it did not launch `prw-review`. A person cloning the repository could read that the window exists, and still had to assemble the synthetic leaf from the usage guide before seeing a non-empty join list.

## User or scientific outcome

The verification skill launches `prw-review` on the offscreen platform, reads the hypothesis list and the three decisions, and keeps that recipe in the feature map. A newcomer runs `samples/fragmented-leaf/generate.sh` and then the printed `prw rank` and `prw-review` commands. The rows stay hypotheses.

## Epistemic-class impact

no. A join stays a hypothesis. A decision does not re-type it.

## Stop and ask

- Changes a public API: no. `prw-review` stays unfrozen.
- Changes the project format: no
- Changes the privacy policy ([SECURITY_AND_PRIVACY.md](../docs/SECURITY_AND_PRIVACY.md)): no
- Changes evidence semantics (text status, epistemic class, or the meaning of a hypothesis): no

## Schema impact

none.

## Algorithm and benchmark impact

none. The sample runs the existing generator. No BenchmarkLabel row in the repository is added or edited.

## New dependencies

none. The window already uses PySide6-Essentials in the `ui` group. The offscreen drive needs the platform library `libEGL.so.1` on the machine. That library is not a Python dependency.

## Acceptance criteria

- [x] `.cursor/skills/verify-prw/features/review-window.md` is in the feature map, and a live verify-prw run drove help, the seeded pair, Load synthetic pair, the label-file refusal, and a missing path.
- [x] `samples/fragmented-leaf/generate.sh` writes the seed-3 leaf outside the checkout and prints the rank and review commands for the first and third sorted fragment files.
- [x] The sample README states that the pixels are `synthetic_tear`, that TIFF files are not committed, and that the rank list is hypotheses.
- [x] The diff contains no image bytes.

## Tests

The verify-prw live drive is the proof for the window. Existing pytest covers the offscreen widgets. No new product test. No read of `data/`, `scans/`, or `real_data/`.

## Provenance effects

none beyond the envelopes the existing commands already write. `random_seed` stays `3` on `generate` and omitted on rank.

## Non-goals

- HTR, a worker process, a project store, and the rest of P7.
- An algorithm change, a benchmark comparison, or a committed TIFF.
- Treating the offscreen transcript as a historical join.

## Open questions this depends on

[Q-ENG-06](../docs/OPEN_QUESTIONS.md#q-eng-06), [Q-ENG-01](../docs/OPEN_QUESTIONS.md#q-eng-01), and [Q-SCI-15](../docs/OPEN_QUESTIONS.md#q-sci-15) stay open.
