---
name: deliver
description: Run the delivery pipeline on a feature — plan, adversarial review, vertical slices, tests before code by a separate agent, scripted validation, per-slice code review. Triggers: "/deliver <feature> [--tier S|M|L]", "deliver init <profile>", "deliver doctor", "deliver upgrade", "run the pipeline on", "deliver this feature".
---

# /deliver

You are the orchestrator. You own the state: only you run `pipeline start`, `pipeline phase`
and `pipeline verdict`. Agents produce artifacts, tests, code and verdict JSON; the CLI
produces evidence; you move the phase forward and stop at the human approval points.

Resolve the CLI once, first thing: `PIPELINE="${CLAUDE_PLUGIN_ROOT}/bin/pipeline"`; if
`CLAUDE_PLUGIN_ROOT` is unset, `PIPELINE="$HOME/.claude/local-marketplace/plugins/delivery-kit/bin/pipeline"`.
Nothing is on PATH. Every `pipeline …` below means `"$PIPELINE" …`, and once the worktree
exists (step 0.3) every call is `"$PIPELINE" -C <worktree> …` — the state is keyed by the repo
root the CLI sees, so a call from the main checkout and one from the worktree address
different state. Put `PIPELINE=<absolute path>` and the worktree path into every agent prompt.
Full contract: `${CLAUDE_PLUGIN_ROOT}/docs/CLI.md`.

Write everything you hand to agents and to the human in normal prose. Never drop
verified/assumed markers.

## `deliver init <profile>`

1. `ls "${CLAUDE_PLUGIN_ROOT}/profiles/"` — the profile must be one of the files listed.
2. `pipeline init --from "${CLAUDE_PLUGIN_ROOT}/profiles/<profile>.json"` (add `--force` only
   if the user asked to overwrite).
3. Read the new `.claude/pipeline.json`; create `<artifacts_dir>/` if `init` did not.
4. Append `${CLAUDE_PLUGIN_ROOT}/templates/CLAUDE-snippet.md` to the repo's `CLAUDE.md`
   (create it if absent), substituting the `cmd.*` values and `{artifacts_dir}` from the
   profile.
5. Commit those two paths only — `git add .claude/pipeline.json CLAUDE.md` and
   `git commit -m "Add delivery-kit pipeline profile"` — so the tree is clean for the next step.
6. `pipeline doctor`. Report its output verbatim. If it fails, stop and list what the repo
   must provide (usually a runnable empty test suite).

## `deliver doctor`

Run `pipeline doctor`, quote the output, stop.

## `deliver upgrade`

1. Compare `.claude/pipeline.json` with the profile it came from (same `runner`) — show a
   unified diff of keys added or renamed in the kit's profile; never overwrite repo values.
2. Compare the repo's artifact files against `${CLAUDE_PLUGIN_ROOT}/templates/` for missing
   sections (headings only).
3. Show the patch. Apply only after the user confirms. Update `kit_version` last.

## `deliver <feature> [--tier S|M|L]`

Tier defaults to S. Pick M when the request spans several slices with a known design, L
when it introduces a new module, architecture or external contract. Say which tier you chose
and why in one sentence before starting.

### 0. Preconditions

1. `.claude/pipeline.json` must exist — otherwise run `deliver init` first (ask which profile).
2. `pipeline doctor` must exit 0. If not, stop and report; do not start the feature on a red
   or dirty tree.
3. Create the feature worktree and work there for everything that follows:
   `git worktree add ../<repo>-<feature> -b feature/<feature>`; record its absolute path as
   `WORKTREE`. From here on every CLI call is `"$PIPELINE" -C "$WORKTREE" …`. Every agent is
   spawned with `WORKTREE` as its working directory and `PIPELINE=<absolute path>` in the
   prompt. Do not use `isolation: worktree` on agents — each would get its own throw-away
   worktree and the implementer would never see the test-author's tests.
4. `pipeline -C "$WORKTREE" start <feature> --slice S01 --tier <tier>`.

### 1. Plan (every tier; S runs the planner in `mode=slices-only`)

1. `pipeline phase plan`.
2. Spawn `planner` (`subagent_type: "delivery-kit:planner"`) with: feature, tier, the request
   text verbatim, `WORKTREE`, `PIPELINE`. Tier S: add `mode=slices-only` — it writes only
   `SLICES.md` (one slice) and `slices/S01/SPEC.md`. M and L: it writes PLAN.md (+ DESIGN.md
   for L), SLICES.md, `slices/*/SPEC.md`.
3. Read its final message. If it lists NEEDS CLARIFICATION markers, put each question to
   the human and re-spawn the planner with the answers. Repeat until none remain.
4. L only — critic loop, cap 3 rounds:
   a. Spawn `reviewer` with `lens=plan`, feature, `WORKTREE`, `PIPELINE`.
   b. Take the JSON block from its message. Write its `facts` + `findings` to
      `<artifacts_dir>/<feature>/REVIEW-plan.md`; run
      `pipeline verdict plan <PASS|FAIL> --findings <that file>`.
   c. On FAIL: re-spawn the planner with the findings file; go to a. On the third FAIL, stop
      and hand the open findings to the human.
5. Human approval point (L always; M when the planner left Unknowns): show the slice list,
   the Unknowns and the review verdict; wait for an explicit "approved".

### 2. Per slice — in `depends-on` order from SLICES.md

For each slice `<S>`:

1. `pipeline start <feature> --slice <S> --tier <tier>` (sets the current slice).
2. `pipeline phase tests` (clears `base_tree`). Spawn `test-author` with feature, slice,
   `WORKTREE`, `PIPELINE`. Its stop is gated by the `require-red` hook; read its quoted
   `pipeline test` summary. If it reports `spec-conflict`, resolve with the human before
   continuing.
3. `pipeline phase implement` (records `base_tree` — the tree the implementer's diff is
   judged against). Spawn `implementer` with feature, slice, `WORKTREE`, `PIPELINE`. It
   commits its own green work during this phase: `gate-commit` requires only a fresh green
   `validate --quick` row with no protected or test paths changed, no verdict yet. Its stop is
   gated by `require-green`. Read `pipeline status`:
   - `status: blocked` (three red gates) → stop, show the human what is red.
   - `spec-update` in its message → a test must change, so re-enter the test phase:
     `pipeline phase tests` → re-spawn `test-author` with the finding → `pipeline phase
     implement` → re-spawn `implementer`. Never let the test-author edit while the phase is
     `implement` — its edits would count as the implementer's protected-path violation. Count
     this as one fix round.
4. `pipeline validate` (full: lint, typecheck, slice tests, whole suite, build, probes).
   Red → re-spawn `implementer` with the failing output (phase stays `implement`); count a
   fix round.
5. `pipeline phase review`. Spawn `reviewer` with `lens=code`, feature, slice, `WORKTREE`,
   `PIPELINE`. Take the JSON block; write its findings to
   `<artifacts_dir>/<feature>/slices/<S>/REVIEW-code.md` (inside the worktree, not the
   state dir); `pipeline verdict code <PASS|FAIL> --findings <that file>`.
   If the slice has probes: also `pipeline verdict feature <PASS|FAIL>` from the latest probe
   rows in `pipeline status` (all exit 0 → PASS).
6. FAIL → fix round. Findings that need code only: `pipeline phase implement` → re-spawn
   `implementer` with the findings file → step 4 → step 5, re-reviewing the code lens only.
   Findings that need a test change: the step 3 `spec-update` sequence first. Fix rounds are
   capped at 3 per slice (`block_count` plus your own count); at the cap, stop and hand the
   open findings to the human.
7. PASS → the implementer's commits are already on the branch. Commit anything still
   uncommitted yourself (REVIEW-code.md, SLICES.md status): mark the slice `done` in
   SLICES.md, then `git -C "$WORKTREE" add -A && git -C "$WORKTREE" commit -m "<slice>: <outcome>"`
   — `gate-commit` in phase `review` requires the PASS verdicts you just recorded plus a fresh
   green validate row (it re-runs `validate --quick` itself if the tree moved). Then
   `pipeline phase done`, next slice.

Tier S: one slice (from the slices-only planner run), steps 1–7 once; the reviewer runs the
code lens, and the feature lens only if the slice has probes.

### 3. Integration review (M and L, after the last slice)

1. `pipeline start <feature> --slice integration --tier <tier>`; `pipeline phase review`.
2. `pipeline validate` over the whole branch.
3. Spawn `reviewer` with `lens=code`, `WORKTREE`, `PIPELINE`, scope "whole feature:
   `git diff <default-branch>...HEAD` plus all probe rows". Write findings to
   `<artifacts_dir>/<feature>/REVIEW-integration.md`; record with `pipeline verdict code`.
4. FAIL → implementer fix round (`pipeline phase implement`, cap 3) → `pipeline phase review`
   → re-review.

### 4. Feature done — human approval point

Show: the slice table with statuses, the last `validate` row, the verdicts, open
findings (if any), the branch name and worktree path. Offer to open the MR/PR; do not
open it or merge without an explicit yes. Remove the worktree only when asked.

## Spawning agents — prompt contents

Every agent prompt carries: feature, slice (if any), tier, the absolute worktree path as cwd,
`PIPELINE=<absolute path to bin/pipeline>`, the artifact paths it must read, for the planner
on tier S `mode=slices-only`, and for re-spawns the findings file. Agents do not inherit
your context; do not assume they know the request. Never tell an agent to record a verdict or
move the phase — that is yours.

## When something is denied

A hook's exit-2 message says what failed and what to run. Do what it says; do not re-issue
the same call. A gate that fails three times is a signal to involve the human, not to try a
fourth time.
