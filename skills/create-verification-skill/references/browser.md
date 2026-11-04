# Browser drives: fence, driver pitfalls, clipboard, HTML evidence

Read when the app has a web UI. The rules in SKILL.md are the short form; this file holds the detail and the cases that earned them.

- **Address the run by the host the framework believes it is on.** `next dev` reports every
  request's `req.url` as `http://localhost:PORT` whatever the Host header said, so a route that
  redirects with `new URL(path, req.url)` moved a browser on `127.0.0.1` to another cookie origin
  and the claim silently ran signed out (verify-daily-words). Bind loopback only, but hand out
  `localhost:PORT` as the run's URL, the app's own absolute-URL setting (`APP_URL`) and the cookie
  domain.

- **Fence the browser as well as the server.** Route every request in the Playwright driver:
  the run's own origin passes (not all of loopback: the owner's dev server is loopback too), the
  fake vendor host is served from the stand-in, everything else is aborted and logged and fails
  the drive unless the steps `allow()` it. `context.route` does not see WebSockets, and a service
  worker's requests bypass it unless the context sets `serviceWorkers: 'block'`. Grant no permissions by default (notifications, clipboard), and **measure** which path that
  drives before writing it down, because it changes between Chromium builds: in
  verify-expense-tracking's Chromium a focused page could *write* the clipboard with no grant (its
  share button ended on the "copied" toast), while Chromium 145 under Playwright 1.58 refused
  `writeText` with `NotAllowedError`, and that refusal found fast-order's worst bug (the app threw
  away the order it had just paid an LLM for). Observe every `writeText` with an init script that
  records the text and the browser's answer and passes the call through (never fake the answer),
  drive the success path with the grant and read the clipboard back, and drive the refusal path
  without it. Start the browser from `env -i` so no `DISPLAY`/`WAYLAND_DISPLAY` lets it reach the
  owner's desktop clipboard (WSLg). A wrapped
  harness's own browser is not fenced: verify-run-insights reuses the capture harness's seeder but
  runs its commit pass in the fenced driver, because the harness would have fetched the fake
  store's URLs from the real vendor. With no request routing (a raw CDP driver), fence Chrome with
  a dead proxy in its environment (`all_proxy`/`https_proxy`/`http_proxy` and the upper-case
  twins = `http://127.0.0.1:9`, `no_proxy=localhost,127.0.0.1`): Chromium on Linux reads them and
  bypasses loopback itself. Prove it by opening a harmful host in a throwaway tab and requiring
  `ERR_PROXY_CONNECTION_FAILED` on the error page, not with an in-page `fetch`: the app's CSP
  refuses that too, so "Failed to fetch" proves nothing. Give Chrome the run's HOME, or it writes
  `~/.cache/dconf` into the user's home.

- **The browser driver must not create its own failures.** Playwright's screenshot hides the
  caret by injecting a style, and mid-hydration React reports that as a hydration mismatch the
  app does not have. Pass `caret: 'initial'` and wait for `networkidle`. Dev-only overlays (Next's
  dev-tools badge) sit on top of real controls and swallow clicks, so hide them with an init
  script. Resolve the steps-file path before the script `cd`s anywhere. Give steps an
  `allow(regex)` for console errors a journey causes on purpose (a revoked link's 404), rather
  than loosening the rule for everyone. Run the browser in the seeded user's time zone: an app
  that re-detects the zone from the browser otherwise moves the user's day boundary mid-journey.
  Headless Chromium answers `Notification.permission === "denied"` with no grant, which is an end
  state to assert, not a failure. Log `requestfailed` with its URL: the console only says "Failed
  to load resource", and the URL is what told verify-expense-tracking the Blob PUT was the one
  failing. In a Next app, `getByRole('alert')` also matches `<next-route-announcer>`, which holds
  the page title, so a wrong-password check "read" the title; locate the app's own alert
  (`p[role=alert]`, or filter by text). Keep a short `DEV_ONLY` list of page errors that only
  `next dev` produces, logged as "dev-only, not counted", and admit an entry only after grepping
  the production bundle for its source: React's development client times server components with
  `performance.measure`, and a server `redirect()` mid-navigation throws "cannot have a negative
  time stamp" in about half the runs; `react-dom-client.production.js` has no such call.

- **HTML evidence is the visible text.** Server-rendered pages carry a framework payload in
  `<script>` tags, and a regex strip keeps that payload and loses the page. Save the HTML, and print
  the visible text with each `aria-label` inline (`[Mark as done]`) through a real HTML parser.
  That is what lets a recipe assert on what the user reads without a browser. It is not the whole
  page under a dev server: a Next `notFound()` page's copy lived only in the RSC payload, so the
  text view showed the brand and nothing else. Assert such a status with the HTTP drive and its
  copy with the browser. And the status itself lies when the route has a `loading.tsx`: the
  loading screen streams first, so `notFound()` arrives after a 200 was sent. Another user's
  record answered 200 with "Not found" in the title; assert the title and the absence of the other
  user's data (grep the saved HTML for it), and keep 404 assertions for routes without a loading
  screen.
