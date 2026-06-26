# Postmortem: Installing a Working Delve (dlv) Debugger

**Date:** 2026-06-26

**Goal:** Get the Go debugger (Delve) usable on this project so we can trace bugs
with real runtime values instead of only server logs.

**Outcome:** ✅ `dlv` upgraded from v1.25.2 → v1.27.0 (built with Go 1.25.7); the
`/dbg` workflow (`cmd/dlv/*.sh`) is verified working end-to-end.

**Time cost:** Much higher than expected — a 5-minute install turned into a deep
environment debugging session because of two *layered* problems.

---

## TL;DR

There were **two independent problems stacked on top of each other**:

1. **Primary blocker (the real issue):** Our `dlv` was built with Go 1.24.4, but the
   project compiles with Go 1.25.7. Go 1.25 emits **DWARFv5** debug info, and a Delve
   built with Go < 1.25 **cannot read DWARFv5**. So the debugger refused to run.

2. **Secondary blocker (what made the fix take forever):** Upgrading `dlv` required
   rebuilding it with Go 1.25.7, and that rebuild kept failing with
   `expected 'package', found 'EOF'` on source files that *demonstrably had content*.
   Root cause: a **WSL2 flaky-read** issue during Go's concurrent module-cache
   extraction produced **0-byte files**, AND it **poisoned Go's build hash-cache** with
   empty-content hashes. Bad wifi earlier had compounded it with truncated downloads.

**Final fix:** re-extract the corrupted module zips with `unzip` + `go clean -cache`
(drop the poisoned hashes) + rebuild `dlv` with `GOTOOLCHAIN=go1.25.7`.

---

## Symptom timeline

### 1. Batch mode rejected
First run of `dlv_test.sh` (piping commands via stdin):
```
Stdin is not a terminal, use '-r' to specify redirects for the target process
or --allow-non-terminal-interactive=true if you really want to specify a redirect for Delve
```
**Fix:** add `--allow-non-terminal-interactive=true` so Delve accepts commands from a
pipe. (Now baked into the scripts.)

### 2. DWARFv5 not readable — the actual blocker
```
To debug executables using DWARFv5 or later Delve must be built with Go version 1.25.0 or later
```
- Installed: `dlv` v1.25.2, **built with Go 1.24.4** (`/home/miftah/.gvm/pkgsets/go1.24.4/global/bin/dlv`).
- Project: `go.mod` says `go 1.25.7`; gvm's base Go is 1.24.4 but the project
  auto-switches to the 1.25.7 toolchain → binaries carry **DWARFv5**.
- Mismatch → debugger can't read our binaries.

### 3. The DWARFv4 workaround that doesn't exist
Tried forcing the debugged binary down to DWARFv4 via
`--build-flags="-gcflags=all=-dwarf-version=4"`:
```
flag provided but not defined: -dwarf-version
usage: compile [options] file.go...
```
Confirmed via `go tool compile -help` and `go tool link -help`: **there is no
`-dwarf-version` flag**. DWARF version is not user-selectable in this toolchain.
→ The only path is to **rebuild `dlv` with Go 1.25+**.

### 4. Rebuild fails: `go install dlv@latest`
```
github.com/go-delve/delve@v1.27.0 requires go >= 1.25 (running go 1.24.4)
```
Base Go is 1.24.4. **Fix:** force the toolchain — `GOTOOLCHAIN=go1.25.7 go install ...`.

### 5. The rabbit hole: `expected 'package', found 'EOF'`
With the toolchain forced, the build repeatedly failed:
```
.../github.com/go-delve/delve@v1.27.0/cmd/dlv/dlv_test.go:1:1: expected 'package', found 'EOF'
```
Then, after `go clean -cache`, the SAME error but on **many different files across many
unrelated modules** (x/sys, starlark, go-dap, cobra, pflag, cilium/ebpf, x/arch, …),
a **different set each run**, stabilizing at **exactly 23 files**.

---

## Investigation (how we narrowed it down)

| Check | Result | Conclusion |
|---|---|---|
| Disk space (`df -h`) | 818G free, 15% used | Not a full disk |
| Inodes (`df -i`) | 5% used | Not inode exhaustion |
| Memory (`free -h`) | 14G available | Not memory pressure |
| Sequential file writes ×500 | 0 came back 0-byte | Plain FS writes are reliable |
| Concurrent file writes ×800 | 0 came back 0-byte | Generic concurrency is fine |
| `unzip -t` on cobra zip | ZIP OK | Downloaded zip is intact |
| `unzip -p` active_help.go | 2634 bytes | Content exists in the zip |
| `ls`/`wc -c` on the 23 "EOF" files | all had full content (2848, 4862, 3072 …) | **Files are NOT 0-byte on disk, yet Go reads them as empty** |
| Toolchain `compile`/`link` binaries | intact, non-zero | Compiler itself not corrupt |
| Trivial `hello.go` build | prints "hi" | Toolchain works for small builds |
| **Standalone module importing only `pflag`** | **fails on `bool.go` (3072 bytes) with EOF** | Reproduced in isolation — not a Delve-specific build quirk |
| Re-extract 12 modules with `unzip`, rebuild | **still EOF** | On-disk content wasn't the (only) problem |
| **`go clean -cache`, then build `pflag` module ×5** | **5/5 SUCCESS** | 🎯 **The build hash-cache was poisoned** |

---

## Root cause

Two reinforcing failures, both downstream of **WSL2 intermittently returning EOF on
file reads** during Go's high-concurrency module extraction / compilation:

1. **0-byte module-cache extractions.** Go's module extractor wrote some source files
   as 0 bytes. (`cat` could read other copies from page cache, which is why content
   sometimes "appeared" — but Go's compiler read empties.) Earlier downloads under a
   **bad wifi connection** also truncated some zips, worsening the cache state.

2. **Poisoned build hash-cache (the sticky part).** Go's build cache stores a content
   hash per source file keyed by `(path, mtime, size)`. When a transient read returned
   empty, Go cached the **empty-content hash** for that file. On every subsequent build
   Go reused the cached (empty) hash and reported `found 'EOF'` **deterministically** —
   even after the on-disk file was correct again. Re-extracting with `unzip` didn't help
   because `unzip` *preserves the zip's original mtime*, so the poisoned cache key still
   matched. Only `go clean -cache` cleared it.

The reason the dlv rebuild "stuck at exactly 23" was this poisoned cache: those 23
packages were permanently marked bad until the cache was wiped.

---

## The fix (what actually worked)

```bash
# 1. Repair any 0-byte files in the affected modules using unzip (Go's extractor
#    reproduces the 0-byte files; unzip writes them correctly).
MODBASE=/home/miftah/.gvm/pkgsets/go1.24.4/global/pkg/mod
DL=$MODBASE/cache/download
# for each bad "module@version": chmod -R u+w "$MODBASE/<mod@ver>"
#   then: unzip -oq "$DL/<modpath>/@v/<ver>.zip" -d "$MODBASE"

# 2. Drop the poisoned build hash-cache.
GOTOOLCHAIN=go1.25.7 go clean -cache

# 3. Rebuild dlv with the matching toolchain, overwriting the old binary.
GOBIN=/home/miftah/.gvm/pkgsets/go1.24.4/global/bin \
  GOTOOLCHAIN=go1.25.7 GOPROXY=https://goproxy.cn,direct \
  go install github.com/go-delve/delve/cmd/dlv@latest
```

Verification that the cache was the real culprit: a one-import test module built
**5/5** after `go clean -cache`, having failed deterministically before it.

### Cleanup
- Removed the bogus `-gcflags=all=-dwarf-version=4` build flag from the scripts (it was
  only ever a workaround for the old `dlv`, and the flag doesn't exist anyway). Scripts
  now pass no build flags by default; `DLV_BUILD_FLAGS` is an opt-in escape hatch.

---

## Verification (end-to-end)

```
$ dlv version
Version: 1.27.0   (built with Go 1.25.7 → reads DWARFv5)

$ cmd/dlv/dlv_test.sh ./chatbot/cache TestFastLane_HandleCachedRequest <cmdfile>
Breakpoint 1 set at ... fastlane_test.go:56
[Breakpoint 1] ... (hits goroutine(8):1 total:1)
[8 goroutines]  + full stack trace

$ cmd/dlv/dlv_trace.sh --test 'HandleCachedRequest' ./chatbot/cache -- -test.run .../ProcessesCacheHit
> (*FastLane).HandleCachedRequest(ctx, SubmitRequestArgs{RequestID:"test-req", Question:"test question", ...}, "ai_chatbot_conv:prevquestiontestquestion", ...)
>> (*FastLane).HandleCachedRequest => (true)
PASS
```

---

## Lessons & prevention

1. **Keep `dlv` in lockstep with the project's Go major version.** Whenever the project
   bumps Go (e.g. 1.25 → 1.26), rebuild Delve:
   `GOTOOLCHAIN=go<ver> go install github.com/go-delve/delve/cmd/dlv@latest`.
   A version skew shows up as *"must be built with Go version X or later"* (DWARF).

2. **`expected 'package', found 'EOF'` on a file that clearly has content = cache
   corruption, not your code.** It is a WSL2 flaky-read symptom. Recovery:
   - `unzip -o <zip> -d <pkg/mod>` to repair 0-byte extractions, **and**
   - `go clean -cache` to drop poisoned content hashes (this is the step people miss —
     re-extraction alone is not enough because `unzip` keeps the old mtime).

3. **Don't install Go modules over flaky wifi.** Truncated downloads seed the module
   cache with bad files that resurface later. We only made progress after switching to a
   stable connection (phone hotspot).

4. **There is no `-dwarf-version` compiler flag.** Don't chase forcing DWARFv4; fix the
   `dlv` version instead.

5. If corruption ever looks widespread, the nuclear option is `go clean -modcache`
   (re-downloads everything) — but pair it with `go clean -cache`, or the poisoned hash
   cache will keep biting.

---

## Quick recovery cheat-sheet

```bash
# "dlv won't read my binary" (DWARF version error):
GOTOOLCHAIN=go<project-go-version> go install github.com/go-delve/delve/cmd/dlv@latest

# "go build says found 'EOF' on files that have content" (WSL2 cache corruption):
go clean -cache                                   # always do this first
# if still failing, repair the named module(s):
unzip -o <pkg/mod>/cache/download/<mod>/@v/<ver>.zip -d <pkg/mod>
go clean -cache && <retry build>
# last resort:
go clean -modcache && go clean -cache
```
