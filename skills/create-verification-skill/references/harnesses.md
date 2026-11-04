# Wrapping the repo's own harnesses and reading their defaults

Read when the repo has an e2e suite, smoke scripts, a capture or seed script, or a dev server config with a proxy. The rules in SKILL.md are the short form; this file holds the detail and the cases that earned them.

- **Existing harnesses first:** e2e suites, smoke scripts, Postman/http files, compose test
  stacks, seed scripts, fixtures. A harness the repo already maintains beats anything you
  invent. Wrap it, don't replace it. Check how it picks its target (a `BASE_URL`-style env var,
  a flag): wrapping should be "point it at the run". If the target is hardcoded in a config the
  harness loads, write a wrapper config into the run's snapshot that imports the repo's and
  overrides only the target (verify-daily-words: `{...base, use: {...base.use, baseURL}, webServer:
  undefined}`), so no tracked file changes; edit the harness only when it cannot be wrapped.
  When a wrapped check reports the whole suite missing, suspect its input before the product:
  verify-agentic-docs fed the repo's popup checker the minified build through its `--index`
  shortcut and it reported all 51 popups MISSING; it parses unminified HTML. Let a harness run in
  its own default mode, inside the run's snapshot, with its temp dir under the run. Drop
  any "start or reuse a server" block: Playwright's `reuseExistingServer` happily reuses whatever
  the owner left on the default port. Specs that skip without a session variable
  (`DW_TEST_SESSION`) should get the run's token, so they run instead of skipping. Under `env -i`
  with a per-run HOME, Playwright cannot find its browsers: pass `PLAYWRIGHT_BROWSERS_PATH`.
  **Read every default the harness falls back to, and classify each like an external call.**
  jmtarot's `tools/e2e/chrome.mjs` defaulted to the production URL, to CDP port 9222, and to a
  persistent profile holding the owner's real Google session; wrapping it meant passing the run's
  base, port and a throwaway profile on every call and refusing its `login`/`reset` verbs. A repo
  rule against a browser library ("no Playwright") binds the harness too: wrap the driver it has.
  The app's own dev config is a default of the same kind: fast-order's `vite.config.ts` proxied
  `/api` to the production Render backend while the README said it proxied to the local one, so
  `npm run dev` was a harmful command. Trust the config over the docs; serve the dev server with a
  wrapper config that imports the repo's and overrides only target, host, port and cache dir, and
  prove the hop in doctor (a unique path that the run's backend answers 404, plus the repo's own
  proxy log line naming the target). **Read the shell scripts around a harness, not only its
  specs**, every branch: fast-order's `test-*.sh` ran `npm install -D` into the checkout,
  `playwright install --with-deps` (sudo), and, when `docker compose ps` showed nothing up,
  `deploy-compose.sh` = `docker compose down` + rebuild of the owner's stack. Wrap the inner command
  (`playwright test` under a wrapper config, the specs copied into the snapshot with their
  hardcoded owner URLs rewritten), never the script. **Then read what a passing harness asserts:**
  fast-order's integration spec passed on the clipboard-error stamp (it checked only `length > 50`),
  so its green proved nothing about the bug the run found. Say so in the feature file.
