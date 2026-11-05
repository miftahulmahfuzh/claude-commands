import { expect, mock, test } from 'claude-code/testing'

const ENTERED = ($: any, e: any) => ({ text: e.text, context: e.context })
const SPAWNED = { model: 'sonnet', agentId: 'a1' }
const SPAWN = { tool_use_id: 't1', prompt: 'verify', description: 'verify', subagentType: 'verifier' } as const
const OPUS = 'claude-opus-4-7'
const BAND = {
  plugin: 'swarm-deck', component: 'AbovePrompt', requestId: 'band', surface: 'terminal',
  viewport: { columns: 120, rows: 40 },
  props: { hasSurvey: false, isWorking: false, maxRows: 4, bodyColumns: 100, scroll: { offset: 0, bodyRows: 4 }, view: {} },
} as const

// Every spawn that reached the end of the chain, and every quota file write, since week().
let spawns: any[] = []
let writes: any[] = []

/**
 * A session whose weekly window reads `pct` and whose model is `model`. `limits` overrides
 * the whole rateLimits list.
 */
function week(on: any, pct: number | null, env: Record<string, string> = {}, limits?: unknown[], model = 'claude-sonnet-5-5') {
  spawns = []
  writes = []
  mock.env(on, env)
  mock.clock(on)
  on('ui.log', () => ({ value: undefined }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }))
  on('prompt.submit', ENTERED)
  on('session.model', () => ({ value: model }))
  on('fs.write', (_: any, e: any) => { writes.push(e); return { value: undefined } })
  on('agent.spawn', ($: any, e: any) => { spawns.push(e); return SPAWNED })
  on('session.usage', () => ({ value: { startedAt: 0, context: { tokens: 1, window: 100, percent: 1 }, cost: {},
    rateLimits: limits ?? (pct === null ? [] : [
      { kind: 'five_hour', percentUsed: 99, resetsAt: '2026-11-06T00:00:00Z' },
      { kind: 'seven_day', percentUsed: pct, resetsAt: '2026-11-09T00:00:00Z' }]) } }))
}

const doCmd = ($: any) => $.prompt.submit({ text: '/do T1', command: { name: 'do', args: 'T1' }, wait: false, origin: { kind: 'composer' } })

test('under threshold: no quota line, verifier spawns', async ($, on) => {
  week(on, 84)
  expect((await doCmd($)).context ?? []).toEqual([])
  expect(await $.agent.spawn(SPAWN)).toEqual(SPAWNED)
})

test('at threshold: quota line attached and verifier denied', async ($, on) => {
  week(on, 85)
  const out = await doCmd($)
  expect(out.context).toHaveLength(1)
  expect(out.context[0]).toContain('Weekly quota 85% used (resets 2026-11-09T00:00:00Z) -- ECONOMY MODE')
  const spawn = await $.agent.spawn(SPAWN)
  expect(spawn.deny).toContain('self-verified (quota economy, 85%)')
  // only the verifier is refused
  expect(await $.agent.spawn({ ...SPAWN, subagentType: 'Explore' })).toEqual(SPAWNED)
})

test('over threshold on /analyze too', async ($, on) => {
  week(on, 96)
  const out = await $.prompt.submit({ text: '/analyze x', command: { name: 'analyze', args: 'x' }, wait: false, origin: { kind: 'composer' } })
  expect(out.context[0]).toContain('96% used')
})

test('no rateLimits (off a subscription): normal mode', async ($, on) => {
  week(on, null)
  expect((await doCmd($)).context ?? []).toEqual([])
  expect(await $.agent.spawn(SPAWN)).toEqual(SPAWNED)
})

test('no seven_day window: normal mode', async ($, on) => {
  week(on, 0, {}, [{ kind: 'five_hour', percentUsed: 99 }])
  expect(await $.agent.spawn(SPAWN)).toEqual(SPAWNED)
})

test('CLAUDE_QUOTA_ECONOMY_PCT moves the threshold', async ($, on) => {
  week(on, 60, { CLAUDE_QUOTA_ECONOMY_PCT: '50' })
  expect((await $.agent.spawn(SPAWN)).deny).toContain('60%')
})

test('CLAUDE_QUOTA_ECONOMY_PCT raised: 90% is normal under 95', async ($, on) => {
  week(on, 90, { CLAUDE_QUOTA_ECONOMY_PCT: '95' })
  expect(await $.agent.spawn(SPAWN)).toEqual(SPAWNED)
})

test('under threshold: models untouched', async ($, on) => {
  week(on, 84)
  await $.agent.spawn({ prompt: 'x', subagentType: 'Explore' })
  await $.agent.spawn({ prompt: 'x', subagentType: 'Explore', model: 'opus' })
  expect(spawns.map(s => s.model)).toEqual([undefined, 'opus'])
})

test('at threshold: an unnamed spawn becomes sonnet', async ($, on) => {
  week(on, 85)
  await $.agent.spawn({ prompt: 'x', subagentType: 'Explore' })
  expect(spawns[0].model).toBe('sonnet')
})

test('at threshold: opus and fable rewritten, explicit haiku and sonnet kept', async ($, on) => {
  week(on, 90)
  for (const model of ['opus', 'fable', OPUS, 'haiku', 'sonnet']) {
    await $.agent.spawn({ prompt: 'x', subagentType: 'Explore', model })
  }
  expect(spawns.map(s => s.model)).toEqual(['sonnet', 'sonnet', 'sonnet', 'haiku', 'sonnet'])
})

test('at threshold: a fork of an opus parent is denied', async ($, on) => {
  week(on, 90)
  const out = await $.agent.spawn({ prompt: 'x', fork: true, parentModel: OPUS } as any)
  expect(out.deny).toBe('economy mode: a fork inherits claude-opus-4-7; dispatch a named subagent with model sonnet instead')
  expect(spawns).toHaveLength(0)
})

test('at threshold: a fork of a sonnet parent passes', async ($, on) => {
  week(on, 90)
  await $.agent.spawn({ prompt: 'x', fork: true, parentModel: 'sonnet' } as any)
  expect(spawns).toHaveLength(1)
})

test('at threshold: the verifier is still denied when it names opus', async ($, on) => {
  week(on, 90)
  const out = await $.agent.spawn({ ...SPAWN, model: 'opus' })
  expect(out.deny).toContain('self-verified (quota economy, 90%)')
  expect(spawns).toHaveLength(0)
})

test('opus session at threshold: context line and band say to switch', async ($, on) => {
  week(on, 90, {}, undefined, OPUS)
  const out = await doCmd($)
  expect(out.context[0]).toContain('This session runs claude-opus-4-7; economy mode requires sonnet/haiku -- switch with /model sonnet')
  const band = await $.ui.mount(BAND)
  expect(await band.find({ type: 'Text', text: /economy mode requires sonnet\/haiku/ })).toBeDefined()
  await band.unmount()
})

test('sonnet session at threshold: band stays quiet', async ($, on) => {
  week(on, 90)
  await doCmd($)
  const band = await $.ui.mount(BAND)
  expect(await band.find({ type: 'Text', text: /economy mode requires/ })).toBeUndefined()
  await band.unmount()
})

test('quota file: economy reading written for swarm.py', async ($, on) => {
  week(on, 90, { HOME: '/home/t' })
  await doCmd($)
  expect(writes[writes.length - 1].path).toBe('/home/t/.claude/swarm-deck/quota.json')
  expect(JSON.parse(writes[writes.length - 1].text)).toMatchObject({
    seven_day: 90, threshold: 85, economy: true, resetsAt: '2026-11-09T00:00:00Z' })
})

test('quota file: under threshold it says economy false', async ($, on) => {
  week(on, 84, { HOME: '/home/t' })
  await doCmd($)
  expect(JSON.parse(writes[writes.length - 1].text)).toMatchObject({ seven_day: 84, economy: false })
})

test('usage() throws: fail open, models untouched', async ($, on) => {
  mock.env(on, {})
  mock.clock(on)
  spawns = []
  on('prompt.submit', ENTERED)
  on('agent.spawn', ($: any, e: any) => { spawns.push(e); return SPAWNED })
  on('session.usage', () => { throw new Error('boom') })
  expect((await doCmd($)).context ?? []).toEqual([])
  expect(await $.agent.spawn(SPAWN)).toEqual(SPAWNED)
  await $.agent.spawn({ prompt: 'x', subagentType: 'Explore', model: 'opus' })
  expect(spawns[spawns.length - 1].model).toBe('opus')
})
