# delivery-kit

A Claude Code plugin for spec-driven, test-first software delivery with deterministic
evidence gates. Generic core, per-repo profile.

Cycle: plan → adversarial review → vertical slices → per slice: spec → tests (by one agent)
→ implementation (by another) → scripted validation → code/feature review → next slice.

## What is in here

```
.claude-plugin/plugin.json   plugin manifest
agents/                      planner, reviewer (lens=plan|code), test-author, implementer
skills/deliver/SKILL.md      /deliver <feature> [--tier S|M|L], /deliver init <profile>, doctor, upgrade
hooks/hooks.json             protect-paths (PreToolUse), gate-commit (PreToolUse git commit)
bin/pipeline                 single-file Python 3 CLI, stdlib only; tests/ beside it
templates/                   PLAN.md DESIGN.md SLICES.md SPEC.md REVIEW.md pipeline.json CLAUDE-snippet.md
profiles/                    nestjs.json rails-ptc.json go.json
rubric/code-review.md        the one review rubric
docs/PLAN.md                 design document (audit, design, rollout, comparison, cost model)
```

Design, rationale and open questions: `docs/PLAN.md`.

## Principles

1. Artifacts over chat — every stage reads and writes files.
2. The author never grades its own work — reviews run in a fresh, read-only context.
3. Evidence is produced by a script (`pipeline`), never inferred from the model. Gates re-run
   or re-hash; they never trust a prose "green".
4. Tests come from the spec, before the code, by a different agent.
5. Every factual claim carries a resolvable receipt or an `[A]` tag.
6. Right-size the process: tiers S / M / L.

## Adopting in a repo

1. `/deliver init <profile>` — copies `profiles/<profile>.json` to `.claude/pipeline.json`,
   creates the artifacts dir, appends the CLAUDE snippet with exact test/lint/typecheck commands.
2. `pipeline doctor` — refuses to start until git is clean, the runner is detected, `test_all`
   exits 0 and hooks are reachable. Greenfield repos must scaffold a runnable empty suite first.
3. `/deliver <feature>` — starts at tier S by default.

State and evidence live outside the repo under `~/.claude/pipeline-state/<repo-id>/`.

## Installing locally

Registered in the local marketplace `~/.claude/local-marketplace/.claude-plugin/marketplace.json`
as `delivery-kit@abdelwahab-local`. For development: `claude --plugin-dir <this directory>`.

## Coexistence with other setups

- Agents are namespaced: spawn them as `delivery-kit:planner`, `delivery-kit:reviewer`,
  `delivery-kit:test-author`, `delivery-kit:implementer`. A repo's own `.claude/agents/planner.md`
  (PTC has one) is a different agent and is not shadowed.
- The hooks in `hooks/hooks.json` are global once the plugin is enabled. Every gate exits 0
  immediately when the current repo has no `.claude/pipeline.json` or no active feature
  (`current.json`), so repos that do not use the kit only pay one `python3` start per matched
  tool call.
- State never enters the repo: `~/.claude/pipeline-state/<repo-id>/`.
- `rtk`: a leading `rtk ` in any configured command is stripped before running; the CLI parses
  runner output itself.

## Status

0.1.0 — CLI, hooks, agents, skill, templates, profiles and rubric written; 40 CLI tests
(`python3 -m unittest discover -s tests`). Pilot pending on `~/projects/ptc-nest-onboarding`.
Build order is in `docs/PLAN.md` §4.
