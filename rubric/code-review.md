# Code review rubric

The one rubric. Applied by the kit's `reviewer` (lens=code) and by any repo-specific
reviewer that references it. Reviews are read-only and come from a fresh context.

## Severity

- **Critical** — wrong result, data loss, security hole, protected or test path edited by the
  implementer, evidence missing or stale for a "done" claim. Blocks the slice.
- **Important** — a spec criterion without a real test, a test weakened or deleted, scope
  outside the slice, an abstraction with one caller, mixed structural/behavioural commit,
  a completion claim without an evidence row. Blocks unless the SPEC states a mitigation.
- **Minor** — style, naming, formatting. Not reported.

Every finding: `file`, `line`, one-sentence defect, concrete fix. No praise, no restating the
diff.

## 1. Correctness at the seams

- Inputs from outside the module (HTTP, CLI, queue, DB rows, env) are validated once, at the
  boundary; internal calls are trusted.
- Error paths return or raise what the SPEC says; no swallowed exceptions, no `rescue`/`catch`
  that hides the cause.
- Nil/empty/zero/duplicate/concurrent cases named in the AC are handled; the test proves it.
- Transactions do not wrap external I/O; retries are idempotent.

## 2. Tests

- Every AC in SPEC.md maps to at least one test that fails if the behaviour is removed.
- Assertions are on observable results, not on the implementation's internals.
- No tautologies (`expect(x).toBe(x)`, asserting the mock returned what it was told to).
- No assertions inside conditionals or loops that can run zero times.
- The unit under test is not mocked; collaborators may be, external systems should be.
- No test was deleted, skipped, marked pending, or had its assertion loosened in this diff.
  Check `git diff <base_tree> -- <test_globs>`: it must be empty for the implementer's range.

## 3. Scope

- The diff touches only the modules listed in SPEC.md "Touched modules", plus files the
  tests required. Anything else is scope creep.
- No file matching `protected_globs` changed. No file matching `test_globs` changed by the
  implementer.
- No unrelated fixes, formatting sweeps, or dependency bumps.

## 4. Security

- No string-built SQL, shell commands, or HTML from user input; parameterised APIs used.
- No secrets, tokens, or credentials in code, tests, fixtures, or logs.
- Authorisation checks are where the SPEC places them and are tested for the denied case.
- New endpoints or commands fail closed.

## 5. Simplicity gate

- No new abstraction (class, interface, factory, provider, module) without a second caller in
  this diff.
- No flags, options, or parameters for cases the SPEC does not name.
- No backwards-compatibility shims where the old code could be changed.
- Three similar lines beat a premature helper.

## 6. Commit hygiene

- Structural commits (rename, move, extract, reorder) contain no behaviour change.
- Behavioural commits contain no structural noise.
- Subjects are imperative and say why, not what.

## 7. Evidence

- The latest `validate` row: `failed == 0`, `flaky == false`, `protected_dirty == []`, `tree`
  equals the current `git write-tree`.
- Every HTTP/UI criterion has a probe row with exit 0.
- Any of these phrases in the handoff or commit messages without a matching evidence row is
  an Important finding: "done", "works", "should work", "all green", "verified", "tested
  manually", "should pass", "looks good", "no issues".
- A rejected tool call that was re-issued unchanged is an Important finding.
