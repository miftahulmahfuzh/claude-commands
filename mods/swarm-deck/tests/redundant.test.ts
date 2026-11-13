import { expect, mock, test } from 'claude-code/testing'

// MEASURED 2026-11-13 on random-twin-yardstick (five phases, one coordinator): the deck sent
// 16 wakes and 14 of them told the coordinator nothing it had not already been told. These
// replay that session's sequences. The deck is the backstop: it speaks when nothing else did.

const START = { surface: 'terminal', isInteractive: true, cwd: '/repo' } as const
const USAGE = { value: { startedAt: 0, context: { tokens: 1, window: 100, percent: 1 }, rateLimits: [], cost: {} } }
const ROW = 'swarm/ears/phase/4'
const SENT = 'swarm/ears/sent/4'
const TICK = 15000
const VERIFY = 'python3 ~/.claude/skills/swarm/swarm.py verify --slug ears --apply'
const DONE = 'DONE phase 4 P1-ENG-VZXN, commit b080d87c pushed to feature/ears: the yardstick is the seventh screen condition'

function storeSpy(on: any, seed: Record<string, unknown> = {}) {
  const saved = new Map<string, unknown>(Object.entries(seed))
  on('store.get', ($: any, e: any) => ({ value: saved.get(e.key) }))
  on('store.set', ($: any, e: any) => { saved.set(e.key, e.value); return { value: undefined } })
  on('store.keys', () => ({ value: [...saved.keys()] }))
  return saved
}

/** The coordinator of `ears`, with the two files swarm.py keeps for it. */
function coordinator(on: any) {
  const files: any = {
    ledger: { slug: 'ears', coordinator_session_id: 'orch', phases: [{ n: 4, status: 'spawned' }] },
    runtime: { sessions: { '4': { name: 'impl-ears-p4' } }, reaped: {} },
  }
  mock.env(on, {})
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.id', () => ({ value: 'orch' }))
  on('session.usage', () => USAGE)
  on('command.register', () => ({ value: undefined }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null } }))
  on('fs.list', () => ({ value: [{ name: 'ears', kind: 'dir', size: 0, isLink: false }] }))
  on('fs.read', ($: any, e: any) => ({
    value: JSON.stringify(String(e.path).endsWith('/.runtime.json') ? files.runtime : files.ledger),
  }))
  on('ui.log', () => ({ value: undefined }))
  on('tool.call', () => ({ result: 'ok' }))
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  // Everything that reaches the session's prompt; the deck's own wakes are the ones counted.
  const woken: string[] = []
  on('prompt.submit', ($: any, e: any) => {
    if (String(e.text).startsWith('swarm-deck:')) woken.push(e.text)
    return { text: e.text }
  })
  return { files, woken }
}

function row(over: Record<string, unknown>) {
  return { slug: 'ears', phase: '4', session: 'phase-4', status: 'working', turns: 1, lastTool: 'Bash',
           contextPct: 10, decided: 0, shells: [], ...over }
}

/** The phase's own SendMessage, arriving in the coordinator as a cross-session message. */
async function peerMessage($: any, text: string) {
  await $.prompt.submit({
    text: '<cross-session-message from="uds:/run/x.sock" from-name="impl-ears-p4" from-mode="bypass">\n' + text +
      '\n</cross-session-message>',
    isMeta: true, wait: false, origin: { kind: 'peer' },
  } as any)
}

/** Advance the clock one refresh at a time, keeping the phase's heartbeat fresh. */
async function run(clock: any, saved: Map<string, unknown>, ms: number, over: Record<string, unknown>, at: { now: number }) {
  for (let left = ms; left > 0; left -= TICK) {
    at.now += TICK
    saved.set(ROW, row({ ...over, updatedAt: at.now - 1000 }))
    await clock.advance(TICK)
  }
}

// --------------------------------------------------------------------------- reports

test('a report the phase already delivered as a message is not sent again', async ($, on) => {
  // 15:24:27 the phase's DONE arrived as a message; 15:28:10 the deck woke the coordinator
  // with the same text. Seven times in the set.
  const { files, woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  await run(clock, saved, 30000, {}, at)

  files.ledger.phases[0] = { n: 4, status: 'done', commit: 'b080d87c' }
  saved.set(SENT, [{ to: 'orch-ears', text: DONE, delivered: true, at: at.now }])
  await peerMessage($, DONE)
  await run(clock, saved, 10 * 60000, { status: 'finished' }, at)

  expect(woken).toEqual([])
})

test('a report sent while the coordinator verified the finished phase is not sent again', async ($, on) => {
  const { files, woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  await run(clock, saved, 30000, {}, at)

  files.ledger.phases[0] = { n: 4, status: 'done', commit: 'b080d87c' }
  saved.set(SENT, [{ to: 'orch-ears', text: DONE, delivered: true, at: at.now }])
  await run(clock, saved, 15000, { status: 'finished' }, at)
  await $.tool.call({ tool: 'Bash', command: VERIFY } as any)
  await run(clock, saved, 10 * 60000, { status: 'finished' }, at)

  expect(woken).toEqual([])
})

test('a report that never arrived wakes the coordinator, once, after two minutes', async ($, on) => {
  // Held for approval in a session on another permission mode: `delivered` still says true.
  const { woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  await run(clock, saved, 30000, {}, at)

  saved.set(SENT, [{ to: 'orch-ears', text: 'BLOCKED phase 4: both branches are irreversible', delivered: true, at: at.now }])
  await run(clock, saved, 105000, {}, at)
  expect(woken).toEqual([])
  await run(clock, saved, 30000, {}, at)
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('phase 4 sent a report 2m ago that has not reached this session')
  expect(woken[0]).toContain('BLOCKED phase 4: both branches are irreversible')

  await run(clock, saved, 10 * 60000, {}, at)
  expect(woken).toHaveLength(1)
})

test('a report that was not delivered wakes the coordinator at once', async ($, on) => {
  const { woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)

  saved.set(SENT, [{ to: 'orch-eras', text: DONE, delivered: false, at: 1000 }])
  await run(clock, saved, 15000, {}, at)
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('phase 4 sent a report that was NOT delivered: DONE phase 4')
})

// --------------------------------------------------------------------------- finishes

test('a turn that ends before its commit exists wakes nobody when the report follows', async ($, on) => {
  // 15:20:30 "phase 4 is finished" -> verify said pending. The commit and report came at 15:24.
  const { files, woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  await run(clock, saved, 30000, {}, at)

  await run(clock, saved, 4 * 60000, { status: 'finished' }, at)
  expect(woken).toEqual([])

  files.ledger.phases[0] = { n: 4, status: 'done', commit: 'b080d87c' }
  saved.set(SENT, [{ to: 'orch-ears', text: DONE, delivered: true, at: at.now }])
  await peerMessage($, DONE)
  await $.tool.call({ tool: 'Bash', command: VERIFY } as any)
  await run(clock, saved, 10 * 60000, { status: 'finished' }, at)
  expect(woken).toEqual([])
})

test('a phase that finished and then never reported is the finish worth a wake', async ($, on) => {
  const { woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  await run(clock, saved, 30000, {}, at)

  await run(clock, saved, 4 * 60000 + 45000, { status: 'finished' }, at)
  expect(woken).toEqual([])
  await run(clock, saved, 30000, { status: 'finished' }, at)
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('phase 4 finished its turn 5m ago and nothing followed')
  expect(woken[0]).toContain('[row swarm/ears/phase/4: status finished')

  await run(clock, saved, 20 * 60000, { status: 'finished' }, at)
  expect(woken).toHaveLength(1)
})

test('a finished phase nobody announced is announced by the deck when no watch runs', async ($, on) => {
  // The 2026-11-11 night: `done` in the ledger, no message tool, no watch, an idle coordinator.
  const { files, woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  await run(clock, saved, 30000, {}, at)

  files.ledger.phases[0] = { n: 4, status: 'done', commit: 'b080d87c' }
  await run(clock, saved, 45000, { status: 'finished' }, at)
  expect(woken).toEqual([])
  await run(clock, saved, 30000, { status: 'finished' }, at)
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('phase 4 is recorded done at b080d87c in the ledger, and this session has not verified since')

  await run(clock, saved, 10 * 60000, { status: 'finished' }, at)
  expect(woken).toHaveLength(1)
})

test('with a watch running, the ledger line is the watch\'s to announce', async ($, on) => {
  const { files, woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  await run(clock, saved, 30000, {}, at)

  files.runtime.watch = { pid: 1, at: at.now / 1000, interval: 10 }
  files.ledger.phases[0] = { n: 4, status: 'done', commit: 'b080d87c' }
  await run(clock, saved, 60000, { status: 'finished' }, at)
  // The watch exits once every phase is terminal; the deck must not pick the line up then.
  delete files.runtime.watch
  await run(clock, saved, 10 * 60000, { status: 'finished' }, at)
  expect(woken).toEqual([])
})

test('a session that ended on unfinished work still wakes the coordinator', async ($, on) => {
  const { woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  await run(clock, saved, 30000, {}, at)

  await run(clock, saved, 15000, { status: 'done' }, at)
  expect(woken).toEqual([])
  await run(clock, saved, 15000, { status: 'done' }, at)
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('phase 4\'s session has ended, and the ledger does not record it done')
})

// --------------------------------------------------------------------------- long shells

const PYTEST = { command: 'engine/.venv/bin/pytest engine/tests -q', startedAt: 30000, agent: false }

test('a long shell is the watch\'s to report while a watch is running', async ($, on) => {
  // 13:54:54 the watch said "SHELL phase 2: running 5m00s (pid 182877) [progressing]";
  // 13:55:07 the deck said "phase 2 has had one shell running 5m". One of them is enough.
  const { files, woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  for (let i = 0; i < 48; i++) {
    files.runtime.watch = { pid: 1, at: at.now / 1000, interval: 10 }
    await run(clock, saved, 15000, { shells: [PYTEST] }, at)
  }
  expect(at.now).toBe(12 * 60000)
  expect(woken).toEqual([])
})

test('with no watch the deck warns about a long shell once, then only every thirty minutes', async ($, on) => {
  const { woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)

  await run(clock, saved, 5 * 60000 + 45000, { shells: [PYTEST] }, at)
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('phase 4 has had one shell running 5m: engine/.venv/bin/pytest engine/tests -q')

  // 10m, 15m, 20m, 25m: the same shell, nothing new to say.
  await run(clock, saved, 23 * 60000, { shells: [PYTEST] }, at)
  expect(woken).toHaveLength(1)
  await run(clock, saved, 3 * 60000, { shells: [PYTEST] }, at)
  expect(woken).toHaveLength(2)
  expect(woken[1]).toContain('one shell running 30m')
})

// --------------------------------------------------------------------------- timing

test('nothing is submitted mid-turn, and what the turn made moot is never sent', async ($, on) => {
  // 14:52:46 a wake was queued behind a ten-minute turn and read, stale, at 15:00:55.
  const { files, woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  await run(clock, saved, 30000, {}, at)

  await $.turn.start({ turnId: 't1' })
  files.ledger.phases[0] = { n: 4, status: 'done', commit: 'b080d87c' }
  await run(clock, saved, 3 * 60000, { status: 'finished' }, at)
  expect(woken).toEqual([])
  // In that same turn the coordinator verifies, as it does on the watch's ACT line.
  await $.tool.call({ tool: 'Bash', command: VERIFY } as any)
  await $.turn.complete({ turnId: 't1', answer: 'ok', durationMs: 10, isAborted: false, usage: null } as any)
  await run(clock, saved, 10 * 60000, { status: 'finished' }, at)
  expect(woken).toEqual([])
})

test('a wake held back by a turn is sent when the turn ends', async ($, on) => {
  const { woken } = coordinator(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const at = { now: 0 }
  await $.session.start(START)
  await run(clock, saved, 30000, {}, at)

  await $.turn.start({ turnId: 't1' })
  saved.set(SENT, [{ to: 'orch-eras', text: DONE, delivered: false, at: at.now }])
  await run(clock, saved, 60000, {}, at)
  expect(woken).toEqual([])
  await $.turn.complete({ turnId: 't1', answer: 'ok', durationMs: 10, isAborted: false, usage: null } as any)
  await run(clock, saved, 15000, {}, at)
  expect(woken).toHaveLength(1)
})
