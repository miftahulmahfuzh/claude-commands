import { expect, mock, test } from 'claude-code/testing'

/** Stub the store with a Map the test can read back. Returns the Map. */
function storeSpy(on: any) {
  const saved = new Map<string, unknown>()
  on('store.get', ($: any, e: any) => ({ value: saved.get(e.key) }))
  on('store.set', ($: any, e: any) => {
    saved.set(e.key, e.value)
    return { value: undefined }
  })
  return saved
}

/** The shape $.session.usage() answers with. */
const USAGE = { value: { startedAt: 0, context: { tokens: 42000, window: 200000, percent: 21 }, rateLimits: [], cost: {} } }

const START = { surface: 'terminal', isInteractive: true, cwd: '/work' } as const
const QUESTION = {
  tool: 'AskUserQuestion',
  questions: [{ question: 'Which migration numbering should phase 3 use?', options: [] }],
} as const

/** Claude Code's own answer, so a test can tell "passed through" from "denied". */
const PASSED_THROUGH = { result: 'the dialog rendered' }

test('a phase session cannot ask: the dialog is refused and the ladder is handed back', async ($, on) => {
  mock.env(on, { SWARM_SLUG: 'swarm-write-set-gate', SWARM_PHASE: '2', SWARM_COORDINATOR: 'impl-swarm-write-set-gate' })
  mock.clock(on)
  storeSpy(on)
  on('session.usage', () => USAGE)
  on('session.start', () => ({ cwd: '/work' }))
  on('ui.log', () => ({ value: undefined }))
  on('tool.call', () => PASSED_THROUGH)

  await $.session.start(START)
  const out = await $.tool.call(QUESTION)

  // Denied, not passed on: Claude Code's own behaviour never ran.
  expect(out).not.toEqual(PASSED_THROUGH)
  expect(out.deny).toBeDefined()
  // The refusal has to be actionable, or the phase just stops instead of deciding.
  expect(out.deny).toContain('phase 2')
  expect(out.deny).toContain('swarm-write-set-gate')
  expect(out.deny).toContain('an invariant in CLAUDE.md or the plan index')
  expect(out.deny).toContain('completion_report.decisions')
})

test('the guard fails CLOSED: a hook that throws still refuses the dialog', async ($, on) => {
  mock.env(on, { SWARM_SLUG: 'swarm-write-set-gate', SWARM_PHASE: '2' })
  mock.clock(on)
  storeSpy(on)
  on('session.usage', () => USAGE)
  on('session.start', () => ({ cwd: '/work' }))
  // Make the guard's own $.ui.log reject, so the hook throws before reaching next().
  // A skipped hook would let the dialog render -- the exact stall this mod removes.
  on('ui.log', () => ({ deny: 'simulated hook failure' }))
  on('tool.call', () => PASSED_THROUGH)

  await $.session.start(START)
  const out = await $.tool.call(QUESTION)

  expect(out).not.toEqual(PASSED_THROUGH)
  expect(out.deny).toContain('phase 2')
})

test('outside a swarm the guard is dormant and the dialog is untouched', async ($, on) => {
  // No SWARM_* variables: an ordinary interactive session.
  mock.env(on, {})
  mock.clock(on)
  storeSpy(on)
  on('session.start', () => ({ cwd: '/work' }))
  on('tool.call', () => PASSED_THROUGH)

  await $.session.start(START)
  const out = await $.tool.call(QUESTION)

  // This mod denies a tool in EVERY session on the machine. Dormancy outside a swarm
  // is the safety property the whole design rests on, so it is pinned here.
  expect(out).toEqual(PASSED_THROUGH)
})
