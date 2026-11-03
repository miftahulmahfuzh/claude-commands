---
name: create-verification-skill
description: Generate a repo-local verify-<app> skill that launches a throwaway instance of the app, drives it the way a user does, and saves evidence, plus a feature map of what proves each feature. Use for /create-verification-skill, "make a verify skill for this repo", or when a repo has no scripted way for an agent to prove its own work.
disable-model-invocation: true
---

# Create a verification skill

Adapted from pstack's `create-verification-skill` (`cursor/plugins/pstack`), plus what building
`~/mcp-notes/.claude/skills/verify-notesd`, `~/agentic_golang/.claude/skills/verify-agentic` and
`~/seer/.claude/skills/verify-seer` taught us. Read the one closest to your repo before you start:
verify-notesd is the small example (Node daemon, one Postgres, Playwright UI); verify-agentic is the
heavy one (compiled Go server, Docker-isolated Arango + Redis, real LLM under a budget, egress
control, an existing e2e harness wrapped); verify-seer has two halves sharing one database (a
Next.js app behind a serverless Postgres driver, shimmed to a local Postgres; a Python CLI with a
denylist of commands that write outside the run) and a per-run snapshot for a dev server that
locks its directory; `~/run-insights/.claude/skills/verify-run-insights` is the fullest web app
(Next.js on Neon and Vercel Blob, both answered by one loopback stand-in, the LLM budget enforced
where calls leave the process, demo data committed through the app's own review screen).

**Why this exists.** `phase-planner` writes a **Proof** section that names
`.claude/skills/verify-*`, `/implement` and `/do` run it, and the `verifier` agent re-runs it
with fresh context before anything lands. Without a verify skill, all of that degrades to "the
tests pass". The skill you write is read cold, mid-task, by an agent that has never seen the
app. Write it for that reader.

**Run unattended.** Answer everything from the repo. Ask the user only what the code cannot
tell you, and if nobody is there to answer, decide, write the decision into the skill's
Gotchas, and go on. The one question worth asking up front, when someone is there and the
arguments do not settle it: if the app's core is a paid dependency (an LLM app), should verify
run it for real by default? The default below is yes, under a budget.

## 1. Interview the repo

Answer these from code, README, CLAUDE.md, Makefile/package scripts, compose files, CI config:

- **Surface:** what a user actually touches: HTTP API, web UI, CLI/TUI, MCP, a bot, a queue
  consumer. Pick the primary one; note the rest.
- **Existing harnesses first:** e2e suites, smoke scripts, Postman/http files, compose test
  stacks, seed scripts, fixtures. A harness the repo already maintains beats anything you
  invent. Wrap it, don't replace it. Check how it picks its target (a `BASE_URL`-style env var,
  a flag): wrapping should be "point it at the run". If the target is hardcoded, add the override
  to the harness itself, a few lines, rather than forking it.
- **The real client's sequence:** read the frontend, mobile client or the existing e2e client
  for the exact calls a user's action makes: body encoding per API version (multipart on one
  route, JSON on another), polling, which stream it opens, which headers carry auth. The drive
  command replays that sequence; guessing it produces 400s that look like product bugs.
- **Run:** the exact local start command, ports, env vars, config files, seed data, auth.
- **Auth:** how a signed-in user is recognised, read in the app's session code. Mint a session
  with the app's own encoder and a per-run secret; never add a bypass to the app. Read identity
  rules from the code, not from env alone: a section may admit one hardcoded email on top of the
  allowlist (verify-seer: `/sera` 404'd for the minted user until the run signed in as the address
  `lib/sera/access.ts` names). A 404 or a redirect on first drive is the gate before it is a bug.
- **Dependencies:** each database, cache, queue and third-party API, and how each can be
  isolated per run (its own Docker container or database name, a local emulator, a fake). Never
  the user's own dev containers. A heavy service with cheap namespaces (Postgres, Arango) gets one
  shared verify container and a database per run; one without them (Redis) gets a container per
  run. Any response or answer cache must be per-run, or a repeated journey replays a cached
  answer instead of exercising the code.
- **The client library decides, not the URL.** Read how the app opens each connection.
  Serverless drivers (Neon's `@neondatabase/serverless`, PlanetScale, libsql over HTTP, Supabase
  REST) speak HTTP or WebSocket to a vendor proxy, never TCP, so a local Postgres cannot answer
  them. Build the stand-in into the harness: a small shim that speaks the vendor protocol in front
  of the run's database, plus a preload (`NODE_OPTIONS=--import`) that routes the driver to it. Do
  not edit app code, and do not give up and point at the hosted service. verify-seer's
  `neon-shim.mjs` is about 100 lines and served every query the app and its seeders sent.
- **Object stores and other vendor SDKs need a stand-in too.** Look for the SDK's own API-URL
  override (`@vercel/blob` reads `VERCEL_BLOB_API_URL`, and the browser bundle reads the
  `NEXT_PUBLIC_` twin, inlined at compile time) and answer that API from the same loopback
  process. Then follow every path, not only the server's:
  - The browser's direct upload sends no option headers: the options (random suffix, size cap,
    content types, expiry) ride inside the signed client token, and the type comes from the file
    extension. A stand-in that skips them stored unsuffixed names the app then rejected; one that
    accepts what the vendor would refuse produces false passes. Verify the token and enforce it.
  - Apps validate URLs against the vendor's host (`*.public.blob.vercel-storage.com`). Keep that
    host with a fake store id, serve that one host from the stand-in (preload rewrite on the
    server, `page.route` in the browser), and refuse every other host of the vendor, production's
    included.
  - SDKs prefer ambient credentials over the configured token (`VERCEL_OIDC_TOKEN` beats
    `BLOB_READ_WRITE_TOKEN`). `env -i` drops them; name them in Gotchas anyway.
- **The migration tool may not reach a local database.** drizzle-kit needs a TCP driver the
  serverless app never installed. Apply the journal yourself, in order, one transaction per file,
  and record it where the tool would, so schema-drift checks agree.
- **Classify every external call by harm, not by price:**
  - *Harmful:* messages real people (chat alerts, SMS, email), writes to production or shared
    systems, moves money, places orders or touches a live broker/exchange account, triggers a
    production CI workflow, anything irreversible. Pinned off in `up`, with no flag that turns it
    on.
  - *Harmful to integrity, though nothing leaves the machine:* writes to tracked or frozen repo
    files, to shared local stores other sessions read, git operations aimed at another checkout,
    and spending or peeking at a sealed or budgeted dataset (a held-out test window). For a CLI,
    list every subcommand by what it writes (the run's own state / shared local state / tracked
    files / external) and refuse the last three by name in the drive command. verify-seer refuses
    13 engine commands and 6 lab subcommands this way, including one that git-adds in the main
    checkout even when run from a worktree.
  - *Paid, and the product itself* (the LLM in an LLM app): **real by default**, behind a per-run
    budget counted in vendor calls (see "Count paid calls where they leave"), with journeys
    targeted at the change. A stub-backed verify of an LLM app is a unit
    test with extra steps: it cannot plan, route or answer. Keep a stub only as `--offline`, for
    plumbing, labelled as not proof.
  - *Paid or external, peripheral* (a data gateway, a search API the feature does not need, an
    LLM that only decorates a non-LLM app): off unless a flag opts in. Note any free-tier quota the
    production cron shares, and when that cron runs, so opted-in drives stay clear of it.
  - **Follow each feature's success path to its last write.** When it passes through a pinned-off
    sink, the success state cannot be produced locally, whatever else you enable. Say so in the
    feature's Gotchas, prove the refusal end state plus the unit tests, and do not pay for the
    paid step in front of it (verify-seer: a receipt is saved only after its image is committed to
    a GitHub branch, so a billed vision read would still end in "not kept").
- **Observe:** what proves behavior: response bodies, DB rows, files written, logs, exit codes,
  screenshots.
- **Isolate:** can two instances run at once? Port 0 or a free-port picker, per-run data dirs,
  per-run DB names. Check for per-directory locks too, not only ports: Next 16's `next dev` locks
  `.next/dev` in the project directory, so a second server on another port still exits. Serve such
  a tool from a per-run snapshot of its directory (rsync the sources and hard-link dependencies
  with `cp -al`, which took 0.2 s for 17k files; a symlinked `node_modules` breaks Turbopack). The
  snapshot is a build artifact, so doctor warns when the tree changes. If something cannot be
  isolated, say so in the skill, and make the script refuse to share it.

If the checkout does not build or start as-is, fix that first, or stop and report it exactly.
A skill written against a broken base teaches wrong steps.

## 2. Build the lever: one script, many subcommands

Write `.claude/skills/verify-<app>/scripts/verify.sh` (or the repo's language, if a shell script
would be awkward). Agents call subcommands; they never hand-write launch sequences. Required:

| Subcommand | Does |
|---|---|
| `up [flags]` | Starts a fresh instance from the CURRENT checkout (works in any worktree). Prints `RUN=`, `URL=` (or the equivalent handle) and `EVIDENCE=`. Returns only when the app is usable, not merely when a process answers. |
| `doctor RUN` | Read-only: process alive, health answers, the port belongs to THIS run, dependencies answer, which commit it serves, and a warning if HEAD moved since `up`. |
| drive commands | One per surface (`api`, `cli`, `ui`, `mcp`, `sql`, ...). Each saves its request and its response as a numbered evidence file and prints it. |
| `note RUN "text"` | Appends a line to `evidence/LOG.md`, the human summary of what was proven. |
| `down RUN` / `down --all` | Kills exactly what `up` started, drops per-run state, keeps evidence. |
| `ls` | Runs, state, evidence count. |

Hard-won rules. Each one is a bug we actually hit in `verify-notesd`, `verify-agentic` or
`verify-seer`:

- **Never let the daemon hold the caller's pipe.** Start it with `setsid`, with stdin from
  `/dev/null` and stdout/stderr to a log file, and NOT as part of a `cd && ... &` list (that
  backgrounds a bash wrapper, records the wrong pid, and hangs every `$(verify.sh up)`).
- **Record the process group, kill the group.** `kill -- -$PGID`. Never `pkill` by name: the
  user's real instance has the same name.
- **Doctor checks port ownership** by comparing the listener's process group with the run's,
  not with a pid regex.
- **Binary responses go to a file** with their size and sha256, never to the terminal. Raw bytes
  corrupt the agent's output and every `grep` after them. Use one `curl -w` (a second `-w`
  silently replaces the first).
- **Real env beats config files, and `env -i` beats both.** Start every process the run owns
  from `env -i` plus the run's own values (PATH, HOME, locale, then the pinned settings), so no
  secret exported in the caller's shell leaks in. If the app reads a dotenv file, point it at a
  file the run generates (`SEER_ENV_FILE`-style) instead of letting it find the real one. Pin every
  path and endpoint the app reads (DB URL, data dir, home dirs, ports) to per-run values, and blank
  what the classification above keeps off.
  Check how the app's config loader merges env and files before trusting this, including whether
  `VAR=` (set but empty) counts as set: godotenv's `Load` keeps it, some loaders fall back to the
  file or a default.
- **Blanking a URL is not isolation.** Code falls back to hardcoded hosts when its env var is
  empty (verify-agentic: blanked BE URLs still reached a dev gateway). Add egress control, chosen
  per runtime, because no single mechanism covers them all:
  - Go, Python (urllib, requests), curl: a dead `HTTP(S)_PROXY` (both cases) plus a `NO_PROXY`
    allowlist of loopback and the services the run may reach.
  - Node: `fetch` ignores proxy env (Node 22). Load a preload with `NODE_OPTIONS=--import` that
    wraps `globalThis.fetch` and rejects every host off the allowlist, logging what it blocked.
    Next and similar frameworks wrap fetch after the preload, so the guard stays underneath.
  - Build tools can need the network, and a dead proxy can break them: behind one, Turbopack could
    not fetch `next/font/google` files and every page answered 500. Allowlist that CDN in the
    guard, leave the proxy off that process, and say so.
  Prove both directions from `doctor` without sending anything out: a probe to a harmful host
  must fail against the dead proxy. After the first real journey, list the hosts the logs mention
  and confirm each was allowed. State in Gotchas that this is best effort: `node:http(s)` used
  directly, or a native fetcher, slips past.
- **Compiled apps: build per run, stamp the build.** `up` builds into the run dir from the
  checkout and injects the commit (plus `-dirty`) into whatever the health/version endpoint
  reports. Doctor warns when HEAD **or the working tree** changed since `up`: an edit without a
  commit leaves a stale binary too.
- **Readiness distinguishes "not up yet" from "up and broken".** Poll for the usable state, but
  stop after a few identical 5xx answers and print the log tail. verify-seer's first `up` waited
  4.5 minutes on a page that had been failing the same way since second 5.
- **Copy state files with a read-only open.** Some tools migrate a database on connect even for a
  read (Seer's lab migrates `lab.sqlite` that way). Copy the committed state with the database's
  backup API from a `mode=ro` connection, and hash the protected original before and after the
  proving pass.
- **Count paid calls where they leave, not per drive command.** In a web app most paid calls are
  side effects: a commit fires a narrative and a coach's reaction in `after()`, a page view
  generates prose, a cron fans out. Put the counter in the stand-in and take one call from it in
  the egress guard before each fetch to a paid host; an empty budget fails the fetch the way a
  vendor outage does, so the app shows its own failure state. Record the mode (`real` /
  `offline`) in the run's metadata and print it from `doctor` and `ls`, so nobody cites an
  offline run as proof. Measure each journey's cost on the proving pass and print the table in
  the skill (verify-run-insights: an upload 1, a commit 2-3, one coach turn 3-5).
- **Seeding refuses paid calls; `up` arms the budget last.** Seeding through the app fires the
  same side effects as using it (25 demo commits fired 49 LLM calls). Refuse them unspent while
  seeding, arm the budget once `up` is done, and write the residue (failed turn rows, an error log
  full of refusals) into Gotchas.
- **Fence the browser as well as the server.** Route every request in the Playwright driver:
  loopback passes, the fake vendor host is served from the stand-in, everything else is aborted
  and logged. Grant no permissions (notifications, clipboard) and say in the feature file which
  fallback path that drives (a refused clipboard shows the share link in a field). A wrapped
  harness's own browser is not fenced: verify-run-insights reuses the capture harness's seeder but
  runs its commit pass in the fenced driver, because the harness would have fetched the fake
  store's URLs from the real vendor.
- **When the guard cannot see a sink, make it structurally empty.** Web push posts with
  `node:https`, which a fetch guard never sees. The run's database holds only subscriptions its
  own browser made, the VAPID pair is minted per run, and `doctor` prints the subscription count:
  state that argument in Gotchas instead of claiming a fence that is not there.
- **State drives are read-only.** `sql`, `aql`, `redis` refuse writes (a read-only transaction,
  or a keyword/command allowlist). Writes go through the app's own routes, or they prove nothing.
- **The agent's shell may not be bash.** The Bash tool can run zsh, which does not word-split
  `$VAR` and refuses functions whose names collide with aliases. Scripts are executables with a
  `#!/usr/bin/env bash` shebang; recipes in the feature map never depend on word splitting or
  inline functions.
- **`docker exec -i` inside a `while read` loop eats the loop's input.** Only the first of 38
  migrations ran, silently. Give every `-i` command in a loop `</dev/null` or its own file.
- **No `| head` inside the script.** Under `set -o pipefail`, a reader that closes early
  SIGPIPEs the writer and `set -e` aborts the drive halfway, here before a body file was renamed.
  Cap output in the producer (a line-limit argument), never in a pipe after it. Likewise give
  `curl -w` a separator (`%{http_code}|%{content_type}`): a content type contains a space.
- **HTML evidence is the visible text.** Server-rendered pages carry a framework payload in
  `<script>` tags, and a regex strip keeps that payload and loses the page. Save the HTML, and print
  the visible text with each `aria-label` inline (`[Mark as done]`) through a real HTML parser.
  That is what lets a recipe assert on what the user reads without a browser.
- **The browser driver must not create its own failures.** Playwright's screenshot hides the
  caret by injecting a style, and mid-hydration React reports that as a hydration mismatch the
  app does not have. Pass `caret: 'initial'` and wait for `networkidle`. Dev-only overlays (Next's
  dev-tools badge) sit on top of real controls and swallow clicks, so hide them with an init
  script. Resolve the steps-file path before the script `cd`s anywhere.
- **`down` copies the server log into evidence** before deleting run state: it is the record of
  every decision the run made.
- **Evidence lives outside the repo and outside the worktree**
  (`~/.local/state/<app>-verify/<run>/evidence/`), so it survives `down` and worktree deletion,
  and is never committed by accident.
- **Number evidence files by drive order** (`01-api-...txt`), counting only the primary files.
  Files `up` writes itself (a seed pass) take a `00-` prefix the counter skips.
- **Steps files take arguments** (`ui RUN steps.mjs -- <id> <date>`), so a recipe can act on the
  extraction or run an earlier drive printed instead of hard-coding one.

Make scripts executable, `bash -n` clean, and print usage when called with no arguments.

## 3. Write the SKILL.md

`.claude/skills/verify-<app>/SKILL.md`, with frontmatter (`name: verify-<app>` and a
`description` saying what it proves, when to use it, and what it never touches). Sections, each
with real commands from this repo and no placeholders:

- **Launch:** `up` and its flags (rebuild frontend, seed fixtures, enable a paid dependency).
- **Doctor:** when to run it (before the first drive and after any surprise) and what its
  warnings mean.
- **Drive:** a table of the drive commands, plus one complete example per surface (a UI steps
  file, a CLI invocation, an API call). Prefer stable handles: routes, ARIA labels, test ids,
  prompt strings.
- **Targeted, not exhaustive** (when a drive costs money): pick only the feature-map entries the
  change touches, what each drive costs, the default budget and how to raise it.
- **Evidence:** where it lands, and the proof standards:
  - Use the real user path, never a test-only endpoint.
  - Capture the action AND the resulting state, and read side effects back.
  - For a bug fix, show the failure first.
  - Nondeterministic output (LLMs): assert on structure (route, tools, persisted fields, status)
    and quote text only as support. One miss earns one re-run; two misses are a finding.
  - A step that could not be driven is `inconclusive` with its reason. Never weaken a journey
    to make it pass.
- **Cleanup:** `down`. Evidence survives it.
- **Feature map:** points at `features/README.md`, and says that a user-facing change updates its
  entry in the same change.
- **Gotchas:** what must never be driven (the harmful class: anything that messages real
  people, production or shared systems, money), what stays off unless a flag opts in, where the
  isolation is best effort, what cannot be produced locally, flaky timings.

## 4. Seed the feature map

`features/README.md` (an index table: feature, file, surfaces, and paid calls per entry when
drives cost money) plus one file per user-facing feature. Start with the 5 to 8 most important,
taken from routes, commands, menus and docs.

**Drive first, write second.** Run each journey by hand against a live run, then write the file
with the end states you saw pasted in. Predicted end states are wrong surprisingly often: in
verify-agentic, 6 recipes written from reading code failed on first run (a field the app had
superseded, a cache that pre-generates, a body encoding, a metric name). Every file has exactly
these four H2s:

- `## Sub-features`
- `## How to get to it (user POV)`
- `## Driving it with verify.sh` (real commands, and the end state that proves each one)
- `## Gotchas`

If seed data lacks a precondition a journey needs, the journey reports failure, and the reason
goes in Gotchas.

- **Seed through the app when the app derives state.** Records, badges and insights computed on
  commit cannot be inserted honestly by a seeder. Reuse the repo's own seeder for raw inputs, then
  commit through the real screen in `up` (25 runs took 40 s).
- **Fixed demo data ages out of time windows.** Crons and digests filter on recency ("a run in the
  last 60 days"); dated demo data answers `users: 0` forever after. Find the window in the code,
  and give recipes a user-path way to make data recent (re-date it in the review form).
- **Wait on the app's own signal, never on the page settling.** A typing indicator going away,
  a pending card's copy disappearing. A page-text-stability loop stopped early on a static
  sidebar; a heading predicted from another page ("What happened") never appeared on this one.

## 5. Prove every recipe before handing over

A skill that was never executed is a draft. Run, for real:

1. `up`, then `doctor` on the run, and once for each mode flag (`--offline`, rebuild flags). A
   flag you deliberately did not exercise (it would reach an external service) is listed as
   `inconclusive` in the report, never silently skipped.
2. **Every journey in every feature file, once.** Fix the recipe when the recipe was wrong
   (wrong arg name, wrong column, wrong route). When the APP is wrong, record it as a product
   bug in the final report and do not paper over it in the map.
3. **Every surface against every seed mode.** When two halves of the app read the same seed
   (a web UI and a CLI or worker), drive each half on it, not only the half the seed was written
   for. Seed scripts drift from the schema the other half needs: Seer's demo seeder, written for
   the UI, omitted the columns migration 006 added after it, and the engine's `paper_check` crashed
   on it. Only driving the engine on demo data found that.
4. **Isolation, proven rather than assumed.** Run two instances at once, write through the app in
   one, and read the other's state to show the write did not cross. Hash every file the harness
   must never touch (a committed database, a shared store's manifest, `.env.local`) before the
   first `up` and after the last `down`,
   and check `git status` on the paths it could have dirtied.
5. `down`, then confirm the evidence still exists and no process or per-run DB is left behind.

Run `down` after every failed attempt too. Expect this pass to find bugs in your own script:
it is the point of the pass.

## 6. Wire it into the repo

- `.claude/skills/verify-<app>/` must be tracked by git. If `.gitignore` hides `.claude/`,
  un-ignore that path; keep `.claude/settings.local.json` ignored.
- Add one line to the repo's `CLAUDE.md` (Conventions, or wherever commands live) pointing at
  the skill and the feature map.
- Any dev dependency the drives need (Playwright, an HTTP client) goes into the repo's own
  manifest at a pinned version. Prefer browsers and tools already installed on this machine.
- The repo's own gates cover the new files: its formatter, linter and source guards scan
  `.claude/` too, and a dead-code scanner (knip) reports every helper `verify.sh` starts by path as
  an unused file. Run them, and give the scanner a commented ignore for the skill directory.
- Confirm the scripts are committed executable: `git ls-files -s` shows `100755`. A repo with
  `core.fileMode=false` records `100644` whatever the disk says; fix with
  `git update-index --chmod=+x <file>`.
- Commit with the repo's conventions (its CHANGELOG under Unreleased if it keeps one, unless its
  CLAUDE.md reserves the changelog for a release command) and push to the default branch, unless
  the repo's CLAUDE.md says otherwise.
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

## Report

End with:
- the skill path and its subcommands;
- the feature-map entries, and which journeys were proven, failed, or inconclusive, each with
  its evidence path;
- product bugs found (app wrong, not recipe wrong), each with a one-line root cause when you
  found it, so the user can say "fix it" without a second investigation;
- failures that were already on the base (a red test unrelated to the skill), kept apart from
  the bugs the pass found;
- what the skill deliberately never drives;
- the commit sha.

When the user asks for a product bug to be fixed, the new skill proves the fix: a failing test
first, then the journey that found it, on a fresh run (verify-run-insights' first use was its own
elevation-record finding, `0.12 km` -> `118 m`).
