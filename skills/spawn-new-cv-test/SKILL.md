---
name: spawn-new-cv-test
description: Use when the user wants a computer-vision live-coding practice problem — "/spawn-new-cv-test", "give me a CV problem", "let's practice for the Boon interview", "spawn a new CV test", "another practice round", "test me on floor plans" — or when they want to rehearse driving Claude Code under an interview clock. Scaffolds a sealed attempt, writes the brief, and opens it in a fresh Claude Code session in its own tmux window.
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

## Step 0 — Make sure the repo is there

```bash
test -d ~/cv-problems || git clone git@github.com:miftahulmahfuzh/cv-problems.git ~/cv-problems
python3 ~/cv-problems/bin/cvtest.py status
```

`status` tells you which archetypes have been attempted. If `~/cv-problems/.venv` is
missing, say so and stop — a practice run without the environment is not a practice
run.

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
  ground truth JSON, includes the `TYP. OF 4` banked-run trap). Best for anything
  needing a verifiable count, measurement or scale. Write a new generator beside it
  if the archetype needs different data; seed it and emit ground truth.
- **Existing fixtures** — `fixtures/mock/` (candlestick chart, document table,
  shapes, landscape photo). Best for tiers 1–3.
- **User-supplied** — for realism and messy input. Ask for it in one line: say what
  kind of image would suit and where to drop it. Then **actually open it with the
  Read tool** and judge it: resolution, is it vector or raster, is the thing to be
  found actually visible, does it have a verifiable answer. If it does not work,
  say precisely why and what would work instead, then ask again. Do not accept an
  image you cannot score.
- **Real drawings from the web** — public plan-set sheets, for tier 4 realism.
  Accept that ground truth is then approximate and say so in the brief.

Put the data in `workspace/input/` **after** Step 3 creates it.

## Step 3 — Scaffold

```bash
cd ~/cv-problems
python3 bin/cvtest.py new --slug <short-slug> --title "<title>" --minutes <N>
```

It prints the attempt path, the workspace, and where the brief goes. It also writes
the workspace `CLAUDE.md` carrying the environment rules and the integrity rules.
Do not edit those rules out.

Copy the data into `workspace/input/`.

## Step 4 — Write the brief and the ground truth

**`attempts/<slug>/PROBLEM.md`** — how an interviewer would actually say it. Terse.
Four short sections: what the data is, what you want, what the deliverable is and
where it goes, and the time budget. Leave **one or two genuine forks** unresolved
(what counts as one object; is the legend included; pixels or metres; what to do
with the ambiguous case) — those forks are the thing being tested. Never leave the
*deliverable* ambiguous; real interviewers state the artifact.

Do not name the technique. "Count the receptacles" — not "use template matching to
count the receptacles."

**`attempts/<slug>/GROUND_TRUTH.json`** — the expected numbers, the acceptable
resolutions of each fork and why, and the traps you planted. For synthetic data,
copy the generator's JSON in. For real data, record your own best answer and mark it
approximate. This file is what makes the evaluation about correctness rather than
vibes.

Both files live in the attempt directory, **never** in `workspace/`.

## Step 5 — Spawn

```bash
python3 bin/cvtest.py spawn --attempt attempts/<date>-<slug>
```

It refuses if the brief is missing or `input/` is empty, so a half-built attempt
cannot start a clock. On success it records the start time and prints the window and
pane ids. The session boots **idle with no prompt** — it must wait for the candidate.

## Step 6 — Hand over

Print, in this order and nothing else:

1. The **full brief**, verbatim, in a fenced block. The candidate reads it here; the
   file is sealed from the session, not from them.
2. The tmux window name and how to get there (`Ctrl-b` then the window number, or
   `tmux select-window -t <window-id>`).
3. The clock: budget, and that it started at spawn.
4. One line: *"When you're done — or out of time — run `/finish-cv-test` in that
   window."*

Then stop. Do not offer hints, do not restate the approach, do not answer "how would
you do this" while the clock is running. If the user asks for help mid-run, say the
clock is running and offer to debrief at `/finish-cv-test` — unless they explicitly
abandon the attempt, which is their call to make.

## Step 7 — Commit

Commit the scaffold so the attempt is tracked even if the run is abandoned:

```bash
cd ~/cv-problems && git add -A && git commit -q -m "attempt: <slug> — <title>" && git push -q
```

## Notes

- Not inside tmux: `cvtest.py spawn` refuses and prints the manual `claude -n`
  command. Pass it on rather than trying to work around it.
- The spawned session runs `--permission-mode bypassPermissions` so the clock is not
  spent on prompts.
- A second attempt at the same archetype is fine and often useful — `new` will refuse
  a duplicate slug on the same day, so vary the slug.
