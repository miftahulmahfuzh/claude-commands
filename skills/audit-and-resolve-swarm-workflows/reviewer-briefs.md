# Reviewer briefs

Three general-purpose agents, dispatched in one message. Paste each brief as written, fill in the
two placeholders, and update the file lists when the inventory (SKILL.md step 1) found new files.

`{KNOWN}` — the entries of `known-intentional.md`, verbatim.
`{SINCE}` — the commit range since the last audit, and the files it touched.

## Shared rules (append to every brief)

```
Read-only: do not edit any file.

The owner's rules: every rule exists once, in the file that owns it (see "One owner per rule" in
CLAUDE.md), and an agent must never meet two rules it has to choose between. Prose that disagrees
with what the code does counts as a conflict.

Report four kinds of finding:
1. CONFLICT — two instructions (or prose vs code) that disagree: different thresholds, a different
   order of steps, a precedence ladder in a different order, a spec format the parser rejects. Quote
   both, with file:line.
2. DRIFTED DUPLICATE — the same rule in 2+ places, worded so the meaning differs or a clause is
   missing. Quote the copies, file:line, and say what differs.
3. STALE — a reference to something that no longer exists or was superseded (a flag, a step, a path,
   a mechanism described as current). Grep the repo before claiming something is gone.
4. IDENTICAL BLOAT — passages over 10 lines copied near-verbatim. Bloat candidates, not bugs.

Do NOT report these; they are deliberate decisions:
{KNOWN}

Changed since the last audit (look hardest here): {SINCE}

Only report what you verified by reading the actual lines. Every finding needs file:line and a
short quote of each side. No style preferences, no "could be clearer". At most one line per
finding on which copy should win and why. Rank: conflicts, drifted duplicates, stale, bloat. If a
category is empty, say so — a short honest report beats a padded one. Under 1000 words.
```

## 1. Execution

```
You are auditing a repo of Claude Code prompt files (markdown specs agents follow) at
/home/miftah/claude-commands.

Scope — the EXECUTION side: commands/implement.md, commands/do.md, agents/completion-handler.md,
agents/pusher.md, agents/task-locator.md, agents/context-loader.md, agents/plan-generator.md,
agents/readme-updater.md, agents/verifier.md. Cross-check against CLAUDE.md and
docs/architecture-notes.md, which summarize these rules.

/do and /implement intentionally share some sections. A shared section is only a finding if the
copies have DRIFTED, or if it is a rule some agent both already call should own (commit safety
belongs to pusher; landing and its verifier gate to completion-handler step 5a). Read both files
fully.

Check especially: who lands a plan set and whether it can happen twice; whether every path to
landing runs the same verification gate; whether the completion_report each executor sends has
every field completion-handler reads; whether pusher's procedure obeys its own rules.
```

## 2. Planning

```
You are auditing a repo of Claude Code prompt files (markdown specs agents follow) at
/home/miftah/claude-commands. The workflow adopted outside methods: Cursor's pstack
(skills/engineering-principles/SKILL.md, skills/create-verification-skill/) and Kiro's EARS
acceptance criteria (docs/ears/README.md, skills/swarm/ears_trace.py). Pay special attention to
whether an adoption left rules that overlap or contradict what the workflow already had.

Scope — the PLANNING side: commands/analyze.md, agents/phase-planner.md, agents/plan-reconciler.md,
agents/plan-generator.md, skills/engineering-principles/SKILL.md, docs/ears/README.md,
skills/swarm/ears_trace.py (its docstring, argparse and the formats it parses),
skills/create-task/SKILL.md (only where it reads the plan index's Requirements table). Cross-check
against CLAUDE.md and docs/architecture-notes.md.

Known coupling that must agree: /analyze Step 8 with plan-reconciler rules 6-7; the criteria table
and journey format across analyze.md, phase-planner.md, plan-reconciler.md, verifier.md and
ears_trace.py (separators, ids, exit codes, who fills the Journeys column, what may go in Open
Questions); the precedence ladder in every file that states it.
```

## 3. Swarm and swarm-deck

```
You are auditing a repo of Claude Code prompt files and helper code at
/home/miftah/claude-commands.

Scope — SWARM ORCHESTRATION and the swarm-deck mod: commands/analyze-orchestrator.md,
skills/swarm/SKILL.md, skills/swarm/swarm.py (docstring, argparse, and the functions behind every
behavior the prose describes: verify, reap, watch, land, spawn/launch, resolve_model, doctor,
find, runnable), agents/integrator.md, mods/swarm-deck/hooks/register.js (guards, quota economy,
verifier refusal, tool.check auto-answer, prompt.submit context blocks, coordinator wake-ups),
mods/swarm-deck/README.md, docs/swarm-deck-mod-design.md. Cross-check against CLAUDE.md
("Swarm orchestration") and docs/architecture-notes.md.

Check especially: rules stated in both analyze-orchestrator.md and skills/swarm/SKILL.md (the
orchestrator owns coordinator rules; the skill should point to it); text the mod injects into
sessions (quotaLine, deny messages, wake-ups) against what the command files tell the same agent;
prose claims about swarm.py (flags, exit codes, what verify/reap/land/runnable do in shared and
isolated mode) against the code; the mod README and design doc against register.js.
```
