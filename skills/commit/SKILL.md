---
name: commit
description: Use when work is finished and should go into git — "/commit", "commit this", "commit and push", "ship it", "that's done, commit it" — or before any push, PR or hand-off. Lists the files this session actually changed, shows the whole diff, flags dead code, commented-out blocks, duplicated test functions and debug leftovers, runs the test files that touch the changed modules, and only then commits with a message that says why.
---

# Commit

At ~30 commits a day the commit is not a formality, it is the last gate anything passes through.
Three things have gone out through it: dead code left in a renderer, a test function duplicated by
a bookkeeping subagent, and an edit swept in under a peer's commit message. All three are
mechanically detectable in the seconds before the commit, and invisible for weeks after it.

**The order is the whole skill.** List, diff, flag, test, then commit. Each step can stop the
commit; none of them is worth skipping because the change "is only a one-liner".

## 1. List the files, from the session and not from the tree

Write out the paths this session changed, before running any git command. Then:

```bash
git status --porcelain
```

Compare the two lists. **Dirty does not mean yours.** A path dirty in the tree but absent from
your list belongs to someone — a peer phase mid-write, an earlier session, a generated file — and
it stays out of this commit and gets named in the report. A path in your list but not dirty means
you did not actually change it, or an editor wrote it back; find out which.

Never `git add -A`, `git add .`, `git add -u`, or `git commit -a`. In a repo where other sessions
share the worktree, see `agents/pusher.md` for the full mechanics — the short version is that the
*index* is shared too, so `git add -- <paths>` followed by a bare `git commit` still takes a
peer's staged files. Bind the commit itself:

```bash
git add -- <each new file>                      # a pathspec commit only sees tracked files
git commit -m "<msg>" -- <every path, new and old>
```

And when a file is genuinely shared with a peer who has uncommitted edits in it, a pathspec
commit reads the *working tree* and takes their edit too. Use a private index then:

```bash
IDX=.git/index-$$; GIT_INDEX_FILE=$IDX git read-tree HEAD
GIT_INDEX_FILE=$IDX git add -- <only your paths>
GIT_INDEX_FILE=$IDX git commit -m "<msg>"
rm -f "$IDX"
```

## 2. Show the whole diff

```bash
git diff HEAD -- <your paths>
```

All of it, not a summary. Read it as a reviewer who did not write it: this is the only moment the
change is cheap to judge and the only moment the full context is still loaded.

## 3. Flag what a reviewer would flag

Mechanical first, because the eye slides over exactly these:

```bash
git diff HEAD -- <your paths> > /tmp/commit-review.diff
# code that was commented out rather than deleted
grep -nE '^\+[[:space:]]*(//|#|--)[[:space:]]*(if|for|while|func|def|return|class|console\.|print\(|[A-Za-z_]+[[:space:]]*\()' /tmp/commit-review.diff
# debug leftovers
grep -nE '^\+[[:space:]]*(console\.log|print\(|fmt\.Print|println!|debugger)\b' /tmp/commit-review.diff
```

Both verified 2026-10-23 against a synthetic diff: they catch a commented-out `if` block and a
commented-out function body, and leave a genuine explanatory comment alone. They are **flags, not
verdicts** — a `print` in a CLI command is the output, and a commented line explaining why is the
point of comments. Judge each one; do not auto-strip.

Then the stack's own dead-code check, on the changed files only:

| Stack | Command | Catches |
|---|---|---|
| Python | `ruff check --select F <files>` | `F811` a redefined/duplicated function, `F401` unused import, `F841` unused variable |
| Go | `go build ./... && go vet ./...` | duplicate `func TestX` in one package (it will not compile), unreachable code, bad printf |
| Go, deeper | `staticcheck ./...` *if installed* | `U1000` unused unexported code |
| TypeScript | `npx tsc --noEmit` | unused locals and params **only if** the tsconfig sets `noUnusedLocals` / `noUnusedParameters` |

**Duplicated test functions are a per-stack problem, not a general one.** Python and Go catch them
for free — measured 2026-10-23, `ruff check --select F` on a file with `test_alpha` defined twice
reports `F811 Redefinition of unused test_alpha`, and in Go a duplicate `func TestX` in a package
fails to build. Vitest and Jest do **not**: two `it("same name")` blocks both run, and a copy of a
whole `describe` block reads green while shadowing the original. So for a JS/TS test file, grep
the added test names and check for repeats:

```bash
grep -nE '^\+[[:space:]]*(it|test|describe)\(' /tmp/commit-review.diff \
  | sed -E 's/.*(it|test|describe)\(["'"'"'`]([^"'"'"'`]*).*/\2/' | sort | uniq -d
```

A repo's own CLAUDE.md may name a narrower lint (Seer's CI is `ruff check engine`, bugs only —
`E9` and `F` minus `F401` — because the tree has thousands of long lines and frozen records that
must not be reformatted). **The repo's configured command always wins over the table above**, and
never run a formatter the repo does not already run.

## 4. Run the tests that touch what changed

The files, not the suite. A full suite is slower and, on 30 commits a day, gets skipped — which is
how a change ships untested.

| Stack | Command |
|---|---|
| Python | `pytest <tests/test_<module>.py for each changed module>` |
| Go | `go test ./<each changed package>/...` |
| TS (vitest) | `npx vitest related --run <changed files>` — present in vitest 3.2.7, verified |
| Markdown / config only | no tests; say so rather than implying a run |

If a changed module has no test file, say that in the report — an untested module is a fact worth
one line, not a reason to stop.

**A red test is a stop.** Fix it, or state plainly that the commit is going out red and why. Never
weaken or delete a test to get green: a test that was red before you started is still red because
of something, and finding out costs less than the commit that buries it.

## 5. Write why, not what

The diff already says what. The subject line follows **whatever this repo already uses** — read
`git log --oneline -20` first, because 329 commits of a convention beat any template here (Seer
uses `lab: M00NN …`, `docs:`, `chore:`). The body is where the value is:

- the problem or decision that made this necessary
- what was tried and rejected, if that is why the code looks odd
- the measurement, if a number drove the change — with the command that produced it
- anything a reader would otherwise have to reconstruct from the diff

Skip the body only for a change whose why is fully contained in its subject. Keep any attribution
lines the environment asks for.

## 6. Commit, then read back what you committed

```bash
git show --stat --format="" HEAD
```

If that file list is not your list, **say so — do not amend, reset or rewrite.** A wrong message
is cosmetic; rewriting history in a tree other sessions are pushing to is not. Report:

- the commit hash and its file list
- every dirty path you deliberately left out, by name
- every flag you judged and waved through, with the reason
- what you ran and what it said

## Never

| Temptation | Rule |
|---|---|
| "`git add -A`, it's all mine anyway" | List first. It is how you find out it is not. |
| "Skip the diff, I just wrote it" | You wrote it across many turns. Read it once as a whole. |
| "The flag is a false positive, strip it" | Judge it and say so in the report. Silent stripping is how the real one gets missed. |
| "Full suite is too slow, skip tests" | Run the files that touch what changed. That is the compromise. |
| "Delete the failing test, it's unrelated" | Then it was red before you started, and that is a finding. |
| "`git commit -a` is faster" | It commits a peer's half-written files under your message. |
| "Amend to fix the file list" | Report it. Never rewrite a tree others are pushing to. |
