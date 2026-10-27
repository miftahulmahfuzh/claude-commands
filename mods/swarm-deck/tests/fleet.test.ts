import { expect, mock, test } from 'claude-code/testing'

const START = { surface: 'terminal', isInteractive: true, cwd: '/work' } as const
const USAGE = { value: { startedAt: 0, context: { tokens: 42000, window: 200000, percent: 50 }, rateLimits: [], cost: {} } }

const PANE = {
  plugin: 'swarm-deck',
  component: 'Pane',
  requestId: 'fleet',
  viewport: { columns: 120, rows: 40 },
  props: {
    title: 'swarm write-gate',
    isFocused: true,
    bodyColumns: 64,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

function storeSpy(on: any, seed: Record<string, unknown> = {}) {
  const saved = new Map<string, unknown>(Object.entries(seed))
  on('store.get', ($: any, e: any) => ({ value: saved.get(e.key) }))
  on('store.set', ($: any, e: any) => {
    saved.set(e.key, e.value)
    return { value: undefined }
  })
  on('store.keys', () => ({ value: [...saved.keys()] }))
  return saved
}

function asPhase(on: any) {
  mock.env(on, { SWARM_SLUG: 'write-gate', SWARM_PHASE: '2', SWARM_COORDINATOR: 'impl-write-gate' })
  on('session.usage', () => USAGE)
  on('session.start', () => ({ cwd: '/work' }))
  on('ui.log', () => ({ value: undefined }))
  on('command.register', () => ({ value: undefined }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }))
}

test('/fleet draws a row for every phase that has reported', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  storeSpy(on, {
    'swarm/write-gate/phase/1': { slug: 'write-gate', phase: '1', status: 'idle', lastTool: 'Edit', contextPct: 30, decided: 0, updatedAt: 0 },
    'swarm/write-gate/phase/3': { slug: 'write-gate', phase: '3', status: 'working', lastTool: 'Bash', contextPct: 70, decided: 0, updatedAt: 0 },
    'other-set/phase/1': { slug: 'nope', phase: '1', status: 'working', updatedAt: 0 },
  })

  await $.session.start(START)
  await $.command.run({ command: 'fleet', args: '' })

  // Box and Text only, so the same tree has to draw in all three apps -- that is the
  // whole reason the deck refuses Raster and Image, which are terminal-only.
  for (const surface of ['terminal', 'desktop', 'vscode'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect(await ui.find({ type: 'Text', text: /^p1/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^p2/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^p3/ })).toBeDefined()
    // Keys belonging to another set must not bleed into this deck.
    expect(await ui.find({ type: 'Text', text: 'set write-gate' })).toBeDefined()
    await ui.unmount()
  }
})

test('a phase that stopped heartbeating reads QUIET, not working', async ($, on) => {
  asPhase(on)
  const clock = mock.clock(on)
  // Phase 3 last reported at t=0 and is not this session, so nothing refreshes it.
  storeSpy(on, {
    'swarm/write-gate/phase/3': { slug: 'write-gate', phase: '3', status: 'working', lastTool: 'Bash', contextPct: 70, decided: 0, updatedAt: 0 },
  })

  await $.session.start(START)
  await clock.advance(120000)
  await $.command.run({ command: 'fleet', args: '' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })

  // A row that still says "working" and stopped updating two minutes ago is the picture
  // of the stall this mod exists to remove. It must not read as healthy.
  expect(await ui.find({ type: 'Text', text: /QUIET/ })).toBeDefined()
  await ui.unmount()
})

test('forks decided alone surface on the deck while the night is still going', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  storeSpy(on)
  on('tool.call', () => ({ result: 'the dialog rendered' }))

  await $.session.start(START)
  await $.tool.call({
    tool: 'AskUserQuestion',
    questions: [{ question: 'Which migration numbering should phase 3 use?', options: [] }],
  })
  await $.command.run({ command: 'fleet', args: '' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })

  expect(await ui.find({ type: 'Text', text: 'Decided without asking: 1' })).toBeDefined()
  await ui.unmount()
})

test('a session with no set is told how to name one instead of drawing an empty deck', async ($, on) => {
  mock.env(on, {})
  mock.clock(on)
  storeSpy(on)
  on('session.start', () => ({ cwd: '/work' }))
  on('command.register', () => ({ value: undefined }))

  await $.session.start(START)
  const answer = await $.command.run({ command: 'fleet', args: '' })

  expect(answer.text).toContain('/fleet <slug>')
})
