import { expect, mock, test } from 'claude-code/testing'

// Guard 4: a command that uses a declared shared resource runs under `swarm.py lease`, in
// any session in the repo. Measured 2026-11-11 on mcp-notes session-fork-awareness: two
// phases and the coordinator ran test:int on one Postgres at once, ~5 minutes became ~30.

const START = { surface: 'terminal', isInteractive: true, cwd: '/repo' } as const
const USAGE = { value: { startedAt: 0, context: { tokens: 1, window: 100, percent: 1 }, rateLimits: [], cost: {} } }
const SWARM_PY = "'/home/u/.claude/skills/swarm/swarm.py'"

const SHARED = { resources: { pg: { match: ['npm run test:int', 'scripts/test-int\\.sh'], isolate: 'none' } } }
const ISOLATED = { resources: { pg: { match: ['test:int'], isolate: 'per-checkout' } } }
const CAPPED = { resources: { pg: { match: ['test:int'], isolate: 'per-checkout', max_concurrent: 2 } } }

type Queue = { capacity: number, holding: unknown[], waiting: unknown[] }

/**
 * A session in /repo whose .workflows/swarm.json is `config` (null: no file). Core's own
 * Bash answers with the input it was handed, so a test reads back what would have run.
 */
function inRepo(on: any, config: unknown, queue: Queue | null = { capacity: 1, holding: [], waiting: [] },
                env: Record<string, string> = {}, opts: { brokenRepo?: boolean, raw?: string } = {}) {
  mock.env(on, { HOME: '/home/u', ...env })
  mock.clock(on)
  const saved = new Map<string, unknown>()
  on('store.get', ($: any, e: any) => ({ value: saved.get(e.key) }))
  on('store.set', ($: any, e: any) => { saved.set(e.key, e.value); return { value: undefined } })
  on('store.keys', () => ({ value: [...saved.keys()] }))
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.usage', () => USAGE)
  on('session.id', () => ({ value: 'me' }))
  on('command.register', () => ({ value: undefined }))
  on('ui.log', () => ({ value: undefined }))
  on('session.repo', () => opts.brokenRepo ? { deny: 'simulated failure' } : { value: { root: '/repo', remote: null } })
  on('fs.list', () => ({ value: [] }))
  on('fs.read', ($: any, e: any) => {
    if (opts.raw !== undefined) return { value: opts.raw }
    if (e.path === '/repo/.workflows/swarm.json' && config !== null) return { value: JSON.stringify(config) }
    return { deny: 'ENOENT' }
  })
  const asked: string[][] = []
  on('process.run', ($: any, e: any) => {
    asked.push(e.argv)
    return { value: { stdout: JSON.stringify({ swarm: true, leases: { pg: queue } }), stderr: '', code: 0 } }
  })
  on('tool.call', ($: any, e: any) => ({ result: { ran: e.command, background: e.run_in_background === true } }))
  return asked
}

async function bash($: any, command: string) {
  return await $.tool.call({ tool: 'Bash', command } as any) as any
}

test('a command on a shared resource is rewritten to run under the lease', async ($, on) => {
  inRepo(on, SHARED)
  await $.session.start(START)
  const out = await bash($, 'cd sub && npm run test:int 2>&1 | tail -5')
  expect(out.result.ran).toBe('python3 ' + SWARM_PY + " lease pg --repo '/repo' -- \"${SHELL:-/bin/bash}\" -c " +
    "'cd sub && npm run test:int 2>&1 | tail -5'")
  // Free queue: nothing to wait for, so the call stays in the foreground.
  expect(out.result.background).toBe(false)
})

test('quotes in the command survive the rewrite', async ($, on) => {
  inRepo(on, SHARED)
  await $.session.start(START)
  const out = await bash($, "npm run test:int -- -t 'it\\'s a name'")
  expect(out.result.ran).toContain(`-c 'npm run test:int -- -t '\\''it\\'\\''s a name'\\'''`)
})

test('behind someone, the leased call goes to the background instead of timing out', async ($, on) => {
  inRepo(on, SHARED, { capacity: 1, holding: [{ who: 'p5' }], waiting: [] })
  await $.session.start(START)
  const out = await bash($, 'npm run test:int')
  expect(out.result.ran).toContain(' lease pg ')
  expect(out.result.background).toBe(true)
})

test('an isolated resource with no cap runs as written; a capped one is leased', async ($, on) => {
  inRepo(on, ISOLATED)
  await $.session.start(START)
  expect((await bash($, 'npm run test:int')).result.ran).toBe('npm run test:int')
})

test('max_concurrent on an isolated resource still leases it, to bound the load', async ($, on) => {
  inRepo(on, CAPPED, { capacity: 2, holding: [{ who: 'p2' }], waiting: [] })
  await $.session.start(START)
  const out = await bash($, 'npm run test:int')
  expect(out.result.ran).toContain(' lease pg ')
  expect(out.result.background).toBe(false)
})

test('a command already under a lease, or one that uses nothing declared, is left alone', async ($, on) => {
  const asked = inRepo(on, SHARED)
  await $.session.start(START)
  const leased = "python3 ~/.claude/skills/swarm/swarm.py lease pg -- npm run test:int"
  expect((await bash($, leased)).result.ran).toBe(leased)
  expect((await bash($, 'npm test')).result.ran).toBe('npm test')
  expect(asked).toEqual([])
})

test('a home-made wait on another session\'s test run is refused, pointing at the lease', async ($, on) => {
  inRepo(on, SHARED)
  await $.session.start(START)
  for (const loop of [
    "until ! pgrep -f 'vitest' >/dev/null; do sleep 5; done; npm run test:int",
    "while pgrep -f 'session-fork-awareness-p5/node_modules/.bin/vitest' >/dev/null; do sleep 10; done",
    'until [ -z "$(pgrep -f node_modules/.bin/vitest)" ]; do sleep 10; done',
  ]) {
    const out = await bash($, loop)
    expect(out.deny).toContain('polling the process table')
    expect(out.deny).toContain('pg')
  }
  // A loop that waits on something else is none of this guard's business.
  expect((await bash($, 'until curl -s localhost:7317; do sleep 1; done')).result).toBeDefined()
})

test('a pgrep -f wait loop is refused for any target: it matches its own shell and never ends', async ($, on) => {
  inRepo(on, SHARED)
  await $.session.start(START)
  // MEASURED 2026-11-11: phase 2 hung on exactly this. The Bash call's own `zsh -c` wrapper
  // carries the pattern in its command line, so pgrep -f always finds at least itself.
  const out = await bash($, 'until [ -z "$(pgrep -f my-build-step)" ]; do sleep 10; done')
  expect(out.deny).toContain('its own shell')
})

test('a swarm phase is refused the wait loop even in a repo that declares nothing', async ($, on) => {
  inRepo(on, null, null, { SWARM_SLUG: 'ears', SWARM_PHASE: '4' })
  await $.session.start(START)
  const out = await bash($, "until ! pgrep -f vitest; do sleep 5; done")
  expect(out.deny).toContain('swarm.py lease <resource> -- <command>')
})

test('no declaration, no lease: the command runs as written', async ($, on) => {
  inRepo(on, null)
  await $.session.start(START)
  expect((await bash($, 'npm run test:int')).result.ran).toBe('npm run test:int')
})

test('fails OPEN: a broken lookup leaves the command exactly as written', async ($, on) => {
  inRepo(on, SHARED, undefined, {}, { brokenRepo: true })
  await $.session.start(START)
  expect((await bash($, 'npm run test:int')).result.ran).toBe('npm run test:int')
})

test('a malformed swarm.json is no declaration', async ($, on) => {
  inRepo(on, null, undefined, {}, { raw: '{ "resources": ' })
  await $.session.start(START)
  expect((await bash($, 'npm run test:int')).result.ran).toBe('npm run test:int')
})
