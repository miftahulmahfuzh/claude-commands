---
name: update-ats-cv
description: Use when asked to edit, restyle, retarget or regenerate an ATS resume/CV PDF - "update-ats-cv <input.pdf> <description>", "tighten my CV to one page", "add my new project to my resume", "make the Skills section wider", "rewrite my CV summary for this job posting". Rebuilds the PDF from a YAML content model with millimetre-level control over margins, leading, letter-spacing and columns, and guarantees the page count instead of hoping it fits.
---

# update-ats-cv

Regenerate an ATS-safe CV PDF from an existing one, applying a plain-English list of
changes, with total control over the layout.

`<input.pdf>` is only a *source of content and visual style* — it is parsed, never
patched. The deliverable is a brand-new PDF drawn from a `*.cv.yaml` content model.
That is what makes "shave 4pt off every gap" and "extend Skills to the right margin"
tractable requests.

## Invocation

```
/update-ats-cv <input_ats_cv.pdf> <description of the changes>
```

The description is free-form and may mix content edits ("add my speech-recognition
work"), structural edits ("drop the Languages section"), and typographic edits
("reduce the margins", "the two degree lines are too far apart").

## Hard rules

1. **The page-count invariant is not negotiable.** `page.max_pages` (default 1) is
   enforced by the renderer. It never spills to a second page; if the content cannot
   fit at the tightest rung of the fit ladder it exits non-zero with how many body
   lines are over. When that happens, **cut content** — do not quietly bump
   `max_pages` or shrink the type below the ladder floor.
2. **Never invent experience.** If the description says "add the multi-agent work",
   read the actual codebase / repo / doc and describe what is really there. A resume
   claim that collapses in an interview is worse than a missing bullet.
3. **Verify by looking.** After every render, run `cv_preview.py` and *Read the PNG*.
   Layout defects (collisions, a stranded widow line, a heading orphaned at the
   bottom) are invisible in the fit numbers.
4. **Verify the extraction.** Run the reading-order check below. An ATS reads text,
   not pixels; a beautiful PDF that extracts scrambled is a failed deliverable.
5. **Report what you changed and what you cut**, per item of the description.

## Workflow

### 1. Extract the source

```bash
python3 ~/.claude/skills/update-ats-cv/cv_extract.py input.pdf
```

Gives you: page geometry and real content margins, every span with bbox / size /
colour, the vector rules and bullet marks, reading-order text, and a typeface
identification pass. Use the span y-coordinates to derive the source's actual
spacing tokens (heading→rule, rule→body, title→date, bullet pitch) so the rebuild
inherits the original rhythm rather than a generic one.

Note on flattened PDFs (producer `iLovePDF`, Chrome print, most CV builders): fonts
appear as `Type3` with their real names stripped, and **bold is often faked** by
overprinting the same glyphs twice — you will see a vector rect mirroring each bold
span's bbox. Trust the width-match table, not the font names.

### 2. Write or update `<name>.cv.yaml`

Schema and every tunable: `SCHEMA.md`. Put the YAML next to the output PDF.
If a `.cv.yaml` for this person already exists, **edit it** rather than re-deriving
from the PDF — it is the source of truth, the PDF is a build artefact.

### 3. Render

```bash
python3 ~/.claude/skills/update-ats-cv/cv_render.py name.cv.yaml \
    -o Name-ATS-CV.pdf --autofit
```

`--autofit` walks `FIT_LADDER` from loosest to tightest and picks the **first** rung
that fits, so the page is as airy as the content allows. It prints the chosen rung
plus the remaining slack in body lines — a large positive slack means you have room
to add a bullet; a rung far down the ladder means the content is over-stuffed and
prose should be cut instead.

### 4. Look at it

```bash
python3 ~/.claude/skills/update-ats-cv/cv_preview.py Name-ATS-CV.pdf --against input.pdf
```

Read the emitted `*.compare.png` (old left, new right). Check: no orphaned section
heading at the page foot, no one-word last lines, column groups bottom-aligned
sensibly, bullet marks vertically centred on their first line.

### 5. Check what an ATS actually sees

```bash
python3 -c "import fitz,sys; print(fitz.open(sys.argv[1])[0].get_text())" Name-ATS-CV.pdf
```

The output must read **top to bottom in visual order** — name, contact, summary,
each section in order — with every word intact and no glyph-per-line fragmentation.
The renderer emits text in document order specifically to guarantee this; if you
change `Layout.paint`, re-verify.

## Editing recipes

| Ask | Where |
|---|---|
| "keep it to one page" | `page.max_pages` + `--autofit` (already the default) |
| "there's wasted space at the bottom" | **add content** — the render's `note:` line tells you how many body lines are free. `--expand` pads the gaps instead, which is rarely what is wanted |
| "the gaps are huge and uneven" | rebuild `space.*` from the body line pitch — see "A tight, consistent rhythm" in `SCHEMA.md` |
| "reduce the margins / padding" | `page.margin` — 32-34pt is tight but still prints safely; below ~28pt looks cramped and some printers clip |
| "tighten everything vertically" | `theme.leading` (1.66 is airy, 1.50 is tight-but-readable, below 1.40 crowds descenders) |
| "these two lines are too far apart" | the specific `space.*` token — see `SCHEMA.md` for the map |
| "make Skills span the full width" | delete the neighbouring group from the `columns` section and raise its `columns:` count |
| "put Skills and Languages side by side" | one `columns` section with two `groups`, each with its own `columns` count |
| "the headings look too tight/loose" | `theme.tracking.section` / `.entry` / `.name` (em units) |
| "add a bold lead-in to a bullet" | `{lead: "Search Engine Development:", text: "..."}` |
| "different font" | drop TTFs named `<Family>-<weight>.ttf` into `assets/fonts/` and set `theme.family` |

## Content guidance

- **Compacting prose is the highest-leverage move.** One line of 9pt body ≈ 13.7pt of
  page. Rewriting three two-line bullets into three 1.4-line bullets frees ~2 lines —
  more than any margin change.
- Lead with the verb and the system, not with "Responsible for".
- Keep a concrete anchor in each bullet (a technology, a number, a named system);
  those are the tokens both keyword filters and humans look for.
- Do not pad the Skills grid to make it rectangular. A ragged last column is fine;
  an invented skill is not.

## Dependencies

`python3` with `pymupdf` and `pyyaml`. Vendored: Lora 400/500/600/700 + italics
(SIL OFL, licence in `assets/fonts/OFL.txt`). No network access needed at render
time.
