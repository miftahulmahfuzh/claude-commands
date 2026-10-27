import { expect, mock, test } from 'claude-code/testing'

const START = { surface: 'terminal', isInteractive: true, cwd: '/work' } as const
const USAGE = { value: { startedAt: 0, context: { tokens: 1, window: 100, percent: 1 }, rateLimits: [], cost: {} } }
const ROW = 'swarm/write-gate/phase/2'
const HOUR = 3600_000

const PANE = {
  plugin: 'swarm-deck', component: 'Pane', requestId: 'fleet', surface: 'terminal',
  viewport: { columns: 120, rows: 40 },
  props: { title: 'swarm', isFocused: true, bodyColumns: 64, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const
const BAND = {
  plugin: 'swarm-deck', component: 'AbovePrompt', requestId: 'band', surface: 'terminal',
  viewport: { columns: 120, rows: 40 },
  props: { hasSurvey: false, isWorking: false, maxRows: 4, bodyColumns: 100, scroll: { offset: 0, bodyRows: 4 }, view: {} },
} as const

function storeSpy(on: any, seed: Record<string, unknown> = {}) {
  const saved = new Map<string, unknown>(Object.entries(seed))
  on('store.get', ($: any, e: any) => ({ value: saved.get(e.key) }))
  on('store.set', ($: any, e: any) => { saved.set(e.key, e.value); return { value: undefined } })
  on('store.keys', () => ({ value: [...saved.keys()] }))
  return saved
}

function asPhase(on: any) {
  mock.env(on, { SWARM_SLUG: 'write-gate', SWARM_PHASE: '2', SWARM_COORDINATOR: 'impl-write-gate' })
  on('session.usage', () => USAGE)
  on('session.start', () => ({ cwd: '/work' }))
  on('command.register', () => ({ value: undefined }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }))
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  // Fired through the test's own `$`, so both answer with { value } -- the kit says so
  // in its error, and the shape differs from a hook's own result.
  on('agent.spawn', () => ({ value: { agentId: 'a1' } }))
  on('session.end', () => ({ value: undefined }))
}

/*
 * NOTE ON WHAT IS NOT TESTED HERE.
 *
 * `claude plugin test` cannot fire agent.spawn or session.end through its `$`: both come
 * back "no implementation", with a stub registered, in either result shape, and with no
 * other stub in the file. They are mods API call paths, and the kit says a test cannot
 * fire one -- it has to be triggered through the mod.
 *
 * So the two hooks that write `finalizing` and `done` are verified in a live session
 * instead, and what is tested here is where the logic actually lives: `shown()`, which
 * decides what the deck displays. Rows are seeded directly, which is also closer to the
 * real case -- a coordinator reads rows OTHER sessions wrote.
 */

function row(over: Record<string, unknown> = {}) {
  return { slug: 'write-gate', phase: '3', status: 'working', lastTool: 'Bash', contextPct: 20, updatedAt: 0, ...over }
}

test('a session that said goodbye is never quiet, however long ago it said it', async ($, on) => {
  asPhase(on)
  const clock = mock.clock(on)
  storeSpy(on, { 'swarm/write-gate/phase/3': row({ status: 'done' }) })

  await $.session.start(START)
  await clock.advance(6 * HOUR)
  const ui = await $.ui.mount(PANE)

  // THE FIX. Every row of a finished set used to read QUIET in yellow forever, because
  // "finished cleanly" and "died mid-run" both look like "stopped heartbeating".
  expect(await ui.find({ type: 'Text', text: /done/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /QUIET/ })).toBeUndefined()
  await ui.unmount()

  const band = await $.ui.mount(BAND)
  expect(await band.find({ type: 'Text', text: /gone quiet/ })).toBeUndefined()
  await band.unmount()
})

test('an old silent row is history, not an emergency', async ($, on) => {
  asPhase(on)
  const clock = mock.clock(on)
  // Died mid-run and never said goodbye -- but hours ago.
  storeSpy(on, { 'swarm/write-gate/phase/3': row() })

  await $.session.start(START)
  await clock.advance(3 * HOUR)
  const ui = await $.ui.mount(PANE)

  // Nobody is going to rescue a run that ended this morning, and a yellow row that can
  // never be cleared teaches you to ignore yellow rows.
  expect(await ui.find({ type: 'Text', text: /stale/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /QUIET/ })).toBeUndefined()
  await ui.unmount()

  const band = await $.ui.mount(BAND)
  expect(await band.find({ type: 'Text', text: /gone quiet/ })).toBeUndefined()
  await band.unmount()
})

test('a phase that died minutes ago is still an emergency', async ($, on) => {
  asPhase(on)
  const clock = mock.clock(on)
  storeSpy(on, { 'swarm/write-gate/phase/3': row() })

  await $.session.start(START)
  await clock.advance(5 * 60_000)
  const ui = await $.ui.mount(PANE)
  expect(await ui.find({ type: 'Text', text: /QUIET/ })).toBeDefined()
  await ui.unmount()

  const band = await $.ui.mount(BAND)
  expect(await band.find({ type: 'Text', text: /phase 3 has gone quiet/ })).toBeDefined()
  await band.unmount()
})

test('the endgame and the boot are distinguishable, which they were not before', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  storeSpy(on, {
    'swarm/write-gate/phase/3': row({ phase: '3', status: 'finalizing' }),
    'swarm/write-gate/phase/4': row({ phase: '4', status: 'starting' }),
  })

  await $.session.start(START)
  const ui = await $.ui.mount(PANE)

  // A phase handing off to completion-handler and a phase that has only just booted both
  // used to render `idle`, which is the same word used for a phase that finished.
  expect(await ui.find({ type: 'Text', text: /finalizing/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /starting/ })).toBeDefined()
  await ui.unmount()
})

test('a report that reached nobody stops nagging once the run is over', async ($, on) => {
  asPhase(on)
  const clock = mock.clock(on)
  storeSpy(on, { 'swarm/write-gate/phase/3': row({ status: 'done', undelivered: 2 }) })

  await $.session.start(START)
  await clock.advance(4 * HOUR)
  const band = await $.ui.mount(BAND)

  // It mattered that night. It is not an action item a week later, and a band that
  // cannot be cleared is a band nobody reads.
  expect(await band.find({ type: 'Text', text: /reached nobody/ })).toBeUndefined()
  await band.unmount()
})
