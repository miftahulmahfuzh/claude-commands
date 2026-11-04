# Process control, env, compiled builds, readiness, shell pitfalls

Read while writing verify.sh, or when copying a sibling's verify.sh into a different runtime. The rules in SKILL.md are the short form; this file holds the detail and the cases that earned them.

- **Never let the daemon hold the caller's pipe.** Start it with `setsid`, with stdin from
  `/dev/null` and stdout/stderr to a log file, and NOT as part of a `cd && ... &` list (that
  backgrounds a bash wrapper, records the wrong pid, and hangs every `$(verify.sh up)`).
- **Record the process group, kill the group.** `kill -- -$PGID`. Never `pkill` by name: the
  user's real instance has the same name. Wait for the whole group to be gone (`pgrep -g $PGID`),
  not the leader: `next dev`'s workers outlived it and wrote into the snapshot while `down`'s
  `rm -rf` ran, which failed under `set -e` and left the run half torn down. Retry the removal.
  A daemon that detaches its children escapes the group: a tmux server `setsid`s itself and every
  pane gets its own session. When everything the run starts lives in one network namespace (see
  egress), the namespace is the run's identity: `down` kills every pid whose
  `/proc/PID/ns/net` matches the run's, and nothing else can match.
- **Doctor checks port ownership** by comparing the listener's process group with the run's,
  not with a pid regex. A port Docker publishes is held by root's `docker-proxy`, so `ss -p` lists
  the LISTEN with no process: report it as held by the owner, never as free.
- **Binary responses go to a file** with their size and sha256, never to the terminal. Raw bytes
  corrupt the agent's output and every `grep` after them. Use one `curl -w` (a second `-w`
  silently replaces the first). When the binary is the product (an Excel or PDF export), give it
  its own drive that saves the file and prints what a reader sees, parsed with the app's own
  library from the run's snapshot (`createRequire(<snapshot>/package.json)('exceljs')`): sheets,
  header, rows, which cells are coloured, the filename from `Content-Disposition`. A sha256
  proves nothing about the content.
- **Real env beats config files, and `env -i` beats both.** Start every process the run owns
  from `env -i` plus the run's own values (PATH, HOME, locale, then the pinned settings), so no
  secret exported in the caller's shell leaks in. If the app reads a dotenv file, point it at a
  file the run generates (`SEER_ENV_FILE`-style) instead of letting it find the real one. Pin every
  path and endpoint the app reads (DB URL, data dir, home dirs, ports) to per-run values, and blank
  what the classification above keeps off. A `.env.local` written by `vercel env pull` holds literal
  `[SENSITIVE]` for redacted values and `VERCEL="1"`: read a value from it only when it is not the
  placeholder, fall back to what CLAUDE.md documents, and never let `VERCEL` through (apps branch on
  it for TLS and migrations; `VERCEL=0` is truthy).
  Check how the app's config loader merges env and files before trusting this, including whether
  `VAR=` (set but empty) counts as set: godotenv's `Load` keeps it, some loaders fall back to the
  file or a default. Schema validators split the other way: zod's `z.url().optional()` accepts an
  unset `AUTH_URL` and refuses `AUTH_URL=` at boot. Omit an optional variable, or give it the
  run's own value; never blank it. A loader that reads `./.env` from the working directory
  (godotenv's `Load()`, python-dotenv's default) fills every variable `env -i` left unset from
  whatever `.env` sits there: start the process in an empty directory of the run's. And every
  variable with a default is pinned too: fast-order's unset `PORT` falls back to 8080, the owner's.

- **Compiled apps: build per run, stamp the build.** `up` builds into the run dir from the
  checkout and injects the commit (plus `-dirty`) into whatever the health/version endpoint
  reports. Doctor warns when HEAD **or the working tree** changed since `up`: an edit without a
  commit leaves a stale binary too. When the app has no version endpoint and no variable to
  `-ldflags -X` into (an `-X` on a missing symbol is silently ignored), let the toolchain stamp it:
  `go build -buildvcs=true` from the checkout records `vcs.revision` and `vcs.modified`, read back
  with `go version -m` (lines look like `build	vcs.revision=…`; an awk on field 2 misses them).
  Doctor then proves the listener runs that binary (`readlink /proc/<listener pid>/exe`). Build
  offline and leave the owner's caches alone: `GOPROXY=off GOFLAGS=-mod=readonly GOTOOLCHAIN=local`,
  the owner's module cache read, a `GOCACHE` under the verify state. The owner's cache may not hold
  the repo's modules at all (lunch-delivery: gin and pq missing, so the offline build failed). Then
  give the harness its own `GOMODCACHE`, filled once per `go.sum` hash by `go mod download` in a
  directory holding a COPY of `go.mod`/`go.sum`, with
  `GOPROXY=file://<owner GOMODCACHE>/cache/download,https://proxy.golang.org` (owner's cache first),
  and fail if the copied `go.sum` changed: the checkout is never written. 20 s once, then offline.
- **Readiness distinguishes "not up yet" from "up and broken".** Poll for the usable state, but
  stop after a few identical 5xx answers and print the log tail. verify-seer's first `up` waited
  4.5 minutes on a page that had been failing the same way since second 5. One exception: a known
  transient failure that sticks until the server restarts (Turbopack's `next/font/google` fetch,
  which ignores DNS options and proxies, failed once in five `up`s and every page answered 500
  until a restart). Match its log signature and restart the server, bounded (three tries), keeping
  each failed log.

- **A network namespace with exits: the answer to a hardcoded port that is taken.**
  lunch-delivery's `r.Run(":8080")` met an unrelated container on the host's :8080. In a fresh
  namespace the app binds its own :8080, untouched code. Measured on this kernel:
  `unshare --map-current-user -n` alone cannot raise loopback (`ip link set lo up`: EPERM, the uid is
  not root inside); `unshare --map-current-user --keep-caps -n sh -c 'ip link set lo up && exec "$@"'`
  can, and then `setpriv --inh-caps=-all --ambient-caps=-all --bounding-set=-all` drops every
  capability before the anchor process starts. The run still needs a database, a counting proxy
  and a URL the host can open: Unix sockets cross namespaces, so a bridge inside (the anchor) and
  the stand-in outside hold the two ends of each pipe (in-ns `127.0.0.1:3128` -> `standin.sock` =
  `HTTPS_PROXY`; in-ns `127.0.0.1:5433` -> `pg.sock` -> the verify container's port; host URL port
  -> `app.sock` -> in-ns `:8080`). Start the app with `nsenter -t <anchor> -U -n
  --preserve-credentials --wd=<snapshot>`; prove the listener with `nsenter … ss -ltnp` (it only
  sees the namespace's sockets) and `/proc/PID/exe`; `down` kills by namespace. Doctor proves the
  fence with no proxy (`curl` to the paid host exits 6) and that `127.0.0.1:<owner's DB port>` is
  refused inside. Every other tool the run starts (the repo's tests, its SMTP scripts) joins the
  same namespace.
- **Copy state files with a read-only open.** Some tools migrate a database on connect even for a
  read (Seer's lab migrates `lab.sqlite` that way). Copy the committed state with the database's
  backup API from a `mode=ro` connection, and hash the protected original before and after the
  proving pass.

- **State drives are read-only.** `sql`, `aql`, `redis` refuse writes (a read-only transaction,
  or a keyword/command allowlist). Writes go through the app's own routes, or they prove nothing.
  Give them a bare-value mode for recipes (`ID=$($V sql RUN --value "select id …")`): `psql`'s
  table output puts the dashes on the line a recipe's `sed -n 3p` expected the id on. And an
  `until RUN "select one value" EXPECTED [SECONDS]` that polls it, so a recipe waits on the
  database's state (a run's status, a row written in `after()`) instead of a sleep or page text.
- **The agent's shell may not be bash.** The Bash tool can run zsh, which does not word-split
  `$VAR` and refuses functions whose names collide with aliases. Scripts are executables with a
  `#!/usr/bin/env bash` shebang; recipes in the feature map never depend on word splitting or
  inline functions, and quote every URL with a `?` (zsh globs it and refuses with "no matches
  found" before the script runs).
- **`docker exec -i` inside a `while read` loop eats the loop's input.** Only the first of 38
  migrations ran, silently. Give every `-i` command in a loop `</dev/null` or its own file.
- **No `| head` inside the script.** Under `set -o pipefail`, a reader that closes early
  SIGPIPEs the writer and `set -e` aborts the drive halfway, here before a body file was renamed.
  Cap output in the producer (a line-limit argument), never in a pipe after it. The same pair
  kills a `x="$(ss … | grep pid=…)"` the first time nothing matches: grep exits 1, and doctor
  stopped halfway through its report with no message when the owner's port was free. Every grep
  in a `$(...)` that may match nothing gets `|| true` inside the substitution. Likewise give
  `curl -w` a separator (`%{http_code}|%{content_type}`): a content type contains a space. The
  same SIGPIPE kills the script from outside: `verify.sh seed | sed -n 1,12p` stopped the seed
  before it locked the cache and wrote its manifest. Send long commands to a file and read it.

- **`down` copies the server log into evidence** before deleting run state: it is the record of
  every decision the run made.
- **Evidence lives outside the repo and outside the worktree**
  (`~/.local/state/<app>-verify/<run>/evidence/`), so it survives `down` and worktree deletion,
  and is never committed by accident.
- **Number evidence files by drive order** (`01-api-...txt`), counting only the primary files.
  Files `up` writes itself (a seed pass) take a `00-` prefix the counter skips.
- **Steps files take arguments** (`ui RUN steps.mjs -- <id> <date>`), so a recipe can act on the
  extraction or run an earlier drive printed instead of hard-coding one.

Make scripts executable, `bash -n` clean, and print usage when called with no arguments. (`bash -n`
found an apostrophe inside `"${x:+…owner's…}"`, reported as a syntax error at the function's closing brace.)

- **Isolate:** can two instances run at once? Port 0 or a free-port picker, per-run data dirs,
  per-run DB names. Check for per-directory state too, not only ports: Next 16's `next dev` locks
  `.next/dev` in the project directory, so a second server on another port still exits, and Next
  15 has no lock but two dev servers would share and clobber one `.next`. Serve such
  a tool from a per-run snapshot of its directory (rsync the sources and hard-link dependencies
  with `cp -al`, which took 0.2 s for 17k files; a symlinked `node_modules` breaks Turbopack). The
  snapshot is a build artifact, so doctor warns when the tree changes. Site generators that
  write into their source directory: see no-server-shapes.md.
