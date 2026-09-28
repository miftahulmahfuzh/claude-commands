---
name: edit-pdf-text
description: Use when text inside an existing PDF has to be changed, corrected or swapped and the file cannot simply be re-exported from its source — "/edit-pdf-text file.pdf replace X with Y", a typo in a signed or stamped document, a wrong date, name, address or amount, a surat/kontrak/invoice that has already been printed and scanned into a form. Especially when the page carries colored backgrounds, scans, photos, materai, logos or signatures that must survive the edit untouched.
---

# Edit text inside a PDF

## Overview

A PDF does not store "text on a page". It stores *show operators* in a content stream:
codes into a font, positioned by an absolute text matrix. Editing text means rewriting
those codes. Everything else in the file — background art, scanned images, stamps,
signatures, the structure tree — then stays byte-identical because you never touched it.

**Core principle: change the glyphs, never paint over them.**

The reflex of covering the old text with a white rectangle and drawing new text on top
destroys any colored or scanned background, and it is the single most common way this
task is done wrong.

## The tool

`pdftext.py` sits **next to this SKILL.md**. Resolve it from wherever the skill is
installed rather than assuming a path:

```bash
S="$(dirname "$(find ~/.claude/skills ~/claude-commands/skills -name SKILL.md -path '*edit-pdf-text*' 2>/dev/null | head -1)")/pdftext.py"
python3 "$S" --help
```

It needs PyMuPDF (`pip install pymupdf`); numpy makes `verify` faster.

## Workflow

```bash
python3 "$S" find    in.pdf "<text to change>" --new "<replacement>"
python3 "$S" replace in.pdf out.pdf --old "<text to change>" --new "<replacement>"
python3 "$S" verify  in.pdf out.pdf --crops ./crops
```

1. **`find` first, always.** `find --new "<replacement>"` reports the font, size, color,
   position, the raw stream bytes, the *minimal edit*, and whether it is possible at all.
2. **Read the report.** Check the `editable:` verdict and every note under it.
3. **`replace`.** It refuses an ambiguous match — pass `--occurrence N` or `--all`
   deliberately. It refuses to write over its own input.
4. **`verify`.** Non-negotiable. See the gate below.
5. **Look at the crops.** A PDF can extract as correct text and still render wrong.
   `--crops` writes a tight strip per changed region (`pageN_rM_{before,after}.png`) *and*
   a whole-page render per changed page (`pageN_full_{before,after}.png`). The strips are
   for judging glyph rendering — spacing, overlap, the width-0 trap. The whole-page render
   is for the "is the materai/signature/photo still there" glance. Neither is the proof:
   the per-page **image SHA-1** in `verify` is what actually proves a stamp or scan is
   untouched.

`dump` prints every piece of real text on a page in content-stream order — use it when
`find` reports no match, to see what the PDF actually contains.

### Several edits: one invocation, not a chain

Repeat `--old`/`--new` in matching pairs. They are applied in order to one output file.

```bash
python3 "$S" replace in.pdf out.pdf \
    --old "Loading In"  --new "Loading out" \
    --old "Surabaya"    --new "Tanjung Priok"
```

Do **not** chain `in → tmp1 → tmp2 → out` by hand. Chaining invites verifying an
intermediate against the final file, which proves nothing about the earlier edits, and it
leaves temp PDFs lying around. If any pair fails, the whole run aborts and writes nothing,
so you never get a half-edited document.

**Always `verify` against the original input**, never against an intermediate.

## Why `find` reduces the edit

Asked to turn `Loading In` into `Loading out`, the tool edits `In` → `out`, not the whole
phrase. This matters: a PDF producer typically emits **one show operator per word**, each
with its own absolute `Tm`. Rewriting only the word that actually changed leaves every
other word's position exactly as the producer set it.

```
minimal : 'In' -> 'out'          <- one chunk, one Tm, surgical
```

The reduction is per **character**, not per word, so it will happily cut mid-word:
`"Jakarta, 10 Oktober 2025"` → `"Jakarta, 3 November 2025"` reduces to
`'10 Okto' -> '3 Novem'`, keeping the shared `ber 2025` tail. That looks alarming the
first time; it is correct, and it is doing less damage than a whole-phrase rewrite would.

When the minimal edit still spans several chunks, `find` says so. That path works — the
replacement is emitted from the first chunk and the leftovers are re-anchored after it —
but inspect the crop with extra care.

## Traps this tool handles for you

| Trap | What you would otherwise see |
|---|---|
| Text split by kerning: `[(I)29(n)22(;)] TJ` | `grep` finds nothing; the phrase isn't a contiguous string |
| One show op per word, each with its own `Tm` | Replacing a phrase scrambles word positions |
| Replacement is wider or narrower | The rest of the line collides or gaps (`--reflow line`, default; `--reflow none` disables) |
| **A glyph declared with width 0** | Producers declare `/Widths` only for characters the document uses. Introduce a letter the original never contained and it draws with *zero advance*, so the next letter lands on top of it — while the extracted text reads perfectly. `replace` detects this and writes the real advance into `/Widths`. |
| Type0 / Identity-H fonts | Codes are 2-byte glyph ids, not ASCII; handled via the font's `ToUnicode` map |
| Subset font missing the new glyph | `editable: NO` — the outline simply is not in the file |
| Text in Form XObjects or a second content stream | Naive page-stream edits miss it |
| Several matches inside one content stream | Each edit rewrites the whole stream, so naive offsets clobber each other |
| `Tj`, `TJ`, `'`, `"` | All four are read and re-serialized in their original form |

## When in-place editing cannot work

- **`find` reports no match and `dump` doesn't show the words.** The "text" is pixels in a
  scanned image. No text edit exists. Say so; offer to redraw that region instead, which
  *will* alter the scan.
- **`editable: NO` — glyph not in the font.** The character's outline was never embedded.
  Either pick wording that reuses available characters, or re-embed a font, which changes
  the file substantially. Say which you did.

Do not silently fall back to white-box-and-retype. If in-place editing is impossible, say
so and let the user choose.

## Verification gate

Never report success on a PDF edit without running `verify` and reading its output.
"Nothing else changed" is a claim about a binary file; `verify` is what makes it checkable.

It reports:

- **page count** and **per-page image SHA-1** — proves scans, stamps, photos are untouched.
- **rendered pixel diff, clustered into regions** — one region per edited area, *not* one
  union box. Coordinates are PDF user space, y up from the bottom — the same frame `find`
  prints, so the two are directly comparable.
- **text diff** — the extracted-text lines that differ.

What to actually check:

- Pages you did not edit come back `identical`.
- The **number of regions matches the number of edits** you made.
- Each region's y-range sits on the baseline `find` reported for that edit.
- Each region's x-range starts no further left than the x `find` reported for the first
  changed chunk. Compare against **that number**, not against a general sense of where the
  line begins — when the edit starts at the line's first word, the region legitimately
  starts there too. A region reaching left of `find`'s x means untouched words moved.
- The text diff shows exactly the lines you intended and no others.

## Common mistakes

- Going straight to `replace` without `find`, then being surprised by an ambiguous match.
- Trusting the text diff alone. Correct extracted text can still render as overlapping
  glyphs — that is exactly the width-0 trap. Look at the crop.
- Hand-chaining multiple edits instead of passing repeated `--old`/`--new`.
- Verifying against an intermediate file rather than the original.
- Treating a capitalization difference as too small to confirm. "Loading out" and
  "Loading Out" are different edits — use what the user wrote, and flag it if it looks
  unintended.

## Output modes

`replace` does an **append-only incremental save** by default: the original bytes are kept
verbatim and only changed objects are appended, so the file grows slightly. Pass
`--rewrite` for a compacted full save when size matters more than byte-level provenance.

## Tests

`./run_tests.sh` builds its own fixtures and runs 20 cases — kerned `TJ`, hex strings,
`Tj`/`'`, Type0/Identity-H, colored backgrounds, multi-chunk spans, zero-width glyphs,
several matches in one stream, multi-edit runs, insertions, and the refusals. Two extra
cases run against a real document if you point at one:

```bash
./run_tests.sh                              # 20 synthetic cases
REAL_PDF=/path/to/real.pdf ./run_tests.sh   # + 2 real-document cases
```

Run it after any change to `pdftext.py`.
