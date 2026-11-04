# Proving pass and report: the cases behind the rules

Read when a proving step surprises you, or before writing the final report. The rules in SKILL.md are the short form; this file holds the detail and the cases that earned them.

1. `up`, then `doctor` on the run, and once for each mode flag (`--offline`, rebuild flags). A
   flag you deliberately did not exercise (it would reach an external service) is listed as
   `inconclusive` in the report, never silently skipped.
2. **Feed every transform-on-write hook and every write validator input it must reject.** A
   formatter, linter or migration that runs on save is where content gets destroyed:
   verify-nvim-config's worst finding was a Lua file with one syntax error replaced, on disk, by
   the formatter's error message, because the save hook never read the exit status. A happy-path
   drive passed on the same hook. A public write route is the same kind of door: send it the
   inputs the browser cannot produce. Two of the ninth run's findings: a file-URL check that was a
   substring test (`https://evil.example/.public.blob.vercel-storage.com/x.jpg` was stored and
   shown to the admin as a link), and a date check by `Date.parse`, which rolls `2026-02-31` over,
   so Postgres refused it and the user got a 500 blaming the database. Look-alike hosts (the
   trusted host in the path or as a subdomain of another), impossible dates, over-limit counts,
   unknown keys, whitespace-only required fields, an oversized body. When the input would reach a
   paid call, send it under `fault drop`: the stand-in reads the whole request before dropping it,
   so the evidence shows what would have been billed and nothing is (fast-order: a menu of spaces
   passed validation, and a 2.6 MB body went to the vendor whole). Two drops do not trip a
   three-failure breaker; mind the third.
3. **Every journey in every feature file, once.** Fix the recipe when the recipe was wrong
   (wrong arg name, wrong column, wrong route). When the APP is wrong, record it as a product
   bug in the final report and do not paper over it in the map. Before calling a UI failure a
   product bug under a dev server, rule out the dev mode itself: React StrictMode mounts, unmounts
   and remounts every component, and an effect that guards with a `started` ref while its cleanup
   aborts the fetch never re-issues it (verify-jmtarot: a translation stuck on "translating", a chat
   loop that went to `stopped` on the aborted request). Read the effect, say "dev-only" in the
   feature file with the reason, and drive the route the effect calls.
4. **Every surface against every seed mode.** When two halves of the app read the same seed
   (a web UI and a CLI or worker), drive each half on it, not only the half the seed was written
   for. Seed scripts drift from the schema the other half needs: Seer's demo seeder, written for
   the UI, omitted the columns migration 006 added after it, and the engine's `paper_check` crashed
   on it. Only driving the engine on demo data found that.
5. **Isolation, proven rather than assumed.** Run two instances at once, write through the app in
   one, and read the other's state to show the write did not cross. With no write path (a static
   site), make a temporary edit, `sync` it into one run, read both, then `git checkout --` it and
   check `git status`. Pick a probe you have seen rendered: a section's `_index.md` body never
   reached the page, so the first probe read 0 in both runs and proved nothing; its title did.
   Prove the failure path the same way (a broken template must fail `up` and `sync` with the
   generator's error). A stateless app still has in-process state: trip one run's circuit breaker
   and show the other answering 200 at the same moment. Hash every file the harness
   must never touch (a committed database, a shared store's manifest, `.env.local`, an owner's
   browser profile) before the first `up` and after the last `down`, list the user's `~/.cache`
   before and after (that diff caught Chrome writing `dconf` outside the run), and check
   `git status` on the paths it could have dirtied. Take these hashes before the script's first
   `up`, not after it: the tenth run took them after, and could only argue the first run clean.
6. `down`, then confirm the evidence still exists and no process or per-run DB is left behind.
7. **Re-prove what you changed after the full pass.** Fixes made while writing the feature files
   (a new drive option, a corrected recipe) get one short run of their own before the commit.

Run `down` after every failed attempt too. Expect this pass to find bugs in your own script:
it is the point of the pass.

## Report

End with:
- the skill path and its subcommands;
- the feature-map entries, and which journeys were proven, failed, or inconclusive, each with
  its evidence path;
- product bugs found (app wrong, not recipe wrong), each with a one-line root cause when you
  found it, so the user can say "fix it" without a second investigation. State how many runs each
  was seen in: an LLM-dependent finding drawn from one run is a hypothesis (verify-jmtarot's
  "translation never stored" became "stored after a repair, sometimes" on the second run). Before
  blaming a vendor SDK, reproduce its behaviour in a ten-line script: that one showed the SDK's
  iterator did throw, which moved the root cause into the app's own gate;
- a harness lesson that implicates a sibling verify skill only after reproducing it there. The
  fifth run reported verify-run-insights' uploads as "probably broken the same way"; reproduced,
  they passed, because the failure needed a condition (`onUploadProgress`) that app never met;
- failures that were already on the base (a red test unrelated to the skill), kept apart from
  the bugs the pass found;
- what the skill deliberately never drives;
- the commit sha.

When the user asks for a product bug to be fixed, the new skill proves the fix: a failing test
first, then the journey that found it, on a fresh run (verify-run-insights' first use was its own
elevation-record finding, `0.12 km` -> `118 m`). Drive the same input on the base and on the fix
(`git stash`, run, `stash pop`) and keep both end states. For a race, first find the input that
forces the branch: verify-jmtarot's first re-drive took the other side of the race (a clean 500)
and proved nothing; a reading with no question settles the verdict at once and hits the fixed path
every time.

## 6. Wire it into the repo

- `.claude/skills/verify-<app>/` must be tracked by git. If `.gitignore` hides `.claude/`,
  un-ignore that path; keep `.claude/settings.local.json` ignored.
- Add one line to the repo's `CLAUDE.md` (Conventions, or wherever commands live) pointing at
  the skill and the feature map.
- Any dev dependency the drives need (Playwright, an HTTP client) goes into the repo's own
  manifest at a pinned version. Prefer browsers and tools already installed on this machine. When
  the commit is limited to the paths you create (the manifest is not one), or the stand-in needs a
  driver the app does not ship (a Neon-only app has no `pg` or `ws`), install them pinned into a
  tool directory under the verify state (`$VERIFY_HOME/.tools`, installed once by `up`) and load
  them with `createRequire` from there; the app's processes never see it.
- The repo's own gates cover the new files: its formatter, linter and source guards scan
  `.claude/` too, and a dead-code scanner (knip) reports every helper `verify.sh` starts by path as
  an unused file. Run them, and give the scanner a commented ignore for the skill directory.
- Confirm the scripts are committed executable **before the first commit**: `git ls-files -s`
  shows `100755`. A repo with `core.fileMode=false` records `100644` whatever the disk says; run
  `git update-index --chmod=+x <file>` right after the `git add` (checking only after the commit
  cost verify-agentic-docs a second commit).
- Name the skill and its state directory so neither collides with a sibling: `ls
  ~/.local/state/*-verify` first. `~/agentic` could not use `agentic-verify`, which
  `~/agentic_golang`'s verify-agentic owns, so it became `verify-agentic-docs` /
  `agentic-docs-verify`.
- Commit with the repo's conventions (its CHANGELOG under Unreleased if it keeps one, unless its
  CLAUDE.md reserves the changelog for a release command, or its entries record only product
  features) and push to the default branch, unless the repo's CLAUDE.md says otherwise. When the
  user limits the commit to the paths you create, the one-line CLAUDE.md edit this step requires is
  the only exception: commit it explicitly, skip the changelog, and say both in the report. If the
  default branch auto-deploys (a `vercel.json` with `deploymentEnabled.main`), note that the push
  deploys unchanged app code.
- **The index may hold someone else's staged work.** In a shared checkout (an active swarm or
  orchestration), `git add <your paths> && git commit` also commits whatever a peer has already
  staged. Commit through an isolated index instead, then sync only your paths into the real one:

  ```sh
  export GIT_INDEX_FILE=$SCRATCH/verify.index && git read-tree HEAD
  git add -- .claude/skills/verify-<app> CLAUDE.md && git commit -m '...'
  unset GIT_INDEX_FILE && git add -- .claude/skills/verify-<app> CLAUDE.md
  git status --porcelain     # the peer's lines must read exactly as before
  ```

  Without that last `git add` the real index still shows your new files as staged deletions.
