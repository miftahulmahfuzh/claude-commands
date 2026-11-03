---
name: engineering-principles
description: Ten engineering principles a planner applies while writing a plan, recording which decision each one changed. Read by phase-planner and plan-generator; not for direct use.
disable-model-invocation: true
---

# Engineering principles

Distilled from Lauren Tan's pstack (`cursor/plugins/pstack`, `docs/guide/08-principles.md`).
They are read once, at planning time. The plan carries the decisions they produced, so the
sessions that implement the plan never load this file. That is the point: the principles cost
one read per plan, not one read per agent.

**How to apply them.** Go through the list against the work you are planning. For each one
that triggers, change the plan, then record the change in the plan's **Principles applied**
section as `<principle>: <the decision it changed>`. A principle named without a decision behind
it was not applied, so leave it out. Usually two to four apply. If none do, write `none
triggered` and move on.

## Scope: how much to build

1. **Subtract before you add.** Before adding to something, look for what it makes obsolete:
   dead branches, unused options, the adapter the new path replaces. Delete that first, in an
   earlier step or phase, then build on the smaller base.
2. **Laziness protocol.** Prefer the smallest change that solves the stated problem: delete
   over modify, modify over add, reuse over new abstraction. A framework for a single caller
   is scope creep.
3. **Build the lever.** When the work is repetitive (a sweep, a migration, many similar
   edits) or hard to check by eye, plan a script, codemod or generator that does or proves it,
   so a reviewer reruns the script instead of trusting the diff. Do one unit by hand first to
   learn the recipe. The bar is "not trivial", not "repeated".

## Correctness: where state and rules live

4. **Boundary discipline.** Validate and normalize external input once, where it enters
   (HTTP handler, MCP tool, file parser, env), and trust the typed value inside. Scattered
   re-validation deep in the code is a smell.
5. **Make illegal states unrepresentable.** When two fields can contradict each other, or a
   flag only means something in one mode, change the type or schema so the bad combination
   cannot be built, instead of checking for it at runtime.
6. **Fix root causes.** For a bug, the plan states the reproduction and the cause traced to a
   line, before any change. A fix without a reproduction is a guess. **Attack the premise:**
   if two fixes with one shared assumption have already failed, write that assumption down and
   test it directly before planning a third.

## Verification: what counts as proof

7. **Prove it works.** Each phase ends with proof on the real artifact (the running app, the
   real command, the written row), not "it compiles" or "the unit test I wrote passes". If the
   repo has a verification skill (`.claude/skills/verify-*`), the plan's **Proof** uses it.
8. **Sequence into verifiable units.** Order steps and phases so each one ends in a check that
   can fail. A long run of edits verified only at the end is one giant unverified unit.
9. **Test behavior, not implementation.** Tests assert what a caller or user can observe, so
   they fail when the behavior breaks and survive a refactor. A test that mocks the unit
   under test, or asserts on private calls, proves nothing.

## Meta

10. **Encode lessons in structure.** If the analysis shows the same mistake made twice
    (a footgun in a convention, a recurring review comment), plan a lint, check, type or test
    that makes it impossible, instead of another sentence in a doc.
