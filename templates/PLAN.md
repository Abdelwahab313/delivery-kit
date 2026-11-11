# <feature> — plan

Tier: M | L. Status: draft | approved. Date: <YYYY-MM-DD>.

Receipt legend: **V** verified — the receipt is a `path:line` in this repo, a command with its
quoted output, or a documentation id listed in `.claude/pipeline.json` `docs`. **A** assumed —
listed under Unknowns with how it will be verified. Where the request is ambiguous, write a
NEEDS CLARIFICATION marker (square brackets, colon, the question) in place; none may remain
at approval.

## Problem

What is wrong or missing today, for whom, and how it shows. One paragraph.

## Scope

- In:
- Out (non-goals):

## Constraints

Hard limits the solution must respect (compatibility, performance, security, deadlines,
repo conventions), each with a receipt.

## Facts

| # | Claim | Receipt | V/A |
|---|---|---|---|
| 1 | | `path:line` / `cmd → output` / `/org/project` | V |
| 2 | | | A |

## Unknowns

- [A] <claim from the Facts table> — verify by <command, file, or question to the human>.
- one NEEDS CLARIFICATION marker per open question to the human

## Approach

How the change will be made, by module, in the order the slices will land. Reference Facts
rows by number rather than restating them.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
