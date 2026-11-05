import { expect, mock, test } from 'claude-code/testing'

const HOME = '/home/u'
const GATE = HOME + '/.claude/skills/swarm/plan_graph.py'
const WT = '/wt/seer-adversarial'
const INDEX = WT + '/.workflows/plan/SEER_ADVERSARIAL_PLAN.md'
const MAIN = '/repo'
const ORCH = MAIN + '/.workflows/orchestration/seer-adversarial'

/** What the engine itself answers for a prompt that entered: the text and its context. */
const ENTERED = ($: any, e: any) => ({ text: e.text, context: e.context })

/** plan_graph.py --json, as the real one prints it: present plans carry plan_path. */
function graph(root: string, n: number, gone: number[] = []) {
  const phases = []
  const missing = []
  for (let i = 1; i <= n; i++) {
    const cell = '.workflows/plan/seer-adversarial/phase-' + i + '.md'
    const absent = gone.includes(i)
    phases.push({ n: i, title: 'Phase ' + i, depends_on: [], wave: 0, writes: [], plan: cell,
                  plan_path: absent ? null : root + '/' + cell, plan_bytes: absent ? null : 1000 * i })
    if (absent) missing.push({ phase: i, plan: cell, tried: root + '/' + cell })
  }
  return { slug: 'seer-adversarial', index: 'x', root, phases, collisions: [], missing_plans: missing }
}

/**
 * A session in `cwd` over a small filesystem. `files` maps a path to its text, `dirs` a
 * directory to its sub-directories; `graphs` maps an index to plan_graph's JSON for it.
 * Every process.run is recorded, so a test can say the gate was never asked.
 */
function world(on: any, opts: { cwd?: string, files?: Record<string, string>,
                                 dirs?: Record<string, string[]>, graphs?: Record<string, unknown> }) {
  const files = opts.files || {}
  const runs: string[][] = []
  mock.env(on, { HOME })
  on('session.cwd', () => ({ value: opts.cwd || WT }))
  on('fs.exists', ($: any, e: any) => ({ value: e.path in files }))
  on('fs.read', ($: any, e: any) => {
    if (!(e.path in files)) throw new Error('ENOENT ' + e.path)
    return { value: files[e.path] }
  })
  on('fs.stat', ($: any, e: any) => {
    if (!(e.path in files)) throw new Error('ENOENT ' + e.path)
    return { value: { kind: 'file', size: files[e.path]!.length, mtimeMs: 0, isLink: false } }
  })
  on('fs.list', ($: any, e: any) => {
    const subs = (opts.dirs || {})[e.path]
    if (!subs) throw new Error('ENOENT ' + e.path)
    return { value: subs.map(name => ({ name, kind: 'dir', size: 0, mtimeMs: 0, isLink: false })) }
  })
  on('process.run', ($: any, e: any) => {
    runs.push([...e.argv])
    const ok = (stdout: string, exitCode = 0) =>
      ({ value: { exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } })
    if (e.argv[0] === 'git') return ok(MAIN + '/.git\n')
    const index = e.argv[e.argv.length - 1]
    const g = (opts.graphs || {})[index]
    // Exit 1 with the JSON on stdout is how the real gate reports a missing plan.
    return g ? ok(JSON.stringify(g), 1) : ok('', 1)
  })
  on('prompt.submit', ENTERED)
  return runs
}

function submit($: any, name: string, args: string) {
  const text = '/' + name + ' ' + args
  return $.prompt.submit({ text, command: { name, args }, wait: false, origin: { kind: 'composer' } })
}

test('all phase plans present: one block names each by absolute path and size', async ($, on) => {
  const runs = world(on, { files: { [INDEX]: '# Plan' }, graphs: { [INDEX]: graph(WT, 7) } })

  const out = await submit($, 'analyze-orchestrator', '-f .workflows/plan/SEER_ADVERSARIAL_PLAN.md')

  // The prompt itself is untouched: the answer rides beside it, where the user never sees it.
  expect(out.text).toBe('/analyze-orchestrator -f .workflows/plan/SEER_ADVERSARIAL_PLAN.md')
  expect(out.context).toHaveLength(1)
  const block = out.context![0]!
  expect(block).toContain('index: ' + INDEX)
  expect(block).toContain('resolved against root: ' + WT)
  // MEASURED: phase-7.md was the one an `ls | head` cut off. It is named here regardless.
  expect(block).toContain('phase 7: ' + WT + '/.workflows/plan/seer-adversarial/phase-7.md (7000 bytes)')
  expect(block).toContain('All 7 phase plans are present; do not re-list or search for them.')
  // The gate was asked, by the relative path made absolute against the session cwd.
  expect(runs).toContainEqual(['python3', GATE, '--json', INDEX])
})

test('one phase plan missing: it is named with the path tried and the root', async ($, on) => {
  world(on, { files: { [INDEX]: '# Plan' }, graphs: { [INDEX]: graph(WT, 7, [7]) } })

  const out = await submit($, 'analyze-orchestrator', '-f ' + INDEX)

  const block = out.context![0]!
  expect(block).toContain('phase 7: MISSING -- Plan cell `.workflows/plan/seer-adversarial/phase-7.md`, tried ' +
    WT + '/.workflows/plan/seer-adversarial/phase-7.md')
  expect(block).toContain('resolved against root: ' + WT)
  expect(block).toContain('1 of 7 phase plans are missing: phase 7.')
  expect(block).not.toContain('All 7 phase plans are present')
})

test('/implement --phase N gets that phase alone, beside the index', async ($, on) => {
  world(on, { files: { [INDEX]: '# Plan' }, graphs: { [INDEX]: graph(WT, 7) } })

  const out = await submit($, 'implement', '-f ' + INDEX + ' --phase 3')

  const block = out.context![0]!
  expect(block).toContain('index: ' + INDEX)
  expect(block).toContain('phase 3: ' + WT + '/.workflows/plan/seer-adversarial/phase-3.md (3000 bytes)')
  // The main context holds only the phase it is implementing (implement.md Step 2).
  expect(block).not.toContain('phase-2.md')
  expect(block).toContain("Phase 3's plan is present")
})

test('--resume finds the index through the ledger\'s plan field', async ($, on) => {
  world(on, {
    cwd: MAIN,
    files: {
      [ORCH + '/ledger.json']: JSON.stringify({ slug: 'seer-adversarial', plan: INDEX }),
      [INDEX]: '# Plan',
    },
    graphs: { [INDEX]: graph(WT, 7) },
  })

  const out = await submit($, 'analyze-orchestrator', '--resume seer-adversarial')

  expect(out.context![0]).toContain('index: ' + INDEX)
  expect(out.context![0]).toContain('All 7 phase plans are present')
})

test('--resume with the worktree gone falls back to the durable copy and its phase-N.md', async ($, on) => {
  const durable = ORCH + '/PLAN.md'
  const files: Record<string, string> = {
    [ORCH + '/ledger.json']: JSON.stringify({ slug: 'seer-adversarial', plan: INDEX }),
    [durable]: '# Plan',
  }
  for (let i = 1; i <= 7; i++) files[ORCH + '/phase-' + i + '.md'] = 'x'.repeat(i)
  world(on, {
    cwd: MAIN,
    files,
    dirs: { [MAIN + '/.workflows/orchestration']: ['seer-adversarial'] },
    // Against the main checkout the worktree's Plan cells resolve to nothing.
    graphs: { [durable]: graph(MAIN, 7, [1, 2, 3, 4, 5, 6, 7]) },
  })

  // A bare --resume: exactly one unlanded set, so it is the one.
  const out = await submit($, 'analyze-orchestrator', '--resume')

  const block = out.context![0]!
  expect(block).toContain('index: ' + durable)
  expect(block).toContain('phase 7: ' + ORCH + '/phase-7.md (7 bytes) -- the durable copy beside the index')
  expect(block).toContain('All 7 phase plans are present')
})

test('garbage arguments pass the prompt through untouched, and the gate is never run', async ($, on) => {
  const runs = world(on, { files: {}, graphs: {} })

  for (const args of ['', '--status seer-adversarial', '-f', '-f does/not/exist.md', '--phase x']) {
    const out = await submit($, 'analyze-orchestrator', args)
    // No block at all, not an empty one: fail OPEN means the prompt as typed.
    expect(out.context).toBeUndefined()
    expect(out.text).toBe('/analyze-orchestrator ' + args)
  }
  expect(runs.filter(r => r[0] === 'python3')).toEqual([])
})

test('a gate that crashes or prints nonsense still lets the prompt through', async ($, on) => {
  world(on, { files: { [INDEX]: '# Plan' }, graphs: {} })

  // stdout '' -> JSON.parse throws inside the hook. The .catch replays next(e).
  const out = await submit($, 'implement', '-f ' + INDEX + ' --phase 2')
  expect(out.context).toBeUndefined()
  expect(out.text).toBe('/implement -f ' + INDEX + ' --phase 2')
})

test('any other command, or plain text, is untouched', async ($, on) => {
  const runs = world(on, { files: { [INDEX]: '# Plan' }, graphs: { [INDEX]: graph(WT, 7) } })

  const other = await submit($, 'do', '-f ' + INDEX)
  expect(other.context).toBeUndefined()
  const plain = await $.prompt.submit({ text: 'run -f ' + INDEX, wait: false, origin: { kind: 'composer' } } as any)
  expect(plain.context).toBeUndefined()
  expect(runs).toEqual([])
})
