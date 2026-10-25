---
name: verify-prw
description: Drive the parchment-workbench headless CLI (prw) from a disposable synthetic-fixture directory and capture command transcripts. Use when verifying checksum verification, fixture generation, segmentation, join ranking, or provenance output, or when a change to those commands needs a user-level proof. There is no Qt shell to launch.
---

# Verify parchment-workbench

The user-facing surface that exists is the headless CLI. `prw` and `python -m prw.cli` both call `prw.cli:main`. The Qt shell in ADR-0005 is not in the package: there is no window, URL, or port. Do not start a GUI, and do not report a library call or a pytest as this proof.

Command names are unfrozen. Drive the commands below as they are. `agree`, `assemble`, `assembly-rank`, `edge`, `frame`, `join-presence`, `placement-error`, and `recall` are real commands and have no feature file. A run that does not drive them has not verified them.

Run every helper command below from the checkout root, so `uv run` selects this project.

## Launch

```text
uv run python .cursor/skills/verify-prw/verify_prw.py launch
```

Launch creates `$TMPDIR/prw-verify/<run-id>/` outside the checkout, with empty `images/`, `benchmarks/`, and `scratch/` directories. It then runs the seed and one checksum self-check. Ready means both exited 0, the page file matches the image manifest, and doctor passes. The self-check transcripts live in that instance's `seed/` directory and are deleted on cleanup. They are not proof. Drive `verify` again through `run` before claiming the checksum path.

The seed command, with `CODE` equal to `git rev-parse HEAD` at launch, is:

```text
uv run python -m prw.cli generate \
  --benchmarks <instance>/benchmarks \
  --images <instance>/images \
  --missing-fragment-percentage 0 \
  --edge-erosion 0 \
  --rotation 0 \
  --lighting-variation 0 \
  --random-seed 3 \
  --code-version CODE
```

Ready prints `prw-verify ready <run-id>` and the doctor fields. A failed launch removes the instance it created and prints `prw-verify launch failed; instance removed <run-id>`. There is no migration and no server. The seed does not write `manifest.json` or `originals/`.

Two run ids can launch at the same time. They do not share directories. This CLI has no shared desktop session.

`code_version` is that commit SHA. A dirty worktree can still be ready: doctor prints `worktree: dirty` and does not fail for that. The SHA does not include uncommitted edits. Doctor fails when HEAD changes after launch.

## Doctor

```text
uv run python .cursor/skills/verify-prw/verify_prw.py doctor --run RUN_ID
```

Run doctor before driving whenever a command fails or the tree changes. Success prints `prw-verify doctor ok` and these lines:

- `run_id`, `root`, `images`, `benchmarks`, `scratch`
- `page`, `page_hash`, `page_bytes`
- `fragments` (space-separated manifest fragment file names, at least two)
- `version` (`0.0.0`)
- `code_version` (HEAD at launch, still the current HEAD)
- `worktree` (`clean` or `dirty`)
- `commands` (`agree,assemble,assembly-rank,edge,frame,generate,join-presence,placement-error,provenance,rank,recall,segment,verify`)

Doctor is the readiness check. It re-hashes the seeded page and fragment files, re-reads `image_manifest.json`, requires `benchmarks/labels.json` and `benchmarks/provenance.json`, confirms `prw --help` and `prw.__version__`, and refuses a stale or live `active.pid`. It does not write the instance, the evidence directory, or source files. A failure prints the reason on stderr and does not print `prw-verify doctor ok`.

Export the same check as shell assignments:

```text
eval "$(uv run python .cursor/skills/verify-prw/verify_prw.py exports --run RUN_ID)"
```

That sets `RUN_ID`, `ROOT`, `IMAGES`, `BENCHMARKS`, `SCRATCH`, `PAGE`, `PAGE_HASH`, `PAGE_BYTES`, `CODE`, `FRAGMENT_A`, `FRAGMENT_B`, `FRAGMENT_A_PATH`, `FRAGMENT_B_PATH`, `FRAGMENT_A_HASH`, and `FRAGMENT_B_HASH`.

## Drive

Each drive is a new session. Its standard input is that session's controlling terminal. Standard output and standard error are separate pipes. The harness runs, from the checkout root:

```text
uv run python -m prw.cli <arguments>
```

`run` refuses when doctor would fail, when this run id already has a drive in progress, and when an argument points at `data/`, `scans/`, `real_data/`, or a TIFF inside the checkout. One run id is one instance. A second concurrent `run` on that id exits 1 with `This run already has a drive in progress.` Start another `launch` when you need a second instance.

```text
uv run python .cursor/skills/verify-prw/verify_prw.py run \
  --run "$RUN_ID" \
  --feature FEATURE \
  --entry "ENTRY" \
  --step STEP \
  -- <prw arguments>
```

`FEATURE` and `STEP` are lowercase words separated by hyphens. `ENTRY` is the user entry point from the feature file, on one line. The helper exits with the CLI status. Exit 1 or 2 from the CLI is the observation when the feature says so, and the evidence files are still written. A harness refusal exits 2 and does not leave a finished evidence directory.

Follow `.cursor/skills/verify-prw/features/README.md` and the feature file. Parse JSON stdout. Assert fields. Do not treat a skipped entry point as verified through another command.

## Evidence

Finished transcripts are written to:

```text
.cursor/skills/verify-prw/artifacts/<feature>/<run-id>/<step>/
```

| File | Contents |
| --- | --- |
| `command.txt` | The exact `uv run python -m prw.cli ...` argv |
| `stdout.txt` | Standard output |
| `stderr.txt` | Standard error |
| `exit_code.txt` | The CLI status |
| `cwd.txt` | The checkout root |
| `meta.txt` | `feature`, `entry`, `step`, and `run_id` |

A proof captures the command and the resulting state. For a file the command must leave unchanged, record a second observation (a later `verify`, a matching manifest hash, or `shasum -a 256` before and after). The seeded leaf is the baseline. A journey that needs a different fixture writes it under `$SCRATCH` and says so. Do not point a journey at `labels.json` to decide whether a join is correct.

## Cleanup

```text
uv run python .cursor/skills/verify-prw/verify_prw.py cleanup --run RUN_ID
```

Cleanup signals only the process recorded for that run, and only when `ps` shows `prw.cli` and the process group is that session. It then deletes `$TMPDIR/prw-verify/<run-id>/`. It does not delete `.cursor/skills/verify-prw/artifacts/`. A second cleanup prints `prw-verify cleanup absent <run-id>` and exits 0. Run cleanup after a failed drive so the temp directory does not stay behind. Keep the evidence.

## Helpers

The helper is `.cursor/skills/verify-prw/verify_prw.py`. It uses the Python standard library and is not a runtime dependency of `parchment-workbench`. Invoke it with `uv run python`.

```text
uv run python .cursor/skills/verify-prw/verify_prw.py launch
uv run python .cursor/skills/verify-prw/verify_prw.py doctor --run RUN_ID
uv run python .cursor/skills/verify-prw/verify_prw.py exports --run RUN_ID
uv run python .cursor/skills/verify-prw/verify_prw.py run --run RUN_ID --feature FEATURE --entry "ENTRY" --step STEP -- <prw arguments>
uv run python .cursor/skills/verify-prw/verify_prw.py cleanup --run RUN_ID
```

When the commands or the feature map change, run `/maintain-verification-skill`.
