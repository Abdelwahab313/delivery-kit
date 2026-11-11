# Reliable delivery pipeline — audit + proposal (v2)

Date: 2026-11-11. Status: proposal, nothing applied. v2 after an independent adversarial
review of v1 (read-only critic, fresh context; its findings are folded in, not appended).
Scope: the agent setup on this machine (`~/.claude` + PTC `.claude/`), judged against the
cycle **plan → design → review → slice → per slice: spec + TDD → validator → code review +
feature review → next slice**, with hallucination controls throughout; packaged so a new repo
can adopt it in minutes.

Receipt legend: **[V]** verified by reading the file / running the command / fetching the
doc on 2026-11-11. **[A]** assumed — check before building on it.

---

## 1. Audit — what exists

### Coverage per stage

| Stage | PTC `.claude/` | Global `~/.claude` | Verdict |
|---|---|---|---|
| Plan | `planner` agent, stops on open questions [V `.claude/agents/planner.md:114-139`] | 3 overlapping planners: `plannotator-setup-goal`, `claude-mem:make-plan`, `wayfinder` [V] | covered, duplicated |
| Design | `designer` (HTML mocks) [V] | `grilling`, `grill-with-docs`, `domain-modeling` (last two near-duplicates) [V] | covered |
| Plan/design review | operator only — QA told not to review the plan [V `qa.md:184-185`] | plannotator UI (human) | **GAP: no adversarial agent** |
| Slice | file-level numbered steps, horizontal [V `planner.md:276-284`] | `make-plan` phases horizontal; `wayfinder` tickets "not slices of a build" [V] | **GAP: no vertical slices** |
| Spec-driven / TDD | failing repro spec for bugs only [V `planner.md:295`]; features write specs *after* code [V `implementer.md:52-91`] | zero hits for TDD/red-green/test-first in any global skill, agent, rule [V] | **GAP for features; red run never recorded** |
| Validator | implementer self-reports "all green"; QA trusts it [V `implementer.md:171-177`, `qa.md:299`] | `claude-mem:do` LLM verification subagent [V] | **GAP: no deterministic gate** |
| Code review per slice | `qa` once per ticket, diff base hard-coded `develop` [V `qa.md:154`]; `[Full]` steps self-reviewed [V `implementer.md:67`] | `simplify`, `security-review`, `cavecrew-reviewer` | per ticket, partly self-review |
| Feature review per slice | `qa` Playwright journey, once per ticket [V] | built-in `run` only | per ticket, PTC only |

### Enforcement today

- Only deterministic gates: 4 PreToolUse hooks — `rtk`, `block-real-chrome.sh`,
  `mr-text-guard.py`, `youtrack-comment-guard.py` [V]. None checks tests, evidence or claims.
- Zero `Stop` / `SubagentStop` / `TaskCompleted` hooks [V]. No agent declares `hooks`,
  `effort`, `maxTurns`, `isolation` [V].
- Every anti-hallucination rule (`~/.claude/rules/claims.md`, `context7.md`, `tool-choice.md`)
  is prose [V]. `claims.md:3-5` records that the previous prose store was violated within 14
  days of being written.

### Failure history [V `~/.claude/memory/retro/2026-08-19/HALLUCINATIONS.md`, 135 sessions]

1. Derived numbers stated as observed (proxy metrics, too-narrow windows).
2. Hand-computed timestamps → silent false negatives.
3. Generated list members instead of reading the list — 7 events.
4. Assumptions in the same voice as measurements (ci18-7346: 4 nonexistent references in one
   plan, `HALLUCINATIONS.md:77-79`; ci18-7471: 5 correcting commits in a day).
5. Wrong picture of file location/content — 31 events.
6. Rejected calls retried unchanged.
7. Proxy-verified fixes regressed 3×; observation-verified held 5/5
   [V PTC `.claude/memory/observed-behavior-only.md`].
8. Operator is the reviewer: 44 recheck prompts vs 1 rework prompt; pipeline unused
   (0 planner/qa spawns on 07-26)
   [V `~/.claude/projects/-Users-abdelwahab-projects-otgs-private-translation-cloud/memory/pipeline-gates-and-principles.md`].

Last retro 2026-08-19 — ~84 days unmeasured. Never applied: 07-26 F1, F3–F7; 08-19 F5–F7
[V `~/.claude/memory/retro/*/FIXES.md`].

### Defects in the current setup

| # | Defect | Receipt |
|---|---|---|
| D1 | 5 PTC agents default to the frozen `develop` branch | [V `planner.md:63-66`, `qa.md:154`, `implementer.md:34`, `designer.md:43`, `mr-reviewer.md:32-34`] |
| D2 | All 9 PTC agents pin stale models `claude-opus-4-7`/`-4-8`, `claude-sonnet-4-6` | [V frontmatter] |
| D3 | `claude-mem:do` pushes after every phase and orders doc citations in code comments | [V `~/.claude/plugins/cache/thedotmack/claude-mem/15.15.1/skills/do/SKILL.md:23,37`] |
| D4 | `rtk` PreToolUse rewrite makes auto mode return "no verdict" → Bash calls sent twice (≥8× in one session, 5/8 in the critic's) and **rewrites test commands** (`npx jest x` → `rtk jest x`) | [V observed; critic dry-run] |
| D5 | caveman "drop hedging" has no carve-out for verified/assumed markers, docs, subagent prompts | [V caveman SessionStart text] |
| D6 | `tool-choice.md` mandates Grep/Glob tools this harness lacks; `abdo_writer` limited to `Read, Grep, Glob` | [V tool list] |
| D7 | `/lesson` writes to `memory/lessons/`, never loaded | [V `claims.md:3-5`] |
| D8 | Domain rules loaded in every repo (`gitlab-oss-contributing.md`, `youtrack-writes.md`, ECS preflight) — ~3.6k tokens always-on | [V byte counts] |
| D9 | PTC agents/hooks untracked → unversioned, unshared | [V `git ls-files`] |
| D10 | Code-review rules exist 3× (`qa.md`, `mr-reviewer.md`, `commands/code-review.md`) | [V] |

---

## 2. Design

### Principles

1. **Artifacts over chat.** Every stage reads and writes files.
2. **The author never grades its own work.** Reviews run in a fresh, read-only context.
3. **Evidence is produced by a script, never inferred from the model or from tool hooks.**
   One CLI (`pipeline`) runs tests/validation, parses runner output, and writes evidence
   **outside the repo**. Gates re-run or re-hash; they never trust a prose "green".
4. **Tests come from the spec, before the code, by a different agent.** Protected paths are
   verified by `git diff` at validation, not only by intercepting tools.
5. **Every factual claim carries a resolvable receipt or an [A] tag**; a hook resolves
   `path:line` receipts mechanically, the critic checks meaning.
6. **Right-size the process** (S / M / L). Small changes don't pay for the full cycle.
7. **Generic core + per-repo profile.** Same plugin in PTC and `ptc-nest-onboarding`.

### Tiers

| Tier | When | Stages |
|---|---|---|
| **S** | ≤ 1 slice, no design decision, ≤ ~10 files | SPEC → test-author → implementer → `pipeline validate` → one review (code lens; feature lens only if the slice has HTTP/UI AC) |
| **M** | several slices, design known | PLAN (short, no DESIGN) → SLICES → per-slice loop → integration review |
| **L** | new module/architecture/external contract | PLAN + DESIGN → critic loop (cap 3) → human approval → SLICES → per-slice loop → integration review |

### Artifacts — `<artifacts_dir>/<feature>/`

```
PLAN.md          problem, scope / non-goals, constraints, Facts table (claim | receipt | V/A),
                 Unknowns, [NEEDS CLARIFICATION: …] markers (none may remain at approval)
DESIGN.md        (L only) modules, interfaces, data model, sequence, decisions, risks
REVIEW-plan.md   critic verdicts per Facts row: CONFIRMED / UNSUPPORTED / REFUTED + severity
SLICES.md        vertical slices: id, user-visible outcome, EARS acceptance criteria
                 ("WHEN … THE SYSTEM SHALL …"), test list, touched modules, depends-on (required),
                 status. Written by the planner as its last step (no separate slicer).
slices/S01/SPEC.md   AC + test file paths + probe list. Written by the planner; test-author
                     may append test paths, nothing else.
slices/S01/probes/   scripted feature probes (curl / Playwright script) — exit code = result
```

State and evidence live **outside the repo**, written only by the `pipeline` CLI:

```
~/.claude/pipeline-state/<repo-id>/<feature>/<slice>/
  state.json       {phase, base_tree, block_count, verdicts:{code, feature}}
  evidence.jsonl   {ts, kind: red|green|infra|validate|probe, cmd, exit, parsed:{passed, failed},
                    tree: <git write-tree>, test_hashes, flaky: bool}
```

### Per-repo profile — `.claude/pipeline.json`

```json
{
  "kit_version": "0.1.0",
  "artifacts_dir": "specs",
  "runner": "jest",
  "test_globs": ["src/**/*.spec.ts", "test/**"],
  "shared_globs": ["test/factories/**", "test/fixtures/**"],
  "protected_globs": ["jest.config.*", "package.json", ".claude/pipeline.json", "tsconfig*.json"],
  "cmd": {
    "test_slice": ["npx jest {test_files}"],
    "test_all":   ["npm test"],
    "lint":       ["npm run lint"],
    "typecheck":  ["npx tsc --noEmit"],
    "build":      ["npm run build"],
    "e2e":        ["npm run test:e2e"]
  },
  "docs": { "nestjs": "/nestjs/docs.nestjs.com", "prisma": "/websites/prisma_io", "bullmq": "/nestjs/bull" }
}
```

- `runner` selects an output parser (`jest`, `rspec`, `go`, `pytest`, `generic`) so "red" means
  *tests ran and N failed*, not "exit non-zero".
- `shared_globs`: editable by both test-author and implementer (factories, fixtures).
- `protected_globs`: editable by neither during tests/implement phases.
- `docs`: the only ctx7 library ids accepted as receipts (critic re-resolves them).
- PTC profile: `runner: rspec`, `test_slice: ["make test ARGS={test_files}"]` plus a frontend
  entry, `test_globs: ["backend/spec/**/*_spec.rb", "frontend/**/*.test.*"]`,
  `shared_globs: ["backend/spec/factories/**", "backend/spec/support/**"]`,
  `protected_globs: ["Makefile", "backend/.rubocop.yml", "frontend/jest.config.js", …]`.
  Because `make test` boots a container per run, the one-test-at-a-time cycle (A6) is used
  only inside a long-lived test container / watch mode; otherwise tests are run per slice.

### Roles — plugin agents (generic)

| Agent | Model / effort | Tools | Job |
|---|---|---|---|
| `planner` | opus / high (L, M) | read, ctx7, write own artifacts | PLAN (+ DESIGN for L), then SLICES and each SPEC. Every fact: `path:line`, command, or pinned doc id — else [A] + Unknowns. Reads lists, never generates members. |
| `reviewer` (one agent, `lens` argument) | opus / high; sonnet for S | read-only + Bash (no Edit/Write) | `lens=plan`: adversarial critic of PLAN/DESIGN, re-derives Facts, simplicity gate, re-resolves doc ids. `lens=code`: slice diff vs SPEC — real assertions, no tautologies, protected paths untouched, scope creep, security, mixed structural/behavioural commits. Reports Critical/Important only. Verdict returned as structured JSON to the orchestrator. |
| `test-author` | sonnet / medium | edit `test_globs` + `shared_globs` only | From SPEC: contract → integration → unit tests; runs `pipeline test --slice`; **must produce a red row whose test-file hashes equal its final files**. Also writes `probes/` for HTTP/UI AC. |
| `implementer` | sonnet / medium; opus after 2 blocks | edit anything except `test_globs`/`protected_globs` | Smallest change to green, one test at a time where the runner allows, refactor on green; structural and behavioural changes in separate commits. Cannot stop while `pipeline validate --quick` is red (cap 3, then stops as `blocked`). May file a `spec-update` finding when an existing test must change; the orchestrator re-spawns test-author for it. |
| `validator` | **script** `pipeline validate` | — | lint, typecheck, slice tests, full suite, build, probes; writes evidence with tree hash; re-runs a red slice test once to flag flakes. |
| feature verification | **script** `pipeline probe` | — | runs `probes/` against the running app; exit codes to evidence. The reviewer (`lens=code`) reads probe results — no prose "observed vs expected" without a probe row. |

Fix loop: findings → implementer → `pipeline validate` → re-review of the failing lens only.
Cap 3 rounds (counted in `state.json`), then stop and hand the open findings to the human.
After the last slice: integration review (`lens=code` over the whole feature diff + all probes).

### Orchestration

`/deliver <feature> [--tier S|M|L]` skill:

1. `pipeline init` if no profile; `pipeline doctor` (git clean, `test_all` exits 0 on the
   current suite, runner adapter parses output, hooks installed) — refuses to start otherwise.
2. Creates **one feature worktree** (`git worktree add`, or `EnterWorktree`) and runs every
   agent with cwd there. No `isolation: worktree` frontmatter — that gives each subagent a
   throw-away worktree branched from the default branch and deleted on exit
   [V ctx7 sub-agents docs], so implementer would never see test-author's tests.
3. Sets phase via `pipeline phase <plan|tests|implement|review>`; spawns agents; records
   reviewer verdicts via `pipeline verdict <lens> <PASS|FAIL> --findings <file>` **itself**
   (orchestrator authority, not the reviewed agent's).
4. Two human approval points: plan approved (L), feature done.

Optional deterministic variant later: saved Workflow script (`~/.claude/workflows/`) with
schema-typed agent outputs; needs opt-in per run [V Workflow tool schema].

### Enforcement hooks (deterministic, 5)

Facts used [V code.claude.com hooks + sub-agents docs, fetched 2026-11-11]: `PreToolUse`,
`Stop`, `SubagentStop`, `TaskCompleted` can block (exit 2 / `decision: block`); agent
frontmatter accepts `skills`, `effort`, `maxTurns`, `model`, `disallowedTools`.
[V ctx7 `/websites/code_claude` plugins/components + sub-agents, 2026-11-11] **plugin agents
ignore the `hooks`, `mcpServers` and `permissionMode` frontmatter fields** — hooks must ship
in the plugin's `hooks/hooks.json`, where `SubagentStop` entries match on `agent_type`. Those
plugin-wide hooks apply whenever the plugin is enabled; the workspace trust dialog applies only
to frontmatter hooks of project-level agents, so it does not apply here. [V same fetch] hook
input carries `agent_id` and `agent_type` on `PreToolUse` (when fired inside a subagent) and
always on `SubagentStop`, together with `agent_transcript_path` and `last_assistant_message`.

| Hook | Event | Blocks when | Authority |
|---|---|---|---|
| H1 `protect-paths` | PreToolUse `Edit\|Write\|Bash` (plugin-wide) | phase ∈ {tests, implement} and target ∈ paths the role may not edit. For Bash: best-effort regex on redirections / `sed -i` / `git checkout --` / `rm` touching `test_globs` ∪ `protected_globs`. | speed bump — real check is H4/H5's `git diff` |
| H3 `require-red` | SubagentStop, `hooks.json` matcher `agent_type = test-author` | `pipeline check red` fails: no row with `kind=red`, `parsed.failed>0`, `test_hashes == current` | CLI |
| H4 `require-green` | SubagentStop, `hooks.json` matcher `agent_type = implementer` | `pipeline validate --quick` red, **or** `git diff --name-only <base_tree>` touches `test_globs`/`protected_globs`. Increments `block_count`; at 3 lets the agent stop with `status=blocked`. | CLI |
| H5 `gate-commit` | PreToolUse Bash `git commit*` | `pipeline check commit` fails: no `validate` row with `tree == git write-tree` and `failed==0`, or protected-paths diff dirty, or required verdicts ≠ PASS, or a `flaky: true` row unresolved | CLI (re-runs validate when the tree hash is stale instead of trusting old rows) |
| H6 `lint-claims` | SubagentStop, `hooks.json` matcher `agent_type = planner\|reviewer` (reviewer: only when the lens is `plan`, read from `state.json`) | any `[NEEDS CLARIFICATION]` left; a V-tagged row without receipt; a `path:line` receipt that doesn't resolve (`test -f` and `line ≤ wc -l`); a doc id not in `pipeline.json.docs` | CLI |

`rtk`: `pipeline` strips a leading `rtk ` and parses runner output itself, so test results are
unaffected; the double-round-trip in auto mode is accepted (Q1 decided: keep rtk).

Residual risk, stated: an implementer that deliberately calls `pipeline phase`/`pipeline
verdict` via Bash can lie to the state. Hook input exposes `agent_type` inside subagents
[V above], so H1 denies `pipeline phase|verdict` whenever `agent_type` is present and is not
the orchestrator; the code reviewer remains the catch for anything H1's regex misses. The
threat model is drift and laziness, not sabotage.

### Hallucination controls, end to end

- Receipts or [A] on every claim; `path:line` resolved by H6; doc ids pinned per repo; critic
  re-derives meaning.
- Tests from spec, by another agent, red observed with matching hashes (H3).
- "Done" = CLI-written exit codes + tree hash (H4, H5), never a summary.
- Feature behaviour = probe exit codes, not prose.
- Reviewers read-only, fresh context, severity floor (skip style).
- Banned completion phrasing without an evidence row ("should work", "Done!") — reviewer flags.
- Rejected tool calls are never retried unchanged (existing rule, now also a reviewer check).

---

## 3. Cleanup of the current setup

| # | Action | Fixes |
|---|---|---|
| C1 | PTC agents: base/target `develop` → `staging` in the 5 files | D1 |
| C2 | PTC agents: `model: opus`/`sonnet` aliases (or `inherit`) + `effort`, `maxTurns` | D2 |
| C3 | Stop using `claude-mem:do`/`:build` for delivery | D3 |
| C4 | **Recommend: disable the rtk PreToolUse hook while auto mode is on** (two independent sessions measured ≥50% double round-trips; it also rewrites test commands). Keep `rtk` for manual use. Final call: Q1 | D4 |
| C5 | caveman: carve-out for plans, specs, reviews, subagent prompts; never drop V/A markers — or off during `/deliver` | D5 |
| C6 | Reconcile `tool-choice.md` with this harness's tools; widen `abdo_writer` tools | D6 |
| C7 | `/lesson` writes into `rules/` or is retired | D7 |
| C8 | Move PTC/GitLab/YouTrack rules to project scope ([A] or path-scoped rules if supported) | D8 |
| C9 | Pipeline lives in a git-tracked plugin (see §6); PTC keeps only `pipeline.json` + PTC skills | D9 |
| C10 | One review rubric file, referenced by the `reviewer` agent and PTC `mr-reviewer` | D10 |
| C11 | Run `/workflow-retro` now (baseline) and 2 weeks after rollout | measurement |

---

## 4. Rollout

1. **Build the kit**: `pipeline` CLI (single-file Python 3, stdlib only) with its own tests
   (fixture stdin → expected exit code; runner-output fixtures for jest/rspec); hooks H1, H3–H6;
   4 agents; `/deliver` skill with `init`, `doctor`, `upgrade`; templates; profiles
   (`nestjs`, `rails-ptc`, `go`).
2. **Pilot** on `~/projects/ptc-nest-onboarding` M0–M1 (greenfield). `pipeline doctor` must
   pass on the empty suite first — today the repo has only `PLAN.md`, so M0 scaffolding comes
   before the first slice.
3. **Port** to PTC: replace PTC planner/implementer/qa with kit agents + `rails-ptc` profile;
   inject PTC-only skills (`verify-in-browser`, `test-data`, `ptc-code-conventions`) via
   `skills:` frontmatter.
4. **Measure** with `/workflow-retro` and `claude-mem:agent-cost-report` against the C11 baseline:
   red-before-green compliance, findings per slice per lens, human rechecks, fix rounds,
   tokens per slice.

---

## 5. Comparison with published workflows (sources fetched 2026-11-11)

| | Stages | Independent review | Test-first | Slice size | Validation | Enforcement |
|---|---|---|---|---|---|---|
| Anthropic best practices | interview → SPEC.md → build in fresh session → verify → fresh reviewer | yes — fresh-subagent review, read-only reviewer tools | encouraged | n/a | prefers runnable pass/fail; Stop hook; app verification | "make it a hook… CLAUDE.md is for guidelines"; keep the enforced set small |
| GitHub Spec Kit | constitution → specify → plan → tasks → implement ⇄ converge | not described | **mandatory** (Art. III), contract → integration → e2e → unit | tasks, `[P]` | LLM converge loop | templates + optional hooks |
| AWS Kiro | requirements (EARS) → design → tasks | human Markdown review | no | tasks in dependency waves | agent + hooks | hooks, steering files |
| obra/superpowers | brainstorm → worktree → plan → subagent per task → TDD → review → finish | **yes, per task** | **mandatory**; delete code written before the test | 2–5 min tasks | LLM rule: fresh evidence, banned phrases | prose |
| BMAD v6 | clarify → plan → build+verify → learn | per-story code review [secondary source] | optional module | stories | LLM | prose |
| Harper Reed | spec → prompt plan → todo → execute | human | optional | right-sized chunks | tests / human | human |
| Kent Beck | plan.md of tests → one test at a time | human watching | **mandatory** | one test | run all tests each time | human; watches for deleted tests |
| Matt Pocock skills | grill → to-spec → to-tickets → tdd → implement → code-review | end review | **mandatory**, vertical slice | tracer-bullet tickets | LLM | prose |
| **This proposal v2** | tiers S/M/L; plan → critic → slices → test-author → implement → CLI validate → review | **yes, per slice** | **mandatory, red proven by hash-matched CLI row** | vertical slice ≈ half a day | **script + tree-hashed evidence** | **5 hooks + CLI** |

Unique here: deterministic gates on test evidence, test-author ≠ implementer, scripted feature
probes, mechanical receipt resolution. Adopted from the field: tiers (BMAD/superpowers),
`[NEEDS CLARIFICATION]` (Spec Kit), EARS AC (Kiro), simplicity gate + contract-first + real DB
over mocks (Spec Kit), one test at a time + structural/behavioural commit split (Beck),
severity floor + small enforced set + reuse built-ins where the harness has them (Anthropic;
this harness today has PTC's project `code-review`, `simplify`, `security-review` — no `/verify`),
banned completion phrases (superpowers), required `depends-on` (Pocock), worktree per feature.

Sources: code.claude.com/docs/en/best-practices · anthropic.com/engineering/building-effective-agents ·
github.com/github/spec-kit (README, spec-driven.md) · kiro.dev/docs/specs, /hooks, /steering ·
github.com/obra/superpowers (README; TDD, subagent-driven-development, verification-before-completion skills) ·
github.com/bmad-code-org/BMAD-METHOD, docs.bmad-method.org (per-story loop: secondary only) ·
harper.blog/2025/02/16/my-llm-codegen-workflow-atm · newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes ·
github.com/mattpocock/skills

---

## 6. Recipe — the `delivery-kit` plugin

Packaging follows the Claude Code plugin layout [V github.com/anthropics/claude-code plugins/README.md]:

```
~/.claude/local-marketplace/plugins/delivery-kit/       ← git repo (private), symlinked or cloned here
  .claude-plugin/plugin.json      name, version
  agents/                         planner.md reviewer.md test-author.md implementer.md
  skills/deliver/SKILL.md         /deliver <feature> [--tier], /deliver init <profile>, doctor, upgrade
  hooks/hooks.json                H1 protect-paths, H5 gate-commit (PreToolUse), H3/H4/H6 (SubagentStop by agent_type)
  bin/pipeline                    single-file Python 3, stdlib only; tests/ beside it
  templates/                      PLAN.md DESIGN.md SLICES.md SPEC.md REVIEW.md pipeline.json CLAUDE-snippet.md
  profiles/                       nestjs.json rails-ptc.json go.json
  rubric/code-review.md           the one review rubric (C10)
  README.md                       how to adopt in a new repo
```

Register in `~/.claude/local-marketplace/.claude-plugin/marketplace.json` next to `vue-ts-lsp`
[V existing manifest]; enable once in `~/.claude/settings.json` `enabledPlugins`. Develop/test
with `claude --plugin-dir <path>` [V plugins README].

**Adopting in a new repo (< 10 min):**

1. `/deliver init nestjs` → copies `profiles/nestjs.json` to `.claude/pipeline.json`, creates
   `specs/`, appends the `CLAUDE-snippet.md` block (exact test/lint/typecheck commands — the
   Anthropic BP rule), adds `.claude/pipeline-state` nothing (state is outside the repo).
2. `pipeline doctor` → fails loudly until: git clean, runner detected, `test_all` exits 0,
   hooks reachable. Greenfield repos must scaffold a runnable empty suite first.
3. `/deliver <feature>` → starts at tier S by default.

**Upgrading:** `kit_version` in `pipeline.json`; `/deliver upgrade` diffs the repo profile and
templates against the kit and shows the patch.

**Template vs generated:** hooks, agents, CLI, rubric, templates are kit files (never edited in
the repo); `pipeline.json` values, artifacts and probes are generated per repo.

---

## 7. Cost model — reliable *and* cheap

Where tokens go in an agentic cycle, and what this design does about each:

| Sink | Lever |
|---|---|
| Always-on context (~15–20k tokens per prompt today: CLAUDE.md+rules, caveman, claude-mem index, ~180 skill names) [A estimate] | C8 project-scoping of rules; prune unused plugins/skills (retro 08-19 F7); keep the kit's injected text ≤ 1k tokens |
| Double Bash round-trips from rtk in auto mode | C4 |
| Long main-thread sessions re-reading the same files | fresh, narrow agents per stage; forks share the prompt cache; stable agent prompts with variable content last |
| Model tier | opus/high only where judgment pays: planner (L/M), reviewer. sonnet/medium for test-author and implementer, which work from a written spec; escalate implementer to opus only after 2 blocks |
| Review rounds | severity floor (Critical/Important), cap 3 rounds, re-review only the failing lens, S-tier single review |
| Human rechecks (44 per retro window) | evidence rows and probe results replace "did you test it?" |
| Verification | validator, probes and hooks are scripts: zero tokens, deterministic, re-runnable |
| Oversized plans | tier S skips PLAN/DESIGN; `[NEEDS CLARIFICATION]` stops guessing-then-rewriting |

No per-slice cost figure is claimed here — measure it on the pilot with
`claude-mem:agent-cost-report` and set the baseline before tuning.

---

## 8. Decisions (2026-11-11)

- Q1 rtk: **keep as is.** `pipeline` strips a leading `rtk ` and parses runner output itself;
  the auto-mode double round-trip is accepted. C4 dropped.
- Q2 caveman: **carve-out.** Plans, specs, reviews and subagent prompts are written normal;
  verified/assumed markers are never dropped.
- Q3 Orchestration default: **`/deliver` skill.** Workflow script is a later variant.
- Q4 Kit location: **git repo at `~/.claude/local-marketplace/plugins/delivery-kit`**, pushed to
  the private GitHub repo `Abdelwahab313/delivery-kit`.
- Q5 (resolved from docs, see §2 Enforcement hooks): hook input exposes `agent_type`; plugin
  agents ignore frontmatter `hooks`, so every SubagentStop gate lives in `hooks/hooks.json`.
