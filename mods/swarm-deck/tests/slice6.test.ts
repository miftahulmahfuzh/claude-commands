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
function asCoordinator(on: any, me: string, env: Record<string, string> = {}) {
  mock.env(on, env)
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.id', () => ({ value: me }))
  on('session.usage', () => USAGE)
  on('command.register', () => ({ value: undefined }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null } }))
  on('fs.list', () => ({ value: [{ name: 'ears', kind: 'dir', size: 0, isLink: false }] }))
  on('fs.read', () => ({ value: JSON.stringify({ slug: 'ears', coordinator_session_id: 'orch' }) }))
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

test('the coordinator is woken when a phase finishes -- once, and not for history', async ($, on) => {
  const woken = asCoordinator(on, 'orch')
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ status: 'working', updatedAt: 0 }) })

  await $.session.start(START)
  // The first refresh only seeds: a coordinator adopting a set mid-run is not woken for it.
  expect(woken).toEqual([])

  saved.set(ROW, row({ status: 'finished', updatedAt: 14000 }))
  await clock.advance(15000)
  expect(woken).toHaveLength(1)
  expect(woken[0]).toContain('phase 4 is finished')
  expect(woken[0]).toContain('swarm.py verify --slug ears --apply')

  saved.set(ROW, row({ status: 'finished', updatedAt: 29000 }))
  await clock.advance(15000)
  expect(woken).toHaveLength(1)
})

test('the coordinator is woken at each threshold a shell crosses -- the progress report', async ($, on) => {
  const woken = asCoordinator(on, 'orch', { MAX_SHELL_SCRIPT_DURATION: '1m' })
  const clock = mock.clock(on)
  const shells = [{ command: 'npm test', startedAt: 0, agent: true }]
  const saved = storeSpy(on, { [ROW]: row({ shells, updatedAt: 0 }) })

  await $.session.start(START)
  for (let t = 15000; t <= 135000; t += 15000) {
    saved.set(ROW, row({ shells, updatedAt: t - 1000 }))
    await clock.advance(15000)
  }
  // 1m and 2m crossed: two wakes, each naming the command and that a subagent runs it.
  expect(woken).toHaveLength(2)
  expect(woken[0]).toContain('one shell running 60s (in a subagent): npm test')
  expect(woken[1]).toContain('2m')
})

test('a session that only watches someone else\'s set is never woken', async ($, on) => {
  const woken = asCoordinator(on, 'a-bystander')
  const clock = mock.clock(on)
  const saved = storeSpy(on, { [ROW]: row({ status: 'working', updatedAt: 0 }) })

  await $.session.start(START)
  saved.set(ROW, row({ status: 'finished', updatedAt: 14000 }))
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
