---
name: verify-prw
description: "Drive the parchment-workbench headless CLI (prw) in an isolated tmux session and capture transcripts plus scratch-dir side effects. Use when proving verify, generate, segment, edge, or rank, or when asked to verify prw behavior without a Qt window."
---

# Verify parchment-workbench

The user surface today is the headless CLI. `python -m prw.cli` and the `prw` entry point call ingest (`verify`), coordinate frames (`frame`), provenance envelopes (`provenance`), the synthetic fixture generator (`generate`), segmentation (`segment`, including caller-supplied scale), outline agreement (`agree`), chord edges (`edge`), pairwise joins in physical order (`rank`), and join recall (`recall`). There is no Qt window in this package. Do not start a GUI. Command names and flags are unfrozen and are not a stable interface.

Two runs can proceed side by side. Each launch owns one root under `/tmp/prw-verify/<run-id>` with its own scratch directories and tmux sessions. There is no port and no shared database. Never drive a root this run did not launch.

## Launch

`uv` and `tmux` must already be on `PATH`. This checkout has no runtime dependencies. Launch installs the dev environment from `uv.lock`, creates an empty scratch tree outside the git checkout, and starts one tmux session. Ready means that session's pane has printed `PRW_VERIFY_READY 0.0.0` and `src/prw` imports at version `0.0.0`. An empty scratch directory is the usable state: there is no project database and no migration to apply. `generate` is a user command, not launch seed data.

From the repository root:

```bash
export PATH="${HOME}/.local/bin:${PATH}"
.cursor/skills/verify-prw/bin/verify-prw launch
```

Export the values it prints before any later command:

```bash
export PRW_VERIFY_ROOT=...
export SCRATCH_BENCHMARKS=...
export SCRATCH_IMAGES=...
export EVIDENCE=...
export CODE_VERSION=...
```

`CODE_VERSION` is `git rev-parse --short=12 HEAD` at launch. Pass that string as `--code-version` on commands that require one.

Ready checks, all of which launch waits for:

- `uv sync` finished and its log is `$PRW_VERIFY_ROOT/evidence/uv-sync.txt`.
- The session named in the launch output is alive.
- `$PRW_VERIFY_ROOT/ready` and the session pane both contain the line `PRW_VERIFY_READY 0.0.0`.
- `$SCRATCH_BENCHMARKS` and `$SCRATCH_IMAGES` exist and are empty.
- Both directories resolve under `/tmp/prw-verify/` and outside the git checkout, `data/`, `scans/`, and `real_data/`.

If launch fails after it has printed a root, run cleanup on that root before retrying. Launch never writes TIFF bytes, `labels.json`, or `manifest.json`.

## Doctor

Run doctor after launch and again before the first drive of a fresh root. Doctor is read-only toward the package and the scratch tree: it does not generate fixtures, does not kill sessions, and does not change CLI state. It does write its report to `$EVIDENCE/doctor.txt`.

```bash
.cursor/skills/verify-prw/bin/verify-prw doctor
```

Drive only when the report contains `doctor_ok=yes`. A passing report also contains:

- `session_alive=yes` for the launch session.
- `prw_version=0.0.0` and `python` at 3.12 or newer.
- `qt_imported=no` after importing `prw.cli`.
- `cli_file` ending in `src/prw/cli.py` inside this checkout.
- `scratch_benchmarks` and `scratch_images` pointing at this run's scratch.
- The same `run_id` and `code_version` launch printed.

Doctor also requires both `uv run python -m prw.cli --help` and `uv run prw --help` to list `verify`, `frame`, `provenance`, `generate`, `segment`, `agree`, `edge`, `rank`, and `recall`. If doctor fails, do not drive. Fix the harness or the environment, then doctor again.

## Drive

The harness is `verify-prw drive`. It starts a new tmux session for that step, runs `uv run python -m prw.cli` with the arguments after `--`, and waits until the process writes an exit code. The pane stays open until cleanup.

```bash
.cursor/skills/verify-prw/bin/verify-prw drive \
  --feature <feature> \
  --step <step> \
  -- <prw-args>
```

`<feature>` and `<step>` are lowercase tokens (`[a-z0-9-]`). Every filesystem argument must resolve inside `$PRW_VERIFY_ROOT/scratch`. The harness refuses a path inside the git checkout, `data/`, `scans/`, `real_data/`, or anywhere else. Read the feature file before choosing arguments. Recipes in `features/` are literal.

After a command that writes files, record the scratch tree without copying TIFF bytes:

```bash
.cursor/skills/verify-prw/bin/verify-prw observe \
  --feature <feature> \
  --step <step>
```

Stdout of every successful record is one canonical JSON document: sorted keys, no insignificant whitespace. Exit `0` is a completed record. Exit `1` is a domain failure printed as JSON on stdout (`IntegrityFailure`, `FailedEdgeChord`, `FailedPairwiseJoin`). Exit `2` is a usage or `ValueError` message on stderr with empty stdout. A traceback is a harness or product failure, not an expected result.

These commands are mapped in `features/`: `generate`, `verify`, `segment`, `edge`, `rank`. `frame`, `provenance`, `agree`, and `recall` exist on the CLI and are not mapped yet. Do not report them as verified through another command.

## Evidence

Evidence lives at `$PRW_VERIFY_ROOT/evidence` (the `EVIDENCE` value launch prints). Cleanup deletes scratch and tmux sessions and leaves this directory in place.

For each drive step the harness writes:

- `command.txt` — the `uv run python -m prw.cli ...` invocation.
- `pane.txt` — the tmux pane, including the command line, stdout, stderr, and `PRW_VERIFY_DONE exit=<code>`. The pane wraps at the tmux window width. Assert intact JSON on `stdout.txt` and `stderr.txt`. Use the pane to see the typed command and the `PRW_VERIFY_DONE` line.
- `stdout.txt`, `stderr.txt`, `exit_code.txt` — the process streams.
- `side_effects.txt` — from `observe`. One `file <path> size=<bytes> sha256=<hex> tiff=<yes|no>` line per scratch file, plus `manifest_json=absent` and `originals=absent` when those project markers were not created.

A proof has to show the user action and the resulting state. For a write, the printed `content_hash` or the on-disk file name has to match `side_effects.txt`, and a second look has to show the TIFF bytes were not rewritten by a later read-only command. `observe` stores hashes, not TIFF payloads. Do not copy `*.tif` into the evidence directory or into git.

The creation proof for this skill is the `generate` / `write-leaf` step. Its transcript is committed at `.cursor/skills/verify-prw/proof/` so the proof survives outside `/tmp`. Later runs keep their evidence under `$PRW_VERIFY_ROOT/evidence` and do not overwrite `proof/` unless a maintainer is replacing that snapshot. `proof/` must not contain TIFF bytes, `labels.json`, or a scratch tree.

Mocks are not used. The CLI does not open a network connection. `uv sync` reads the local lockfile and cache; it is the documented install step, not a product call. If a recipe names a dry run, confirm what it skipped by listing files, not by trusting the flag name. None of the mapped commands is a dry run.

## Cleanup

Cleanup kills only the tmux sessions recorded in `$PRW_VERIFY_ROOT/sessions.txt` and removes `$PRW_VERIFY_ROOT/scratch`. It does not kill by process name.

```bash
.cursor/skills/verify-prw/bin/verify-prw cleanup
```

A successful cleanup prints `evidence_survives=yes` and `scratch_removed=yes`, then lists the files still under `evidence/`. Confirm those files are still on disk before treating the run as finished. Run cleanup after a failed launch or drive too, so a broken attempt does not leave a session behind. If `PRW_VERIFY_ROOT` was not exported, pass `--root` with the path launch printed:

```bash
.cursor/skills/verify-prw/bin/verify-prw --root "$PRW_VERIFY_ROOT" cleanup
```

## Helpers

The only helper is `.cursor/skills/verify-prw/bin/verify-prw`. It is executable. Run it from the repository root. Subcommands:

```bash
.cursor/skills/verify-prw/bin/verify-prw launch
.cursor/skills/verify-prw/bin/verify-prw doctor
.cursor/skills/verify-prw/bin/verify-prw drive --feature generate --step write-leaf -- generate ...
.cursor/skills/verify-prw/bin/verify-prw observe --feature generate --step write-leaf
.cursor/skills/verify-prw/bin/verify-prw cleanup
.cursor/skills/verify-prw/bin/verify-prw --root "$PRW_VERIFY_ROOT" doctor
```

`launch` ignores `--root` because it allocates the root. `drive` and `observe` read `PRW_VERIFY_ROOT` or, if that is unset, `/tmp/prw-verify/latest`. That pointer is the most recent launch on this machine. When more than one root exists, pass `--root` or export `PRW_VERIFY_ROOT`. Optional `PRW_VERIFY_PARENT` must stay under `/tmp` and outside the checkout; the default is `/tmp/prw-verify`.

## Maintenance

When the CLI changes, run `/maintain-verification-skill` so the feature map stays aligned with the commands. This seed covers five commands. Add a feature file before claiming a command is verified.
