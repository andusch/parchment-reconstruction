# Review ranked joins

Review ranked joins opens `prw-review` on two fragment images and lists every join as a hypothesis. Rank 1 is the first row. Reject, Keep as hypothesis, and Defer append a decision and leave the other rows in place. The window blocks in the Qt event loop and prints nothing. This drive reads that window on the offscreen platform.

## Sub-features

- `review-help` prints the command help.
- `review-rank` lists 32 hypotheses for the seeded pair and keeps every row after a decision.
- `review-synthetic` does the same after Load synthetic pair.
- `review-refuse-label` shows a BenchmarkLabel refusal in the window.
- `review-missing` shows a missing-path refusal in the window.

## How to get to it (user POV)

- Run `prw-review --help` in a terminal.
- Run `prw-review --image LABEL PATH --image LABEL PATH --foreground-threshold N --code-version CODE --pixels-per-mm N --uncertainty N` in a terminal. The window needs a display. It ranks once when it opens.
- Press Load synthetic pair, Reject hypothesis, Keep as hypothesis, or Defer in the window.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, `$IMAGES`, `$BENCHMARKS`, `$FRAGMENT_A_PATH`, and `$FRAGMENT_B_PATH`.
- `uv sync` has installed the `ui` group, and `libEGL.so.1` loads, so `import PySide6` succeeds.
- Record `shasum -a 256 "$BENCHMARKS/labels.json"` and keep the digest.

- **Print help.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature review-window --entry "prw-review --help" --step help --program prw-review -- --help`. Exit code `0`. stderr is empty. stdout contains `Rank 1 is a hypothesis.` and `not a stable interface.`
- **Rank the seeded pair.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature review-window --entry "prw-review two images" --step ranked --program prw-review-offscreen -- --image piece-a "$FRAGMENT_A_PATH" --image piece-b "$FRAGMENT_B_PATH" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `0`. stderr is one line, `This plugin does not support propagateSizeHints()`. Parse stdout as one JSON object. `lines_before` has 32 strings. The first starts with `Rank 1 hypothesis`. Every line contains `hypothesis`. The text does not contain `correct_join`. `lines_after_reject`, `lines_after_keep`, and `lines_after_defer` each have 32 strings. The first reject line contains `rejected-via-ValidationDecision` and `hypothesis`. `lines_after_keep` index 1 contains `validation accept`, `hypothesis`, and `status proposed`. `lines_after_defer` index 2 contains `validation defer`, `hypothesis`, and `status proposed`. `status` is `Ranked hypotheses.` `status_after_decisions` is `Recorded a validation decision. The other hypotheses stay.` `banner` contains `hypothesis`, `Rank 1`, and `not a historical join`. `note` contains `does not delete`. `caption` contains `fragment-local` and `hypothesis`. `legend` contains `piece-a`, `piece-b`, and `hypothesis`. `title` contains `hypothes`. `outlines` contains `interpretation`. `code_version` equals `$CODE`. `thread_id` is not `0` and is not `ui_thread_id`. `pixmap_width` and `pixmap_height` are greater than `0`.
- **Load synthetic pair.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature review-window --entry "prw-review Load synthetic pair" --step synthetic --program prw-review-offscreen -- --load-synthetic --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `0`. stderr is the same plugin line. The JSON checks match the ranked step, including 32 lines and the three decision rows.
- **Pass the label file as an image.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature review-window --entry "prw-review labels.json" --step refuse-label --program prw-review-offscreen -- --image piece-a "$BENCHMARKS/labels.json" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `0`. stderr is the plugin line. `status` is `A BenchmarkLabel join file is not a rank path.` `lines_before` is that one string. `outlines` is `No outline was loaded.` The label digest is still the first digest.
- **Ask for a missing name.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature review-window --entry "prw-review missing image" --step missing --program prw-review-offscreen -- --image piece-a "$IMAGES/fragment-0.tif" --image piece-b "$FRAGMENT_B_PATH" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `0`. stderr is the plugin line and does not contain `Traceback` or `Fragment files:`. `status` contains that path and `is not a fixture image.` `lines_before` is that one status string.
- **Seed survives.** `shasum -a 256 "$BENCHMARKS/labels.json"` prints the first digest. Run doctor again. It prints `prw-verify doctor ok`.
- **Proof.** The evidence directory contains `help`, `ranked`, `synthetic`, `refuse-label`, and `missing`.

## Gotchas

- An operator session uses a display. `prw-review` then blocks and prints no list. This recipe does not open a display. `drive_review.py` calls `prw.review_window.main` on the offscreen platform, prints one JSON object, and exits. A pytest is not this proof.
- Offscreen Qt can segfault while the process tears the platform plugin down. The driver flushes the report and exits with `os._exit`. The transcript is that report.
- `--help` imports PySide6 before it parses arguments. A missing `libEGL.so.1` exits `1` with an `ImportError` traceback on stderr and empty stdout.
- The offscreen plugin writes `This plugin does not support propagateSizeHints()` to stderr once a window is shown. Help does not show a window, so its stderr stays empty.
- A refusal stays on the window status line. The harness then exits `0`. That is not the CLI exit `2`.
- The window does not print `Fragment files:` for a missing path. The CLI does.
- Sorted by file name, the first and second seeded fragments are one raster. This recipe uses the exported pair, which is two rasters, or Load synthetic pair, which ranks the first and third sorted names. Both lists have 32 rows.
- The sketch is a placement in fragment-local millimetres. The report does not contain image bytes.
- `labels.json` is not a rank path. Do not open it to decide whether rank 1 is the join.
