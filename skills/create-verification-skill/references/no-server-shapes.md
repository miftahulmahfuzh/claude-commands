# Static sites, config repos, TUIs, network namespaces, dependency caches

Read when the app is a static site generator, a dotfiles/config repo, a TUI, or a run that needs no network. The rules in SKILL.md are the short form; this file holds the detail and the cases that earned them.

- **Surface:** what a user actually touches: HTTP API, web UI, CLI/TUI, MCP, a bot, a queue
  consumer. Pick the primary one; note the rest. For a static site or docs generator the surface
  is the rendered pages in a browser **and** the production build: the dev server is not what
  ships (`--minify`, a production environment, CI's exact flags), so the build is a drive of its
  own, and a docs site's link check (every internal `href`/`src` and `#anchor` resolving in the
  build) belongs in it. A base path without its trailing slash (`/agentic`) is the site root, not
  a broken link.

- **Where it really runs.** The checkout is often not what the owner runs. A dotfiles repo is
  deployed as a separate clone (`~/.config/nvim` lagged `~/nvim-config` by 4 commits), with its
  own lockfile and installed plugins that a fresh install no longer reproduces. Find the live
  copy and offer `up --live`: the checkout's change on a **copy** (never hard links: the owner's
  files are writable) of the live installed state, plus a read-only `live` drift report (commits
  and files the live copy lacks, `git --no-optional-locks` so `status` cannot touch its index)
  that prints the deploy command and never runs it. Fingerprint the live dirs at `up` and compare
  in `doctor` and `down`. The owner asked for this mid-run in the eighth pass; ask, or offer it.
- **A config repo's surface is the tool started with that config.** For an editor or shell
  config: per-run XDG dirs (config, data, state, cache, runtime) and HOME, the config a snapshot
  of the working tree, the tool inside a run-owned tmux server (`tmux -S <run>/tmux.sock`), a
  fixture project for it to edit (a git repo whose `origin` is a bare repo in the run, so a push
  mapping is provable), and state read over the tool's own RPC (`nvim --remote-expr`).

- **Build the dependency cache from the owner's lock, then diff it against a fresh resolve.**
  Package managers ignore a lock silently: lazy.nvim skips an entry whose branch differs from the
  spec's, so an unpinned plugin followed GitHub's new default branch (an incompatible rewrite)
  while the owner's lock said `master`; and an upstream repo can vanish (`phaazon/hop.nvim`). Pin
  every package to the lock after install (`git checkout <commit>`), take what no longer
  downloads from the live install, and log both. What a fresh install resolves to differently
  (`seed --update`) is a product finding, often the most important one: it is the owner's next
  update or next machine.

  same treatment for a different reason: they write into their source directory. `hugo server`
  rewrote the tracked `assets/jsconfig.json` and the committed `resources/_gen` mtimes, left
  `.hugo_build.lock`, and `hugo --gc` deletes `resources/_gen` outright. Serve from a snapshot,
  and exclude the paths the tool rewrites from both the re-sync and the "tree changed" hash, or
  every sync reports changes and doctor warns forever. If something cannot be isolated, say so
  in the skill, and make the script refuse to share it.

- **When the run needs no network at all, take it away.** `unshare --map-current-user -n`
  (unprivileged, uid kept) starts the run in a namespace with only a downed loopback: no route,
  no DNS, so raw sockets, native code and child processes are refused too, which no proxy or
  fetch wrapper achieves. Unix sockets still cross it, so drive over them. Join it for one-shot
  drives with `nsenter -t <run's pid> -U -n --preserve-credentials`, and prove it in doctor with a
  `curl` from inside (exit 6). Downloads then belong to a separate, explicit online step (`seed`)
  that builds a shared cache.

- **A done line in a log is not success, and an old error is not news.** Hugo prints `Total in
  N ms` after a failed rebuild as well as a good one, so `sync` waits for the done line and then
  checks for an error. It reads only the bytes written after it started (record the log's size
  first): reading the log's tail, a successful sync after a fix still found the earlier ERROR and
  failed. `doctor` reports the latest build's errors only (reset at "Change detected") and fails
  when that build failed, because the server keeps serving the build before it.
- **A shared dependency cache: hard links, read-only files, and a manifest.** `cp -al` gives
  each run a 570 MB plugin tree in under a second. Make the cache's *files* read-only (directories
  stay writable), so an in-place write fails in the run instead of writing through; never `chmod
  -R` a run dir (`down` did, and made the cache writable again through the shared inodes); rewrite
  a file by writing a new one and renaming it. Installed tools name their install dir by absolute
  path (Mason's lua-language-server launcher), and the run then executes the cache's copy, which
  wrote its logs into the cache. Rewrite every text file under the tree that names the source path,
  for the cache and for `--live` alike. `doctor` compares a manifest of the cache (path, size,
  mtime) with the one taken when it was built: it caught both leaks.
- **Unattended installers ask questions.** `:TSInstallSync` asks "reinstall? y/n" for a parser
  that is already there, and a headless editor waits on it forever. Run every install step under
  `timeout` with stdin from `/dev/null`, and install only what is missing.

- **A terminal UI is driven through tmux, read through its RPC.** `send-keys` into the pane is
  the user's typing; key bindings of tmux itself need an attached client (a `script` pty running
  `tmux attach` inside the run) and `send-keys -K -c CLIENT`. `capture-pane -p` (and `-e` for an
  `.ansi` copy) is the screenshot. Read state over the app's own RPC, actions only through keys.
  Insert text as a bracketed paste (`set-buffer` + `paste-buffer -p`): typed text opens completion
  menus and fires insert-mode mappings (`jk` saved the file), and blink.cmp's `<Esc>` closes its
  menu without leaving insert mode, so `:wq` became commit text; leave insert mode with `Escape
  Escape`. A prompt ("Press ENTER", y/n) eats the next keys, and RPC blocks while the app waits on
  `input()`: put a timeout on every RPC call and `screen` after any surprise. Give each restart a
  new socket path: the exiting process removes its socket after the new one already listens on it.
