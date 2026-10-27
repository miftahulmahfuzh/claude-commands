import { expect, mock, test } from 'claude-code/testing'

const START = { surface: 'terminal', isInteractive: true, cwd: '/work' } as const
const USAGE = { value: { startedAt: 0, context: { tokens: 1, window: 100, percent: 1 }, rateLimits: [], cost: {} } }
const RAN = { result: 'the command ran' }

const BAND = {
  plugin: 'swarm-deck',
  component: 'AbovePrompt',
  requestId: 'band',
  surface: 'terminal',
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
  on('ui.log', () => ({ value: undefined }))
  on('command.register', () => ({ value: undefined }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }))
}

test('a command that would wait on a terminal is refused, with the non-interactive way out', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  storeSpy(on)
  on('tool.call', () => RAN)

  await $.session.start(START)
  const out: any = await $.tool.call({ tool: 'Bash', command: 'git rebase -i HEAD~3' })

  expect(out).not.toEqual(RAN)
  expect(out.deny).toContain('interactive git session')
  // A refusal that does not say what to do instead just moves the stall.
  expect(out.deny).toContain('--no-pager')
})

test('ordinary commands are untouched, including ones that merely mention the words', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  storeSpy(on)
  on('tool.call', () => RAN)

  await $.session.start(START)
  const allowed = [
    'git rebase --onto main HEAD~3',
    'pytest -q',
    'git log --no-pager -5',
    'grep -i foo x.py',
    // A guard that refuses legitimate work is worse than one that misses a case: the
    // phase it blocks has no way around it. These are the over-matches an unanchored
    // pattern produces, and each one is a night lost to the fix rather than the bug.
    'echo "one more thing"',
    'echo "on top of that"',
    "git commit -m 'add -i flag support'",
    'grep -r manager src/',
    'cat topics.txt',
    'python manage.py migrate',
  ]
  for (const command of allowed) {
    expect(await $.tool.call({ tool: 'Bash', command })).toEqual(RAN)
  }
})

test('a pager at the end of a pipe is still a pager', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  storeSpy(on)
  on('tool.call', () => RAN)

  await $.session.start(START)
  for (const command of ['git log | less', 'vim a.txt', 'less notes.md', 'sudo vim /etc/hosts']) {
    const out: any = await $.tool.call({ tool: 'Bash', command })
    expect(out.deny).toBeDefined()
  }
})

test('outside a swarm the shell guard is dormant too', async ($, on) => {
  mock.env(on, {})
  mock.clock(on)
  storeSpy(on)
  on('session.start', () => ({ cwd: '/work' }))
  on('command.register', () => ({ value: undefined }))
  on('tool.call', () => RAN)

  await $.session.start(START)
  expect(await $.tool.call({ tool: 'Bash', command: 'vim notes.md' })).toEqual(RAN)
})

test('a report is mirrored into the store, which no approval gate sits in front of', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  const saved = storeSpy(on)
  on('session.send', () => ({ isDelivered: true }))

  await $.session.start(START)
  await $.session.send({ to: 'impl-write-gate', text: 'phase 2 done, commit abc123' })

  // isDelivered true only means the message reached an inbox -- a message held for the
  // user to approve reports exactly this. So the report does not depend on it.
  const mirrored: any = saved.get('swarm/write-gate/sent/2')
  expect(mirrored).toBeDefined()
  expect(mirrored[0].text).toContain('commit abc123')
  expect((saved.get('swarm/write-gate/phase/2') as any).sent).toBe(1)
})

test('a send that reached nobody is counted against the phase', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  const saved = storeSpy(on)
  on('session.send', () => ({ isDelivered: false, reason: 'nobody by that name' }))

  await $.session.start(START)
  await $.session.send({ to: 'impl-typod-name', text: 'phase 2 done' })

  expect((saved.get('swarm/write-gate/phase/2') as any).undelivered).toBe(1)
})

test('the band stays dark while the set is healthy', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  storeSpy(on)

  await $.session.start(START)
  const ui = await $.ui.mount(BAND)

  // A band that is always lit is noise, and noise is how the one night it matters gets
  // scrolled past. Nothing wrong means Claude Code's own band, untouched.
  expect(await ui.find({ type: 'Text', text: 'drawn by Claude Code' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /gone quiet/ })).toBeUndefined()
  await ui.unmount()
})

test('the band lights for a sibling that went quiet', async ($, on) => {
  asPhase(on)
  const clock = mock.clock(on)
  storeSpy(on, {
    'swarm/write-gate/phase/3': { slug: 'write-gate', phase: '3', status: 'working', contextPct: 70, updatedAt: 0 },
  })

  await $.session.start(START)
  // The heartbeat timer also refreshes the rows, so the band is live without anyone
  // having opened the pane -- which is the whole point of it.
  await clock.advance(120000)
  const ui = await $.ui.mount(BAND)

  expect(await ui.find({ type: 'Text', text: /phase 3 has gone quiet/ })).toBeDefined()
  await ui.unmount()
})

test('a report that reached nobody outranks a quiet sibling on the band', async ($, on) => {
  asPhase(on)
  const clock = mock.clock(on)
  storeSpy(on, {
    'swarm/write-gate/phase/3': { slug: 'write-gate', phase: '3', status: 'working', updatedAt: 0 },
    'swarm/write-gate/phase/4': { slug: 'write-gate', phase: '4', status: 'idle', undelivered: 2, updatedAt: 0 },
  })

  await $.session.start(START)
  await clock.advance(120000)
  const ui = await $.ui.mount(BAND)

  // Quiet may resolve itself; a report addressed to nobody never will.
  expect(await ui.find({ type: 'Text', text: /reached nobody/ })).toBeDefined()
  await ui.unmount()
})
