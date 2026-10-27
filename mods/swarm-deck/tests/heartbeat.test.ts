import { expect, mock, test } from 'claude-code/testing'

const START = { surface: 'terminal', isInteractive: true, cwd: '/work' } as const
const USAGE = { value: { startedAt: 0, context: { tokens: 42000, window: 200000, percent: 21 }, rateLimits: [], cost: {} } }
const ROW = 'swarm/write-gate/phase/2'

function storeSpy(on: any) {
  const saved = new Map<string, unknown>()
  on('store.get', ($: any, e: any) => ({ value: saved.get(e.key) }))
  on('store.set', ($: any, e: any) => {
    saved.set(e.key, e.value)
    return { value: undefined }
  })
  return saved
}

function asPhase(on: any) {
  mock.env(on, { SWARM_SLUG: 'write-gate', SWARM_PHASE: '2', SWARM_COORDINATOR: 'impl-write-gate' })
  on('session.usage', () => USAGE)
  on('session.start', () => ({ cwd: '/work' }))
  on('ui.log', () => ({ value: undefined }))
}

test('a phase publishes a row of its own, keyed so no two sessions collide', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  const saved = storeSpy(on)

  await $.session.start(START)

  // One key per PHASE, not per set: the phases of a set run concurrently, so a shared
  // document would have them losing each other's rows on every write.
  const row: any = saved.get(ROW)
  expect(row).toBeDefined()
  expect(row.slug).toBe('write-gate')
  expect(row.phase).toBe('2')
  expect(row.coordinator).toBe('impl-write-gate')
  expect(row.contextPct).toBe(21)
})

test('the row follows the phase: working, what it last touched, then idle', async ($, on) => {
  asPhase(on)
  const clock = mock.clock(on)
  const saved = storeSpy(on)
  on('tool.call', () => ({ result: 'ok' }))
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))

  await $.session.start(START)
  // A session that has booted but not begun is `starting`, not `idle`. The two used to
  // be indistinguishable, which made a phase that had just launched look like one that
  // had finished.
  expect((saved.get(ROW) as any).status).toBe('starting')

  await $.turn.start({ turnId: 't1' })
  expect((saved.get(ROW) as any).status).toBe('working')

  await $.tool.call({ tool: 'Bash', command: 'pytest -q' })
  await clock.advance(15000)
  expect((saved.get(ROW) as any).lastTool).toBe('Bash')

  await $.turn.complete({ turnId: 't1', answer: 'done', durationMs: 10, isAborted: false, usage: null })
  expect((saved.get(ROW) as any).status).toBe('idle')
})

test('a subagent finishing does not park the phase', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  const saved = storeSpy(on)
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))

  await $.session.start(START)
  await $.turn.start({ turnId: 't1' })
  // A subagent's turn ends while the phase itself is still working. Reading that as
  // idle makes a busy session look parked -- the one misreading a deck built to spot
  // quiet sessions cannot afford.
  await $.turn.complete({ turnId: 't2', agentId: 'sub-1', answer: 'x', durationMs: 5, isAborted: false, usage: null })

  expect((saved.get(ROW) as any).status).toBe('working')
})

test('a refused fork is written down where it outlives the coordinator', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  const saved = storeSpy(on)
  on('tool.call', () => ({ result: 'the dialog rendered' }))

  await $.session.start(START)
  await $.tool.call({
    tool: 'AskUserQuestion',
    questions: [{ question: 'Which migration numbering should phase 3 use?', options: [] }],
  })

  const decided: any = saved.get('swarm/write-gate/decided/2')
  expect(decided).toBeDefined()
  expect(decided.length).toBe(1)
  expect(decided[0].question).toContain('migration numbering')
  // and the row carries the count, so the deck shows it without reading every list
  expect((saved.get(ROW) as any).decided).toBe(1)
})

test('outside a swarm nothing is published at all', async ($, on) => {
  mock.env(on, {})
  const clock = mock.clock(on)
  const saved = storeSpy(on)
  on('session.start', () => ({ cwd: '/work' }))
  on('tool.call', () => ({ result: 'ok' }))

  await $.session.start(START)
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await clock.advance(60000)

  // No heartbeat, no timer, no rows: an ordinary session is not instrumented by a mod
  // it never opted into.
  expect(saved.size).toBe(0)
})
