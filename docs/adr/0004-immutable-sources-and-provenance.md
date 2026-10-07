# ADR 0004: Immutable sources and provenance

- Status: Accepted
- Date: 2026-10-07

## Context

Later readers need to know which bytes a hypothesis used and which parameters produced it. Editing a scan in place destroys that link. The agent rules require checksum verification and a provenance record on every derived artifact.

## Decision

Original source bytes are immutable. Ingest records SHA-256 and byte length outside the pixels and verifies the digest before later reads. A failed checksum is not usable evidence.

Every derived artifact records source hashes, the full parameter blob and its SHA-256, the algorithm name and version, the model hash, the code version, and the decoder name and version. Hash fields include the `sha256:` algorithm identifier. Hash-only parameters are not acceptable. `random_seed` is present when the algorithm used randomness and absent when the algorithm is deterministic. An absent seed is part of the reproducibility key. P0 defines this envelope and does not serialize it. The field list is `ProvenanceEnvelope` in the data model.

Real scans, `data/`, `scans/`, `real_data/`, and TIFF sources never enter Git or agent context.

## Consequences

- Cropping and enhancement write a new derivative that cites the source hash.
- A deterministic algorithm omits `random_seed`. Calling an unseeded random generator is a defect once runs exist.
- A stored project uses schema version `1` in `manifest.json`. The envelope is part of that schema. A later change migrates from version `1` and includes migration tests.
- Model hash is the token `absent` when a run uses no model. It is never omitted from the envelope definition, and it is never an empty string.

## Related

- [DATA_MODEL.md](../DATA_MODEL.md#provenanceenvelope)
- [SCAN_PROTOCOL.md](../SCAN_PROTOCOL.md)
- [ADR 0001](0001-local-only-processing.md)
