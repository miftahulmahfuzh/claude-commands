# Other tools

Commands and skills in this repo that stand on their own: they are not part of the
`/analyze` → `/implement` / `/do` → swarm pipeline described in the [README](../README.md).
They install the same way (`./sync.sh`).

## Commands

| Command | What it does |
|---|---|
| `/dbg` | Drives Delve to get runtime truth instead of inferring from logs |
| `/token-maxxing` | Starts a high-consumption session on deliberately useful work; `/token-maxxing N` fans out N of them in parallel |
| `/token-maxxing-update-docs` | Records that session |
| `/up-version` | Semver bump + CHANGELOG from commits since the last tag |

`/token-maxxing` renames its session too, like the pipeline commands do (see the README's
[Session names](../README.md#session-names)): `tokenmax-<idea>` at step 5, and for
`/token-maxxing N` `tokenmax-orch-<date>` on the coordinator (step C4) and `tokenmax-<idea>` on
each worker (step W1).

### `/dbg`

Drives **Delve** in batch mode for runtime values — real call sequences, argument values,
goroutine stacks, post-mortem state — instead of guessing which `log.Debug` fired.

```bash
/dbg <what you want to debug>
Context: <symptom>
Error: <optional logs>
```

| Script | Purpose |
|---|---|
| `dlv_trace.sh` | print every call to matching funcs, with args and return values |
| `dlv_test.sh` | batch breakpoint-debug one test, scripted |
| `dlv_core.sh` | post-mortem a crashed or hung server from a core dump |

**This command is different from the others:** the scripts live in the *target Go project*, not
in `~/.claude/`. Reference copies are in [`cmd/dlv/`](../cmd/dlv) — see [setup](#setup-for-dbg).

```
Need the code paths?          → /analyze   (static)
Need what ACTUALLY happens?   → /dbg       (runtime, via Delve)
Ready to fix it?              → /implement or /do
```

#### Setup for `/dbg`

One-time setup per Go project — the scripts are committed alongside the code so the team shares
the same entry points:

```bash
cp -r ~/claude-commands/cmd/dlv cmd/dlv
chmod +x cmd/dlv/*.sh

# dlv must be built with the project's Go major version — Go 1.25 emits DWARFv5,
# which a dlv built with Go <1.25 cannot read
GOTOOLCHAIN=go1.25.7 go install github.com/go-delve/delve/cmd/dlv@latest

# optional, in .claude/settings.local.json:
#   "Bash(dlv:*)", "Bash(cmd/dlv/dlv_trace.sh:*)",
#   "Bash(cmd/dlv/dlv_test.sh:*)", "Bash(cmd/dlv/dlv_core.sh:*)"
```

For a live crash, capture a core dump the way you'd capture logs:

```bash
ulimit -c unlimited; go build -o /tmp/agentic .
GOTRACEBACK=crash /tmp/agentic
/dbg analyze this core dump   # then hand over the binary + core file
```

### `/token-maxxing`

Kicks off a deliberately high-consumption session that still lands real work. It reads the 5
most recent `docs/token_maxxing/` docs so it doesn't re-propose finished work, surveys the repo,
and generates 3–5 ranked ideas tagged fresh or continuation — then picks the winner itself, with
no manual selection step. Work lands on `token-maxxing-YYYY-MM-DD` and is merged to `main`
automatically once the session doc is written, unless told otherwise. Big ideas get handed to
`/analyze --no-worktree` rather than freehanded.

```bash
/token-maxxing            # anything
/token-maxxing tests      # bias the menu
/token-maxxing 5          # fan out 5 sessions in parallel, biased toward nothing in particular
/token-maxxing 5 refactor # same, biased toward refactor ideas
```

`/token-maxxing-update-docs` writes the session log (achievement first) and maintains a
newest-first index.

**`/token-maxxing N` (N > 1)** turns this session into a coordinator, borrowing the shape of
`/analyze-orchestrator` without its machinery: it recalls and surveys once, generates a menu of
N ideas with disjoint scope so the workers can never collide, cuts one worktree and branch per
idea, and launches N sessions via `swarm.py launch` — one tmux window each, running this same
command in `--worker` mode. Each worker rolls its assigned idea, writes its own session doc, and
reports back instead of merging; the coordinator verifies and lands each one to `main` the moment
it finishes, rather than waiting for the slowest. There is deliberately no ledger and no
`--resume` — the N ideas don't depend on each other, so recovering from a dead coordinator is
just re-running `/token-maxxing` for whichever idea didn't land.

### `/up-version`

Finds the latest tag on main, analyzes commits since, picks the bump, updates `CHANGELOG.md`
(Keep-a-Changelog), merges, tags, pushes, and returns you to your branch.

---

## Skills

### `commit`
`/commit` — the last gate before git: lists the files this session changed, shows the whole
diff, flags dead code, commented-out blocks, duplicated tests and debug leftovers, runs the tests
that touch the changed modules, and only then commits with a message that says why.

### `confluence-writer`
Getting a document into Confluence with formatting intact, on Server/DC and Cloud. The trick is
to render the doc as HTML, copy the *rendered* page from a browser, and paste rich text —
bypassing every markdown and wiki-markup converter. Also fixes literal `##`/`|` from pasted
markdown and the `conf_wikimarkup_conversion_errors` HTTP 500. Ships `template.html`.

### `confluence-reader`
The read counterpart. Hits `/rest/api/content` with your credentials and saves the body as text
plus every inline image as a local file — PDF export and copy-paste both lose the images. Body
text carries `[IMG: images/<file>]` markers so you only open the ones that matter. Resolves
`/display/`, `viewpage.action?pageId=`, tiny `/x/…`, Cloud, or a bare id.

Credentials come from `CONFLUENCE_PAT`, `CONFLUENCE_USER`/`CONFLUENCE_PASS`, or a git-ignored
`~/.config/confluence-reader/credentials`. `confluence_fetch.py` is stdlib-only.

### `spawn-new-cv-test` / `finish-cv-test`
A two-sided drill for computer-vision live-coding interviews, run against
`github.com/miftahulmahfuzh/cv-problems`. `spawn-new-cv-test` picks a problem off a twelve-rung
ladder, builds the data (synthetic plan sheet with exact ground truth, an existing fixture, or
one you supply), writes a deliberately terse brief, and opens a **fresh Claude Code session in
its own tmux window** to solve it in. `finish-cv-test`, run inside that window, stops the clock,
reconstructs your verbatim instructions from the session's own transcript jsonl, checks the
solution against ground truth, and scores how you *drove the agent* on seven dimensions.

The integrity mechanism is the directory split: the exam session's cwd is
`attempts/<slug>/workspace/`, and the `CLAUDE.md` written there forbids reading the parent —
where `PROBLEM.md` and `GROUND_TRUTH.json` live. Without that, "read PROBLEM.md and do it" is a
valid move and the drill measures nothing.

Trust is propagated, never invented, the same way `swarm` does it: a brand-new workspace path
would otherwise stop on the folder-trust dialog and eat the opening minutes of a timed run.

### `issue-ticket-reader`
The Jira counterpart. Pulls the description **and every comment in thread order** — on a
returning ticket the bug report is usually in the comments — plus linked issues, subtasks, and
every attachment. Videos are sampled into timestamped JPEG frames via ffmpeg (`--frames N`).
Extras: `--changelog`, `--all-fields`, `--no-attachments`.

Reuses the `confluence-reader` credentials, so it usually needs zero setup. Stdlib-only.

**Limits:** video audio is never transcribed, so a verbally-explained bug isn't readable from
frames; sparse sampling can miss a transient error toast; pdf/xlsx are downloaded, not converted.

### `fetch-gdocs-content`
The Google counterpart. Exports a Doc, Sheet, Slide or Drive file straight from
`docs.google.com/.../export` into local files you can Read — no browser, no copy-paste.
Defaults to **markdown** for Docs because the `txt` export silently drops every hyperlink;
`-f zip` additionally unpacks inline images. Writes `meta.json` with `fetched_at_utc` and a
`sha256`, because a live doc changes under you mid-analysis.

Public "anyone with the link" docs need no setup. For a private one the user signs in once with
`gcloud auth login --enable-gdrive-access --no-activate <account>` — `--no-activate` so reading a
doc doesn't silently switch their active gcloud identity — and the script mints a read-only token
per call. The token is never printed or stored. Stdlib-only.

Invoked as `/fetch-gdocs-content <url> <what you want to know>`; the notes are the deliverable,
not the dump.

### `sync-todos-into-gitlab-board`
`/sync-todos-into-gitlab-board .workflows/todos.md` — one GitLab issue per live task, in the
column its stage says. `todos.md` stays the source of truth.

Identity is read from two channels (the title prefix and the `- TaskID:` line), because a title
edited in the browser would otherwise hide the card and the next run would duplicate it.
`apply` refuses to write while any duplicate exists, and refuses to create more than
`--max-create` (default 10) at once — widening what counts as a task once took a file from 26
entries to 55 and created 28 permanent cards in a shared repo. `plan` is the default and writes
nothing. Only entries under `## Active Tasks` become issues; the root file has 27 live entries
and 28 echoes in its summary and activity log.

**Cost, documented rather than discovered:** a closed GitLab issue leaves `status::completed`
for the Closed column, so finished work sits as an open issue carrying the completed label.

### `update-ats-cv`
`/update-ats-cv <input.pdf> <what to change>` — parses the CV for content *and* visual style,
then redraws it from a `*.cv.yaml` model. The input PDF is never patched, which is what makes
"shave 4pt off that gap" answerable.

The page count is an invariant: `--autofit` walks a ladder of (gap, leading, font) triples and
takes the first that fits, or **exits non-zero** saying how many lines are over. Every gap is a
named token, so "those two lines are too far apart" maps to one number. `cv_extract.py`
identifies the typeface by advance-width matching, because CV builders ship flattened PDFs with
font names stripped and bold faked by overprinting — it found Lora at 0.65% error where the
metadata said nothing. Text is emitted in document order; an earlier version batched glyphs by
color, which rendered identically but made parsers read every heading before any body text.

**Limits:** letter-spacing applies to headings only; the layout engine covers a standard
one-column CV, not a sidebar or two-column body. Needs `pymupdf` + `pyyaml`.

### `edit-pdf-text`
`/edit-pdf-text <file.pdf> <what to change>` — rewrites text *inside* an existing PDF by
editing the glyph codes in its content stream, so background art, scans, stamps, photos and
signatures come through byte-identical. The opposite of `update-ats-cv`, which never patches
its input: here the input is the only copy there is — a signed surat, a stamped invoice — and
re-exporting from source is not on the table.

Covering the old text with a white box and retyping is the obvious approach and it is wrong:
it erases whatever the text sat on. `pdftext.py` instead parses the content stream (`Tj`, `TJ`,
`'`, `"`, Form XObjects, multiple streams), maps codes through the font's `ToUnicode` or
encoding, and rewrites only the bytes that change.

**Reduces the edit before applying it.** "Loading In" → "Loading out" becomes `In` → `out`.
Producers emit roughly one show operator per word, each with its own absolute `Tm`, so editing
only the word that actually changed leaves every other word's position exactly as authored.

**The trap worth knowing:** a producer declares `/Widths` only for characters the document
actually uses. Introduce a letter the original never contained — a `j`, say — and it draws with
**zero advance**, so the next letter lands on top of it, while the extracted text reads
perfectly. `replace` detects this and writes the real advance into `/Widths`, taken from the
embedded font program or the matching standard metrics.

`verify` is the point of the skill as much as `replace` is: per-page image SHA-1, a rendered
pixel diff with its bounding box, before/after crop PNGs, and a text diff. "Nothing else
changed" is a claim about a binary file, and this is what makes it checkable.

**Limits:** text that is pixels in a scan cannot be edited (`find` says so rather than
guessing); a glyph absent from a subset font is refused outright. Needs `pymupdf`.

### `analyze-and-fix-slow-tmux-pane-creation`
Finds where new-pane/new-shell time actually goes, instead of blaming tmux, WSL or a memory
leak. Walks a four-rung ladder — load vs cores and swap vs "used"; `shell -i` vs `shell -f` to
separate the rc files from tmux; a timestamped-`PS4` xtrace to name the exact rc line (`zprof`
cannot see external commands and will point elsewhere); then fd exhaustion and runaway
filesystem scans, which are what turn an ordinary rc command slow. Ships `diagnose.sh`
(read-only). MEASURED 2026-10-02: 22.9 s per pane, of which 18 s was one `lsof` in a
double-quoted alias — the quotes made it run at every startup — and the `lsof` was only slow
because a 2-hour runaway font scan held 95% of the system's file descriptors. Killing the scan
alone took startup to 0.55 s.

### `reap-orphaned-blobs`
Deletes Vercel Blob objects under `shots/` that no database row references, for Run Insights.

### `prune-vercel-deployments`
Clears orphaned per-branch Vercel aliases (the usual reason `--safe` prunes almost nothing —
Vercel never removes a branch's alias when the branch is deleted from git), deletes stale
deployments (`vercel remove <project> --safe --yes`, looping through the 200-per-run cap and
10-minute cooldown), and checks/proposes disabling future preview deployments via
`vercel.json`'s `git.deploymentEnabled`. General-purpose — works in any Vercel-linked repo on
the machine, not tied to one project. A *different* quota from `reap-orphaned-blobs`'s Blob
storage: this one targets the "Deployment Storage" free-tier cap.
