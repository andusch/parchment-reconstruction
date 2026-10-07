# ADR 0001: Local-only processing

- Status: Accepted
- Date: 2026-10-07

## Context

Source images may be unpublished. A network call can disclose them, fetch model weights, or create a dependency the operator did not approve. The agent rules already forbid a network or cloud call without explicit implementation approval.

## Decision

The default application processes data on the local machine. It includes no telemetry, no auto-update call, and no network client. Any network or cloud call requires an explicit implementation approval before the code is added.

## Consequences

- HTR weights, if a later phase uses them, are read from a local path. A downloader is a network call and is not approved here.
- Tests and benchmarks use local fixtures.
- [SECURITY_AND_PRIVACY.md](../SECURITY_AND_PRIVACY.md) is the P0 privacy policy. Changes to it require stop-and-ask.

## Related

- [Q-SCI-14](../OPEN_QUESTIONS.md#q-sci-14)
- [Q-ENG-03](../OPEN_QUESTIONS.md#q-eng-03)
- [Q-PRI-01](../OPEN_QUESTIONS.md#q-pri-01)
- [ADR 0010](0010-local-greek-htr-runtime.md)
