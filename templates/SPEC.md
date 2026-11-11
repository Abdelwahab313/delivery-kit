# <feature> / <S> — spec

Outcome: <one sentence a user or caller can observe>. Depends on: <slice id | none>.

## Acceptance criteria

EARS form, one observable behaviour per line, each covered by a test listed below.

1. WHEN <trigger> THE SYSTEM SHALL <observable result>.
2. WHEN <trigger> AND <condition> THE SYSTEM SHALL <observable result>.
3. IF <failure condition> THEN THE SYSTEM SHALL <observable result>.

## Tests

Repo-relative paths matching `test_globs`. The test-author may append paths here and may
edit nothing else in this file.

- `path/to/contract.spec.ext` — AC 1, 3
- `path/to/integration.spec.ext` — AC 2

## Probes

Executable scripts under `slices/<S>/probes/`, one per HTTP/UI criterion, exit 0 when met.
Write `none` when no criterion is HTTP/UI.

- `probes/01-<name>.sh` — AC 1

## Touched modules

- `path/to/module` — new | changed

## Notes

Constraints specific to this slice, with receipts or `[A]`.
