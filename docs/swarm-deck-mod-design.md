# swarm-deck — a Claude Code mod for the swarm

Design, 2026-10-27. Target: Claude Code v2.1.311 (mods need ≥ 2.1.287; this machine was
on 2.1.269 and was updated as the first step of this work).

## Why a mod and not a hook

A **mod** is a plugin with a `hooks/` JavaScript module whose functions Claude Code calls
*inside its own process*, as middleware: each hook may **observe** (`return next(e)`),
**rewrite** (`next({...e, text})`), or **answer** the event itself (`return { deny }` — the
tool never runs). A settings hook, by contrast, is a shell command fired at a lifecycle
event. Four things a mod can do that a settings hook cannot, all of which this design needs:

- `$.clock.every(ms, fn)` — background work **outside any turn**, so watching a fleet costs
  zero tokens and zero turns.
- `$.store` — a JSON key-value store **shared by every session on the machine**. The docs
  state plainly that `$.fs.write` is not atomic and that data several sessions change belongs
  here.
- `$.session.send({ to, text })` — session-to-session messaging from the mod itself.
- `$.ui.open` / `AbovePrompt` / `command.register({ immediate: true })` — a pane, a band, and
  a `/command` that runs **while Claude is working**.

## What this fixes

The repo's most expensive MEASURED failure: *a phase-2 session held an `AskUserQuestion` for
eight hours and stalled a six-phase set whose answer was rung 1 of the precedence ladder.*

Iron rule 4, the ladder, "both executors are unattended: they never ask" — every bit of that
is currently enforced by **prose in a prompt**. A mod makes it mechanical: the tool call
cannot complete, so the stall cannot happen. That is the whole thesis. The dashboard half is
a convenience; the guard half is the one that pays.

A second, smaller fix: `swarm.py spawn` prints a warning it cannot act on — a child whose
permission mode differs from the coordinator's has its reports *held for approval*, and the
set stalls **silently**. A mod can see the undelivered report and make it loud.

## What already exists elsewhere

The fleet-dashboard niche is crowded (michaelt604/fleet, bennewton999/claude-code-mods,
TheoGegout/claude-agent-watch, leowei31/agent-dashboard-mod, Flightdeck). None of them know
what a phase, a wave, a `depends_on` DAG or a ledger is, and showing that a session is
"waiting for you" still means a human notices at 9am. Our problem is not seeing the stall.
It is that the stall happened.

## Shape

One plugin, two halves sharing one module-level state object. The **marshal** writes (guards,
decisions, heartbeats); the **deck** reads (pane, band). One mod rather than two, because the
deck is only interesting showing what the marshal records, and splitting them would duplicate
the ledger lookup and the `$.store` keys.

```
mods/swarm-deck/
├── .claude-plugin/plugin.json
├── hooks/
│   ├── hooks.json          # { "modules": ["./register.js"] }
│   └── register.js         # the hooks module
└── tests/*.test.ts         # claude plugin test — offline
```

### How it loads: not through sync.sh

Installed plugins are cached by version; the docs are explicit that edits do not reach the
installed copy until the version is bumped and it is installed again. That is the `~/.claude/`
drift scar in CLAUDE.md rebuilt with extra steps. Instead, in `~/.claude/settings.json`:

```jsonc
{ "env": { "CLAUDE_CODE_PLUGIN_DIRS": "/home/miftah/claude-commands/mods/swarm-deck" } }
```

The repo directory **is** the loaded mod, in every session including the `claude -n` children
`swarm.py spawn` opens. One source of truth, no deploy step, no second tree to diverge.
`sync.sh` is untouched and keeps its three artifact types.

### How a session knows what it is

At `session.start` the mod runs `swarm.py find` once against the cwd and caches
`{ slug, phase, role }` in module state. No ledger parsing in JavaScript — `swarm.py` stays
the single reader of the ledger format. A session outside a swarm gets `role: null` and the
mod goes **dormant**: no guards, no heartbeat. `/fleet` stays available, read-only.

## The marshal

### Guard 1 — `AskUserQuestion` cannot complete in a swarm session

```js
on('tool.call', { tool: 'AskUserQuestion' }, guard).catch(failClosed)
```

Returns `{ deny }` without calling `next`, so the question never renders and the child reads
the deny text as the tool result. The text is the precedence ladder verbatim, plus the plan
index's `## Decisions` section, ending with an instruction to decide and record the decision
in `completion_report.decisions`.

It deliberately does **not** call `$.model.complete` to answer the question, even though
model-call time is exempt from the hook's 10-second budget. The child already holds the plan,
the code and the ladder; a detached side-call holds none of that and would decide worse.

The `.catch` handler is load-bearing: `claude plugin validate` warns `gating hook without
.catch`, and a hook that throws is **skipped** — which would let the question reach a human
and stall the night. It must **fail closed**, returning the same deny.

### Guard 2 — interactive shell commands

`tool.call { tool: 'Bash' }` denying `git rebase -i`, `git add -i`, `$EDITOR`, pagers.
CLAUDE.md names these alongside `AskUserQuestion` as stall reintroductions. The pattern list
stays short and says so in a comment: Anthropic's own `blast-radius` sample documents that its
regex misses `git push -f`, and under-claiming is the honest posture.

### Guard 3 — the silent-stall detector

Reports go out via `$.session.send`, which resolves `{ isDelivered: false, reason }`. On a
false, escalate and flag the row instead of going quiet.

**Unverified assumption:** that a message *held for approval* reports `isDelivered: false`
rather than `true`. This is checked at the top of slice 4, before any code leans on it. If it
comes back `true`, guard 3 needs a different signal.

### Addressing

`SessionSendAddress = string | { sessionId } | { agentId }`, where the bare string is "the
tool's own spelling (a name, an agent id, a received `from` address)" — the same name-based
addressing `ListAgents`/`SendMessage` already use. `swarm.py spawn` sets each child's name
with `claude -n`, so the coordinator is addressable by the name the ledger already records.
No session-id bookkeeping to invent.

Verified against the generated declarations for 2.1.311, not the copy on GitHub — that one
lags and has no `$.session.send` at all.

## The deck

### Shared state

One `$.store` key per set, `swarm/<slug>`:

```js
{ coordinator: 'name',
  phases: { '2': { name, status, wave, contextPct, lastTool, updatedAt } },
  decisions: [ { phase, question, chose, why, at } ],   // capped
  flags:     [ { phase, kind: 'undelivered'|'guard', at } ] }
```

The store is capped at 4 MiB of JSON in total, so rows stay small and `decisions` is capped.
The committed ledger remains the durable record; this is the live view.

### Heartbeat

Each child runs `$.clock.every(15_000, …)` writing its own row, refreshed additionally on
`turn.complete` (via `$.session.usage()` → context percent, cost, rate limits) and on
`tool.call` (last tool). This is the part that is impossible without a mod: it runs outside
any turn, so a coordinator watching ten phases spends no tokens to do it.

### Pane

`/fleet`, registered with `immediate: true` so it opens **while Claude is mid-turn**. One row
per phase: wave, status, context bar, last tool, elapsed. Below, a **Decided without asking**
section that fills in live — CLAUDE.md calls that the morning's review queue, and today it is
reconstructed at termination. Here it writes itself as decisions happen, and survives a
coordinator that dies.

### Band

`AbovePrompt` draws **nothing** unless something needs a human: an undelivered report, a guard
trip, or a wave fully green and ready to land. A band that is always lit is noise.

### Deliberate omission: no Raster, no Image

Both are terminal-only, and an `Image` inside tmux needs `allow-passthrough`, `focus-events`,
a non-popup pane and a kitty/Ghostty/iTerm2 host. That is a minefield for a tool we run inside
tmux every day. `Box` + `Text` + `Code` draw identically in the terminal, the Desktop app and
the VS Code extension.

## Constraints the validator enforces

Not style preferences — `claude plugin validate` fails on these, and a hook it cannot see is a
hook Claude Code never calls:

- every call written in full (`$.store.get(…)`); `const s = $.store` fails with
  `$.store is used as a value`
- `$` may be passed only to a **top-level** function — which is exactly the shape the `.catch`
  pattern needs anyway (`guard` and `failClosed` both top-level)
- event names must be string literals; no looping over a list of names
- ES modules, relative imports only; the one bare import allowed is `claude-code`
- do not shadow `on` inside `register`

## Tests

`claude plugin test` runs offline — no session, no sign-in, no network, 5 seconds per test.
Same spirit as `swarm.py selftest`.

1. `AskUserQuestion` in a child → denied, ladder text present, `next` never called
2. guard throws → `.catch` still denies (**fails closed**)
3. **non-swarm session → `AskUserQuestion` passes through untouched**
4. heartbeat writes the expected store row
5. `/fleet` renders against an empty store without crashing

Test 3 is the important one. This mod denies a tool in *every* session on the machine, so
`role: null` dormancy is the safety property the whole design rests on. If it regresses it
breaks ordinary interactive work, not just swarms.

## Build order

1. `role` detection + guard 1 + tests 1–3 — **closes the eight-hour bug**, roughly 80 lines
2. heartbeat + `$.store`
3. `/fleet` pane
4. band + guards 2 and 3, after verifying guard 3's `isDelivered` assumption

## Distribution

Unpublished. It encodes the precedence ladder, the ledger format and the swarm's invariants —
the technique in executable form.
