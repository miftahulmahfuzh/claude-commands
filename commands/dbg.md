# Debug Command - Go Debugger (Delve) Workflows

Use the Go debugger (Delve) to trace runtime behavior instead of relying solely on
server logs. This replaces the "paste logs → guess which `log.Debug` fired → infer
dataflow statically" loop with **real runtime values**: actual call sequences,
argument values, variable state, goroutine stacks, and post-mortem analysis.

## Philosophy

Batch Delve via Bash **>** interactive stepping via MCP, for this codebase:
- It is a concurrent, streaming HTTP server (`:8082`). Breakpoints freeze the whole
  server mid-stream, and pausing changes goroutine timing (heisenbugs in queue /
  cancellation / streamer code).
- Batch mode produces a transcript I can analyze without an interactive token loop.

So the default is: **reproduce the bug as a `go test`, then drive Delve in batch.**

## Usage

```bash
/dbg <what you want to debug>

Context: <symptom / suspected area>
Error: <optional logs>
```

I then pick the right workflow below and drive `dlv` for you.

## The Three Workflows (helper scripts in `cmd/dlv/`)

### 1. Trace dataflow — `cmd/dlv/dlv_trace.sh`
Prints every call to matching functions **with arguments + return values**, no code
changes, no breakpoints. Direct replacement for print-statement archaeology.

```bash
# Trace a deterministic test (preferred — reproducible, no timing noise):
cmd/dlv/dlv_trace.sh --test '<FuncRegexp>' ./chatbot/processing -- -test.run TestX

# Trace the live server while you hit it with curl (runs until Ctrl-C / kill):
cmd/dlv/dlv_trace.sh '<FuncRegexp>' .
```
Output also saved to `/tmp/dlv_trace.log`.

### 2. Breakpoint-debug a test — `cmd/dlv/dlv_test.sh`
Gold standard for **deterministic** bugs. Batch command script, no interactive loop.

```bash
cmd/dlv/dlv_test.sh <package> <TestName> <cmdfile>
# e.g. cmd/dlv/dlv_test.sh ./chatbot/processing TestResumeLoop /tmp/cmds.dlv
```
`<cmdfile>` is a Delve command script (a trailing `quit` is auto-appended):
```
break processing.go:142
condition 1 resp.Sources == nil
continue
print resp
args
goroutines
stack
```

### 3. Post-mortem a crashed/hung server — `cmd/dlv/dlv_core.sh`
The killer move for "it broke in the running server": inspect the **frozen state** at
failure — every variable in every goroutine — offline.

```bash
# Capture: panic -> core dump
ulimit -c unlimited; go build -o /tmp/agentic .
GOTRACEBACK=crash /tmp/agentic        # writes core on panic
# Or dump a live/hung server on demand:
dlv attach $(lsof -t -i:8082)   ->   (dlv) dump /tmp/server.core

# Analyze (non-interactive):
cmd/dlv/dlv_core.sh /tmp/agentic /tmp/server.core [cmdfile]
```

## Delve command cheat-sheet (for cmdfiles)

| command | purpose |
|---|---|
| `break <file>:<line>` / `break pkg.(*Type).Method` | set breakpoint |
| `condition <id> <expr>` | only stop when expr true (avoid stopping every request) |
| `continue` / `next` / `step` / `stepout` | flow control |
| `print <expr>` / `args` / `locals` / `vars` | inspect values |
| `goroutines` / `goroutine <id>` / `stack` | concurrency state |
| `set <var> = <val>` | mutate state |

## Decision tree

```
Bug to debug?
├─ Deterministic / reproducible in a test?
│  ├─ Want the call sequence + arg values?      → dlv_trace.sh --test
│  └─ Want to inspect state at a point?          → dlv_test.sh + cmdfile
├─ Only happens in the live server?
│  ├─ Crashes/panics or hangs?                   → core dump + dlv_core.sh
│  └─ Need to watch calls live?                  → dlv_trace.sh '<regexp>' .
└─ Not reproducible at all?                      → first make it a failing test (TDD)
```

## Environment requirements (one-time, already satisfied)

- `dlv` **must be built with the same Go major version as the project toolchain**.
  Project uses Go 1.25.x (DWARFv5); a `dlv` built with Go <1.25 fails with
  *"must be built with Go version 1.25.0 or later"*. Rebuild:
  `GOTOOLCHAIN=go1.25.7 go install github.com/go-delve/delve/cmd/dlv@latest`
- Batch mode requires `--allow-non-terminal-interactive=true` (scripts handle this).
- If a `go build`/`go install` ever reports `expected 'package', found 'EOF'` on
  files that actually have content: the module cache has 0-byte extractions and/or
  the build cache is poisoned (a WSL2 flaky-read symptom). Fix: re-extract the
  affected module zips with `unzip -o <zip> -d <pkg/mod>` then `go clean -cache`.
