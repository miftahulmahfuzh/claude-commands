---
name: spawn-new-cv-test
description: Use when the user wants a computer-vision live-coding practice problem — "/spawn-new-cv-test", "give me a CV problem", "let's practice for the Boon interview", "spawn a new CV test", "another practice round", "test me on floor plans" — or when they want to rehearse driving Claude Code under an interview clock. Scaffolds a sealed run, writes the brief, and opens it in a fresh Claude Code session in its own tmux window with the brief pinned in a pane above it.
---

# Spawn a new CV practice test

You are the **examiner**. You write the brief and hand it over; you do not solve it,
and you do not coach while it is running. A separate Claude Code session in its own
tmux window is the candidate's assistant.

Repo: `~/cv-problems` (remote `git@github.com:miftahulmahfuzh/cv-problems.git`).
Harness: `~/cv-problems/bin/cvtest.py`.

Keep your own token use lean — this session is the user's long-lived one, and the
point of spawning a window is to keep the work out of it. Do not read the reference
documents end to end; you already know what is in them from their headings.

## What the harness sets up, so you do not have to

- **A neutral workspace.** The run lives in `.runs/<date>-<n>/`, never a path naming
  the task — Claude Code is told its working directory in every system prompt, so
  `attempts/count-receptacles/` would hand over the answer before the candidate
  speaks. The readable slug stays on the attempt directory, which the session never
  sees.
- **A brief pane.** The window is split: the brief on top, the Claude session below,
  focus on Claude. It survives detach and resume, so the candidate can reread the
  task days later; the assistant still cannot read it at all.
- **A worklog artifact.** The session is booted with one fixed setup prompt telling
  it to publish `worklog.html` showing the input images, and its `CLAUDE.md` tells it
  to republish that same file whenever it writes anything into `output/`. The
  terminal cannot show images; this is how the candidate sees input and output.
- **The clock starts at the candidate's first instruction**, not at spawn — reading
  time and artifact setup are not charged to the budget.

## Step 0 — Make sure the repo is there

```bash
test -d ~/cv-problems || git clone git@github.com:miftahulmahfuzh/cv-problems.git ~/cv-problems
python3 ~/cv-problems/bin/cvtest.py status
```

`status` tells you which archetypes have been attempted. If `~/cv-problems/.venv` is
missing, say so and stop — a practice run without the environment is not one.

## Step 1 — Choose the problem

Read the user's arguments. They may name a tier (`tier 4`), an archetype
(`count symbols`), a topic (`floor plans`, `tables`, `CLIP`), or a budget
(`20 min`). With no arguments, **pick the next unattempted archetype** from
`reference/problem-ladder.md`, weighted toward tier 3–4: the interview is decided
there, and tiers 1–2 are already close to muscle memory.

Default budget: **30 minutes**. Tier 1–2 problems get 15–20.

Announce the choice in one line — tier, archetype, budget — and nothing about the
approach. Naming the technique is the answer; do not.

## Step 2 — Choose the data

Pick whichever source actually suits the archetype. Do not ask the user to find an
image when a generator already produces one with exact ground truth.

- **Synthetic** — `fixtures/make_floorplan.py` (plan sheet: vector PDF + raster +
  ground truth JSON, with the `TYP. OF 4` banked-run trap). Best for anything needing
  a verifiable count, measurement or scale. Write a new generator beside it if the
  archetype needs different data; seed it and emit ground truth.
- **Existing fixtures** — `fixtures/mock/` (candlestick chart, document table,
  shapes, landscape photo). Best for tiers 1–3.
- **User-supplied** — for realism and messy input. Ask in one line: say what kind of
  image would suit and where to drop it. Then **actually open it with the Read tool**
  and judge it — resolution, vector or raster, is the thing to be found visible, is
  there a verifiable answer. If it does not work, say precisely why and what would,
  then ask again. Do not accept an image you cannot score.
- **Real drawings from the web** — public plan-set sheets, for tier 4 realism. Ground
  truth is then approximate; say so in `GROUND_TRUTH.json`.

Give the raster to a pixel archetype and the PDF to a text-layer archetype. Handing
over both collapses #11 and #12 into one problem.

## Step 3 — Scaffold

```bash
cd ~/cv-problems
python3 bin/cvtest.py new --slug <short-slug> --title "<title>" --minutes <N>
```

It prints the attempt path, the neutral workspace path and the run id, and writes the
workspace `CLAUDE.md` carrying the environment rules, the worklog rule and the
integrity rules. Do not edit those out.

Copy the data into the workspace's `input/`.

## Step 4 — Write the brief and the ground truth

**`attempts/<date>-<slug>/PROBLEM.md`.** The candidate-facing part must sit under a
heading that starts with `## The brief` — that is what the pane extracts, and a
missing heading dumps the whole file including your examiner notes into it. Put the
brief itself in a block quote; anything below the next `##` heading is yours.

Write it how an interviewer actually talks. Terse. What the data is, what they want,
what the deliverable is and where it goes, the time budget. **Keep it short enough to
fit a third of a terminal** — it is being displayed in a pane, and a brief that
scrolls off the top is a brief nobody rereads.

Leave **one or two genuine forks** unresolved — what counts as one object, is the
legend included, pixels or metres, what to do with the ambiguous case. Those forks
are the thing being tested. Never leave the *deliverable* ambiguous; real
interviewers state the artifact and its path.

Do not name the technique. "Count the receptacles" — not "use template matching to
count the receptacles."

**`attempts/<date>-<slug>/GROUND_TRUTH.json`** — the expected numbers, the acceptable
resolutions of each fork and why, and the traps you planted. For synthetic data, copy
the generator's JSON in. For real data, record your own best answer and mark it
approximate. This file is what makes the evaluation about correctness rather than
vibes.

Both files live in the attempt directory, **never** in the workspace.

## Step 5 — Spawn

```bash
python3 bin/cvtest.py spawn --attempt attempts/<date>-<slug>
```

It refuses if the brief is missing or `input/` is empty, so a half-built run cannot
start a clock, and it refuses rather than hanging if folder trust is not propagable.
On success it prints the window, both pane ids and the trust result.

Confirm the session actually booted before handing over — `tmux capture-pane -p -t
<pane>` should show a Claude prompt and, shortly, an artifact URL. A session still
sitting on a dialog is not a running drill.

## Step 6 — Hand over

Print, in this order and nothing else:

1. The **full brief**, verbatim, in a fenced block.
2. The tmux window name and how to get there (`Ctrl-b` then the window number, or
   `tmux select-window -t <window-id>`), and that the brief is pinned in the top pane.
3. The worklog artifact URL, if the session has printed one yet — otherwise say it
   appears in the session within a few seconds.
4. The clock: the budget, and that it starts at their first instruction.
5. One line: *"When you're done — or out of time — run `/finish-cv-test` in that
   window."*

Then stop. Do not offer hints, do not restate the approach, do not answer "how would
you do this" while the clock is running. If the user asks for help mid-run, say the
clock is running and offer to debrief at `/finish-cv-test` — unless they explicitly
abandon the attempt, which is their call.

## Step 7 — Commit

```bash
cd ~/cv-problems && git add -A && git commit -q -m "attempt: <slug> — <title>" && git push -q
```

## Notes

- Not inside tmux: `spawn` refuses and prints the manual `claude -n` command. Pass it
  on rather than working around it.
- The session runs `--permission-mode bypassPermissions` so the clock is not spent on
  prompts.
- A second attempt at the same archetype is fine and often useful — `new` refuses a
  duplicate slug on the same day, so vary the slug.
- To stop a run early: `tmux kill-window -t <window-id>` and delete the attempt
  directory if nothing was learned from it.
