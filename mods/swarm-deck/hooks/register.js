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

// What the heartbeat reports. Module-level so the hooks share it the way the engine
// intends: one hook records, another publishes.
let lastTool = null
let turns = 0
let decided = []

/**
 * What this phase says it is doing. The deck may override it with what the clock says
 * (see `shown`), but only a session can report these.
 *
 *   starting    booted, no turn yet
 *   working     a turn is running
 *   idle        between turns
 *   finalizing  completion-handler is running -- the endgame, and STICKY: a phase does
 *               not go back to idle once it has started handing off
 *   done        the session ended on purpose
 */
let phaseState = 'starting'
let sent = []
let undelivered = 0

/**
 * This session's own row in the machine-shared store.
 *
 * ONE KEY PER PHASE, not one key per set. $.store is shared by every session on the
 * machine, and a set's phases run concurrently by construction -- so a single
 * `swarm/<slug>` document would have N children doing read-modify-write on it at once
 * and silently losing each other's rows. Giving each phase its own key means no two
 * writers ever touch the same key, and the deck reassembles the set with $.store.keys().
 */
function rowKey() {
  return 'swarm/' + swarm.slug + '/phase/' + swarm.phase
}

/** The forks this phase settled alone -- same one-writer rule as the row. */
function decisionKey() {
  return 'swarm/' + swarm.slug + '/decided/' + swarm.phase
}

/** What this phase told the coordinator -- same one-writer rule again. */
function sentKey() {
  return 'swarm/' + swarm.slug + '/sent/' + swarm.phase
}

/** Name what this phase is doing. Never denies -- see its registration. */
async function watch($, e, next) {
  if (swarm !== null) lastTool = e.tool
  return next(e)
}

/**
 * Publish this session's row. Never throws: a heartbeat that takes the session down,
 * or that takes a tool call down from inside the guard, would be a telemetry feature
 * breaking the thing it reports on.
 */
async function publish($) {
  if (swarm === null) return
  let contextPct = null
  try {
    const usage = await $.session.usage()
    if (usage && usage.context) contextPct = usage.context.percent
  } catch (err) {
    // A session too young to have usage still deserves a row.
  }
  try {
    await $.store.set(rowKey(), {
      slug: swarm.slug,
      phase: swarm.phase,
      coordinator: swarm.coordinator || null,
      status: phaseState,
      turns: turns,
      lastTool: lastTool,
      contextPct: contextPct,
      decided: decided.length,
      sent: sent.length,
      undelivered: undelivered,
      updatedAt: await $.clock.now(),
    })
  } catch (err) {
    // The deck will show this row as stale, which is the correct reading.
  }
}

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
  // No name prefix: the engine already renders `● swarm-deck: ` in front of a log line,
  // and repeating it reads as a bug to anyone watching the transcript.
  await $.ui.log('refused AskUserQuestion in phase ' + swarm.phase +
    ' -- deciding on the ladder instead')
  await record($, e)
  // Republish, or the row keeps a stale count and the deck under-reports the one thing
  // a reviewer is looking for. Both calls are mods API calls, so neither spends the
  // hook's 10s budget, and publish() swallows its own errors -- the deny stands either way.
  await publish($)
  return { deny: denyText(swarm) }
}

/**
 * Append the refused fork to this phase's decision list.
 *
 * The coordinator's termination block has a "Decided without asking" section that is
 * today reconstructed at the end of the run -- which means a coordinator that dies
 * takes the record with it. Writing each fork as it happens makes that section
 * durable, and lets the deck show it while the night is still going.
 */
async function record($, e) {
  const asked = (e.questions && e.questions[0] && e.questions[0].question) || 'unrecorded'
  decided = decided.concat([{ phase: swarm.phase, question: asked, at: await $.clock.now() }])
  try {
    await $.store.set(decisionKey(), decided)
  } catch (err) {
    // The deny still stands: the phase decides either way, and the commit body and
    // completion report carry the decision even when this row is lost.
  }
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

/**
 * Mirror an outgoing report into the store, and note a send that went nowhere.
 *
 * THIS REPLACES THE DETECTOR THE DESIGN ASKED FOR, because the thing it was meant to
 * detect is not detectable. `swarm.py spawn` warns that a child on a different permission
 * mode than its coordinator has its reports "held for the user to approve", and the set
 * then stalls in silence. The plan was to catch that on $.session.send's result -- but
 * the engine's own types settle it: isDelivered true means the message "reached its
 * recipient's queue or inbox", which a held message has. It reports success.
 *
 * So the channel is not made observable; it is made non-essential. Every report is also
 * written to the store, which no approval gate sits in front of, and the coordinator
 * reads it there. A held message stops being a lost night and becomes a slow one.
 *
 * isDelivered false is still worth recording -- it means nobody by that name, several by
 * it, or the recipient gone -- which is a real misconfiguration the deck should show.
 */
async function mirror($, e, result) {
  if (swarm === null) return
  if (result && result.isDelivered === false) undelivered += 1
  // Capped: the store holds 4 MiB for every session on the machine, and the ledger is
  // the durable record. This is the live view of a night, not an archive.
  sent = sent.concat([{
    to: typeof e.to === 'string' ? e.to : JSON.stringify(e.to),
    text: String(e.text || '').slice(0, 2000),
    delivered: !(result && result.isDelivered === false),
    at: await $.clock.now(),
  }]).slice(-20)
  try {
    await $.store.set(sentKey(), sent)
  } catch (err) {
    // The message itself still went; only this copy of it is lost.
  }
  await publish($)
}

/**
 * Write the row one last time, as `done`.
 *
 * Lean on purpose: every session.end hook on the machine shares a 1.5 second budget, so
 * this does a single store.set and skips the $.session.usage() call publish() makes.
 * The last heartbeat's context figure is a second or two old, which is close enough for
 * a row nobody will watch change again.
 */
async function finish($) {
  if (swarm === null) return
  phaseState = 'done'
  try {
    await $.store.set(rowKey(), {
      slug: swarm.slug,
      phase: swarm.phase,
      coordinator: swarm.coordinator || null,
      status: 'done',
      turns: turns,
      lastTool: lastTool,
      contextPct: null,
      decided: decided.length,
      sent: sent.length,
      undelivered: undelivered,
      updatedAt: await $.clock.now(),
    })
  } catch (err) {
    // The row stays at its last heartbeat and ages into `stale`, which is wrong but not
    // alarming -- the failure mode errs towards silence, which is correct for an exit.
  }
}

// ------------------------------------------------------- guard 2: interactive shells

/**
 * Shell commands that wait on a terminal nobody is sitting at.
 *
 * CLAUDE.md names these alongside AskUserQuestion as the ways a stall gets reintroduced,
 * and they are worse in one respect: an editor or a pager holds the Bash tool open with
 * no dialog on screen, so the session looks like it is working rather than waiting.
 *
 * The list is short on purpose, and it is a REMINDER, not a sandbox. Anthropic's own
 * blast-radius sample documents that its pattern misses `git push -f`; this one will miss
 * spellings too. Anything that genuinely must not run belongs in a permission deny rule.
 */
// Only at a command position: start of line, or after ; && || | -- optionally behind
// sudo or an inline VAR=value. Without this anchor, `echo "on top of that"` matches
// `top` and a legitimate command is refused.
const CMD = '(?:^|[;&|\\n])\\s*(?:sudo\\s+|\\w+=\\S+\\s+)*'

const INTERACTIVE = [
  { re: new RegExp(CMD + '(?:vim?|nvim|nano|emacs|pico)\\b'), why: 'it opens an editor' },
  { re: new RegExp(CMD + '(?:less|more|man)\\b'), why: 'it opens a pager that waits for a keypress' },
  { re: new RegExp(CMD + '(?:top|htop|watch)\\b'), why: 'it runs until a key is pressed' },
  { re: new RegExp(CMD + 'git\\s+(?:rebase|add|commit|clean|checkout)\\b[^;&|]*?\\s-{1,2}(?:i|interactive|patch)\\b'),
    why: 'it opens an interactive git session' },
]

/**
 * Blank the contents of quoted strings before matching.
 *
 * A commit message is not a command. Without this, `git commit -m "add -i support"`
 * reads as an interactive rebase and `echo "one more thing"` reads as a pager -- and a
 * guard that refuses legitimate work is worse than one that misses a case, because the
 * phase it blocks has no way around it.
 */
function bare(command) {
  return String(command).replace(/'[^']*'/g, "''").replace(/"[^"]*"/g, '""')
}

function interactiveReason(command) {
  const text = bare(command)
  for (const probe of INTERACTIVE) {
    if (probe.re.test(text)) return probe.why
  }
  return null
}

/** Refuse a command that would wait on a terminal nobody is watching. */
async function shellGuard($, e, next) {
  if (swarm === null) return next(e)
  const why = interactiveReason(e.command || '')
  if (why === null) return next(e)
  return {
    deny: 'Refused: ' + why + ', and this is phase ' + swarm.phase + ' of an unattended ' +
      'swarm set. It would hold the Bash tool open with nothing on screen, which looks ' +
      'like work rather than like waiting.\n\n' +
      'Use the non-interactive form instead: a flag such as --no-pager, -y, --yes or ' +
      '--batch, a here-doc or -m for text an editor would have collected, or the file ' +
      'tools for an edit. If no non-interactive form exists, treat it as out of scope ' +
      'for this phase and say so in your report.',
  }
}

/** Fail CLOSED, for the same reason the AskUserQuestion guard does. */
async function shellFailClosed($, e, next) {
  if (swarm === null) return next(e)
  const why = interactiveReason(e.command || '')
  if (why === null) return next(e)
  return { deny: 'The interactive-command guard failed, so this command was not run.' }
}

// ---------------------------------------------------------------- the deck

// Rows read out of the store, newest read wins. Rendering must not await the store:
// a ui.render hook runs on every redraw, and redraws are throttled at 30/s.
let fleet = []
let reports = []
let fleetSlug = null
// True when the set was NAMED -- by SWARM_SLUG or by `/fleet <slug>` -- rather than
// discovered. A named set is kept; a discovered one is a guess and is re-made on every
// refresh, because the right answer changes under a running coordinator (see pick).
let pinned = false
let deckTimer = null

/** No heartbeat for this long and the session is not live. */
const STALE_MS = 60000

/**
 * Past this, a silent row is history rather than an emergency.
 *
 * MEASURED by looking at a real deck: with nothing running, every row of a finished set
 * read QUIET in yellow and the band stayed lit -- for a set that had ended days earlier.
 * Rows are never deleted from the store, so without this the deck alarms forever about a
 * night that is already over: exactly the "a band that is always lit is noise" failure
 * this mod exists to avoid, committed by the mod itself.
 */
const ABANDONED_MS = 2 * 60 * 60 * 1000

/**
 * What the deck shows for a row: the session's own word, or the clock's.
 *
 * QUIET is deliberately narrow now. It used to mean only "no heartbeat for 60s", which
 * lumped together three unrelated situations -- a phase wedged mid-run, a phase that
 * finished and exited cleanly, and a row left over from last week. Only the first of
 * those is worth a colour.
 */
function shown(row, now) {
  const age = missing(row.updatedAt) ? Infinity : now - row.updatedAt
  // A session that said goodbye is never quiet, however long ago it said it.
  if (row.status === 'done') return { label: 'done', dim: true, alarm: false }
  if (age > ABANDONED_MS) return { label: 'stale', dim: true, alarm: false }
  // Stale beats working: a row that says "working" and stopped updating is the exact
  // picture of the stall this mod removes, and it must not read as healthy.
  if (age > STALE_MS) return { label: 'QUIET', color: 'yellow', alarm: true }
  if (row.status === 'working') return { label: 'working', color: 'green', alarm: false }
  if (row.status === 'finalizing') return { label: 'finalizing', color: 'cyan', alarm: false }
  if (row.status === 'starting') return { label: 'starting', dim: true, alarm: false }
  return { label: 'idle', dim: true, alarm: false }
}

/**
 * Find the set this session should watch, for a session that is not itself a phase.
 *
 * THIS IS THE cwd LOOKUP SLICE 1 REJECTED, AND THE REVERSAL IS DELIBERATE -- do not
 * "fix" the inconsistency by reintroducing it for identity. Identity arms a guard, so a
 * wrong answer there disarms the guard in precisely the session that needed it, which is
 * a lost night. The deck is read-only: a wrong answer here points a dashboard at the
 * wrong set, or at none. Same mechanism, different blast radius, different answer.
 *
 * Returns { root, names }: the repo root the names live under, and every set directory.
 */
async function discover($) {
  let root = null
  try {
    const repo = await $.session.repo()
    root = repo && repo.root
  } catch (err) {
    return { root: null, names: [] }
  }
  if (!root) return { root: null, names: [] }
  try {
    const entries = await $.fs.list(root + '/.workflows/orchestration')
    // 'dir', not 'directory'. The first draft guessed the latter, matched nothing, and
    // the unit test agreed with it because the stub was written from the same guess --
    // which is why this one needed a real repo to catch.
    return { root: root, names: entries.filter(x => x.kind === 'dir').map(x => x.name) }
  } catch (err) {
    // No orchestration directory: this repo has never run a set.
    return { root: root, names: [] }
  }
}

/**
 * Choose among the discovered sets: { slug } when one is the answer, else { sets } to
 * list for the user.
 *
 * SHIPPED BUG: a coordinator ran /fleet and got the PREVIOUS set's deck -- a set that had
 * landed an hour earlier. Its session started while that set's directory was the only one
 * under .workflows/orchestration/ (the coordinator creates its own later), "one set" was
 * adopted silently, and the guess was then never revisited. Two facts the ledger already
 * records settle it instead:
 *
 *   1. coordinator_session_id: `swarm.py init` stamps the session that owns the set. A
 *      session watching its own set is not a guess, however many others sit beside it.
 *   2. landed: a set merged to main is history. It is still reachable as /fleet <slug>,
 *      but it must never be adopted silently -- and its old rows must never light the band.
 *
 * Only then does the old rule apply: one live set is adopted, several are listed, because a
 * dashboard confidently showing the wrong run is worse than a dashboard that asks.
 */
async function pick($) {
  const found = await discover($)
  if (found.names.length === 0) return { sets: [] }
  let me = null
  try {
    me = await $.session.id()
  } catch (err) {
    // Without an id, ownership cannot be proved; the landed filter still applies.
  }
  const live = []
  for (const name of found.names) {
    let ledger = null
    try {
      ledger = JSON.parse(await $.fs.read(found.root + '/.workflows/orchestration/' + name + '/ledger.json'))
    } catch (err) {
      // No readable ledger: unknown, which is not the same as landed. Keep it a candidate.
    }
    if (ledger && me && ledger.coordinator_session_id === me) return { slug: name }
    if (!(ledger && ledger.landed)) live.push(name)
  }
  if (live.length === 1) return { slug: live[0] }
  return { sets: live.length > 0 ? live : found.names }
}

/** Re-make a discovered choice. A named set is left alone. */
async function rediscover($) {
  if (pinned) return
  const choice = await pick($)
  const slug = choice.slug || null
  if (slug !== fleetSlug) {
    // Drop the old set's rows with it, or the band keeps alarming about a set this session
    // no longer watches.
    fleetSlug = slug
    fleet = []
    reports = []
  }
}

function startDeckTimer($) {
  if (deckTimer !== null) return
  deckTimer = $.clock.every(15000, async () => {
    await rediscover($)
    await refresh($)
  })
}

/**
 * Re-read every phase row of one set and ask for a redraw.
 *
 * Enumerating keys is what the per-phase layout buys: no reader ever has to agree with a
 * writer about a document's shape, and a phase that has not started yet is simply a key
 * that is not there.
 */
async function refresh($) {
  if (fleetSlug === null) {
    $.ui.invalidate('ui.render')
    return
  }
  let keys = []
  try {
    keys = await $.store.keys()
  } catch (err) {
    return
  }
  const prefix = 'swarm/' + fleetSlug + '/phase/'
  const sentPrefix = 'swarm/' + fleetSlug + '/sent/'
  const rows = []
  const latest = []
  for (const key of keys) {
    try {
      if (key.startsWith(prefix)) {
        const row = await $.store.get(key)
        if (row) rows.push(row)
      } else if (key.startsWith(sentPrefix)) {
        // The mirrored reports. Without reading these the durability fix is write-only:
        // the text survives an approval gate and then nobody can see it.
        const list = await $.store.get(key)
        if (list && list.length > 0) {
          const last = list[list.length - 1]
          latest.push({ phase: key.slice(sentPrefix.length), text: last.text, at: last.at,
                        delivered: last.delivered })
        }
      }
    } catch (err) {
      // One unreadable key must not blank the whole deck.
    }
  }
  rows.sort((a, b) => Number(a.phase) - Number(b.phase))
  latest.sort((a, b) => Number(a.phase) - Number(b.phase))
  fleet = rows
  reports = latest
  $.ui.invalidate('ui.render')
}

/** `working 41%  Bash   12s ago`, or the reason there is nothing to say. */
function bar(pct) {
  if (pct === null || pct === undefined) return '      '
  const filled = Math.max(0, Math.min(6, Math.round(pct / 100 * 6)))
  return '\u2588'.repeat(filled) + '\u2591'.repeat(6 - filled)
}

/** Missing is not the same as zero: `!then` would call epoch 0 "unknown". */
function missing(v) {
  return v === null || v === undefined
}

function ago(now, then) {
  if (missing(then)) return '--'
  const sec = Math.max(0, Math.round((now - then) / 1000))
  if (sec < 90) return sec + 's'
  if (sec < 5400) return Math.round(sec / 60) + 'm'
  return (sec / 3600).toFixed(1) + 'h'
}

/** The pane's tree. Box and Text only: it has to draw the same in tmux, Desktop and VS Code. */
async function draw($, e) {
  const el = $.ui.resolve(e)
  const Box = el.Box
  const Text = el.Text
  const now = await $.clock.now()
  const children = []

  children.push(Text({ dimColor: true, children: ['set ' + (fleetSlug || '--')] }))

  if (fleet.length === 0) {
    children.push(Text({ children: ['No phase has reported yet.'] }))
    children.push(Text({ dimColor: true, children: ['Rows appear as sessions start.'] }))
  }

  for (const row of fleet) {
    // A row with no timestamp at all is QUIET too. "I cannot tell when this last
    // reported" is not evidence that it is healthy, and on a deck built to spot
    // sessions that went quiet, the unknown case must fall on the safe side.
    const view = shown(row, now)
    children.push(Box({
      flexDirection: 'row',
      columnGap: 2,
      children: [
        Text({ children: ['p' + String(row.phase).padEnd(3)] }),
        Text({ color: view.color, dimColor: view.dim === true,
               children: [view.label.padEnd(10)] }),
        Text({ dimColor: true, children: [bar(row.contextPct)] }),
        Text({ dimColor: true, children: [String(row.lastTool || '--').padEnd(10)] }),
        Text({ dimColor: true, children: [ago(now, row.updatedAt)] }),
      ],
    }))
  }

  const decided = fleet.reduce((n, row) => n + (row.decided || 0), 0)
  if (decided > 0) {
    children.push(Text({ children: [' '] }))
    children.push(Text({ children: ['Decided without asking: ' + decided] }))
    children.push(Text({ dimColor: true, children: ['Review before the set lands.'] }))
  }

  if (reports.length > 0) {
    children.push(Text({ children: [' '] }))
    children.push(Text({ children: ['Latest report'] }))
    // The width the pane actually has, so a long report wraps instead of being clipped.
    const width = Math.max(20, (e.props && e.props.bodyColumns) || 60)
    for (const report of reports) {
      children.push(Box({
        flexDirection: 'row',
        columnGap: 1,
        children: [
          Text({ dimColor: true, children: ['p' + report.phase] }),
          Text({ wrap: 'wrap', dimColor: !report.delivered,
                 color: report.delivered ? undefined : 'yellow',
                 children: [String(report.text || '').slice(0, width * 3).replace(/\s+/g, ' ')] }),
        ],
      }))
      if (!report.delivered) {
        children.push(Text({ color: 'yellow', children: ['  reached nobody -- read it here'] }))
      }
    }
  }

  return Box({ flexDirection: 'column', children: children })
}

/**
 * What, if anything, needs a person right now. Null means draw nothing.
 *
 * A band that is always lit is noise, and noise is how the one night it matters gets
 * scrolled past. So this reports only the two states a human has to act on, and the
 * quiet set -- the overwhelmingly common case -- renders no band at all.
 */
function alarm(now) {
  const quiet = []
  const lost = []
  for (const row of fleet) {
    const view = shown(row, now)
    if (view.alarm) quiet.push(row)
    // An undelivered report from a run that is over is history, not an action. Gate it
    // on the same recency, or a finished set lights the band for good.
    if (row.undelivered > 0 && view.label !== 'done' && view.label !== 'stale') lost.push(row)
  }
  if (lost.length > 0) {
    return 'phase ' + lost.map(r => r.phase).join(', ') +
      ': a report reached nobody -- check the coordinator name in the ledger'
  }
  if (quiet.length > 0) {
    const worst = quiet.map(r => ago(now, r.updatedAt)).join(', ')
    return 'phase ' + quiet.map(r => r.phase).join(', ') + ' has gone quiet (' + worst + ')'
  }
  return null
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    const slug = await $.env.get('SWARM_SLUG')
    const phase = await $.env.get('SWARM_PHASE')
    // Both or neither: a half-set identity means something upstream changed shape, and
    // guessing at it would arm the guard in a session that is not a phase.
    if (slug && phase) {
      // ORDER IS LOAD-BEARING. The guard arms the instant this assignment lands; the
      // heartbeat is started after it. A hook that throws partway is skipped, so if
      // starting the timer fails, this session still cannot ask -- it just goes dark on
      // the deck. The reverse order would trade the invariant for the dashboard.
      swarm = { slug: slug, phase: phase, coordinator: await $.env.get('SWARM_COORDINATOR') }
      // Outside any turn, so a coordinator watching ten phases spends no tokens to do
      // it. 15s is well under the pane's own redraw budget and far above the cost of a
      // single $.store.set.
      $.clock.every(15000, async () => {
        await publish($)
      })
      await publish($)
    }
    // The deck reads whichever set this session belongs to. A session that is not a
    // phase -- a coordinator, most often -- discovers the set instead, and keeps
    // re-discovering it: the set it is about to coordinate may not exist yet.
    if (slug) {
      fleetSlug = slug
      pinned = true
    } else {
      await rediscover($)
    }
    // SHIPPED BUG, slice 4: this timer lived inside the `slug && phase` branch, so a
    // coordinator that ran /fleet got one snapshot and a deck that never updated again.
    // The refresh belongs to the deck, not to being a phase -- and a dashboard that
    // silently stops updating is worse than no dashboard, because it still looks right.
    //
    // Started in any repo that has ever run a set, not only when one was adopted: a
    // coordinator usually starts BEFORE its set exists, and a timer gated on adoption
    // would never start for it.
    if (fleetSlug !== null || (await discover($)).names.length > 0) {
      // Store reads outside any turn cost no tokens, which is what makes an always-on
      // watch affordable, and what lets the band light in a session nobody opened the
      // deck in.
      startDeckTimer($)
      await refresh($)
    }
    // Registered last in this hook: $.command.register throws on a taken name, and a
    // hook that throws is skipped -- which would take the heartbeat down with it.
    try {
      await $.command.register({
        name: 'fleet',
        description: 'Show every phase of the running set',
        argumentHint: '[slug]',
        // Runs WHILE Claude is working. A deck you can only open between turns is a deck
        // you cannot open at the moment you need it.
        immediate: true,
      })
    } catch (err) {
      // Someone else owns /fleet in this session; the guard and heartbeat are unaffected.
    }
    return next(e)
  })

  on('command.run', { command: 'fleet' }, async ($, e) => {
    if (e.args && e.args.trim()) {
      fleetSlug = e.args.trim()
      pinned = true
      fleet = []
      reports = []
    } else if (!pinned) {
      // Never trust an earlier guess: the set this session coordinates may have been
      // created since, and an older one may have landed.
      const choice = await pick($)
      if (choice.slug) {
        if (choice.slug !== fleetSlug) {
          fleet = []
          reports = []
        }
        fleetSlug = choice.slug
      } else {
        fleetSlug = null
        fleet = []
        reports = []
        if (choice.sets.length === 0) {
          return { text: 'no orchestrated set in this repo. Try /fleet <slug>.' }
        }
        // Several: name them rather than pick one. A deck confidently showing the wrong
        // run is worse than one that asks.
        return { text: 'several sets here. Pick one:\n  /fleet ' + choice.sets.join('\n  /fleet ') }
      }
    }
    await refresh($)
    // A session that named a set after startup has no timer yet.
    startDeckTimer($)
    await $.ui.open({ id: 'fleet', title: 'swarm ' + fleetSlug, focus: true, closeOnEscape: true })
    return {}
  })

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    // Every other pane on screen belongs to someone else, built-in /diff included.
    if (e.requestId !== 'fleet') return next(e)
    return draw($, e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const text = alarm(await $.clock.now())
    // Nothing wrong: hand the band back untouched so Claude Code draws its own.
    if (text === null) return next(e)
    const el = $.ui.resolve(e)
    return el.Box({
      flexDirection: 'row',
      columnGap: 1,
      children: [
        el.Text({ color: 'yellow', children: ['swarm'] }),
        el.Text({ children: [text] }),
      ],
    })
  })

  on('tool.call', { tool: 'AskUserQuestion' }, guard).catch(failClosed)

  on('tool.call', { tool: 'Bash' }, shellGuard).catch(shellFailClosed)

  on('session.send', async ($, e, next) => {
    // Observe only: a mod that refuses its own session's messages would be doing the
    // thing it exists to prevent, one layer down.
    const result = await next(e)
    await mirror($, e, result)
    return result
  }).catch(async ($, e, next) => next(e))

  // Every other tool call, only to name what this phase is doing right now. No matcher,
  // so it must be the only unmatched tool.call registration in the module.
  //
  // This one fails OPEN, which is the exact opposite of the guard above and deliberate:
  // the guard's failure would stall the night, while this hook's failure would at worst
  // leave a stale tool name on a dashboard. Telemetry must never be able to refuse work.
  on('tool.call', watch).catch(async ($, e, next) => next(e))

  on('turn.start', async ($, e, next) => {
    if (swarm !== null) {
      turns += 1
      // `finalizing` is sticky: completion-handler's own turns must not drag the phase
      // back to `working`, or the endgame flickers and the deck stops meaning anything.
      if (phaseState !== 'finalizing') phaseState = 'working'
      await publish($)
    }
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    // A subagent finishing is not the phase finishing, and reporting it as idle makes a
    // busy session look parked -- which is the one misreading that matters on a deck
    // built to spot sessions that have gone quiet.
    if (swarm !== null && e.agentId === undefined && phaseState !== 'finalizing') {
      phaseState = 'idle'
      await publish($)
    }
    return next(e)
  })

  // The endgame has a name in this repo: /do and /implement both hand off to
  // completion-handler when the code is written. A phase that has spawned it is not
  // going to start anything new, which is exactly what you want to know when deciding
  // whether a wave is nearly through.
  on('agent.spawn', { subagentType: 'completion-handler' }, async ($, e, next) => {
    if (swarm !== null) {
      phaseState = 'finalizing'
      await publish($)
    }
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    // /clear and /resume END A CONVERSATION, not a session: the process goes on. Marking
    // those `done` would retire a phase that is still working, and the deck would stop
    // watching the session most likely to need it.
    if (swarm !== null && e.reason !== 'clear' && e.reason !== 'resume') {
      await finish($)
    }
    return next(e)
  })
}
