import { expect, mock, test } from 'claude-code/testing'

const ENTERED = ($: any, e: any) => ({ text: e.text, context: e.context })
const SPAWNED = { model: 'sonnet', agentId: 'a1' }
const SPAWN = { tool_use_id: 't1', prompt: 'verify', description: 'verify', subagentType: 'verifier' } as const

/** A session whose weekly window reads `pct`; `limits` overrides the whole list. */
function week(on: any, pct: number | null, env: Record<string, string> = {}, limits?: unknown[]) {
  mock.env(on, env)
  on('ui.log', () => ({ value: undefined }))
  on('prompt.submit', ENTERED)
  on('agent.spawn', () => SPAWNED)
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

test('usage() throws: fail open', async ($, on) => {
  mock.env(on, {})
  on('prompt.submit', ENTERED)
  on('agent.spawn', () => SPAWNED)
  on('session.usage', () => { throw new Error('boom') })
  expect((await doCmd($)).context ?? []).toEqual([])
  expect(await $.agent.spawn(SPAWN)).toEqual(SPAWNED)
})
