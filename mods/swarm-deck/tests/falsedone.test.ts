import { expect, mock, test } from 'claude-code/testing'

// MEASURED 2026-11-13 on random-twin-yardstick: the coordinator was woken twice with
// "phase 4 is done" while phase 4 was one and five minutes into a thirteen-minute turn.
// A hook in phase 4 had run `claude -p` for a one-turn side call; the child inherited
// SWARM_SLUG / SWARM_PHASE, loaded this mod, and wrote `done` onto phase 4's row on exit.

const START = { surface: 'terminal', isInteractive: true, cwd: '/repo' } as const
const USAGE = { value: { startedAt: 0, context: { tokens: 1, window: 100, percent: 1 }, rateLimits: [], cost: {} } }
const ROW = 'swarm/ears/phase/4'

/** A store that also keeps every write to the phase's row, in order. */
function storeSpy(on: any, seed: Record<string, unknown> = {}) {
  const saved = new Map<string, unknown>(Object.entries(seed))
  const writes: any[] = []
  on('store.get', ($: any, e: any) => ({ value: saved.get(e.key) }))
  on('store.set', ($: any, e: any) => {
    saved.set(e.key, e.value)
    if (e.key === ROW) writes.push(e.value)
    return { value: undefined }
  })
  on('store.keys', () => ({ value: [...saved.keys()] }))
  return { saved, writes }
}

/** A session carrying phase 4's environment, whoever it really is. */
function withPhaseEnv(on: any, me: string) {
  mock.env(on, { SWARM_SLUG: 'ears', SWARM_PHASE: '4', SWARM_COORDINATOR: 'orch-ears' })
  on('session.id', () => ({ value: me }))
  on('session.usage', () => USAGE)
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.end', () => ({ sessionId: me }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null } }))
  on('ui.log', () => ({ value: undefined }))
  on('command.register', () => ({ value: undefined }))
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
}

function asCoordinator(on: any, files: Record<string, () => unknown>) {
  mock.env(on, {})
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.id', () => ({ value: 'orch' }))
  on('session.usage', () => USAGE)
  on('command.register', () => ({ value: undefined }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null } }))
  on('fs.list', () => ({ value: [{ name: 'ears', kind: 'dir', size: 0, isLink: false }] }))
  on('fs.read', ($: any, e: any) => {
    const name = String(e.path).split('/').pop() as string
    if (!files[name]) throw new Error('ENOENT ' + e.path)
    return { value: JSON.stringify(files[name]()) }
  })
  on('ui.log', () => ({ value: undefined }))
  const woken: string[] = []
  on('prompt.submit', ($: any, e: any) => { woken.push(e.text); return { text: e.text } })
  return woken
}

function row(over: Record<string, unknown>) {
  return { slug: 'ears', phase: '4', session: 'phase-4', status: 'working', turns: 1, lastTool: 'Bash',
           contextPct: 10, decided: 0, shells: [], ...over }
}

const LEDGER = () => ({ slug: 'ears', coordinator_session_id: 'orch', phases: [{ n: 4, status: 'spawned' }] })

// ------------------------------------------------------------------ the root cause

test('a headless child that inherited the phase identity never writes the phase row', async ($, on) => {
  withPhaseEnv(on, 'side-call')
  mock.clock(on)
  const { saved, writes } = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })

  // `claude -p`, started by a hook of phase 4: one turn, then it exits.
  await $.session.start({ ...START, isInteractive: false })
  await $.turn.start({ turnId: 't1' })
  await $.turn.complete({ turnId: 't1', reason: 'answer', answer: '' } as any)
  await $.session.end({ reason: 'other' } as any)

  expect(writes.map(w => w.status)).toEqual([])
  expect((saved.get(ROW) as any).status).toBe('working')
})

test('an interactive child does not write over a phase that is still heartbeating', async ($, on) => {
  withPhaseEnv(on, 'child')
  const clock = mock.clock(on)
  const { saved, writes } = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })

  await $.session.start(START)
  await $.turn.start({ turnId: 't1' })
  // The phase itself heartbeats on, as it does every 15s.
  saved.set(ROW, row({ updatedAt: 15000 }))
  await clock.advance(15000)
  await $.session.end({ reason: 'other' } as any)

  expect(writes).toEqual([])
  expect((saved.get(ROW) as any).session).toBe('phase-4')
})

test('a respawned phase takes over a row whose writer is gone, and its own row from then on', async ($, on) => {
  withPhaseEnv(on, 'respawn')
  const clock = mock.clock(on)
  // The first phase 4 was killed: no goodbye, last heartbeat a minute ago.
  const { saved } = storeSpy(on, { [ROW]: row({ session: 'killed', updatedAt: 0 }) })
  await clock.advance(60000)

  await $.session.start(START)
  expect((saved.get(ROW) as any).session).toBe('respawn')
  expect((saved.get(ROW) as any).status).toBe('starting')

  await $.turn.start({ turnId: 't1' })
  expect((saved.get(ROW) as any).status).toBe('working')
  await $.session.end({ reason: 'other' } as any)
  expect((saved.get(ROW) as any).status).toBe('done')
})

test('a phase takes over a row that already said done', async ($, on) => {
  withPhaseEnv(on, 'again')
  mock.clock(on)
  const { saved } = storeSpy(on, { [ROW]: row({ session: 'first', status: 'done', updatedAt: 0 }) })

  await $.session.start(START)
  expect((saved.get(ROW) as any).session).toBe('again')
})

// ------------------------------------------------------------------ the coordinator

test('a done that is gone by the next refresh wakes nobody', async ($, on) => {
  const woken = asCoordinator(on, { 'ledger.json': LEDGER })
  const clock = mock.clock(on)
  const { saved } = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })

  await $.session.start(START)
  // One reading says done; the phase's next heartbeat says it never stopped.
  saved.set(ROW, row({ status: 'done', session: 'side-call', updatedAt: 14000 }))
  await clock.advance(15000)
  saved.set(ROW, row({ status: 'working', updatedAt: 29000 }))
  await clock.advance(15000)
  await clock.advance(15000)

  expect(woken).toEqual([])
})

test('a session that really ended wakes once, on the second reading, and names the row it fired on', async ($, on) => {
  const woken = asCoordinator(on, { 'ledger.json': LEDGER })
  const clock = mock.clock(on)
  const { saved } = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })

  await $.session.start(START)
  saved.set(ROW, row({ status: 'done', turns: 7, lastTool: 'SendMessage', updatedAt: 14000 }))
  await clock.advance(15000)
  expect(woken).toEqual([])
  await clock.advance(15000)
  await clock.advance(15000)

  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('set ears changed')
  expect(woken[0]).toContain('- phase 4\'s session has ended, and the ledger does not record it done, failed ' +
    'or blocked [row swarm/ears/phase/4: status done, turns 7, last tool SendMessage, session phase-4, ' +
    'updated 16s ago]')
})

test('a phase swarm.py reaped is closed: read from .runtime.json, where reap records it', async ($, on) => {
  const runtime: any = { sessions: { '4': { name: 'impl-ears-p4' } }, reaped: {} }
  // The ledger exactly as swarm.py writes it: no reaped_at on any phase, ever.
  const woken = asCoordinator(on, { 'ledger.json': LEDGER, '.runtime.json': () => runtime })
  const clock = mock.clock(on)
  const { saved } = storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })

  await $.session.start(START)
  // The coordinator reaped the window before the deck caught up with its row or its report.
  runtime.sessions = {}
  runtime.reaped = { '4': { phase: 4, reaped_at: '2026-11-13T14:48:11+07:00', how: 'closed (done, verified)' } }
  saved.set(ROW, row({ status: 'done', updatedAt: 14000 }))
  saved.set('swarm/ears/sent/4', [{ text: 'DONE phase 4', at: 14000, delivered: false }])
  for (let i = 0; i < 10; i++) await clock.advance(15000)
  expect(woken).toEqual([])

  // Respawned under the same number: it has a session again, so what it says is news.
  runtime.sessions = { '4': { name: 'impl-ears-p4' } }
  saved.set(ROW, row({ status: 'working', updatedAt: 164000 }))
  saved.set('swarm/ears/sent/4', [{ text: 'DONE phase 4, second run', at: 164000, delivered: false }])
  await clock.advance(15000)
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('DONE phase 4, second run')
})
