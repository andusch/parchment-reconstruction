# ADR 0010: Local Greek HTR runtime

- Status: Accepted
- Date: 2026-11-13

## Context

The product applies Ancient Greek handwritten text recognition and stores the result as text status `ocr_inferred`, epistemic class `interpretation`, producer `machine`. The stored name covers HTR. A runtime and a weight file are dependencies with licenses. Fetching weights is a network call, which [ADR 0001](0001-local-only-processing.md) does not allow without explicit implementation approval.

This record was proposed on 2026-10-07 and left blocked. Andu accepted it on 2026-11-13 (Asia/Hong_Kong). The acceptance closes [Q-SCI-04](../OPEN_QUESTIONS.md#q-sci-04), [Q-SCI-14](../OPEN_QUESTIONS.md#q-sci-14), and [Q-ENG-03](../OPEN_QUESTIONS.md#q-eng-03). It does not implement HTR.

## Options

1. ONNX Runtime with local weights.
2. PyTorch with local weights, as a first-party loader. An earlier discussion leaned this way.
3. Kraken >= 7.1.0, calling a weight file on a local path. Kraken uses PyTorch underneath. The product-facing runtime is Kraken.
4. An external local binary invoked with no network call.
5. Defer HTR through the phases that do not need it.

Weights, in every option that uses them, come from a local path. A download is a separate approval. The candidates found with option 3 were PP-OCRv6 medium, other licensed Ancient Greek models that are also Kraken models, and one native `.pt` file. That `.pt` file had no license on its model card.

## Decision

Option 3, with the weight file named below. Kraken >= 7.1.0 is the HTR runtime. This supersedes the earlier lean toward PyTorch with local weights. Kraken uses PyTorch underneath. The product-facing runtime is Kraken. A first-party `torch.load` trainer is not the runtime.

**Scope.** One model covers all polytonic Greek. Separate majuscule and minuscule models are not used.

**Nomina sacra, abbreviations, and mixed-script pages.** Record them under their own `script` or `language` tag and leave them unscored. The model card warns that abbreviation expansion can be unpredictable.

**Weights in the default process.** The operator supplies the weight file from a local path. A network download of weights is allowed only after a later, separate implementation approval. [ADR 0001](0001-local-only-processing.md) stays in force.

**Named model.** PP-OCRv6 medium.

- File: `medium.safetensors`.
- Author: Benjamin Kiessling, ALMAnaCH, Inria Paris. Published 4 August 2026, v1.
- Canonical record: <https://zenodo.org/records/21788410> and <https://doi.org/10.5281/zenodo.21788410> (`10.5281/zenodo.21788410`). The Zenodo record is canonical. An unofficial Hub mirror is not canonical.
- License: Apache License 2.0 (<https://www.apache.org/licenses/LICENSE-2.0>). Attribution and notices are required. Some training datasets are private and not redistributable. That does not change the Apache-2.0 grant on the published weights.
- Official use on the card: Kraken >= 7.1.0, `ocr -m medium.safetensors`.
- Zenodo does not publish a SHA-256 for `medium.safetensors`. This record does not supply one. The Zenodo MD5 for that file is `e3411a453ce3b9e9efae3f8631d85762`. That MD5 is not a provenance `model_hash`. An unofficial Hugging Face LFS digest is not canonical.
- Size: 63.8 MB, as stated on the record.
- A later run that uses the local file stores `model_hash` as the `sha256:` digest of those bytes. This acceptance does not hash the file and does not download it.

**Why this model.** It is the licensed multi-corpus Ancient Greek handwriting model. Licensed alternatives that were found are also Kraken models. The only native `.pt` candidate found had no license on its model card.

**Coverage.** The product scope is one model for all polytonic Greek, and PP-OCRv6 medium is the chosen model. The PP-OCR card does not say "polytonic" and does not claim majuscule, papyrus, or inscription coverage. Ancient Greek training sources listed on the card are EPARCHOS, HPGTR, HTR_CPgr23 (Palatinus graecus 23), and Stavronikita Monastery collections 53, 79, and 114, plus private datasets and synthetic augmentation. The card cites, for greedy CTC with NFD and whitespace normalization, Ancient Greek CER 7.21%, WER 44.03%, on 451 lines. Those figures belong to the card. They are not a character-error number from this workbench. Output on the card is Unicode NFD.

**Storage.** Readings carry `script` and `language`. Stored text is Unicode NFC. Comparison and matching may strip accents and normalize final sigma. Storage never does those stripping steps. An implementation normalizes model output from NFD to NFC before storage. That normalization is an adapter step. It does not change the storage rule. This record does not implement the adapter.

## Consequences

- [Q-SCI-04](../OPEN_QUESTIONS.md#q-sci-04), [Q-SCI-14](../OPEN_QUESTIONS.md#q-sci-14), and [Q-ENG-03](../OPEN_QUESTIONS.md#q-eng-03) are closed. P5 is no longer hard-blocked on those three questions. P5 is not implemented.
- Adding Kraken as a package dependency, wiring a recognizer command, and any weight download are later tickets. Each needs its own implementation approval. This acceptance adds no runtime dependency. The Kraken package license is recorded on the ticket that adds the package. The weight license is the Apache-2.0 grant above.
- The weight file stays outside Git and outside CI. Version stays 0.0.0. No CLI change follows from this record.
- [Q-SCI-16](../OPEN_QUESTIONS.md#q-sci-16) still blocks reporting a character-error number. [Q-SCI-06](../OPEN_QUESTIONS.md#q-sci-06) and [Q-SCI-13](../OPEN_QUESTIONS.md#q-sci-13) stay open. P6, P7, and P8 stay later.
- The stored status remains `ocr_inferred` when the producer is HTR. Epistemic class remains `interpretation`. Producer for a machine reading remains `machine`.
- Model hash in the provenance envelope is the token `absent` for runs that do not use a model. It is never the Zenodo MD5.

## Related

- [Q-SCI-04](../OPEN_QUESTIONS.md#q-sci-04)
- [Q-SCI-14](../OPEN_QUESTIONS.md#q-sci-14)
- [Q-SCI-16](../OPEN_QUESTIONS.md#q-sci-16)
- [Q-ENG-03](../OPEN_QUESTIONS.md#q-eng-03)
- [ADR 0001](0001-local-only-processing.md)
- [P5-01](../../tasks/P5-01.md)
