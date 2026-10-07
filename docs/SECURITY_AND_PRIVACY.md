# Security and privacy

- Status: Draft for review
- Phase: P0
- This file is the privacy policy for P0
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)
- Open-question index: [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)

Later changes to this policy require stop-and-ask under the agent rules in [AGENTS.md](../AGENTS.md).

## Assets

The sensitive assets are unpublished source images and the integrity of the evidence chain built from them. Images may be uncatalogued, under a museum or archive agreement, or culturally restricted. Derived hypotheses matter because a silent edit can be mistaken for observation.

Operator names typed into validation records and sidecars are personal data. How exports treat them is [Q-PRI-02](#q-pri-02).

## Scope of the threat model

The workbench is a single-user local tool. The person at the machine is trusted. This policy addresses accidental disclosure and silent alteration of evidence. It does not treat remote multi-user attacks as the design center.

P0 has no application, no telemetry endpoint, and no account system.

## Threats

- **Accidental commit.** A source image, a project database, or an export is added to Git.
- **Agent ingestion.** An assistant session reads `data/`, `scans/`, `real_data/`, a TIFF, or a model-weight file and copies content into a transcript or a commit.
- **Cloud-sync folders.** A project directory placed under a synced desktop or drive uploads unpublished images. See [Q-PRI-01](#q-pri-01).
- **Logs.** A log line includes a full path, pixel values, or a reading presented without its epistemic class.
- **Model runtime.** A future HTR library checks a license server or downloads weights. That is a network call and is not approved. See [ADR-0001](adr/0001-local-only-processing.md) and [ADR-0010](adr/0010-local-greek-htr-runtime.md).
- **Export.** A bundle leaves the machine with unpublished images or with hypotheses labeled as the original text.

## Controls

- [`.gitignore`](../.gitignore) excludes `data/`, `scans/`, `real_data/`, TIFF sources, `models/`, `exports/`, and the listed weight extensions. Exclusion is not a substitute for care when force-adding files.
- Agents do not read those paths. Tests, when they exist, use synthetic fixtures. See [AGENTS.md](../AGENTS.md).
- Logs record identifiers and hashes. They omit pixel buffers and omit source-file paths when an id is enough.
- The default process has no telemetry, no auto-update network call, and no network client. See [ARCHITECTURE.md](ARCHITECTURE.md).
- Model files, when a later phase is allowed to use them, stay on the local machine and are recorded by hash in the provenance envelope.
- Exports are labeled as hypotheses and carry epistemic class, text status, and hashes. The scholar chooses what leaves the machine.
- Source bytes stay immutable. Validation decisions do not overwrite hypotheses. Checksums are verified before use.
- A museum or archive restriction, if the project must store one, is [Q-PRI-03](#q-pri-03). P0 defines no such field.

## What the local user controls

The project directory is the retention boundary. Removing the directory removes the local copy. The application, once it exists, does not send a copy elsewhere unless a future change to this policy is explicitly approved.

## Open questions

### Q-PRI-01

Should the app warn when the project directory is inside a cloud-sync folder?

A warning can prevent an accidental upload. Detecting sync roots is platform-specific and can be wrong.

- Options: warn when the path is under a known sync root; document the risk and do not detect it; refuse to create a project in a detected sync root.
- Blocks: a P7 warning or refusal. The risk stands in P0 as an operator responsibility.

### Q-PRI-02

Must exports be able to omit operator names?

Names in decisions and sidecars identify who recorded evidence. They are also personal data in a bundle that may be shared.

- Options: exports include actor strings; exports have a switch that omits them; actor strings are never stored.
- Blocks: P8. Until it closes, the data model allows an actor field and this policy treats the name as optional personal data.

### Q-PRI-03

Do museum or archive agreements need an access-restriction field on a project?

Some captures may be stored locally and still be contractually barred from export or from being shown to a wider group.

- Options: no field, with restrictions handled outside the tool; a free-text restriction note that export must display; a structured flag that blocks export until the operator confirms.
- Blocks: any P8 access-control behavior. P0 stores no restriction field.
