/**
 * swarm-deck -- slice 1: the marshal's no-ask guard.
 *
 * MEASURED: a phase-2 session held an AskUserQuestion for eight hours and stalled a
 * six-phase set whose answer was rung 1 of the precedence ladder. Iron rule 4 ("a phase
 * that asks stalls its dependents, a coordinator that asks stalls the whole set") is
 * enforced today only by prose in a prompt -- and a prompt is advice, not a mechanism.
 * This hook answers the tool call instead of letting it render, so the stall cannot
 * happen rather than being asked not to.
 *
 * The session learns it belongs to a swarm from the environment `swarm.py spawn` hands
 * its child, not by parsing the ledger here: swarm.py stays the single reader of that
 * format, and an env var survives a cwd change that a path lookup would not.
 */

// Identity of this session, read once at session.start. Null outside a swarm, which is
// what keeps the guard dormant in ordinary interactive work -- the property test 3 pins.
let swarm = null

/** The ladder, as the executors' own docs state it. Rung 1 beats rung 6. */
const LADDER = [
  '1. an invariant in CLAUDE.md or the plan index',
  '2. the phase\'s exit criteria',
  '3. the code blocks in the plan',
  '4. the plan\'s Why / Requirements table',
  '5. the task text or its note',
  '6. the surrounding convention in the code you are editing',
].join('\n')

/** Build the refusal Claude reads in place of the dialog. */
function denyText(where) {
  return [
    'AskUserQuestion is refused in this session: it is phase ' + where.phase +
      ' of the swarm set "' + where.slug + '", which runs unattended.',
    '',
    'There is nobody at this terminal. A question here does not get answered slowly --',
    'it is never answered, and every phase that depends on this one waits behind it.',
    '',
    'Decide it yourself on the precedence ladder, highest rung that settles it:',
    LADDER,
    '',
    'Then record the decision in completion_report.decisions, with the rung that',
    'settled it. It flows from there into todos.md, the commit body and the swarm',
    'ledger note, and surfaces in the coordinator\'s "Decided without asking" review.',
    '',
    'Stopping is allowed; blocking is not. The only legitimate stop is a fork where',
    'every branch is irreversible -- exit with a report to the coordinator instead of',
    'asking, and say which branches you weighed.',
  ].join('\n')
}

/**
 * The guard. Top-level because `claude plugin validate` only lets `$` reach a
 * function declared at the top level of the module.
 */
async function guard($, e, next) {
  if (swarm === null) return next(e)
  await $.ui.log('swarm-deck: refused AskUserQuestion in phase ' + swarm.phase +
    ' -- deciding on the ladder instead')
  return { deny: denyText(swarm) }
}

/**
 * Fail CLOSED. A hook that throws or times out is SKIPPED, which would let the dialog
 * render and stall the night -- the exact failure this mod exists to remove. The
 * handler has a 1s budget of its own, so it does no work beyond answering.
 */
async function failClosed($, e, next) {
  if (swarm === null) return next(e)
  return { deny: denyText(swarm) }
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    const slug = await $.env.get('SWARM_SLUG')
    const phase = await $.env.get('SWARM_PHASE')
    // Both or neither: a half-set identity means something upstream changed shape, and
    // guessing at it would arm the guard in a session that is not a phase.
    if (slug && phase) {
      swarm = { slug: slug, phase: phase, coordinator: await $.env.get('SWARM_COORDINATOR') }
    }
    return next(e)
  })

  on('tool.call', { tool: 'AskUserQuestion' }, guard).catch(failClosed)
}
