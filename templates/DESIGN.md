# <feature> — design

Tier L only. Status: draft | approved. Companion to `PLAN.md`; cite its Facts by row number.

## Modules

| Module | Responsibility | New / changed | Receipt |
|---|---|---|---|

## Interfaces

Public surface each module exposes: function signatures, HTTP routes, CLI commands, events.
One block per interface; mark each as new or changed.

## Data model

Tables / collections / schemas touched, with the migration direction. Include constraints
and indexes. Receipt for every existing structure cited.

## Sequence

For each main flow: the ordered calls between modules, including failure paths. Text or a
fenced diagram.

## Decisions

| # | Decision | Alternatives considered | Why this one | Receipt |
|---|---|---|---|---|

## Risks

Design-level risks not already in PLAN.md: concurrency, data loss, external contract
breakage, rollout order. Each with a mitigation.
