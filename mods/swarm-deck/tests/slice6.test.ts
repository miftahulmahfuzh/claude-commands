import { expect, mock, test } from 'claude-code/testing'

// Slice 6: nothing in the swarm waits on a person -- not for "is the phase done?", not
// for a shell that hangs, not for a permission dialog. Measured 2026-11-11 on
// ears-acceptance-criteria, where all three happened in one morning.

const START = { surface: 'terminal', isInteractive: true, cwd: '/repo' } as const
const USAGE = { value: { startedAt: 0, context: { tokens: 1, window: 100, percent: 1 }, rateLimits: [], cost: {} } }
const ROW = 'swarm/ears/phase/4'

const PANE = {
  plugin: 'swarm-deck', component: 'Pane', requestId: 'fleet', surface: 'terminal',
  viewport: { columns: 120, rows: 40 },
  props: { title: 'swarm', isFocused: true, bodyColumns: 64, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const
const BAND = {
  plugin: 'swarm-deck', component: 'AbovePrompt', surface: 'terminal',
  viewport: { columns: 120, rows: 40 }, props: {},
} as const

function storeSpy(on: any, seed: Record<string, unknown> = {}) {
  const saved = new Map<string, unknown>(Object.entries(seed))
  on('store.get', ($: any, e: any) => ({ value: saved.get(e.key) }))
  on('store.set', ($: any, e: any) => { saved.set(e.key, e.value); return { value: undefined } })
  on('store.keys', () => ({ value: [...saved.keys()] }))
  return saved
}

function asPhase(on: any, env: Record<string, string> = {}) {
  mock.env(on, { SWARM_SLUG: 'ears', SWARM_PHASE: '4', SWARM_COORDINATOR: 'orch-ears', ...env })
  on('session.usage', () => USAGE)
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null } }))
  on('ui.log', () => ({ value: undefined }))
  on('command.register', () => ({ value: undefined }))
}

/** The coordinator of `ears`, or a bystander when `me` is not the ledger's session. */
function asCoordinator(on: any, me: string, env: Record<string, string> = {},
                       ledger: () => unknown = () => ({ slug: 'ears', coordinator_session_id: 'orch' }),
                       runtime: () => unknown = () => ({})) {
  mock.env(on, env)
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.id', () => ({ value: me }))
  on('session.usage', () => USAGE)
  on('command.register', () => ({ value: undefined }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null } }))
  on('fs.list', () => ({ value: [{ name: 'ears', kind: 'dir', size: 0, isLink: false }] }))
  // Two files live beside each other: the committed ledger and swarm.py's local runtime.
  on('fs.read', ($: any, e: any) => ({
    value: JSON.stringify(String(e.path).endsWith('/.runtime.json') ? runtime() : ledger()),
  }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }))
  on('ui.log', () => ({ value: undefined }))
  const woken: string[] = []
  on('prompt.submit', ($: any, e: any) => { woken.push(e.text); return { text: e.text } })
  return woken
}

function row(over: Record<string, unknown>) {
  return { slug: 'ears', phase: '4', status: 'working', lastTool: 'Bash', contextPct: 10, decided: 0, shells: [], ...over }
}

test('a phase publishes the shell it is running, and clears it when the shell returns', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  const saved = storeSpy(on)
  let during: any = null
  on('tool.call', () => {
    during = (saved.get(ROW) as any).shells
    return { result: 'ok' }
  })

  await $.session.start(START)
  await $.tool.call({ tool: 'Bash', command: 'pytest -q tests/' })

  // While the call was open the row named it; a deck that can only see "working" cannot
  // tell a test run from a hang.
  expect(during).toHaveLength(1)
  expect(during[0].command).toBe('pytest -q tests/')
  expect((saved.get(ROW) as any).shells).toEqual([])
})

test('a backgrounded shell is not timed: it returns at once and is the session\'s to poll', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  const saved = storeSpy(on)
  let during: any = null
  on('tool.call', () => { during = (saved.get(ROW) as any).shells; return { result: 'ok' } })

  await $.session.start(START)
  await $.tool.call({ tool: 'Bash', command: 'npm run build', run_in_background: true })
  expect(during).toEqual([])
})

test('the turn that ran completion-handler ends as finished, not idle', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  const saved = storeSpy(on)
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('agent.spawn', () => ({ model: 'sonnet', agentId: 'a1' }))

  await $.session.start(START)
  await $.turn.start({ turnId: 't1' })
  await $.agent.spawn({ tool_use_id: 't9', subagentType: 'completion-handler', prompt: 'land it', description: 'x' } as any)
  await $.turn.complete({ turnId: 't1', reason: 'answer' } as any)
  // `idle` here is what made a finished phase look like one between turns.
  expect((saved.get(ROW) as any).status).toBe('finished')

  // And it stays finished: a later message to the phase must not hide that it handed off.
  await $.turn.start({ turnId: 't2' })
  expect((saved.get(ROW) as any).status).toBe('finished')
})

test('a shell past MAX_SHELL_SCRIPT_DURATION lights the deck and the band', async ($, on) => {
  asCoordinator(on, 'orch', { MAX_SHELL_SCRIPT_DURATION: '2m' })
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ shells: [{ command: 'pytest -x', startedAt: 0, agent: false }] }) })

  await $.session.start(START)
  // Keep the row fresh, as a live phase's heartbeat would, so the alarm is the shell's.
  await clock.advance(150000)
  saved.set(ROW, row({ shells: [{ command: 'pytest -x', startedAt: 0, agent: false }], updatedAt: 150000 }))
  await $.command.run({ command: 'fleet', args: '' })

  const ui = await $.ui.mount(PANE)
  expect(await ui.find({ type: 'Text', text: 'SHELL' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /sh 3m +pytest -x/ })).toBeDefined()
  await ui.unmount()

  const band = await $.ui.mount(BAND)
  expect(await band.find({ type: 'Text', text: /phase 4: a shell has run 3m -- pytest -x/ })).toBeDefined()
  await band.unmount()
})

test('the coordinator is woken when a phase ends unrecorded -- once, and not for history', async ($, on) => {
  const woken = asCoordinator(on, 'orch')
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ status: 'working', updatedAt: 0 }) })

  await $.session.start(START)
  // The first refresh only seeds: a coordinator adopting a set mid-run is not woken for it.
  expect(woken).toEqual([])

  // One reading is one writer's word: the wake waits for the next refresh to agree.
  saved.set(ROW, row({ status: 'done', updatedAt: 14000 }))
  await clock.advance(15000)
  expect(woken).toEqual([])
  await clock.advance(15000)
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('phase 4\'s session has ended')
  expect(woken[0]).toContain('swarm.py verify --slug ears --apply')

  await clock.advance(15000)
  await clock.advance(15000)
  expect(woken).toHaveLength(1)
})

test('a phase the coordinator reaped never wakes it again, whatever its row or reports do', async ($, on) => {
  const ledger: any = { slug: 'ears', coordinator_session_id: 'orch', phases: [{ n: 4, status: 'done', commit: 'abc1234' }] }
  // Reaped, recorded where swarm.py records it -- the runtime file, never the ledger's phases.
  const runtime: any = { sessions: {}, reaped: { '4': { phase: 4, reaped_at: '2026-11-11T03:30:00Z' } } }
  const woken = asCoordinator(on, 'orch', {}, () => ledger, () => runtime)
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ status: 'finished', updatedAt: 0 }) })

  await $.session.start(START)
  saved.set(ROW, row({ status: 'done', updatedAt: 14000 }))
  saved.set('swarm/ears/sent/4', [{ text: 'DONE phase 4 again', at: 14000, delivered: false }])
  for (let i = 0; i < 12; i++) await clock.advance(15000)
  expect(woken).toEqual([])
})

test('a report stands in for the finish; working again re-arms it', async ($, on) => {
  const woken = asCoordinator(on, 'orch')
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ status: 'working', updatedAt: 0 }) })
  let now = 0
  const tick = async (status: string) => {
    now += 15000
    saved.set(ROW, row({ status, updatedAt: now - 1000 }))
    await clock.advance(15000)
  }

  await $.session.start(START)
  await tick('working')
  // It reported and nobody by that name was there: said at once, and it IS the finish.
  saved.set('swarm/ears/sent/4', [{ text: 'DONE phase 4 at abc1234', at: now, delivered: false }])
  await tick('finished')
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('sent a report that was NOT delivered: DONE phase 4 at abc1234')
  for (let i = 0; i < 28; i++) await tick('finished')
  expect(woken).toHaveLength(1)

  // The coordinator sent it back to work; a finish that nothing follows is news again.
  await tick('working')
  for (let i = 0; i < 22; i++) await tick('finished')
  expect(woken).toHaveLength(2)
  expect(woken[1]).toContain('phase 4 finished its turn 5m ago and nothing followed')
})

test('with no watch running, a long shell wakes the coordinator: at the line, then every sixth', async ($, on) => {
  const woken = asCoordinator(on, 'orch', { MAX_SHELL_SCRIPT_DURATION: '1m' })
  const clock = mock.clock(on)
  const shells = [{ command: 'npm test', startedAt: 0, agent: true }]
  const saved = storeSpy(on, { [ROW]: row({ shells, updatedAt: 0 }) })

  await $.session.start(START)
  for (let t = 15000; t <= 345000; t += 15000) {
    saved.set(ROW, row({ shells, updatedAt: t - 1000 }))
    await clock.advance(15000)
  }
  // 1m crossed; 2m to 5m are the same shell and nothing new.
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('one shell running 60s (in a subagent): npm test')
  for (let t = 360000; t <= 375000; t += 15000) {
    saved.set(ROW, row({ shells, updatedAt: t - 1000 }))
    await clock.advance(15000)
  }
  expect(woken).toHaveLength(2)
  expect(woken[1]).toContain('6m')
})

test('a session that only watches someone else\'s set is never woken', async ($, on) => {
  const woken = asCoordinator(on, 'a-bystander')
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ status: 'working', updatedAt: 0 }) })

  await $.session.start(START)
  saved.set(ROW, row({ status: 'done', updatedAt: 14000 }))
  await clock.advance(15000)
  await clock.advance(15000)
  await clock.advance(15000)
  expect(woken).toEqual([])
})

test('a permission ask in a phase is answered: allowed and logged', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  const saved = storeSpy(on)
  on('tool.check', () => ({ decision: 'ask', reason: 'Dangerous rm operation on possibly-empty variable path' }))

  await $.session.start(START)
  const out: any = await $.tool.check({
    tool: 'Bash', input: { command: 'IDX=$(git rev-parse --git-path index-p4); rm -f "$IDX"' }, approver: 'person',
  } as any)

  // The exact dialog that held phase 4 on 2026-11-11: non-recursive, at worst one file.
  expect(out.decision).toBe('allow')
  const log: any = saved.get('swarm/ears/approvals/4')
  expect(log).toHaveLength(1)
  expect(log[0].verdict).toBe('allowed')
  expect(log[0].asked).toContain('possibly-empty variable path')
})

test('an irreversible ask is denied with a reason the agent can act on, never left open', async ($, on) => {
  asPhase(on)
  mock.clock(on)
  const saved = storeSpy(on)
  on('tool.check', () => ({ decision: 'ask', reason: 'the engine asked' }))
  await $.session.start(START)

  const check = (command: string) =>
    $.tool.check({ tool: 'Bash', input: { command }, approver: 'person' } as any) as Promise<any>

  for (const command of ['rm -rf "$DIR"', 'rm -rf ~', 'sudo rm -fr /', 'cd x && rm -r ..', 'rm -rf /repo',
                         'git push --force origin main']) {
    const out = await check(command)
    expect(out.decision).toBe('deny')
    expect(out.reason).toContain('swarm-deck')
  }
  for (const command of ['rm -rf .workflows/orchestration/x/logs', 'rm -rf "$WT/node_modules"',
                         'git push --force-with-lease origin feature/x', 'rm -rf build']) {
    expect((await check(command)).decision).toBe('allow')
  }
  expect((saved.get('swarm/ears/approvals/4') as any[]).filter(x => x.verdict === 'denied')).toHaveLength(6)
})

test('outside a swarm a permission ask is left to the person', async ($, on) => {
  mock.env(on, {})
  mock.clock(on)
  storeSpy(on)
  on('session.start', () => ({ cwd: '/elsewhere' }))
  on('session.usage', () => USAGE)
  on('command.register', () => ({ value: undefined }))
  on('session.repo', () => ({ value: { root: '/elsewhere', remote: null } }))
  on('fs.list', () => { throw new Error('ENOENT') })
  on('tool.check', () => ({ decision: 'ask', reason: 'the engine asked' }))

  await $.session.start(START)
  const out: any = await $.tool.check({ tool: 'Bash', input: { command: 'rm -f x' }, approver: 'person' } as any)
  expect(out.decision).toBe('ask')
})

test('the live coordinator\'s own asks are answered too', async ($, on) => {
  asCoordinator(on, 'orch')
  mock.clock(on)
  storeSpy(on)
  on('tool.check', () => ({ decision: 'ask', reason: 'the engine asked' }))

  await $.session.start(START)
  const out: any = await $.tool.check({ tool: 'Bash', input: { command: 'rm -f .git/index-p4' }, approver: 'person' } as any)
  expect(out.decision).toBe('allow')
})

test('the coordinator is notified, natively, when its set lands or a phase fails -- once each', async ($, on) => {
  mock.env(on, {})
  const clock = mock.clock(on)
  storeSpy(on, { [ROW]: row({ updatedAt: 0 }) })
  const ledger: any = { slug: 'ears', coordinator_session_id: 'orch',
                        phases: [{ n: 1, status: 'done' }, { n: 2, status: 'spawned' }] }
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.id', () => ({ value: 'orch' }))
  on('session.usage', () => USAGE)
  on('command.register', () => ({ value: undefined }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null } }))
  on('fs.list', () => ({ value: [{ name: 'ears', kind: 'dir', size: 0, isLink: false }] }))
  on('fs.read', () => ({ value: JSON.stringify(ledger) }))
  on('prompt.submit', ($: any, e: any) => ({ text: e.text }))
  const told: string[] = []
  on('ui.notify', ($: any, e: any) => { told.push(e.text); return { value: { isSent: true, channel: 'terminal' } } })

  await $.session.start(START)
  expect(told).toEqual([])

  ledger.phases[1] = { n: 2, status: 'failed', note: 'pytest red' }
  await clock.advance(15000)
  expect(told).toEqual(['ears phase 2 failed: pytest red'])

  ledger.landed = { commit: '74e78853717ea52af0f2cbb67fbfabe93d013ee2' }
  await clock.advance(15000)
  await clock.advance(15000)
  expect(told).toEqual(['ears phase 2 failed: pytest red', 'ears landed: 1/2 phases, main @ 74e7885'])
})
