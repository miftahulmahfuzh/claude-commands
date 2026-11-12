# Known and intentional

Duplications and asymmetries an audit decided to keep. Reviewers get this list and do not
re-report these items. Re-open one only if something about it changed. One line each: what,
where, why, and which audit decided it.

- **The Autonomy and Deciding Without Asking sections are in both `commands/implement.md` and
  `commands/do.md`.** Each executor session needs the precedence ladder in its own prompt; a
  pointer to another command file is not loaded. The copies must stay identical apart from
  wording specific to each executor. (2026-11-12, Z-G86)
- **The ladder's rung 5 is "the user's raw input" in `/analyze` and `plan-reconciler`, but "task
  text / note" in the executors and the orchestrator.** Each actor has a different source;
  `analyze.md` states the difference. (2026-11-12, Z-G86)
- **The trace-rule paragraph is in both `commands/analyze.md` Step 8 and
  `agents/plan-reconciler.md`.** CLAUDE.md requires the two to stay in step; the reconciler runs
  without `/analyze`'s text. (2026-11-12, Z-G86)
- **The Open Questions definition repeats inside `commands/analyze.md`** at each step that writes
  or checks it. The copies agree; each step must be readable on its own. (2026-11-12, Z-G86)
- **The EARS pattern table appears in `commands/analyze.md`, `docs/ears/README.md` and
  `docs/architecture-notes.md`.** One is the spec and two are docs. (2026-11-12, Z-G86)
- **`/do` has no "three checks before the report" (catch up, re-run touched tests, reproduce a
  peer's failure).** Swarm phases always run `/implement` (`swarm.py spawn` writes that prompt),
  so `/do` never runs concurrently with peers in one worktree. (2026-11-12, Z-G86)
- **The small-set rule and the quota-economy rules are in both `agents/completion-handler.md`
  step 5a (a set landed without a coordinator) and `commands/analyze-orchestrator.md` step 6b
  (the coordinator).** Two different actors apply them. Their conditions must stay identical.
  (2026-11-12, Z-G86)
- **The quota-economy Proof rule ("run once, on the cheapest journeys") is in `/implement`,
  `/do` and the mod's `quotaLine`.** The mod line reaches only a session whose prompt went
  through `prompt.submit`; the executors need it in their own text. Wording must match the mod.
  (2026-11-12, Z-G86)
