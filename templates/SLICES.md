# <feature> — slices

Each slice is vertical: something a user or caller can observe end to end, about half a day
of work. `depends-on` is required (`none` when independent). Status is one of
`todo | tests | implement | review | done | blocked`.

| Id | User-visible outcome | Acceptance criteria (EARS) | Tests | Touched modules | Depends on | Status |
|---|---|---|---|---|---|---|
| S01 | | WHEN … THE SYSTEM SHALL … | `path/to/test` | | none | todo |
| S02 | | | | | S01 | todo |

Each row has a `slices/<Id>/SPEC.md` with the full acceptance criteria, the test file list
and the probe list.
