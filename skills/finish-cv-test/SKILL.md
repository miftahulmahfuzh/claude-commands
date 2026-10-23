---
name: finish-cv-test
description: Use when a computer-vision practice attempt is over and needs scoring — "/finish-cv-test", "I'm done", "that's my answer", "time's up", "evaluate how I did" — typed inside the tmux session that was working on the run. Stops the clock, recovers the candidate's verbatim instructions from the session transcript, checks the solution against ground truth, writes EVALUATION.md, and publishes the verdict into the run's worklog artifact.
---

# Finish and evaluate a CV practice attempt

Invoked **inside the run's own session**, whose cwd is `~/cv-problems/.runs/<run-id>/`.

The exam is over the moment this runs. The two restrictions in the workspace
`CLAUDE.md` — do not read outside this directory, do not coach — **lift now**. Read
everything.

## Step 1 — Stop the clock and recover the evidence

Find the attempt directory whose `.exam/meta.json` names this workspace:

```bash
cd ~/cv-problems
grep -l "$(pwd)" attempts/*/.exam/meta.json
python3 bin/cvtest.py finish --attempt attempts/<date>-<slug>
```

This writes `TRANSCRIPT.md` into the attempt directory and prints the hard numbers:
elapsed against budget (measured from the candidate's first instruction, not from
spawn), how many instructions they actually typed, tool calls, files written,
interrupts, the word count of the opening instruction, and the worklog artifact URL.

Those numbers are evidence, not the verdict. A 12-instruction run can be excellent
and a 2-instruction run can be a disaster.

## Step 2 — Read what was actually asked for

In this order:

1. `attempts/<slug>/PROBLEM.md` — the brief, now unsealed.
2. `attempts/<slug>/GROUND_TRUTH.json` — the expected answer, the forks, the traps.
3. `attempts/<slug>/TRANSCRIPT.md` — the candidate's verbatim instructions.
4. The solution in the workspace.

## Step 3 — Check correctness first

Run the candidate's solution. Compare its output against the ground truth, number by
number. **Look at the output artifact** — read the annotated image, not just the
printed count.

Three distinct verdicts, and they must not be blurred:

- **Right, and verified during the run** — the candidate checked and knows it is right.
- **Right, unverified** — correct by luck or by the agent's good defaults. Say so
  plainly; this is the most common outcome and the most dangerous habit.
- **Wrong** — name the specific number and the specific cause.

Check each planted trap: hit, avoided deliberately, or avoided by accident?

## Step 4 — Get a cold read

Dispatch **one** `general-purpose` subagent. Give it the brief, the ground truth and
`TRANSCRIPT.md` — and *not* your own account of the run. Ask it to score the seven
dimensions in `~/cv-problems/reference/prompting-playbook.md` from the transcript
alone, quote the weakest instruction verbatim, and name the single highest-leverage
change.

You helped produce this work, so you are a lenient judge of the instructions that
produced it. The cold read is the correction for that. Where it disagrees with you,
say so in the evaluation rather than silently picking one.

## Step 5 — Write the evaluation

`attempts/<slug>/EVALUATION.md`, following the shape of
`attempts/2026-10-22-rect-center/EVALUATION.md`:

- A one-line verdict up front: passed / passed-unverified / failed, elapsed vs budget.
- The seven dimensions, each **strong / adequate / weak**, each with a quoted
  instruction and a concrete cheaper alternative. A dimension the run did not
  exercise is "not exercised" — do not invent a score.
- **Requirement drift**: anywhere an answer to a clarifying question quietly changed
  the spec. The subtlest failure and the most valuable one to catch.
- A numbered **Carry into the next attempt** list — at most four items, each concrete
  enough to act on without interpretation.
- Which archetype to run next, and why.

Quote actual words from the transcript. Name the specific cv2 call or technique that
would have helped and where it is documented in `reference/`. No praise that is not
attached to a specific decision. Being liked matters less than the next run going
better — but do not manufacture faults either; "not exercised" and "nothing to fix
here" are real findings.

## Step 6 — Close the worklog artifact

The run has been publishing `worklog.html` as it went. Now finish it: republish the
same file (same URL) with three sections appended below the outputs —

- **The brief**, now that it can be shown.
- **Ground truth vs what was produced**, as a small table, with the traps marked hit
  or avoided.
- **The verdict and the carry-forward list**, condensed — the seven scores as a
  compact list and the numbered items. Link to `EVALUATION.md` for the full text.

Keep the images above it. This page is what the candidate actually reviews later:
input, every output in order, then what it should have been and why.

## Step 7 — Record and commit

Update the attempts table at the bottom of `~/cv-problems/README.md` — date, problem,
tier, budget, result, artifact link.

If the run exposed a reusable gap — an API the candidate did not know, a trap worth
naming — add it to the right `reference/` document. The prep kit should get better
every run; that is the compounding part.

```bash
cd ~/cv-problems && git add -A && git commit -q -m "attempt <slug>: <verdict>" && git push -q
```

## Step 8 — Deliver it in the terminal

Print the verdict, the seven scores as a compact list, the carry-forward items, and
the artifact URL. Keep it short — the detail is in the file and on the page. Then
name the next archetype.
