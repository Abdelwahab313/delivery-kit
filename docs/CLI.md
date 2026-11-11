# `pipeline` CLI contract

Single-file Python 3 (stdlib only) at `bin/pipeline`, executable, `#!/usr/bin/env python3`.
Everything that produces evidence or mutates pipeline state goes through this file. Agents,
hooks and the `/deliver` skill call it; nothing else writes under the state dir.

## Locations

| Thing | Where |
|---|---|
| Repo root | `git rev-parse --show-toplevel` from cwd |
| repo-id | `<basename(root)>-<sha1(root)[:8]>` |
| Profile | `<root>/.claude/pipeline.json` (schema: PLAN.md §2 "Per-repo profile") |
| State root | `$PIPELINE_STATE_DIR` if set, else `~/.claude/pipeline-state/<repo-id>/` |
| Current pointer | `<state root>/current.json` → `{"feature": "...", "slice": "S01"}` |
| Slice state | `<state root>/<feature>/<slice>/state.json` and `evidence.jsonl` |
| Artifacts | `<root>/<profile.artifacts_dir>/<feature>/` (PLAN.md, SLICES.md, `slices/<S>/SPEC.md`, `slices/<S>/probes/`) |

`state.json`: `{"phase": "plan|tests|implement|review|done", "tier": "S|M|L", "base_tree": "<git write-tree sha or null>", "block_count": 0, "status": "active|blocked|done", "verdicts": {"plan"?: "PASS|FAIL", "code"?: ..., "feature"?: ...}}`

`evidence.jsonl`, one JSON object per line: `{"ts": iso8601, "kind": "red|green|infra|validate|probe", "cmd": "...", "exit": int, "parsed": {"passed": int, "failed": int, "ran": bool}, "tree": "<git write-tree>", "test_hashes": {"path": "sha1"}, "flaky": bool, "protected_dirty": ["path"], "probe": "name"?}`

Test file set for a slice: paths listed as bullets under a `## Tests` heading in
`slices/<S>/SPEC.md`, resolved relative to the repo root. `--files a b c` overrides.

## Subcommands

| Command | Does | Exit |
|---|---|---|
| `init --from <profile.json> [--force]` | copies the profile to `.claude/pipeline.json`, creates `artifacts_dir`. Refuses to overwrite without `--force`. | 0 / 1 |
| `doctor` | checks, one line each `ok`/`FAIL`: git repo; working tree clean; profile parses and `runner` is one of `jest rspec go pytest generic`; every `cmd.*` entry is a non-empty list; `cmd.test_all` runs, exits 0 **and** the parser yields `ran: true`; state root writable; plugin `hooks/hooks.json` exists next to this file (`<plugin root>/hooks/hooks.json`). | 0 all ok / 1 |
| `start <feature> [--slice S01] [--tier S]` | creates slice state (`phase: plan`, `block_count: 0`, `status: active`, `base_tree: null`), writes `current.json`. Idempotent if the state exists (only updates `current.json`). | 0 |
| `phase <plan\|tests\|implement\|review\|done>` | sets `phase`. Entering `implement` records `base_tree = git write-tree` (the tree after test-author finished — H4 diffs against it). | 0 |
| `test [--files ...]` | runs `cmd.test_slice` with `{test_files}` substituted (space-joined), strips a leading `rtk `, parses output with the `runner` parser, appends a row: `kind: red` if `parsed.failed > 0`, `green` if `ran && failed == 0`, `infra` if the parser saw no test summary (`ran: false`). `test_hashes` = sha1 of each test file's content. Prints the parsed summary. | 0 green / 1 red / 3 infra |
| `validate [--quick]` | runs in order `lint`, `typecheck`, `test_slice` (quick stops here), `test_all`, `build`, then `probe`. First non-zero stops the chain. If `test_slice` is red, re-runs it once; green on the second run → `flaky: true`. Computes `protected_dirty` = files in `git diff --name-only <base_tree>` (when `base_tree` set) matching `protected_globs`, plus `test_globs` when `phase == implement`. Appends ONE row `kind: validate` with the aggregated `parsed`, `tree`, `flaky`, `protected_dirty`. | 0 green and `protected_dirty` empty / 1 otherwise |
| `probe` | runs every executable file in `slices/<S>/probes/` (sorted), one row `kind: probe` each with `probe: <filename>`, `exit`. | 0 all zero / 1 |
| `check red` | last `red` row exists, `parsed.failed > 0`, and its `test_hashes` equal the current hashes of the same files. | 0 / 2 + reason on stderr |
| `check green` | runs `validate --quick`. If red or `protected_dirty` non-empty: `block_count += 1`; if `block_count >= 3` sets `status: blocked` and exits 0 (lets the agent stop), else exits 2 with the reason. Green: exit 0. | 0 / 2 |
| `check commit` | latest `validate` row has `tree == git write-tree` and `failed == 0` and `protected_dirty == []` and `flaky == false`; `verdicts.code == PASS`; `verdicts.feature == PASS` if `probes/` is non-empty. If the only failure is a stale tree, re-runs `validate --quick` first and re-checks. | 0 / 2 + reason |
| `check claims <file ...>` | for each Markdown file: no `[NEEDS CLARIFICATION` left; every Facts-table row tagged `V` has a receipt cell that is non-empty; every receipt of the form `path:line` (also `path:line-line`) resolves (`path` exists under the repo root, `line <= wc -l`); every ctx7 id (`/org/project...`) appears among `profile.docs` values. Prints one line per violation `file:line: reason`. | 0 / 2 |
| `verdict <plan\|code\|feature> <PASS\|FAIL> [--findings <file>]` | sets `verdicts[lens]`; copies the findings file to `<slice state>/findings-<lens>.md` if given. | 0 |
| `status` | prints `state.json` plus the last 5 evidence rows. | 0 |
| `hook <h1\|h3\|h4\|h5\|h6>` | reads the Claude Code hook JSON from stdin, runs the gate below. **Always exits 0 when the repo has no profile or no `current.json`** — the plugin's hooks are global and must not disturb other repos. | 0 / 2 + reason on stderr |

Role from hook input: `agent_type` with an optional `delivery-kit:` prefix stripped
→ `planner`, `reviewer`, `test-author`, `implementer`, or `""` (main thread = orchestrator).
[A] the exact `agent_type` string for plugin agents is confirmed on the pilot.

| Hook | Event / matcher (`hooks/hooks.json`) | Gate |
|---|---|---|
| h1 `protect-paths` | PreToolUse `Edit\|Write\|Bash` | Only when `phase ∈ {tests, implement}` and `agent_type` is set. Target paths: `tool_input.file_path` for Edit/Write; for Bash a best-effort regex over `tool_input.command` for `>`/`>>` redirection targets, `sed -i … <file>`, `rm … <file>`, `git checkout -- <file>`, `mv/cp … <dest>`. Deny when a target matches a glob the role may not edit: test-author may touch `test_globs ∪ shared_globs` only; implementer anything except `test_globs ∪ protected_globs`; any other role: `protected_globs`. Also deny Bash commands containing `pipeline (start\|phase\|verdict)` when `agent_type` is set. |
| h3 `require-red` | SubagentStop, matcher `(delivery-kit:)?test-author` | `check red` |
| h4 `require-green` | SubagentStop, matcher `(delivery-kit:)?implementer` | `check green` |
| h5 `gate-commit` | PreToolUse `Bash`, command matches `^\s*(rtk\s+)?git\b.*\bcommit\b` | `check commit`. No-op when `phase != implement` and `!= review` (plan-phase commits of artifacts are allowed). |
| h6 `lint-claims` | SubagentStop, matcher `(delivery-kit:)?(planner\|reviewer)` | reviewer only when `verdicts` has no `code` lens pending — i.e. `phase == plan`; `check claims` over `<artifacts>/<feature>/*.md` and `slices/*/SPEC.md`. |

Blocking contract: exit 2, reason on stderr (one or more lines, each actionable: what failed,
the command to run, the file to fix). Never JSON on stdout for deny — exit code is the
protocol, so the same path works for PreToolUse and SubagentStop.

## Runner parsers (`parsed`)

| runner | summary line(s) read | `ran` |
|---|---|---|
| `jest` | `Tests:\s+(?:(\d+) failed, )?(?:(\d+) skipped, )?(?:(\d+) passed, )?(\d+) total` | summary present |
| `rspec` | `(\d+) examples?, (\d+) failures?(?:, (\d+) pending)?` | summary present |
| `go` | count `^--- FAIL` as failed, `^--- PASS` as passed; fall back to `^ok\s` / `^FAIL\s` package lines when `-v` is absent | any `ok`/`FAIL`/`---` line |
| `pytest` | `=+ .*?(?:(\d+) failed)?.*?(?:(\d+) passed)?.*? in [\d.]+s` | summary present |
| `generic` | none; `failed = 1 if exit != 0 else 0`, `passed = 1 - failed` | always true |

Output is scanned from the last line backwards (jest and rspec print summaries last; rtk
output, when it slips through, is also tail-summarised).

## Tests

`tests/test_pipeline.py` (unittest, stdlib). Run: `python3 -m unittest discover -s tests -v`.
Fixtures under `tests/fixtures/`: runner outputs (`jest-red.txt`, `jest-green.txt`,
`rspec-red.txt`, `rspec-green.txt`, `go-red.txt`, `go-green.txt`, `pytest-red.txt`,
`pytest-green.txt`) and hook stdin payloads (`h1-*.json`, `h3-*.json`, … with the expected
exit in the filename, e.g. `h5-stale-tree-exit2.json`). Tests build a throwaway git repo in a
temp dir with a `generic` runner whose `test_slice` is a shell script the test controls, and
point `PIPELINE_STATE_DIR` at a temp dir.
