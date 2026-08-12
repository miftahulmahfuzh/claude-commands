#!/usr/bin/env python3
"""Read and write the `.workflows/todos.md` TaskID system. Stdlib only.

The canonical TaskID is `P<0-4>-<PKG>-<L><NNN>` — one letter, three digits.
Anything else is an outlier and `validate` reports it.

Four facts about the real corpus drive the parsing, all measured rather than
assumed:

  * **A section is one of three kinds, and `TodoFile.tasks()` is how you get the
    real task list.** `## Active Tasks` holds unfinished work. `## Completed
    Tasks` is where **`/do` MOVES an entry when it finishes** — still a real,
    current entry, whose `[x]` is the fact that the task is done. Everything else
    (`## Recent Activity`, `## Summary`, `## Quick Stats`) is a log: prose and
    dated snapshots that repeat ids and record what was true then. Treating the
    completed section as a log made a task finished via `/do` invisible, so
    nothing could move its board card to Completed.
  * **The checkbox is the stage, and `Status:` is not.** Across 33 files
    `Completed:` appears 475 times and `Status:` only 146, so keying on `Status:`
    shows most of the history as stageless. In a *log* section the checkbox
    records what happened at the time rather than now: in `chatbot/queue`,
    `P1-QU-A000` is `- [x]` under Completed and `- [ ]` under Recent Activity.
  * **The same ID therefore appears many times per file, legitimately.** All 55
    repeated IDs in the corpus repeat *within* one file and none across files,
    which is what distinguishes a summary echo from a real collision. `tasks()`
    collapses them to one entry, preferring the active section, and reports a
    task present in both an active and a completed section as a conflict —
    `/do` moves rather than copies, so that is an inconsistency, not a state.
  * **Package codes are not unique.** `TT` is claimed by both `tools/tooltest`
    and `tools/tooltypes`, `CMP` by both `chatbot/processing/comparison` and
    `cmd/test_lcmp`. Uniqueness is only ever checked on the whole TaskID across
    every file, never per package.

Subcommands:
  scan [--json]                 the corpus: files, entries, outliers, problems
  validate                      exit 1 if any TaskID is non-canonical or duplicated
  mint PKG [--priority P1] [--letter T]     the next free canonical TaskID
  plan-of TASKID                the canonical plan path for a TaskID
  rename-map [--json]           the old -> new mapping for every outlier
  rename [--apply]              perform it; dry-run unless --apply
  selftest                      offline assertions on synthetic fixtures
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TODOS_GLOB = ".workflows/todos.md"
PLAN_DIR = ".workflows/plan"

ID_RE = re.compile(r"^(P[0-4])-([A-Z]{1,4})-([A-Z0-9]+)$")
CANON_SUFFIX_RE = re.compile(r"^[A-Z][0-9]{3}$")
ANY_ID_RE = re.compile(r"\bP[0-4]-[A-Z]{1,4}-[A-Z0-9]+\b")
ENTRY_RE = re.compile(
    r"^(?P<indent>\s*)- \[(?P<box>[ xX])\]\s+\*\*(?P<id>P[0-4]-[A-Z]{1,4}-[A-Z0-9]+)\*\*\s*(?P<title>.*)$"
)
# A bare reference line -- `- **ID**: text` -- which is NOT a task entry. The
# root todos.md carries a block of these in its summary section.
REF_RE = re.compile(r"^\s*- \*\*(?P<id>P[0-4]-[A-Z]{1,4}-[A-Z0-9]+)\*\*:\s*(?P<text>.*)$")
FIELD_RE = re.compile(r"^(?P<indent>\s+)- \*\*(?P<name>[^*]+)\*\*:\s*(?P<value>.*)$")
SECTION_RE = re.compile(r"^###\s+\[(?P<priority>P[0-4])\]")
H2_RE = re.compile(r"^##\s+(?!#)\s*(?P<title>.+?)\s*$")
AUTHORITATIVE_SECTION = "active tasks"

# An H2 section is one of three kinds, and the distinction is load-bearing:
#
#   active     `## Active Tasks` -- unfinished work, the task's current home
#   completed  `## Completed Tasks` -- where /do MOVES a task when it finishes.
#              Still a real, current entry: the `[x]` there is the fact that the
#              task is done. Treating it as an echo made a task completed via
#              /do invisible, so nothing could move its board card to Completed.
#   log        `## Recent Activity`, `## Summary`, `## Quick Stats` -- prose and
#              dated snapshots that repeat ids and record what was true then.
SECTION_ACTIVE = "active"
SECTION_COMPLETED = "completed"
SECTION_LOG = "log"


PKG_CODE_RE = re.compile(r"^\*\*Package Code\*\*:\s*(?P<code>.+?)\s*$", re.MULTILINE)
PKG_PATH_RE = re.compile(r"^\*\*Package Path\*\*:\s*(?P<path>.+?)\s*$", re.MULTILINE)

FORMER_ID_FIELD = "Former ID"


def section_kind(title):
    t = (title or "").strip().lower()
    if "active" in t:
        return SECTION_ACTIVE
    if "completed" in t or "done" in t:
        return SECTION_COMPLETED
    return SECTION_LOG


class TodoError(Exception):
    """A failure with a message meant for the user."""


# ------------------------------------------------------------------- data model


class Entry:
    __slots__ = ("task_id", "priority", "pkg", "suffix", "title", "done", "fields",
                 "start", "end", "file", "section")

    def __init__(self, task_id, title, done, start, file, section=None):
        m = ID_RE.match(task_id)
        self.task_id = task_id
        self.priority = m.group(1) if m else None
        self.pkg = m.group(2) if m else None
        self.suffix = m.group(3) if m else None
        self.title = title
        self.done = done
        self.fields = {}
        self.start = start
        self.end = start + 1
        self.file = file
        self.section = section

    @property
    def canonical(self):
        return bool(self.suffix and CANON_SUFFIX_RE.match(self.suffix))

    @property
    def authoritative(self):
        """True only under `## Active Tasks` -- unfinished work."""
        return (self.section or "").strip().lower() == AUTHORITATIVE_SECTION

    @property
    def kind(self):
        return section_kind(self.section)

    @property
    def current(self):
        """True when this entry states the task's present state.

        Both `## Active Tasks` and `## Completed Tasks` do -- one says unfinished,
        the other says finished, and /do moves an entry from the first to the
        second. Only log and summary sections are excluded.
        """
        return self.kind in (SECTION_ACTIVE, SECTION_COMPLETED)

    def to_dict(self):
        return {
            "taskId": self.task_id,
            "priority": self.priority,
            "pkg": self.pkg,
            "suffix": self.suffix,
            "title": self.title,
            "done": self.done,
            "canonical": self.canonical,
            "section": self.section,
            "authoritative": self.authoritative,
            "fields": dict(self.fields),
            "file": str(self.file),
            "lines": [self.start + 1, self.end],
        }


class TodoFile:
    def __init__(self, path, root):
        # Both resolved: a caller passing a relative path (`.workflows/todos.md`)
        # with an absolute root is the normal case from a CLI argument, and
        # relative_to raised on it.
        self.path = Path(path).resolve()
        root = Path(root).resolve()
        try:
            self.rel = str(self.path.relative_to(root))
        except ValueError:
            self.rel = str(self.path)
        self.text = self.path.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()
        code = PKG_CODE_RE.search(self.text)
        # One real header declares its code as `CA` -- wrapped in backticks.
        self.pkg_code = code.group("code").strip().strip("`").strip() if code else None
        pkg_path = PKG_PATH_RE.search(self.text)
        self.pkg_path = pkg_path.group("path").strip().strip("`").strip() if pkg_path else None
        self.package_dir = str(self.path.parent.parent.relative_to(root)) or "."
        self.entries, self.refs = parse_entries(self.lines, self.rel)

    def tasks(self):
        """One entry per TaskID: the file's actual task list, plus disagreements.

        A TaskID can appear many times in one file -- once where it lives, and
        again in every rolling-summary bucket and activity-log line. This picks
        the entry that states the present: `## Active Tasks` if the task is there,
        otherwise `## Completed Tasks`. Ids appearing only in a log section are
        not tasks and are dropped.

        `conflicts` is a task present in BOTH an active and a completed section.
        /do *moves* an entry rather than copying it, so that should not happen;
        when it does, the active copy is preferred (a reopen is the likelier
        cause than a stale completion) and the disagreement is reported instead
        of being silently resolved.
        """
        best, conflicts, reported = {}, [], set()
        for e in self.entries:
            if not e.current:
                continue
            seen = best.get(e.task_id)
            if seen is None:
                best[e.task_id] = e
                continue
            if seen.kind != e.kind:
                # One conflict per TaskID, not one per echo: a task in Active
                # plus three rolling-summary buckets would otherwise report the
                # same disagreement three times.
                if e.task_id not in reported:
                    reported.add(e.task_id)
                    conflicts.append({
                        "taskId": e.task_id,
                        "sections": sorted({seen.section, e.section}),
                        "lines": sorted([seen.start + 1, e.start + 1]),
                        "preferred": SECTION_ACTIVE,
                    })
                if e.kind == SECTION_ACTIVE:
                    best[e.task_id] = e
            # same kind twice is a rolling-summary echo: keep the first
        return [best[k] for k in sorted(best)], conflicts


def parse_entries(lines, rel="<memory>"):
    """Split lines into task entries and bare `- **ID**: text` references.

    A module function rather than a method because the rename pass has to
    re-parse text it has just rewritten, before any file exists to read.
    """
    entries, refs = [], []
    current = None
    section = None
    for i, line in enumerate(lines):
        m = ENTRY_RE.match(line)
        if m:
            if current is not None:
                current.end = i
            current = Entry(
                m.group("id"),
                m.group("title").strip(),
                m.group("box").lower() == "x",
                i,
                rel,
                section,
            )
            entries.append(current)
            continue
        if line.startswith("#") or line.strip() == "---":
            h2 = H2_RE.match(line)
            if h2:
                section = h2.group("title")
            if current is not None:
                current.end = i
                current = None
            continue
        ref = REF_RE.match(line)
        if ref and current is None:
            refs.append({
                "taskId": ref.group("id"),
                "text": ref.group("text"),
                "line": i + 1,
                "section": section,
                "authoritative": (section or "").strip().lower() == AUTHORITATIVE_SECTION,
            })
            continue
        if current is not None:
            f = FIELD_RE.match(line)
            if f:
                current.fields[f.group("name").strip()] = f.group("value").strip()
            current.end = i + 1
    if current is not None and current.end <= current.start:
        current.end = len(lines)
    return entries, refs


# ---------------------------------------------------------------------- corpus


def discover(root):
    root = Path(root)
    found = sorted(root.glob(f"**/{TODOS_GLOB}"))
    return [p for p in found if ".git/" not in str(p)]


class Corpus:
    def __init__(self, root):
        self.root = Path(root).resolve()
        paths = discover(self.root)
        if not paths:
            raise TodoError(f"No {TODOS_GLOB} found under {self.root}.")
        self.files = [TodoFile(p, self.root) for p in paths]
        # Index the authoritative entry for each id, and only count a duplicate
        # when two authoritative entries collide -- a summary echo is not one.
        self.by_id = {}
        self.duplicates = {}
        for e in self.authoritative_entries:
            if e.task_id in self.by_id:
                self.duplicates.setdefault(e.task_id, [self.by_id[e.task_id]]).append(e)
            else:
                self.by_id[e.task_id] = e
        # Ids that exist only in a log or summary section still need indexing,
        # so a rename or a uniqueness check can see them.
        for e in self.entries:
            self.by_id.setdefault(e.task_id, e)

    @property
    def entries(self):
        return [e for f in self.files for e in f.entries]

    @property
    def authoritative_entries(self):
        return [e for e in self.entries if e.authoritative]

    @property
    def outliers(self):
        """One per distinct non-canonical id, preferring the authoritative row."""
        out = {}
        for e in self.entries:
            if e.canonical:
                continue
            if e.task_id not in out or (e.authoritative and not out[e.task_id].authoritative):
                out[e.task_id] = e
        return [out[k] for k in sorted(out)]

    def all_ids(self):
        """Every ID mentioned anywhere -- entries and bare references alike."""
        ids = set(self.by_id)
        for f in self.files:
            ids.update(r["taskId"] for r in f.refs)
        return ids

    def used_numbers(self, pkg, letter):
        """Numbers already taken for pkg+letter, across every priority.

        Priority is part of the TaskID, so the same suffix can legally appear
        under two priorities today (P1-MN-TZ019 and P2-MN-TZ019 both exist).
        Reserving per package rather than per priority is what stops a
        re-prioritised task from colliding with a freshly minted one.
        """
        taken = set()
        for task_id in self.all_ids():
            m = ID_RE.match(task_id)
            if not m or m.group(2) != pkg:
                continue
            suffix = m.group(3)
            if suffix.startswith(letter):
                digits = suffix[len(letter):]
                if digits.isdigit():
                    taken.add(int(digits))
        return taken

    def next_suffix(self, pkg, letter, reserved=()):
        letter = letter.upper()[:1] or "A"
        taken = self.used_numbers(pkg, letter) | {
            int(s[1:]) for s in reserved if s[:1] == letter and s[1:].isdigit()
        }
        for n in range(1, 1000):
            if n not in taken:
                return f"{letter}{n:03d}"
        raise TodoError(f"No free number left for {pkg}-{letter}###.")

    def package_codes(self):
        out = {}
        for f in self.files:
            if f.pkg_code:
                out.setdefault(f.pkg_code, []).append(f.package_dir)
        return out


# ------------------------------------------------------------------- validation


def validate(corpus):
    problems = []
    for e in corpus.outliers:
        problems.append(
            {
                "kind": "non_canonical_id",
                "taskId": e.task_id,
                "file": e.file,
                "line": e.start + 1,
                "done": e.done,
            }
        )
    for task_id, entries in corpus.duplicates.items():
        problems.append(
            {
                "kind": "duplicate_id",
                "taskId": task_id,
                "files": [f"{e.file}:{e.start + 1}" for e in entries],
            }
        )
    entry_ids = set(corpus.by_id)
    for f in corpus.files:
        for ref in f.refs:
            m = ID_RE.match(ref["taskId"])
            # A bare reference carries an id too, and `rename` cannot touch one
            # that names no entry -- so validate has to see it, or it reports a
            # clean corpus while non-canonical ids sit in the file.
            #
            # But a reference inside a dated `## Recent Activity` or `## Completed`
            # block is history, not a task registry: no new id is ever minted
            # there. Blocking on those forever would train the reader to ignore
            # a red validator, so they are reported as historical instead.
            if not m or not CANON_SUFFIX_RE.match(m.group(3)):
                problems.append(
                    {
                        "kind": "non_canonical_reference" if ref["authoritative"]
                        else "historical_reference",
                        "taskId": ref["taskId"],
                        "file": f.rel,
                        "line": ref["line"],
                        "section": ref["section"],
                        "hasEntry": ref["taskId"] in entry_ids,
                    }
                )
            if ref["taskId"] not in entry_ids:
                problems.append(
                    {
                        "kind": "reference_without_entry",
                        "taskId": ref["taskId"],
                        "file": f.rel,
                        "line": ref["line"],
                    }
                )
    for code, dirs in corpus.package_codes().items():
        if len(dirs) > 1:
            problems.append({"kind": "shared_package_code", "code": code, "packages": dirs})

    plan_dir = corpus.root / PLAN_DIR
    if plan_dir.is_dir():
        seen = {}
        for p in sorted(plan_dir.iterdir()):
            if not p.is_file():
                continue
            lower = p.name.lower()
            if lower in seen:
                problems.append(
                    {
                        "kind": "case_colliding_plan",
                        "files": [seen[lower], p.name],
                        "bothEmpty": p.stat().st_size == 0
                        and (plan_dir / seen[lower]).stat().st_size == 0,
                    }
                )
            seen[lower] = p.name
            if p.stat().st_size == 0:
                problems.append({"kind": "empty_plan", "file": p.name})
    return problems


# ----------------------------------------------------------------- rename logic


def build_rename_map(corpus):
    """Old -> new for every outlier. Deterministic: sorted by old ID.

    The new suffix keeps the old one's first letter, so `TZ019` becomes `T###`
    and `AUTH001` becomes `A###` -- the mnemonic survives the normalisation.
    """
    mapping = {}
    reserved = {}
    for e in sorted(corpus.outliers, key=lambda x: x.task_id):
        letter = (e.suffix or "A")[:1]
        pkg = e.pkg
        pool = reserved.setdefault(pkg, set())
        suffix = corpus.next_suffix(pkg, letter, reserved=pool)
        pool.add(suffix)
        mapping[e.task_id] = f"{e.priority}-{pkg}-{suffix}"
    return mapping


def _id_pattern(old_ids):
    """One regex for every old id, longest first so no id shadows a prefix."""
    ordered = sorted(old_ids, key=len, reverse=True)
    return re.compile(
        r"(?<![A-Z0-9])(" + "|".join(re.escape(i) for i in ordered) + r")(?![A-Z0-9])"
    )


def rewrite_text(text, mapping, pattern):
    return pattern.sub(lambda m: mapping[m.group(1)], text)


def insert_former_id(lines, entry, old_id):
    """Add `- **Former ID**: <old>` at the end of an entry's field block."""
    if FORMER_ID_FIELD in entry.fields:
        return lines, False
    indent = None
    insert_at = entry.start + 1
    for i in range(entry.start + 1, min(entry.end, len(lines))):
        f = FIELD_RE.match(lines[i])
        if f:
            indent = f.group("indent")
            insert_at = i + 1
    if indent is None:
        indent = "  "
        insert_at = entry.start + 1
    lines = list(lines)
    lines.insert(insert_at, f"{indent}- **{FORMER_ID_FIELD}**: {old_id}")
    return lines, True


def text_files(root):
    """Tracked text files that could mention a TaskID."""
    root = Path(root)
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True, text=True, check=True,
        ).stdout
        names = [n for n in out.split("\0") if n]
    except (subprocess.CalledProcessError, FileNotFoundError):
        names = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
    keep = (".md", ".txt", ".yml", ".yaml", ".json", ".go", ".py", ".sh")
    return [root / n for n in names if n.endswith(keep)]


def plan_path_for(task_id):
    return f"{PLAN_DIR}/{task_id}.md"


def plan_renames(root, mapping):
    """Plan files whose name begins with a renamed ID."""
    plan_dir = Path(root) / PLAN_DIR
    out = []
    if not plan_dir.is_dir():
        return out
    for p in sorted(plan_dir.iterdir()):
        if not p.is_file():
            continue
        for old, new in mapping.items():
            if p.name == f"{old}.md" or p.name.startswith(f"{old}-") or p.name.startswith(f"{old}."):
                out.append((p.name, p.name.replace(old, new, 1)))
                break
    return out


LEDGER_PATH = ".workflows/TASKID-RENAMES.md"
LEDGER_HEADER = """# TaskID renames

The canonical TaskID is `P<0-4>-<PKG>-<L><NNN>` — one letter, three digits.
This file is the durable record of every id that was normalised.

It exists because a `**Former ID**` field can only be stamped on a live entry
under `## Active Tasks`, and many normalised ids survive only as echoes in a
`## Completed` or `## Recent Activity` section, where a stamp would be noise.
Commit messages naming an old id stay findable through this table.
"""


def write_ledger(root, mapping, corpus, today):
    """Append a dated table of old -> new. Idempotent per day is not attempted;
    a second rename run on a clean corpus produces no mapping and no section."""
    path = Path(root) / LEDGER_PATH
    rows = []
    for old in sorted(mapping):
        entry = corpus.by_id.get(old)
        if entry is None:
            state = "unknown"
        elif not entry.authoritative:
            state = "log only"
        else:
            state = "completed" if entry.done else "active"
        rows.append(f"| `{old}` | `{mapping[old]}` | {state} |")
    section = "\n".join(
        [f"\n## {today}\n", "| Old | New | State |", "|---|---|---|"] + rows + [""]
    )
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            text += "\n"
        text += section
    else:
        text = LEDGER_HEADER + section
    path.write_text(text, encoding="utf-8")
    return str(path.relative_to(Path(root)))


def apply_rename(root, mapping, apply=False, today=None):
    root = Path(root).resolve()
    corpus = Corpus(root)
    pattern = _id_pattern(mapping)
    actions: dict = {
        "files": [], "planRenames": [], "formerIds": [], "deletions": [],
        "ledger": LEDGER_PATH,
    }

    # 1. todos.md files: rewrite ids, THEN stamp the old id onto each entry.
    #
    # The order matters and is the whole point. Stamping first meant the blanket
    # id rewrite immediately overwrote `- **Former ID**: P1-MN-AUTH001` with the
    # new id, silently destroying the one thing that keeps 438 commit messages
    # greppable. So: rewrite, re-parse the rewritten lines, then insert.
    inverse = {new: old for old, new in mapping.items()}
    for f in corpus.files:
        original = f.text
        n_renamed = sum(1 for e in f.entries if e.task_id in mapping)
        new_text = rewrite_text(original, mapping, pattern)
        lines = new_text.splitlines()
        reparsed, _ = parse_entries(lines, f.rel)
        # Insert from the bottom up so earlier line numbers stay valid.
        for e in sorted(reparsed, key=lambda x: x.start, reverse=True):
            old_id = inverse.get(e.task_id)
            # Stamp the live entry only. A summary echo gets its id rewritten
            # like everything else, but a Former ID line in a log section is
            # noise -- and would make the stamp look like it appeared N times.
            if not old_id or not e.authoritative:
                continue
            lines, added = insert_former_id(lines, e, old_id)
            if added:
                actions["formerIds"].append({"file": f.rel, "taskId": old_id})
        new_text = "\n".join(lines)
        if original.endswith("\n") and not new_text.endswith("\n"):
            new_text += "\n"
        if new_text != original:
            actions["files"].append({"file": f.rel, "idsRenamed": n_renamed})
            if apply:
                f.path.write_text(new_text, encoding="utf-8")

    # 2. Every other text file that mentions a renamed id.
    todo_paths = {f.path for f in corpus.files}
    for path in text_files(root):
        if path in todo_paths or not path.is_file():
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not pattern.search(original):
            continue
        new_text = rewrite_text(original, mapping, pattern)
        if new_text != original:
            actions["files"].append({"file": str(path.relative_to(root)), "idsRenamed": None})
            if apply:
                path.write_text(new_text, encoding="utf-8")

    # 3. Plan filenames.
    for old_name, new_name in plan_renames(root, mapping):
        actions["planRenames"].append({"from": old_name, "to": new_name})
        if apply:
            src = root / PLAN_DIR / old_name
            dst = root / PLAN_DIR / new_name
            if dst.exists() and dst.resolve() != src.resolve():
                raise TodoError(f"Refusing to overwrite existing plan {new_name}.")
            subprocess.run(
                ["git", "-C", str(root), "mv", "--", str(src), str(dst)],
                check=False, capture_output=True, text=True,
            )
            if src.exists():
                src.rename(dst)

    # 4. The ledger, which covers ids no Former ID stamp can reach.
    actions["ledger"] = LEDGER_PATH
    if apply:
        import datetime
        actions["ledger"] = write_ledger(
            root, mapping, corpus, today or datetime.date.today().isoformat()
        )

    return actions


# ------------------------------------------------------------------ subcommands


def cmd_scan(args):
    corpus = Corpus(args.root)
    problems = validate(corpus)
    live = corpus.authoritative_entries
    summary = {
        "root": str(corpus.root),
        "files": len(corpus.files),
        "entriesTotal": len(corpus.entries),
        "entriesLive": len(live),
        "summaryEchoes": len(corpus.entries) - len(live),
        "active": sum(1 for e in live if not e.done),
        "completed": sum(1 for e in live if e.done),
        "canonical": sum(1 for e in live if e.canonical),
        "outliers": len(corpus.outliers),
        "outliersActive": sum(1 for e in corpus.outliers if not e.done and e.authoritative),
        "problems": problems,
        "packageCodes": corpus.package_codes(),
    }
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0
    print(f"{summary['files']} todos.md, {summary['entriesLive']} live entries "
          f"({summary['active']} active, {summary['completed']} completed) "
          f"+ {summary['summaryEchoes']} summary/log echoes")
    print(f"canonical {summary['canonical']}, outliers {summary['outliers']} "
          f"({summary['outliersActive']} of them active)")
    kinds = {}
    for p in problems:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    for kind, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {kind}: {n}")
    return 0


BLOCKING = ("non_canonical_id", "duplicate_id", "non_canonical_reference")


def cmd_validate(args):
    corpus = Corpus(args.root)
    problems = [p for p in validate(corpus) if p["kind"] in BLOCKING]
    historical = [p for p in validate(corpus) if p["kind"] == "historical_reference"]
    if not problems:
        print(
            f"validate: {len(corpus.authoritative_entries)} live entries "
            f"({len(corpus.entries)} incl. echoes), every TaskID canonical and unique"
        )
        if historical:
            print(
                f"note: {len(historical)} non-canonical id(s) remain in historical log "
                f"sections, which are not a source of new ids:"
            )
            for p in historical:
                print(f"  {p['taskId']}  {p['file']}:{p['line']}  (## {p['section']})")
        return 0
    renamable = 0
    for p in problems:
        if p["kind"] == "duplicate_id":
            print(f"duplicate  {p['taskId']}  {', '.join(p['files'])}", file=sys.stderr)
        elif p["kind"] == "non_canonical_reference":
            note = "" if p["hasEntry"] else "  (no entry -- `rename` cannot reach it)"
            print(f"reference  {p['taskId']}  {p['file']}:{p['line']}{note}", file=sys.stderr)
        else:
            renamable += 1
            print(f"outlier    {p['taskId']}  {p['file']}:{p['line']}", file=sys.stderr)
    print(f"\n{len(problems)} problem(s).", file=sys.stderr)
    if renamable:
        print("Entries fix with: todos.py rename --apply", file=sys.stderr)
    return 1


def cmd_mint(args):
    corpus = Corpus(args.root)
    codes = corpus.package_codes()
    if args.pkg not in codes:
        raise TodoError(
            f"Unknown package code {args.pkg!r}. Known: {', '.join(sorted(codes))}."
        )
    suffix = corpus.next_suffix(args.pkg, args.letter or "A")
    task_id = f"{args.priority}-{args.pkg}-{suffix}"
    print(json.dumps(
        {
            "taskId": task_id,
            "packages": codes[args.pkg],
            "planPath": plan_path_for(task_id),
            "sharedCode": len(codes[args.pkg]) > 1,
        },
        indent=2,
    ))
    return 0


def cmd_plan_of(args):
    print(plan_path_for(args.task_id))
    return 0


def cmd_rename_map(args):
    corpus = Corpus(args.root)
    mapping = build_rename_map(corpus)
    if args.json:
        print(json.dumps(mapping, indent=2))
        return 0
    if not mapping:
        print("nothing to rename")
        return 0
    width = max(len(k) for k in mapping)
    for old in sorted(mapping):
        entry = corpus.by_id.get(old)
        state = "completed" if entry and entry.done else "active"
        print(f"{old:<{width}}  ->  {mapping[old]:<16} [{state}]")
    print(f"\n{len(mapping)} TaskID(s)")
    return 0


def cmd_rename(args):
    corpus = Corpus(args.root)
    mapping = build_rename_map(corpus)
    if not mapping:
        print("nothing to rename")
        return 0
    actions = apply_rename(args.root, mapping, apply=args.apply)
    verb = "renamed" if args.apply else "would rename"
    print(json.dumps(
        {
            "apply": bool(args.apply),
            "verb": verb,
            "taskIds": len(mapping),
            "filesTouched": len(actions["files"]),
            "planRenames": actions["planRenames"],
            "formerIdsStamped": len(actions["formerIds"]),
            "mapping": mapping,
        },
        indent=2,
    ))
    if not args.apply:
        print("\ndry run -- nothing written. Re-run with --apply.", file=sys.stderr)
    return 0


# -------------------------------------------------------------------- selftest

FIXTURE_ROOT = """# Todos: Fixture

**Package Path**: `.` (Project Root)

**Package Code**: MN

---

## Active Tasks

### [P0] Critical
- [ ] **P0-MN-TZ013** Fix template reparsing
  - **Difficulty**: EASY
  - **Context**: parsed on every request
  - **Status**: active

### [P1] High
- [x] **P1-MN-L003** Web search language parameter
  - **Difficulty**: NORMAL
  - **Status**: completed
  - **Plan**: `.workflows/plan/P1-MN-L003.md`
  - **Files Modified**:
    - `a.go` - did a thing
- [x] **P1-MN-AUTH001** Auth rework
  - **Plan**: `.workflows/plan/P1-MN-AUTH001-plan.md`

### [P2] Medium
- [ ] **P2-MN-T001** Already canonical, T-series taken

---

## Completed Tasks

### Recently Completed
- [x] **P1-MN-D001** Finished by /do and moved out of Active Tasks
  - **Completed**: 2026-08-12
  - **Method**: did the thing

### This Week
- [x] **P1-MN-L003** Web search language parameter
  - **Completed**: 2026-05-21

### This Month
- [x] **P1-MN-L003** Web search language parameter
  - **Completed**: 2026-05-21

---

## Recent Activity

### [2026-01-01] - Initial Analysis

#### Completed
- [x] **P0-MN-TZ013** Fix template reparsing
  - **Method**: an echo whose checkbox contradicts the active entry

---

## Summary
- **P2-MN-TZ019**: a bare reference, not an entry
"""

FIXTURE_SUB = """# Todos: Sub

**Package Path**: `chatbot/cancellation`

**Package Code**: `CA`

## Active Tasks

### [P1] High
- [ ] **P1-CA-C001** something
  - **Status**: active
"""


def cmd_selftest(args):
    import shutil
    import tempfile

    failures = []

    def eq(label, got, want):
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    tmp = Path(tempfile.mkdtemp(prefix="todos-selftest-"))
    try:
        (tmp / ".workflows" / "plan").mkdir(parents=True)
        (tmp / ".workflows" / "todos.md").write_text(FIXTURE_ROOT)
        (tmp / "chatbot" / "cancellation" / ".workflows").mkdir(parents=True)
        (tmp / "chatbot" / "cancellation" / ".workflows" / "todos.md").write_text(FIXTURE_SUB)
        (tmp / ".workflows" / "plan" / "P1-MN-AUTH001-plan.md").write_text("# plan\nsee P1-MN-AUTH001\n")
        (tmp / ".workflows" / "plan" / "P1-MN-L003.md").write_text("# plan\n")
        (tmp / ".workflows" / "plan" / "empty.md").write_text("")
        (tmp / "CHANGELOG.md").write_text("- P1-MN-AUTH001 shipped\n- P0-MN-TZ013 pending\n")

        c = Corpus(tmp)
        eq("files", len(c.files), 2)
        # 5 in Active Tasks + 3 in Completed Tasks (D001 + two L003 buckets)
        # + 1 Recent Activity echo of TZ013
        eq("entries", len(c.entries), 9)
        eq("authoritative entries", len(c.authoritative_entries), 5)
        eq("active", sum(1 for e in c.authoritative_entries if not e.done), 3)
        eq("completed", sum(1 for e in c.authoritative_entries if e.done), 2)

        # A summary echo is not a duplicate, and never overrides the live stage.
        eq("no duplicates from echoes", c.duplicates, {})
        eq("authoritative stage wins", c.by_id["P0-MN-TZ013"].done, False)
        eq("indexed entry is authoritative", c.by_id["P0-MN-TZ013"].authoritative, True)
        eq("echo section recorded",
           sorted({e.section for e in c.entries if e.task_id == "P1-MN-L003"}),
           ["Active Tasks", "Completed Tasks"])
        eq("outliers deduped", len(c.outliers), 2)

        # the checkbox is the stage, even when Status: disagrees or is absent
        auth = c.by_id["P1-MN-AUTH001"]
        eq("auth done via checkbox", auth.done, True)
        eq("auth has no Status field", "Status" in auth.fields, False)

        # backticked package code is stripped
        sub = [f for f in c.files if f.package_dir.endswith("cancellation")][0]
        eq("backticks stripped", sub.pkg_code, "CA")

        # fields parsed, including one with a nested list beneath it
        l003 = c.by_id["P1-MN-L003"]
        eq("plan field", l003.fields.get("Plan"), "`.workflows/plan/P1-MN-L003.md`")
        eq("difficulty", l003.fields.get("Difficulty"), "NORMAL")

        # bare reference is a ref, not an entry
        eq("ref not entry", "P2-MN-TZ019" in c.by_id, False)
        eq("ref captured", any(r["taskId"] == "P2-MN-TZ019" for f in c.files for r in f.refs), True)

        # canonical detection
        eq("TZ013 outlier", c.by_id["P0-MN-TZ013"].canonical, False)
        eq("L003 canonical", c.by_id["P1-MN-L003"].canonical, True)
        eq("outlier count", len(c.outliers), 2)

        # minting skips a number already used, per package and across priorities
        eq("mint MN T-series avoids T001", c.next_suffix("MN", "T"), "T002")
        eq("mint MN L-series avoids L003", c.next_suffix("MN", "L"), "L001")
        eq("mint reserved", c.next_suffix("MN", "T", reserved={"T002"}), "T003")
        eq("mint fresh letter", c.next_suffix("MN", "Z"), "Z001")

        # the bare reference reserves its number too
        eq("ref reserves TZ019 under T", 19 in c.used_numbers("MN", "T"), False)

        problems = {p["kind"] for p in validate(c)}
        eq("reports outliers", "non_canonical_id" in problems, True)
        eq("reports dangling ref", "reference_without_entry" in problems, True)
        eq("reports empty plan", "empty_plan" in problems, True)

        # A non-canonical id in a historical log is reported as historical, and
        # must not block: no new id is ever minted in a Recent Activity block.
        hist = [p for p in validate(c) if p["kind"] == "historical_reference"]
        eq("summary ref is historical", [p["taskId"] for p in hist], ["P2-MN-TZ019"])

        # section kinds, and the /do case: a finished task MOVES to a completed
        # section and must stay a real task there
        eq("kind active", section_kind("Active Tasks"), SECTION_ACTIVE)
        eq("kind completed tasks", section_kind("Completed Tasks"), SECTION_COMPLETED)
        eq("kind completed", section_kind("Completed"), SECTION_COMPLETED)
        eq("kind log", section_kind("Recent Activity"), SECTION_LOG)
        eq("kind summary", section_kind("Summary"), SECTION_LOG)
        eq("kind none", section_kind(None), SECTION_LOG)
        root = [f for f in c.files if f.rel.endswith("todos.md") and f.pkg_code == "MN"][0]
        tasks, sec_conflicts = root.tasks()
        ids = {t.task_id for t in tasks}

        # THE /do CASE: a task that exists only under `## Completed Tasks`,
        # having been moved there when it finished. It must still be a task, and
        # it must read as done -- otherwise nothing moves its board card.
        eq("completed-only task survives", "P1-MN-D001" in ids, True)
        d001 = next(t for t in tasks if t.task_id == "P1-MN-D001")
        eq("completed-only reads as done", d001.done, True)
        eq("completed-only is current", d001.current, True)
        eq("completed-only is NOT authoritative", d001.authoritative, False)
        eq("completed-only kind", d001.kind, SECTION_COMPLETED)
        eq("its Completed date is available", d001.fields.get("Completed"), "2026-08-12")

        eq("one entry per id", len(tasks), len(ids))
        eq("log-only id is not a task", "P2-MN-TZ019" in ids, False)
        eq("rolling-summary echoes collapsed",
           len([e for e in root.entries if e.task_id == "P1-MN-L003"]), 3)
        eq("but only one L003 task", len([t for t in tasks if t.task_id == "P1-MN-L003"]), 1)

        # L003 sits in BOTH Active Tasks and Completed Tasks: /do moves rather
        # than copies, so that is an inconsistency, reported not resolved.
        eq("section conflict reported", [c_["taskId"] for c_ in sec_conflicts], ["P1-MN-L003"])
        eq("conflict names both sections", sec_conflicts[0]["sections"],
           ["Active Tasks", "Completed Tasks"])
        eq("active copy preferred",
           next(t for t in tasks if t.task_id == "P1-MN-L003").kind, SECTION_ACTIVE)
        eq("historical never blocks", "historical_reference" in BLOCKING, False)
        eq("no blocking ref problem", [p for p in validate(c)
                                       if p["kind"] == "non_canonical_reference"], [])

        # rename map: keeps the first letter, deterministic, no collisions
        mapping = build_rename_map(c)
        eq("map size", len(mapping), 2)
        eq("AUTH001 -> A###", mapping["P1-MN-AUTH001"], "P1-MN-A001")
        eq("TZ013 -> T002 (T001 taken)", mapping["P0-MN-TZ013"], "P0-MN-T002")
        eq("no new collisions", len(set(mapping.values()) & c.all_ids()), 0)

        # prefix safety: a longer id must not be clobbered by a shorter one
        pat = _id_pattern({"P1-MN-A00": "X", "P1-MN-A001": "Y"})
        eq("longest first", rewrite_text("P1-MN-A001", {"P1-MN-A00": "X", "P1-MN-A001": "Y"}, pat), "Y")

        # dry run writes nothing
        before = (tmp / ".workflows" / "todos.md").read_text()
        dry = apply_rename(tmp, mapping, apply=False)
        eq("dry run inert", (tmp / ".workflows" / "todos.md").read_text(), before)
        eq("dry run saw files", len(dry["files"]) >= 2, True)
        eq("dry run saw plan rename", dry["planRenames"], [{"from": "P1-MN-AUTH001-plan.md", "to": "P1-MN-A001-plan.md"}])

        # apply
        apply_rename(tmp, mapping, apply=True, today="2026-01-02")
        after = (tmp / ".workflows" / "todos.md").read_text()
        eq("new id present", "P1-MN-A001" in after, True)
        eq("old id gone from entry line", "**P1-MN-AUTH001**" in after, False)
        eq("former id stamped", "- **Former ID**: P1-MN-AUTH001" in after, True)
        eq("former id for TZ013", "- **Former ID**: P0-MN-TZ013" in after, True)
        eq("plan field followed the rename", "`.workflows/plan/P1-MN-A001-plan.md`" in after, True)
        eq("canonical id untouched", "**P1-MN-L003**" in after, True)
        eq("changelog rewritten", "P1-MN-A001 shipped" in (tmp / "CHANGELOG.md").read_text(), True)
        eq("plan file renamed", (tmp / ".workflows" / "plan" / "P1-MN-A001-plan.md").exists(), True)
        eq("plan body rewritten", "P1-MN-A001" in (tmp / ".workflows" / "plan" / "P1-MN-A001-plan.md").read_text(), True)

        # the ledger covers every id, including any with no live entry to stamp
        ledger = (tmp / LEDGER_PATH).read_text()
        eq("ledger has both ids", all(i in ledger for i in ("P1-MN-AUTH001", "P0-MN-TZ013")), True)
        eq("ledger has new ids", all(i in ledger for i in ("P1-MN-A001", "P0-MN-T002")), True)
        eq("ledger dated", "## 2026-01-02" in ledger, True)

        # idempotent: a second pass finds nothing left to do
        # every occurrence moved, including the log echo -- one Former ID only
        eq("echo renamed too", after.count("P0-MN-T002"), 2)
        eq("old id gone from entry lines", "**P0-MN-TZ013**" in after, False)
        eq("former id stamped once", after.count("- **Former ID**: P0-MN-TZ013"), 1)

        c2 = Corpus(tmp)
        eq("no outliers left", len(c2.outliers), 0)
        eq("second map empty", build_rename_map(c2), {})
        eq("entries preserved", len(c2.entries), 9)
        eq("authoritative preserved", len(c2.authoritative_entries), 5)
        eq("no duplicates introduced", c2.duplicates, {})
        eq("stage preserved", c2.by_id["P1-MN-A001"].done, True)
        eq("former id readable", c2.by_id["P1-MN-A001"].fields.get("Former ID"), "P1-MN-AUTH001")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print("FAIL\n  " + "\n  ".join(failures), file=sys.stderr)
        return 1
    print("selftest: all assertions passed")
    return 0


# ------------------------------------------------------------------------- main


def main(argv=None):
    parser = argparse.ArgumentParser(prog="todos.py", description=__doc__)
    parser.add_argument("--root", default=".", help="repo root (default: cwd)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_scan)
    sub.add_parser("validate").set_defaults(fn=cmd_validate)
    sub.add_parser("selftest").set_defaults(fn=cmd_selftest)

    p = sub.add_parser("mint")
    p.add_argument("pkg")
    p.add_argument("--priority", default="P1", choices=["P0", "P1", "P2", "P3", "P4"])
    p.add_argument("--letter")
    p.set_defaults(fn=cmd_mint)

    p = sub.add_parser("plan-of"); p.add_argument("task_id"); p.set_defaults(fn=cmd_plan_of)
    p = sub.add_parser("rename-map"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_rename_map)
    p = sub.add_parser("rename"); p.add_argument("--apply", action="store_true"); p.set_defaults(fn=cmd_rename)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except TodoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
