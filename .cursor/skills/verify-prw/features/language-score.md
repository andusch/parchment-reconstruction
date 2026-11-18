# Score language

Score language writes one `language` score for a join the physical gate already admitted, and a screening event for every hypothesis it is offered. A repeated call prints the same run. An exclusion writes no score and no join.

## Sub-features

- `language-admitted` scores two code points and records an admission.
- `language-repeat` prints the same stdout again.
- `language-excluded` records a physical exclusion and writes no score.
- `language-no-grapheme` writes no score when the admitted hypothesis has no grapheme.
- `language-supplied-incomplete` refuses supplied letters that have no treatment.

## How to get to it (user POV)

- Run `prw language` with `--code-version`, `--recorded-at`, `--source-hash`, `--hypothesis-id`, `--hypothesis-type`, and the reading tags.
- Add `--physical-run-id` and `--physical-outcome` together.
- Add `--grapheme text=text_status` for each grapheme. Omit it when the hypothesis has none.
- Add `--supplied-text`, `--supplied-label`, and `--supplied-treatment` together when supplied letters are in the score.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID` and `$CODE`.
- The source hash below is the digest of the bytes `synthetic-language-source`. The command does not open a file for those bytes.

- **Score an admitted join.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature language-score --entry "prw language admitted" --step admitted -- language --code-version "$CODE" --recorded-at 2020-01-01T00:00:00Z --source-hash sha256:4398e645c2b2c267bd45ffb7b311675733cad13046538fc0ee9e767ace05b51f --hypothesis-id 00000000-0000-4000-8000-000000000001 --hypothesis-type join --physical-run-id 00000000-0000-4000-8000-000000000002 --physical-outcome admitted --script Grek --language grc --grapheme ab=ocr_inferred`. Exit code `0`. `record` is `LanguageScores`. `envelope.algorithm_name` is `admitted_reading_language`. `envelope.algorithm_version` is `1`. `envelope.model_hash` is `absent`. The `random_seed` key is absent. `joins` has one object. `score.channel` is `language`. `score.value` is `2`. `assemblies` is empty. `screening[0].gate` is `language`. `screening[0].outcome` is `admitted`.
- **Repeat it.** Run the same command with `--step admitted-repeat`. Exit code `0`. `stdout.txt` is byte-for-byte the same as the admitted step, including `run_id`.
- **Exclude a join the physical gate rejected.** Run the admitted command with `--step excluded` and `--physical-outcome excluded`. Exit code `0`. `joins` is empty. `screening[0].outcome` is `excluded`. stdout does not contain `JoinHypothesis`.
- **Offer no grapheme.** Run the admitted command with `--step no-grapheme` and without `--grapheme`. Exit code `0`. `joins` is empty. `screening[0].outcome` is `excluded`.
- **Omit the supplied-text treatment.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature language-score --entry "prw language supplied incomplete" --step supplied-incomplete -- language --code-version "$CODE" --recorded-at 2020-01-01T00:00:00Z --source-hash sha256:4398e645c2b2c267bd45ffb7b311675733cad13046538fc0ee9e767ace05b51f --hypothesis-id 00000000-0000-4000-8000-000000000001 --hypothesis-type join --physical-run-id 00000000-0000-4000-8000-000000000002 --physical-outcome admitted --script Grek --language grc --grapheme ab=ocr_inferred --supplied-text ab --supplied-label supplied`. Exit code `2`. stdout is empty. stderr contains `treatment`.
- **Proof.** The evidence directory contains `admitted`, `admitted-repeat`, `excluded`, `no-grapheme`, and `supplied-incomplete`.

## Gotchas

- `--recorded-at` is metadata. The same scientific arguments with the same timestamp repeat the run id. A different `--code-version` is a different run.
- `--source-hash` is recorded. The command does not read an image and does not download weights.
- `--grapheme` is `text=text_status`. `ab=ocr_inferred` is two code points. The score is that count. It is not a probability.
- Supplied letters need the text, the label, and the treatment. Leaving the treatment off writes nothing.
- `code_version` is the string passed on the command line. Use `$CODE` so the envelope cites this checkout's HEAD. A dirty worktree does not change that SHA.
