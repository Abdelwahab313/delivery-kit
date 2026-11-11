
## Delivery pipeline (delivery-kit)

This repo is driven by `/deliver`. Exact commands, from `.claude/pipeline.json`:

- Slice tests: `{cmd.test_slice}`
- Whole suite: `{cmd.test_all}`
- Lint: `{cmd.lint}`
- Typecheck: `{cmd.typecheck}`

Run `pipeline validate` before claiming anything is green; the only accepted evidence is a
`validate` row written by the CLI, not a summary. Pipeline state and evidence live outside
the repo under `~/.claude/pipeline-state/`; nothing under this tree records them.
Specs and slices live under `{artifacts_dir}/<feature>/`.
