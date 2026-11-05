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

// --------------------------------------------------------- the plan set, resolved

/**
 * Attach the plan set's files to /analyze-orchestrator and /implement, resolved by
 * plan_graph.py, so neither session ever locates a phase plan by hand.
 *
 * MEASURED 2026-11-05 on seer-adversarial: a coordinator checked for its phase plans with
 * `ls .workflows/plan/<slug>/ .workflows/analyze/ | head`. The one `head` over two
 * listings cut off phase-7.md -- committed, 35 KB -- and the coordinator concluded the
 * plan was missing and went looking with a filesystem-wide `find`. The command's Step 1
 * was then patched to say "decide it with plan_graph.py, never a listing". That is
 * advice. This makes the answer arrive with the prompt instead, so there is nothing left
 * to look for.
 *
 * plan_graph.py stays the ONE reader of the index format, the same rule this mod keeps for
 * identity: the hook parses only the command line and plan_graph's JSON. A second parser
 * of the Plan column here would be a second resolver to disagree with the gate.
 *
 * It fails OPEN, the opposite of the guards and deliberately: this is help, not a gate. A
 * hook that cannot resolve the set leaves the prompt exactly as typed, and the command
 * falls back to running plan_graph.py itself, as it always has. It never drops.
 *
 * Any session, not only a SWARM_* phase: the coordinator is not a phase, and /implement
 * also runs standalone.
 */
const PLANNED = ['analyze-orchestrator', 'implement']

/** Split a command line on whitespace, keeping a quoted path whole. */
function words(args) {
  const out = []
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g
  let m
  while ((m = re.exec(String(args || ''))) !== null) out.push(m[1] ?? m[2] ?? m[3])
  return out
}

/**
 * What the command line asks for: { index } or { resume, slug }, plus a phase for
 * /implement --phase N. Null for anything else -- a --status, a typo, no flag at all --
 * which the hook answers by passing the prompt through untouched.
 */
function planArgs(name, args) {
  const w = words(args)
  const out = {}
  for (let i = 0; i < w.length; i++) {
    if (w[i] === '-f' && w[i + 1] && !w[i + 1].startsWith('-')) out.index = w[++i]
    else if (w[i] === '--phase' && /^\d+$/.test(w[i + 1] || '')) out.phase = Number(w[++i])
    else if (w[i] === '--resume' && name === 'analyze-orchestrator') {
      out.resume = true
      if (w[i + 1] && !w[i + 1].startsWith('-')) out.slug = w[++i]
    }
  }
  if (out.index === undefined && !out.resume) return null
  return out
}

function joinPath(base, path) {
  if (path.startsWith('/')) return path
  return base.replace(/\/+$/, '') + '/' + path.replace(/^\.\//, '')
}

/** `~/x` -> `$HOME/x`. /analyze writes tildes into indexes and ledgers. */
function expand(path, home) {
  if (home && (path === '~' || path.startsWith('~/'))) return home + path.slice(1)
  return path
}

/**
 * The plan index a `--resume [slug]` means, or null.
 *
 * The ledger is read for its `plan` field only -- JSON, not the index format -- and the
 * fallback is the durable copy beside it, the same order `swarm.py spawn_plan` takes. A
 * bare --resume is answered only when exactly one set is unlanded; with several the
 * command's own rule picks, and a hook guessing differently would be worse than silence.
 */
async function resumeIndex($, slug, home) {
  const common = await $.process.run(
    ['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], { timeoutMs: 5000 })
  if (common.exitCode !== 0) return null
  // The parent of the common .git is the main checkout, where the ledger lives -- also
  // from inside a linked worktree.
  const main = common.stdout.trim().replace(/\/\.git\/?$/, '')
  const orch = main + '/.workflows/orchestration'
  if (!slug) {
    const live = []
    for (const entry of await $.fs.list(orch)) {
      if (entry.kind !== 'dir') continue
      const ledger = await readLedger($, orch + '/' + entry.name)
      if (ledger && !ledger.landed) live.push(entry.name)
    }
    if (live.length !== 1) return null
    slug = live[0]
  }
  const ledger = await readLedger($, orch + '/' + slug)
  const recorded = ledger && typeof ledger.plan === 'string' ? expand(ledger.plan, home) : null
  if (recorded && (await $.fs.exists(recorded))) return recorded
  const durable = orch + '/' + slug + '/PLAN.md'
  return (await $.fs.exists(durable)) ? durable : null
}

async function readLedger($, dir) {
  try {
    return JSON.parse(await $.fs.read(dir + '/ledger.json'))
  } catch (err) {
    return null
  }
}

/**
 * plan_graph.py's --json for one index, or null. Exit 1 (a plan missing) and 2 (a
 * collision) are answers, not failures, so the exit code is not checked -- the JSON is.
 */
async function planGraph($, index, home) {
  const script = home + '/.claude/skills/swarm/plan_graph.py'
  const run = await $.process.run(['python3', script, '--json', index], { timeoutMs: 15000 })
  const graph = JSON.parse(run.stdout)
  if (!graph || graph.error || !Array.isArray(graph.phases)) return null
  // A deployed plan_graph.py from before plan_path existed: say nothing rather than
  // half of it.
  if (graph.phases.some(p => p.plan_path === undefined)) return null
  return graph
}

/**
 * One line per phase: where its plan is, or where it was looked for.
 *
 * The durable copy (`orchestration/<slug>/PLAN.md`) keeps the worktree's Plan cells, which
 * resolve against the main checkout and usually find nothing there. Step 2 of the
 * orchestrator copies every phase plan beside it as phase-N.md, verbatim, so a phase the
 * gate could not find is looked for there before it is called missing.
 */
async function phaseLines($, graph, index) {
  const durableDir = /\/\.workflows\/orchestration\/[^/]+\/PLAN\.md$/.test(index)
    ? index.slice(0, -'/PLAN.md'.length) : null
  const tried = new Map((graph.missing_plans || []).map(m => [m.phase, m]))
  const lines = []
  for (const p of graph.phases) {
    if (p.plan_path) {
      lines.push({ n: p.n, ok: true, path: p.plan_path, bytes: p.plan_bytes })
      continue
    }
    if (durableDir) {
      const copy = durableDir + '/phase-' + p.n + '.md'
      const stat = await $.fs.stat(copy).catch(() => null)
      if (stat && stat.kind === 'file') {
        lines.push({ n: p.n, ok: true, path: copy, bytes: stat.size, copy: true })
        continue
      }
    }
    const miss = tried.get(p.n) || {}
    lines.push({ n: p.n, ok: false, cell: miss.plan || p.plan || '(none)', tried: miss.tried || null })
  }
  return lines
}

function planBlock(name, index, graph, lines, phase) {
  const shown = phase === undefined ? lines : lines.filter(l => l.n === phase)
  const out = [
    'swarm-deck: the plan set for /' + name + ', resolved by plan_graph.py before this turn.',
    'index: ' + index,
    'resolved against root: ' + graph.root,
  ]
  for (const l of shown) {
    out.push(l.ok
      ? 'phase ' + l.n + ': ' + l.path + ' (' + l.bytes + ' bytes)' +
        (l.copy ? ' -- the durable copy beside the index' : '')
      : 'phase ' + l.n + ': MISSING -- Plan cell `' + l.cell + '`, tried ' + (l.tried || '(no path)'))
  }
  const missing = shown.filter(l => !l.ok)
  if (missing.length === 0) {
    out.push(phase === undefined
      ? 'All ' + shown.length + ' phase plans are present; do not re-list or search for them.'
      : 'Phase ' + phase + "'s plan is present at the path above; do not re-list or search for it.")
  } else {
    out.push(missing.length + ' of ' + shown.length + ' phase plan' + (shown.length === 1 ? ' is' : 's are') +
      ' missing: ' + missing.map(l => 'phase ' + l.n).join(', ') + '. This is the gate\'s answer;' +
      ' report these lines and the resolved-against-root line exactly, and do not search for the files.')
  }
  return out.join('\n')
}

/** The prompt.submit hook. Every path that is not a clean answer is `next(e)` unchanged. */
async function attachPlan($, e, next) {
  const cmd = e.command
  if (!cmd || !PLANNED.includes(cmd.name)) return next(e)
  const want = planArgs(cmd.name, cmd.args)
  if (want === null) return next(e)
  const home = await $.env.get('HOME')
  if (!home) return next(e)
  let index = null
  if (want.index !== undefined) {
    index = joinPath(await $.session.cwd(), expand(want.index, home))
    if (!(await $.fs.exists(index))) return next(e)
  } else {
    index = await resumeIndex($, want.slug, home)
    if (index === null) return next(e)
  }
  const graph = await planGraph($, index, home)
  if (graph === null) return next(e)
  const phase = cmd.name === 'implement' ? want.phase : undefined
  if (phase !== undefined && !graph.phases.some(p => p.n === phase)) return next(e)
  const lines = await phaseLines($, graph, index)
  const block = planBlock(cmd.name, index, graph, lines, phase)
  return next({ ...e, context: [...(e.context ?? []), block] })
}

/**
 * Quota economy: at or over the weekly threshold, independent verification is cut to the
 * minimum. MEASURED: the owner hit 96% of a small company-paid weekly quota mid-swarm.
 *
 * Returns { pct, resetsAt, threshold } at or over the threshold, null otherwise. Null is
 * also every error and every empty reading (rateLimits is empty off a subscription):
 * this is a cost saver, never a gate, so it fails OPEN to normal mode.
 */
const QUOTA_PCT = 85
// Opus and Fable: the models economy mode takes off every spawn and the main session.
const HEAVY = /opus|fable/i
// Relative to $.env HOME. swarm.py reads the same file to pick a model for spawn/launch.
const QUOTA_FILE_REL = '/.claude/swarm-deck/quota.json'
// The latest reading, kept for the band: a ui.render hook must not await anything.
let quotaNow = null

/**
 * The weekly window, the threshold and this session's model. Null on any error, which is
 * the fail-OPEN answer. Off a subscription there is no seven_day window: a reading with
 * economy false, not an error.
 */
async function reading($) {
  try {
    const raw = await $.env.get('CLAUDE_QUOTA_ECONOMY_PCT')
    const n = Number(raw)
    const threshold = raw && Number.isFinite(n) && n > 0 ? n : QUOTA_PCT
    const usage = await $.session.usage()
    const week = (usage.rateLimits || []).find(r => r.kind === 'seven_day')
    const has = !!week && typeof week.percentUsed === 'number'
    let model = null
    try {
      const m = await $.session.model()
      model = typeof m === 'string' ? m : null
    } catch {
      model = null
    }
    return {
      economy: has && week.percentUsed >= threshold,
      pct: has ? Math.round(week.percentUsed) : null,
      resetsAt: week ? week.resetsAt : null,
      threshold,
      model,
    }
  } catch {
    return null
  }
}

/** Returns { pct, resetsAt, threshold, model } at or over the threshold, null otherwise. */
async function quota($) {
  const r = await reading($)
  return r && r.economy ? r : null
}

/**
 * Refresh the band's reading and write it for swarm.py. Runs on a 15s clock and on every
 * prompt.submit. It writes economy false too, so the file says "normal" and not merely
 * "nothing known"; an error writes nothing and the last file ages out. Never throws.
 */
async function refreshQuota($) {
  const r = await reading($)
  if (r === null) return
  quotaNow = r
  try {
    const home = await $.env.get('HOME')
    if (!home) return
    await $.fs.write(home + QUOTA_FILE_REL, JSON.stringify({
      seven_day: r.pct,
      threshold: r.threshold,
      economy: r.economy,
      resetsAt: r.resetsAt,
      at: await $.clock.now(),
    }, null, 2) + '\n')
  } catch (err) {
    // swarm.py sees an old file, and an old file means the normal rules.
  }
}

/** The band line for an economy session that runs on Opus or Fable, or null. */
function modelBand() {
  if (!quotaNow || !quotaNow.economy || !quotaNow.model || !HEAVY.test(quotaNow.model)) return null
  return 'this session runs ' + quotaNow.model + '; economy mode requires sonnet/haiku -- ' +
    'switch with /model sonnet'
}

function quotaLine(q) {
  const line = 'swarm-deck: Weekly quota ' + q.pct + '% used (resets ' + (q.resetsAt || 'unknown') +
    ') -- ECONOMY MODE: no independent verifier agent (record `self-verified (quota economy, ' +
    q.pct + '%)`); each phase\'s own Proof runs once on the cheapest journeys that cover its ' +
    'exit criteria, skipping paid/live journeys (record `inconclusive (quota economy)`); ' +
    'dispatch no extra review or research agents.'
  const heavy = q.model && HEAVY.test(q.model)
    ? ' This session runs ' + q.model + '; economy mode requires sonnet/haiku -- switch with /model sonnet.'
    : ''
  return line + heavy
}

/** The prompt.submit hook: the plan block (if any), then the quota line (if over). */
async function promptContext($, e, next) {
  const planned = await attachPlan($, e, x => x)
  await refreshQuota($)
  const commanded = ['analyze-orchestrator', 'implement', 'do', 'analyze'].includes(e.command?.name)
  const q = commanded && quotaNow && quotaNow.economy ? quotaNow : null
  if (q === null) return next(planned)
  return next({ ...planned, context: [...(planned.context ?? []), quotaLine(q)] })
}

/**
 * Economy mode for every subagent: no Opus or Fable. A spawn that names none, or names
 * one of them, is set to Sonnet; an explicit haiku or sonnet is kept. Agent definitions
 * here default to opus in their frontmatter, which the hook cannot see, so an unnamed
 * spawn is always Sonnet. A fork inherits its parent's model and ignores `model`, so it
 * is refused instead. Fails OPEN: a cost saver, never a gate on work.
 */
async function modelGuard($, e, next) {
  const q = await quota($)
  if (q === null) return next(e)
  if (e.fork) {
    if (!HEAVY.test(e.parentModel || '')) return next(e)
    await $.ui.log('refused fork -- economy mode, parent ' + e.parentModel)
    return {
      deny: 'economy mode: a fork inherits ' + e.parentModel +
        '; dispatch a named subagent with model sonnet instead',
    }
  }
  const asked = e.model
  if (asked === undefined || asked === null || asked === '' || asked === 'inherit' || HEAVY.test(asked)) {
    return next({ ...e, model: 'sonnet' })
  }
  return next(e)
}

/** Refuse a `verifier` spawn in economy mode. Mechanical, but fails OPEN. */
async function verifierGuard($, e, next) {
  const q = await quota($)
  if (q === null) return next(e)
  await $.ui.log('refused verifier spawn -- weekly quota ' + q.pct + '% (economy mode)')
  return {
    deny: [
      'The verifier agent is refused: weekly quota is ' + q.pct + '% used (economy mode, ' +
        'threshold ' + q.threshold + '%).',
      '',
      'Do not dispatch an independent verifier. Record "self-verified (quota economy, ' +
        q.pct + '%)" in the ledger or report, and land on the phase\'s own Proof run once on',
      'the cheapest journeys that cover its exit criteria. Paid or live journeys are',
      'recorded as "inconclusive (quota economy)", not run.',
    ].join('\n'),
  }
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
    // Every session, not only a phase or a deck: the quota file is for whichever session
    // runs `swarm.py launch`. A reading costs no tokens, so 15s is as cheap as a heartbeat.
    try {
      $.clock.every(15000, async () => {
        await refreshQuota($)
      })
    } catch (err) {
      // No timer: the prompt.submit refresh still keeps the file and the band current.
    }
    await refreshQuota($)
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
    // The swarm alarms keep priority: a quiet phase is more urgent than the model line.
    const text = alarm(await $.clock.now()) ?? modelBand()
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

  // Fails OPEN: a resolver that throws or times out hands the prompt on as typed, and the
  // command runs plan_graph.py itself. Help must never be able to stop a prompt.
  on('prompt.submit', promptContext).catch(async ($, e, next) => next(e))

  // Fails OPEN: a cost saver, not a safety guard. An error lets the spawn through.
  on('agent.spawn', { subagentType: 'verifier' }, verifierGuard).catch(async ($, e, next) => next(e))

  // Every subagent, no matcher. Registered after the verifier refusal: both run in economy
  // mode, and the refusal is a deny, which ends the chain whichever runs first.
  on('agent.spawn', modelGuard).catch(async ($, e, next) => next(e))

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
