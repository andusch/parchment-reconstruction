# ADR 0010: Local Greek HTR runtime

- Status: Proposed, blocked
- Date: 2026-10-07

## Context

The product applies Ancient Greek handwritten text recognition and stores the result as text status `ocr_inferred`, epistemic class `interpretation`, producer `machine`. The stored name covers HTR. A runtime and a weight file are dependencies with licenses. Fetching them is a network call, which [ADR 0001](0001-local-only-processing.md) does not allow without explicit approval. [Q-SCI-14](../ALGORITHM.md#q-sci-14) and [Q-ENG-03](../ARCHITECTURE.md#q-eng-03) are open. Script coverage is [Q-SCI-04](../ALGORITHM.md#q-sci-04).

## Options

1. ONNX Runtime with local weights.
2. PyTorch with local weights.
3. An external local binary invoked with no network call.
4. Defer HTR through the phases that do not need it.

Weights, if used, would be supplied from a local path and recorded by hash. A download would be a separate approval.

## Decision

Not accepted. This ADR is blocked. P0 approves no model, no weight file, no download, and no HTR dependency.

## Consequences

- P5 cannot start the runtime until Q-SCI-04, Q-SCI-14, Q-ENG-03, and a dependency approval are closed.
- Character error rate stays unreportable until [Q-SCI-16](../EVALUATION.md#q-sci-16) freezes a Unicode policy.
- The stored status remains `ocr_inferred` even when the producer is HTR.
- Model hash in the provenance envelope is the token `absent` for runs that do not use a model.

## Related

- [Q-SCI-04](../OPEN_QUESTIONS.md#q-sci-04)
- [Q-SCI-14](../OPEN_QUESTIONS.md#q-sci-14)
- [Q-SCI-16](../OPEN_QUESTIONS.md#q-sci-16)
- [Q-ENG-03](../OPEN_QUESTIONS.md#q-eng-03)
- [ADR 0001](0001-local-only-processing.md)
