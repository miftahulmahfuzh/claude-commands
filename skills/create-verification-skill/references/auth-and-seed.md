# Sessions, seed data and journey waits

Read when the app has sign-in, a database to seed, or journeys that wait on async work. The rules in SKILL.md are the short form; this file holds the detail and the cases that earned them.

- **Auth:** how a signed-in user is recognised, read in the app's session code. Mint a session
  with the app's own encoder and a per-run secret; never add a bypass to the app. Read identity
  rules from the code, not from env alone: a section may admit one hardcoded email on top of the
  allowlist (verify-seer: `/sera` 404'd for the minted user until the run signed in as the address
  `lib/sera/access.ts` names). A 404 or a redirect on first drive is the gate before it is a bug.
  With **database sessions** (Auth.js `strategy: 'database'`) there is no encoder: a session is a
  `sessions` row, so insert one per user with a random token and send it as the cookie; replace any
  fixed token the repo's seeder writes. Seed one user per gate the layout enforces (verify-daily-
  words: `demo` onboarded with history, `stranger` onboarded and empty, `newcomer` not onboarded),
  and let every drive take `--as USER` / `--anon`: sharing, claiming and onboarding need them.
  If the app already ships a dev-only mint route (jmtarot's `POST /api/auth/dev-session`, gated on
  a flag and `NODE_ENV !== 'production'`), use it: it runs the real sign-in upsert, it is not a
  bypass you added, and any new `--as NAME` becomes a fresh user on first use. **JWT claims go
  stale:** a session that carries state (`onb`, a locale) keeps the old value after a drive changes
  it through an API, and the gate then redirects as if nothing happened. Give the script a
  `session RUN USER` that re-mints, and say in each recipe when it is needed.

- **Seed through the app when the app derives state.** Records, badges and insights computed on
  commit cannot be inserted honestly by a seeder. Reuse the repo's own seeder for raw inputs, then
  commit through the real screen in `up` (25 runs took 40 s).
- **Build the seed from the app's own definitions, and still wrap the repo's seeder.** A seed that
  imports the app's schema or form definitions (`node --experimental-strip-types` on
  `src/lib/forms.ts`) and posts through the app's own write route follows every later change to
  the questions. Wrap the repo's seeder as a drive anyway, aimed at the run: in the ninth run it
  failed on base (it answered required file questions with plain text, added after it was
  written), which is a finding, and the reason the harness seeds itself. An app that creates its
  own schema on first use (`ensureSchema`) has two-step readiness: the page answers, then the seed
  goes in through the app, then the page shows the seed.
- **Fixed demo data ages out of time windows.** Crons and digests filter on recency ("a run in the
  last 60 days"); dated demo data answers `users: 0` forever after. Find the window in the code,
  and give recipes a user-path way to make data recent (re-date it in the review form). Better,
  when the seeder is yours: date rows relative to today in the user's zone, so every window has
  data on any day. Then cap every timestamp at now: a seed that stamped today's row at 12:00 put
  it in the future before noon, and the app's freshness watermark (`max(updated_at)`) went
  *backwards* after a real edit.
- **Key every wait and every read-back on the row YOUR action created**, never on "the latest".
  A repo seeder you do not own may date rows later than now: verify-jmtarot's `until … order by
  created_at desc limit 1` found the seed's finished chat run and returned in 4 s, before the
  posted message's run existed. Join through the id the action produced (`trigger_message_id`,
  the question text you typed).
- **Wait on the app's own signal, never on the page settling.** A typing indicator going away,
  a pending card's copy disappearing, a turn meter's aria-label. A page-text-stability loop stopped
  early on a static sidebar; a heading predicted from another page ("What happened") never
  appeared on this one. Three more from verify-daily-words, each a recipe that passed or hung for
  the wrong reason: a "Just added" list that already held seeded words satisfied the wait before
  the save landed; a form that auto-submits on mount detached the button the steps were clicking;
  a redirect chain through two gates (`/onboarding` -> `/today` -> `/birthday`, the last compiling
  on first use) settled the URL twice, so waiting on the URL ended on a blank page. Wait for a
  screen's content, and never tap a control the page drives itself.
- **Record the base's known failures as counts.** When a drive fails on the base for a reason
  outside the change (16 dead links in one generated page), write the count into the feature
  file and the index ("pass if broken stays at 16 and anchors at 0"), so the next agent compares
  counts instead of reading a red exit code as theirs.
- **Pick inputs the seed does not already hold.** The first "add a word" recipe used a word the
  demo seed had; it ended on the duplicate notice and read like a broken save. Point recipes at
  the seed's own list (`grep` the seeder) when choosing inputs.
- **Write down one-shot seed state and the order it forces.** Today's card, a user's onboarding,
  a delivered notification slot happen once per run. Say in each feature file what its journey
  consumes, and order the proving pass around it (the repo's onboarding spec needs the
  un-onboarded user, so it runs before the onboarding journey).
- **Clock windows, not only recency windows.** A scheduled job that only acts between 07:00 and
  19:59 in the user's zone says nothing at 22:00. Give recipes a user-path way to move the clock
  instead of waiting: change the user's zone through the app's own route (an `Etc/GMT±N` zone is
  exact; its sign is POSIX's, inverted: `Etc/GMT-5` is UTC+5).
