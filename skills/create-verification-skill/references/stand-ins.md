# Vendor stand-ins, egress, paid-call budgets, fault injection, fake receivers

Read when the app talks to any third-party API, a serverless database driver, an object store, an LLM, or a sink that messages people. The rules in SKILL.md are the short form; this file holds the detail and the cases that earned them.

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
  - The browser's upload may need HTTP/2. `@vercel/blob/client`'s `upload()` streams its PUT body
    whenever the caller passes `onUploadProgress`, and Chromium sends a streamed request body only
    over HTTP/2: against a plain HTTP/1.1 stand-in every PUT failed with
    `net::ERR_ALPN_NEGOTIATION_FAILED` while the token step answered 200, which reads as a product
    bug. Give the stand-in a second listener on HTTPS + h2 (`node:http2` `createSecureServer`,
    `allowHTTP1`, a per-run self-signed certificate), point the browser's `NEXT_PUBLIC_` twin at it,
    and let only the run's Playwright context accept it (`ignoreHTTPSErrors`). Read the SDK's
    request code for every condition that changes its transport (progress callbacks, multipart
    thresholds) rather than assuming one: verify-run-insights' uploads passed over HTTP/1.1 only
    because no caller asked for progress yet. A curl replay of the browser's sequence cannot find
    any of this; each browser-direct path needs one browser journey.
  - Make the HTTP drive decode a client token it receives into its options (types, size cap,
    suffix, expiry): that proves what the app asks the vendor to enforce without a browser.
  - SDKs prefer ambient credentials over the configured token (`VERCEL_OIDC_TOKEN` beats
    `BLOB_READ_WRITE_TOKEN`). `env -i` drops them; name them in Gotchas anyway.
- **The migration tool may not reach a local database.** drizzle-kit needs a TCP driver the
  serverless app never installed. Apply the journal yourself, in order, one transaction per file,
  and record it where the tool would, so schema-drift checks agree.

  - *Paid, and the product itself* (the LLM in an LLM app): **real by default**, behind a per-run
    budget counted in vendor calls (see "Count paid calls where they leave"), with journeys
    targeted at the change. A stub-backed verify of an LLM app is a unit
    test with extra steps: it cannot plan, route or answer. Keep a stub only as `--offline`, for
    plumbing, labelled as not proof of anything that needs a model. **It is, however, the run's
    fault injection, and it deserves one journey:** drive the product's core action offline and
    read the end state. A vendor outage is a feature no real-mode run exercises; verify-jmtarot's
    offline reading came back HTTP 200, empty, stored as `ok` (a race in the moderation gate
    swallowed the provider error), the worst bug that pass found. It is not only for paid APIs:
    refuse whatever the product loads from outside at runtime. verify-agentic-docs' offline home
    page lost every popup and handler, because its inline script began with an unguarded call
    into the CDN's mermaid. One ReferenceError left a later `let` in its temporal dead zone, so
    every hoisted handler threw. Two runs in a row, `--offline` found the run's worst bug.
  - *Nothing paid or external at runtime?* The stand-in is still the fault injector. Give it a
    `fault db|blob|none` switch that **drops the connection** (destroy the socket, close the h2
    stream) rather than answering 5xx: that is what a dead network looks like, and SDKs retry the
    two differently. Expose it to steps files too (`fault('db')` mid-journey, `none` in the
    driver's `finally`), so outage and recovery are one journey. Then read each SDK's retry
    policy before writing the expected end state: `@vercel/blob/client` retries a failed PUT 10
    times with exponential backoff, so in verify-hospital-inspection-forms an upload on a dead
    connection showed "Mengunggah…" for ~17 minutes with no error. The recipe that waited for the
    error timed out; the finding was the missing timeout. Two of that run's four product findings
    came from this switch.
  - *Public, version-pinned assets the page loads at runtime* (a CDN's script, webfonts): neither
    harmful nor paid. Let the browser fence GET them from an allowlist of those hosts through a
    cache shared across runs (fetched once, then served from disk), so drives are deterministic
    and go online only on a miss. `--offline` refuses them, and that is fault injection too: it is
    what any reader behind a blocking network sees.
  - *Paid or external, peripheral* (a data gateway, a search API the feature does not need, an
    LLM that only decorates a non-LLM app): off unless a flag opts in. Note any free-tier quota the
    production cron shares, and when that cron runs, so opted-in drives stay clear of it.
  - **Follow each feature's success path to its last write.** When it passes through a pinned-off
    sink, the success state cannot be produced locally, whatever else you enable. Say so in the
    feature's Gotchas, prove the refusal end state plus the unit tests, and do not pay for the
    paid step in front of it (verify-seer: a receipt is saved only after its image is committed to
    a GitHub branch, so a billed vision read would still end in "not kept").

- **Blanking a URL is not isolation.** Code falls back to hardcoded hosts when its env var is
  empty (verify-agentic: blanked BE URLs still reached a dev gateway). Add egress control, chosen
  per runtime, because no single mechanism covers them all:
  - Go, Python (urllib, requests), curl: a dead `HTTP(S)_PROXY` (both cases) plus a `NO_PROXY`
    allowlist of loopback and the services the run may reach.
  - Node: `fetch` ignores proxy env (Node 22). Load a preload with `NODE_OPTIONS=--import` that
    wraps `globalThis.fetch` and rejects every host off the allowlist, logging what it blocked.
    Next and similar frameworks wrap fetch after the preload, so the guard stays underneath. Wrap
    `request` and `get` on both `node:http` and `node:https` in the same preload: the module
    objects are shared with `require()`, and a library that calls `https.request` at call time
    (web-push does) is refused before a socket opens. Wrap `get` separately: it does not go
    through the exported `request`.
  - Build tools can need the network, and a dead proxy can break them: behind one, Turbopack could
    not fetch `next/font/google` files and every page answered 500. Allowlist that CDN in the
    guard, leave the proxy off that process, and say so.
  Prove both directions from `doctor` without sending anything out: a probe to a harmful host
  must fail against the dead proxy. After the first real journey, list the hosts the logs mention
  and confirm each was allowed, and include an `https.request` probe in doctor. State in Gotchas
  that this is best effort: a raw `net.connect`, a native addon or a Rust-side fetcher slips past.

- **Count paid calls where they leave, not per drive command.** In a web app most paid calls are
  side effects: a commit fires a narrative and a coach's reaction in `after()`, a page view
  generates prose, a cron fans out. Put the counter in the stand-in and take one call from it in
  the egress guard before each fetch to a paid host; an empty budget fails the fetch the way a
  vendor outage does, so the app shows its own failure state. Record the mode (`real` /
  `offline`) in the run's metadata and print it from `doctor` and `ls`, so nobody cites an
  offline run as proof. Measure each journey's cost on the proving pass and print the table in
  the skill (verify-run-insights: an upload 1, a commit 2-3, one coach turn 3-5). The counter sees
  fetches, not logical calls: an SDK with `maxRetries: 1` spends 2 on a call that fails upstream,
  and an offline run shows 2 refused per attempt. Say so beside the table. List the follow-on spend
  too: one action can mint background work that later page views pay for (a jmtarot reading mints
  a chat run that any page with the chat button then advances, 5-9 calls), so a recipe's budget is
  its own calls plus what it leaves pending.
  **A runtime with no preload (Go, Python) counts at a proxy.** Make the stand-in an HTTP proxy on
  loopback and point `HTTPS_PROXY` (both cases) at it: CONNECT to the paid host is terminated with
  a per-run leaf certificate signed by a per-run CA that only the app trusts (Go: `SSL_CERT_FILE`
  = the CA and `SSL_CERT_DIR` = an empty dir; Python requests: `REQUESTS_CA_BUNDLE`), and each
  request inside the tunnel is one call: read whole, saved with its credential redacted, counted,
  forwarded, or refused by destroying the socket. CONNECT to anything else is dropped and logged, so
  the same process is the fence. This keeps the app's own config path: fast-order's Gemini base URL
  is a constant in code, so pointing a base-URL variable at the stand-in was not possible without
  switching providers. Decode `Content-Encoding` for the record only (Go asks for gzip), and give
  the script a `calls` drive that prints each saved request's model, prompt and reply: it is how a
  reader sees what the app asks the vendor for.
- **Give the fault switch `drop` and `hang`, and read the client's resilience code first.** Drop
  proves the error path, hang proves the timeout (fast-order: a 502 after exactly the handler's
  30 s context, "printing…" on screen meanwhile). A circuit breaker is per-process state that
  journeys leave behind: after three dropped calls gobreaker stays open 30 s and a failed half-open
  probe reopens it, so the next journey fails fast with no call leaving. Write those counts into
  the expected end state (calls reaching the stand-in per print: 1, 1, 1, then 0), and tell
  recipes to wait out the timeout or `down` + `up`. Every `ui` ends with `fault none`. When the
  client's timeout is minutes (lunch-delivery: 5 min, and `context.Background()` so the browser
  giving up cancels nothing; the stand-in logged the close after 308 s), drive the hang with a short
  client `--max-time` in the background, carry on with other journeys, and read the stand-in's
  close time afterwards. Before writing the drop end state, read what the app deletes before the
  call: lunch-delivery's reset path deleted the good cached answer first, so one failed call cost it.
- **Seeding refuses paid calls; `up` arms the budget last.** Seeding through the app fires the
  same side effects as using it (25 demo commits fired 49 LLM calls). Refuse them unspent while
  seeding, arm the budget once `up` is done, and write the residue (failed turn rows, an error log
  full of refusals) into Gotchas.

- **Turn a harmful sink into a fake receiver, so its success path becomes provable.** A sink you
  only fence (web push, a webhook, an SMS gateway) leaves its feature unproven past the refusal.
  When the protocol lets the app address an arbitrary endpoint, stand one up on loopback and
  register it through the app's own route. verify-daily-words' stand-in is a push service on
  HTTPS with a per-run self-signed certificate the app trusts through `NODE_EXTRA_CA_CERTS`
  (nothing else trusts it); `push subscribe` mints a device key pair and posts the
  subscription JSON to `POST /api/push/subscription`, and the sink checks the VAPID `k=` against
  the run's key and decrypts each payload (RFC 8291 aes128gcm, ~30 lines of `node:crypto`). The
  hourly tick then proves sent / quiet / no-slot / 410-pruned with the decrypted text as evidence.
  Keep the structural argument as well (VAPID pair minted per run, the browser never granted
  notifications, the guard refusing `https.request` elsewhere) and make `doctor` fail when any
  stored endpoint points outside the run's sink. Where no fake can stand in, fall back to making
  the sink structurally empty and say so in Gotchas.
  **Email is the easiest fake receiver:** point `SMTP_HOST` at a ~150-line SMTP server in the run
  that speaks what the real relay does (smtp.gmail.com:587: EHLO, STARTTLS, AUTH only after TLS),
  checks the run's credentials and keeps each message as JSON with its links. Go's `smtp.PlainAuth`
  refuses AUTH without TLS unless the host is literally `localhost`/`127.0.0.1`, and `SendMail`
  starts TLS whenever it is offered, so offer it with a leaf for `IP:127.0.0.1` signed by the run's
  CA (`SSL_CERT_FILE`): the app then runs the same TLS path production does. A `mail RUN --path`
  drive lets recipes follow the link without trusting its host: lunch-delivery's link host came
  from the request's `Origin` header, which is how the run found reset-link poisoning
  (`--origin https://evil.example` mailed a valid token there) and a hardcoded `localhost:8080`
  fallback (the unrelated container on this machine). Have the HTTP drive send `Origin: <run URL>`
  on writes by default, as a browser does, and `--no-origin`/`--origin` to probe.
