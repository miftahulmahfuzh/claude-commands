import { expect, mock, test } from 'claude-code/testing'

const START = { surface: 'terminal', isInteractive: true, cwd: '/repo' } as const
const USAGE = { value: { startedAt: 0, context: { tokens: 1, window: 100, percent: 1 }, rateLimits: [], cost: {} } }
const PASSED_THROUGH = { result: 'the dialog rendered' }

const PANE = {
  plugin: 'swarm-deck', component: 'Pane', requestId: 'fleet', surface: 'terminal',
  viewport: { columns: 120, rows: 40 },
  props: { title: 'swarm', isFocused: true, bodyColumns: 64, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

function storeSpy(on: any, seed: Record<string, unknown> = {}) {
  const saved = new Map<string, unknown>(Object.entries(seed))
  on('store.get', ($: any, e: any) => ({ value: saved.get(e.key) }))
  on('store.set', ($: any, e: any) => { saved.set(e.key, e.value); return { value: undefined } })
  on('store.keys', () => ({ value: [...saved.keys()] }))
  return saved
}

/** A coordinator: no SWARM_* identity, but a repo with orchestration directories. */
function asCoordinator(on: any, sets: string[]) {
  mock.env(on, {})
  on('session.start', () => ({ cwd: '/repo' }))
  on('command.register', () => ({ value: undefined }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null } }))
  // kind is 'dir'. Writing 'directory' here once made this suite agree with a bug in
  // the code it was testing, which a stub written from memory will always risk.
  on('fs.list', () => ({ value: sets.map(name => ({ name, kind: 'dir', size: 0, isLink: false })) }))
  // A file alongside the set directories must not be read as a set.
  on('fs.stat', () => ({ value: { kind: 'dir' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }))
  on('session.usage', () => USAGE)
}

test('the deck is NOT a guard: a discovered set must never arm the refusal', async ($, on) => {
  asCoordinator(on, ['portfolio-access-grant'])
  mock.clock(on)
  storeSpy(on)
  on('tool.call', () => PASSED_THROUGH)

  await $.session.start(START)
  const out = await $.tool.call({
    tool: 'AskUserQuestion',
    questions: [{ question: 'Ship it?', options: [] }],
  })

  // Identity arms the guard; discovery only points the dashboard. If these two ever get
  // merged, an ordinary session in a repo that once ran a swarm stops being able to ask
  // its user anything -- so this is the test that keeps them apart.
  expect(out).toEqual(PASSED_THROUGH)
  expect(await $.tool.call({ tool: 'Bash', command: 'vim notes.md' })).toEqual(PASSED_THROUGH)
})

test('a coordinator adopts the one set in its repo and keeps refreshing', async ($, on) => {
  asCoordinator(on, ['portfolio-access-grant'])
  const clock = mock.clock(on)
  const saved = storeSpy(on)

  await $.session.start(START)

  // SHIPPED BUG, slice 4: the refresh timer sat in a phase-only branch, so a coordinator
  // got one snapshot and a deck that never moved again.
  saved.set('swarm/portfolio-access-grant/phase/1', {
    slug: 'portfolio-access-grant', phase: '1', status: 'working', lastTool: 'Bash', contextPct: 10, updatedAt: 0,
  })
  await clock.advance(15000)

  const ui = await $.ui.mount(PANE)
  expect(await ui.find({ type: 'Text', text: /^p1/ })).toBeDefined()
  await ui.unmount()
})

test('/fleet adopts the single set when the session started before it existed', async ($, on) => {
  // A coordinator runs /analyze, which CREATES .workflows/orchestration/<slug>/. At its
  // session.start there was nothing to discover, so the command path has to adopt too --
  // and the first version told the user there were "several" of exactly one, because the
  // tests covered zero sets and two but never one through this path.
  asCoordinator(on, ['portfolio-access-grant'])
  mock.clock(on)
  const saved = storeSpy(on, {
    'swarm/portfolio-access-grant/phase/1': { slug: 'portfolio-access-grant', phase: '1', status: 'idle', updatedAt: 0 },
  })

  await $.session.start(START)
  const answer = await $.command.run({ command: 'fleet', args: '' })

  // Opened the pane, said nothing.
  expect(answer.text).toBeUndefined()
  const ui = await $.ui.mount(PANE)
  expect(await ui.find({ type: 'Text', text: 'set portfolio-access-grant' })).toBeDefined()
  await ui.unmount()
})

test('several sets are listed, never guessed between', async ($, on) => {
  asCoordinator(on, ['portfolio-access-grant', 'swarm-write-set-gate'])
  mock.clock(on)
  storeSpy(on)

  await $.session.start(START)
  const answer = await $.command.run({ command: 'fleet', args: '' })

  // A deck confidently showing the wrong run is worse than one that asks.
  expect(answer.text).toContain('/fleet portfolio-access-grant')
  expect(answer.text).toContain('/fleet swarm-write-set-gate')
})

test('a repo that never ran a set says so', async ($, on) => {
  asCoordinator(on, [])
  mock.clock(on)
  storeSpy(on)

  await $.session.start(START)
  const answer = await $.command.run({ command: 'fleet', args: '' })
  expect(answer.text).toContain('no orchestrated set in this repo')
  // Claude Code prints the plugin's name in front of a command's text, so repeating it
  // here renders as "swarm-deck: swarm-deck: ...".
  expect(answer.text).not.toContain('swarm-deck:')
})

test('the mirrored report is readable on the deck, not merely stored', async ($, on) => {
  asCoordinator(on, ['write-gate'])
  mock.clock(on)
  storeSpy(on, {
    'swarm/write-gate/phase/3': { slug: 'write-gate', phase: '3', status: 'idle', updatedAt: 0 },
    'swarm/write-gate/sent/3': [
      { to: 'impl-write-gate', text: 'phase 3 done, migration 0004 regenerated from the merged schema', at: 0, delivered: false },
    ],
  })

  await $.session.start(START)
  await $.command.run({ command: 'fleet', args: '' })
  const ui = await $.ui.mount(PANE)

  // The whole point of mirroring: a report held behind an approval gate is still
  // readable here, so the night is slow rather than lost.
  expect(await ui.find({ type: 'Text', text: /migration 0004 regenerated/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /reached nobody -- read it here/ })).toBeDefined()
  await ui.unmount()
})

/**
 * A coordinator whose repo's sets and ledgers can change under it, as they do when
 * /analyze-orchestrator creates its own set after the session started.
 */
function asLiveCoordinator(on: any, sets: string[], ledgers: Record<string, unknown>, sessionId: string) {
  mock.env(on, {})
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.id', () => ({ value: sessionId }))
  on('command.register', () => ({ value: undefined }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null } }))
  on('fs.list', () => ({ value: sets.map(name => ({ name, kind: 'dir', size: 0, isLink: false })) }))
  on('fs.read', ($: any, e: any) => {
    const slug = e.path.split('/').slice(-2)[0]
    if (!(slug in ledgers)) throw new Error('ENOENT ' + e.path)
    return { value: JSON.stringify(ledgers[slug]) }
  })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }))
  on('session.usage', () => USAGE)
}

test('a coordinator started beside a landed set gets its OWN set on /fleet, not the old one', async ($, on) => {
  // SHIPPED BUG: orch-chat-bar-brain started while notes-spine-images-ui -- landed an hour
  // earlier -- was the only directory under .workflows/orchestration/. It was adopted
  // silently at session.start and /fleet kept drawing it after chat-bar-brain existed.
  const sets = ['notes-spine-images-ui']
  const ledgers: Record<string, unknown> = {
    'notes-spine-images-ui': { slug: 'notes-spine-images-ui', coordinator_session_id: 'old', landed: { commit: 'abc' } },
  }
  asLiveCoordinator(on, sets, ledgers, 'me')
  mock.clock(on)
  storeSpy(on, {
    'swarm/notes-spine-images-ui/phase/1': { slug: 'notes-spine-images-ui', phase: '1', status: 'done', updatedAt: 0 },
    'swarm/chat-bar-brain/phase/1': { slug: 'chat-bar-brain', phase: '1', status: 'working', updatedAt: 0 },
  })

  await $.session.start(START)
  sets.push('chat-bar-brain')
  ledgers['chat-bar-brain'] = { slug: 'chat-bar-brain', coordinator_session_id: 'me' }
  const answer = await $.command.run({ command: 'fleet', args: '' })

  expect(answer.text).toBeUndefined()
  const ui = await $.ui.mount(PANE)
  expect(await ui.find({ type: 'Text', text: 'set chat-bar-brain' })).toBeDefined()
  await ui.unmount()
})

test('a set this session coordinates wins over other live sets', async ($, on) => {
  asLiveCoordinator(on, ['a-set', 'b-set'], {
    'a-set': { slug: 'a-set', coordinator_session_id: 'someone-else' },
    'b-set': { slug: 'b-set', coordinator_session_id: 'me' },
  }, 'me')
  mock.clock(on)
  storeSpy(on)

  await $.session.start(START)
  const answer = await $.command.run({ command: 'fleet', args: '' })

  expect(answer.text).toBeUndefined()
  const ui = await $.ui.mount(PANE)
  expect(await ui.find({ type: 'Text', text: 'set b-set' })).toBeDefined()
  await ui.unmount()
})

test('a landed set is never adopted silently, but can still be named', async ($, on) => {
  asLiveCoordinator(on, ['old-set'], { 'old-set': { slug: 'old-set', landed: { commit: 'abc' } } }, 'me')
  mock.clock(on)
  storeSpy(on)

  await $.session.start(START)
  // One directory, but it is history: listed, not adopted.
  expect((await $.command.run({ command: 'fleet', args: '' })).text).toContain('/fleet old-set')

  expect((await $.command.run({ command: 'fleet', args: 'old-set' })).text).toBeUndefined()
  const ui = await $.ui.mount(PANE)
  expect(await ui.find({ type: 'Text', text: 'set old-set' })).toBeDefined()
  await ui.unmount()
})
