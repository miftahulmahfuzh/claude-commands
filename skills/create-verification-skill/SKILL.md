---
name: create-verification-skill
description: Generate a repo-local verify-<app> skill that launches a throwaway instance of the app, drives it the way a user does, and saves evidence, plus a feature map of what proves each feature. Use for /create-verification-skill, "make a verify skill for this repo", or when a repo has no scripted way for an agent to prove its own work.
disable-model-invocation: true
---

# Create a verification skill

Adapted from pstack's `create-verification-skill` (`cursor/plugins/pstack`), plus eleven runs of
this skill. This file is the short form. The detail, and the case behind every rule, is in
`references/`; read a reference only when the repo has that shape:

| Reference | Read when the repo has |
|---|---|
| `references/harnesses.md` | an e2e suite, smoke/capture/seed scripts, a dev server with a proxy |
| `references/browser.md` | a web UI |
| `references/auth-and-seed.md` | sign-in, a database to seed, journeys that wait on async work |
| `references/stand-ins.md` | any third-party API, a serverless DB driver, an object store, an LLM, a sink that messages people |
| `references/no-server-shapes.md` | a static site, a config/dotfiles repo, a TUI, a run that needs no network |
| `references/process-and-env.md` | always while writing `verify.sh` in a runtime no sibling used |
| `references/proving-and-report.md` | a proving step that surprises you; before the report |

## 0. Copy a sibling first

The siblings are working code. Pick the closest, read its `SKILL.md` and `scripts/`, and copy
its `verify.sh`, stand-in, preload and browser driver, renaming the env prefix; they already
embody most rules below. When the vendor SDK versions match (compare `node_modules`), the
stand-in copies as is: the ninth run answered its first `up` 7 minutes in, and every bug came
from journeys, not plumbing.

| Sibling (`~/<repo>/.claude/skills/…`) | Shape |
|---|---|
| `mcp-notes/…/verify-notesd` | small: Node daemon, one Postgres, Playwright UI |
| `agentic_golang/…/verify-agentic` | compiled Go server, Docker Arango + Redis, real LLM, wrapped e2e harness |
| `seer/…/verify-seer` | Next.js on a Neon shim + a Python CLI with a write denylist; per-run snapshot |
| `run-insights/…/verify-run-insights` | Neon + Blob stand-in, LLM budget at egress, seed through the app's screen |
| `daily-words/…/verify-daily-words` | database sessions, owner's pinned port, wrapped Playwright, web push as fake receiver |
| `expense-tracking/…/verify-expense-tracking` | compact Neon + Blob, HTTPS + h2 stand-in, tools outside the repo |
| `jmtarot/…/verify-jmtarot` | "no Playwright" (own CDP driver wrapped), dev-only session route, `--offline` found the worst bug |
| `agentic/…/verify-agentic-docs` | Hugo static site: snapshot + `sync`, production `build` drive, link check |
| `nvim-config/…/verify-nvim-config` | dotfiles TUI via tmux, network namespace, read-only dep cache, `--live` |
| `hospital-inspection-forms/…/verify-hospital-inspection-forms` | Neon + Blob, no paid call, `fault db\|blob`, `.xlsx` read back |
| `fast-order/…/verify-fast-order` | stateless Go + Vite LLM app: TLS-intercepting egress proxy counts calls, `fault drop\|hang`, breaker |
| `lunch-delivery/…/verify-lunch-delivery` | Go + Gin with a hardcoded taken port: netns whose only exits are Unix sockets, Postgres per run, fake SMTP (STARTTLS), counting proxy |

**Why this exists.** `phase-planner` writes a **Proof** section naming `.claude/skills/verify-*`,
`/implement` and `/do` run it, the `verifier` agent re-runs it cold. Without it all of that is
"the tests pass". Write for a reader who has never seen the app.

**Unattended.** Answer from the repo; decide what the code cannot answer, record it in Gotchas,
go on. Never block, not even on the paid core: an LLM app runs its LLM for real, under a budget.
A mid-run message from the owner gets folded in and recorded.

**Skip what does not apply** (a static site has no auth or budget), with one Gotchas line each.
Process, fence, evidence and proving rules apply to every shape.

## 1. Interview the repo

From code, README, CLAUDE.md, scripts, compose and CI files. Trust the config over the docs.

- **Surface:** what a user touches (HTTP, web UI, CLI/TUI, MCP, bot, worker). For a site the
  production build is a surface too.
- **Existing harnesses:** the unit suite counts: read what its tests dial (the owner's
  `localhost:5432`, a real SMTP host) and run it inside the run's fence. Wrap them, pointed at the run (wrapper config in the snapshot, specs
  copied with hardcoded owner URLs rewritten). Read every default they fall back to, every branch
  of the shell script around them (installs into the checkout, `sudo`, `docker compose down` of
  the owner's stack), and what a passing spec actually asserts. → `harnesses.md`
- **The real client's sequence:** the exact requests a user action makes (encoding, polling,
  streams, auth headers). Guessing produces 400s that look like bugs.
- **Where it really runs:** a deployed clone or installed state that differs from the checkout
  gets an `up --live` on a copy. → `no-server-shapes.md`
- **Run:** start command, ports, env, config files, seed, auth. A dev config may point at
  production (a Vite proxy to Render): that command is harmful.
- **The owner's ports:** documented ports, compose-published ports, framework defaults (3000,
  5173, 4173) and the app's own fallback `PORT` are the owner's. The free-port picker refuses
  them, `up` never stops or reuses their holder, `doctor` only reports it. A hardcoded port goes
  in a network namespace, not an app edit (with exits for the DB and proxy → `process-and-env.md`). Say the decision in Gotchas and the CLAUDE.md line.
- **Auth:** mint sessions with the app's own encoder or dev-only route and a per-run secret;
  never add a bypass. One seeded user per gate. → `auth-and-seed.md`
- **Dependencies:** each store and API, isolated per run (shared verify container with a
  database per run; a container per run for Redis-like stores; never the owner's containers).
  Caches per run. The client library decides what can answer it (a serverless driver speaks
  HTTP, not TCP). → `stand-ins.md`
- **Classify every external call by harm, not price:**
  - *Harmful* (messages people, writes production or shared systems, money, orders, production
    CI, deploys, the owner's accounts): pinned off, no flag. Turn the sink into a fake receiver
    when the protocol allows, so its success path is provable.
  - *Harmful to integrity* (tracked files, shared local stores, git in another checkout, sealed
    datasets): refuse by name in the drive commands.
  - *Paid and the product* (the LLM): real by default under a per-run budget counted where
    calls leave; `--offline` is fault injection and gets one journey (it found the worst bug in
    several runs).
  - *Nothing paid:* the stand-in still gets a fault switch that drops connections.
  - *Public pinned assets* (CDN scripts, fonts): an allowlisted shared cache; `--offline` refuses.
  - *Peripheral paid:* off unless a flag opts in.
  - Follow each success path to its last write; through a pinned-off sink it cannot be produced
    locally, so prove the refusal and say so.
- **Observe:** bodies, rows, files, logs, exit codes, screenshots.
- **Isolate:** free ports, per-run data, and per-directory state (a dev server that locks or
  rewrites its directory runs from a per-run snapshot: rsync + `cp -al` dependencies).

If the checkout does not build or start, fix that first or stop and report it.

## 2. One script, many subcommands

`.claude/skills/verify-<app>/scripts/verify.sh`. Agents call subcommands, never launch by hand.

| Subcommand | Does |
|---|---|
| `up [flags]` | fresh instance from the CURRENT checkout; prints `RUN=`, `URL=`, `EVIDENCE=`, mode; returns when usable |
| `doctor RUN` | read-only: alive, health, port owned by this run's process group, deps, commit served, HEAD/tree drift, egress probes both ways |
| drive commands | one per surface; each saves request + response as a numbered evidence file and prints it |
| `note RUN "text"` | appends to `evidence/LOG.md` |
| `down RUN` / `--all` | kills exactly what `up` started, keeps evidence (logs copied in first) |
| `ls` | runs, state, mode, evidence count |

Optional: `sync RUN` for a snapshot edit loop, `build RUN` when what ships differs from dev,
`fault RUN …`, `calls RUN` (what the app sent a paid vendor), `budget RUN`.

Rules (each was a bug once; details in `process-and-env.md`):

- `setsid` daemons with stdin `/dev/null` and output to a log; record the process group and kill
  the group, waiting until it is empty; never `pkill` by name.
- Every process from `env -i` + the run's values, in an empty working directory (cwd dotenv
  loaders fill unset vars); pin every variable that has a default; never let ambient credentials
  (`VERCEL*`, OIDC tokens) through; omit optional vars rather than blanking them.
- Compiled apps: build per run, stamp the commit (`-buildvcs`, `go version -m`), prove the
  listener runs that binary (`/proc/PID/exe`), build offline with the verify state's caches (its
  own module cache when the owner's lacks the repo's modules, filled from a copy of `go.sum`).
- Egress control per runtime (dead or counting proxy for Go/Python/curl, a preload for Node),
  proven from `doctor`, stated as best effort. → `stand-ins.md`
- Readiness: poll the usable state; stop on repeated identical 5xx and print the log tail.
- Binary responses to a file with size + sha256; a product binary gets a drive that reads it.
- State drives (`sql`, …) are read-only, with a `--value` mode and an `until` poller.
- Bash under `set -euo pipefail`: no `| head` in the script, `|| true` on greps in `$(…)`, a
  separator in `curl -w`, `</dev/null` on `docker exec -i` in loops, shebang scripts because
  the caller may be zsh, quoted URLs with `?`, `bash -n` clean, usage with no arguments.
- Evidence under `~/.local/state/<app>-verify/<run>/evidence/`, numbered by drive order; steps
  files take arguments.

## 3. Write the SKILL.md

Frontmatter `name: verify-<app>` and a `description` (what it proves, when, what it never
touches). Sections with real commands, no placeholders: **Launch**, **Doctor** (when, and what
each warning means), **Drive** (a table plus one complete example per surface; stable handles),
**Targeted, not exhaustive** (cost per journey, default budget), **Evidence** (where, and the
standards: real user path, action AND resulting state, failure first for a bug fix, structure
over text for nondeterministic output with one re-run, `inconclusive` with a reason, never
weaken a journey), **Cleanup**, **Feature map**, **Gotchas** (never driven, flag-gated, best
effort, not producible locally, flaky timings, every decision you made).

## 4. Seed the feature map

`features/README.md` (feature, file, surfaces, paid calls per journey) plus one file per
user-facing feature, the 5 to 8 most important first. Each file has exactly these H2s:
`## Sub-features`, `## How to get to it (user POV)`, `## Driving it with verify.sh` (commands and
the end state seen), `## Gotchas`.

**Drive first, write second:** paste the end states you saw; predicted ones are wrong often.
Wait on the app's own signal and key read-backs on the row your action created; record base
failures as counts; pick inputs the seed lacks; note one-shot seed state and clock windows.
→ `auth-and-seed.md`

## 5. Prove every recipe before handing over

0. Hash every file the harness must never touch (`.env*`, committed databases, owner profiles),
   list `~/.cache`, and note the owner's containers' start times, **before the first `up`**.
1. `up` + `doctor`, once per mode flag; a flag not exercised is `inconclusive`.
2. Feed every write validator and transform-on-write hook what it must reject (look-alike hosts,
   impossible dates, whitespace-only fields, oversized bodies, unknown keys, forged cookies, an
   `Origin`/`Host` an attacker picks); send would-be-billed inputs under `fault drop`. Change what
   a cache's key ignores (edit a row, reorder) and press again. After a 200, read every side
   effect back and grep the log for swallowed warnings.
3. Every journey in every feature file once. Fix wrong recipes; record a wrong app as a product
   bug. Rule out dev-mode artifacts (StrictMode double effects) before blaming the app.
4. Every surface against every seed mode.
5. Isolation: two runs at once, a write (or an in-process state change such as a tripped breaker)
   in one, absent from the other.
6. `down`; evidence remains, no process, port or per-run DB left; re-check the step-0 hashes,
   `~/.cache`, the containers and `git status`.
7. Re-prove anything you changed after the full pass.

`down` after every failed attempt. Expect bugs in your own script. → `proving-and-report.md`

## 6. Wire it into the repo

- Track `.claude/skills/verify-<app>/` (un-ignore it; keep `settings.local.json` ignored). Name
  skill and state dir so no sibling collides (`ls ~/.local/state/*-verify`).
- One line in `CLAUDE.md` pointing at the skill and feature map (create CLAUDE.md if absent).
- Drive dependencies: prefer what the repo and machine already have; otherwise pin them in the
  repo manifest, or in `$VERIFY_HOME/.tools` when the commit is limited to your paths.
- Run the repo's own gates over the new files; give dead-code scanners a commented ignore.
- `git ls-files -s` must show `100755` for scripts; with `core.fileMode=false`, run
  `git update-index --chmod=+x` right after `git add`.
- Commit only your paths plus the CLAUDE.md line (`git add -- <paths>`), with the repo's
  conventions; CHANGELOG under Unreleased unless the repo reserves it or the user limited the
  commit. Push to the default branch unless CLAUDE.md forbids it, and say whether that deploys.
- When the index holds a peer's staged work, commit through an isolated index:

  ```sh
  export GIT_INDEX_FILE=$SCRATCH/verify.index && git read-tree HEAD
  git add -- .claude/skills/verify-<app> CLAUDE.md && git commit -m '...'
  unset GIT_INDEX_FILE && git add -- .claude/skills/verify-<app> CLAUDE.md
  git status --porcelain     # the peer's lines must read exactly as before
  ```

## Report

- the skill path and subcommands;
- each feature-map entry: proven, failed or inconclusive, with its evidence path;
- product bugs with a one-line root cause and how many runs saw each (an LLM-dependent finding
  from one run is a hypothesis; reproduce an SDK's behaviour in ten lines before blaming it);
- harness lessons about a sibling only after reproducing them there;
- base failures, kept apart;
- what is never driven; the commit sha and whether the push deploys or runs CI.

Asked to fix a bug the pass found: failing test first, then the same journey on base and on the
fix (`git stash`), on a fresh run, with the input that forces the branch.
