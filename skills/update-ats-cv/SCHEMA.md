# `*.cv.yaml` schema

Every key is optional and falls back to the defaults in `cv_render.py`
(`DEFAULT_THEME`, `DEFAULT_SPACE`). All measurements are PostScript points (1pt =
1/72"); A4 is 595.28 x 841.89.

---

## `page`

```yaml
page:
  size: A4                # A4 | LETTER
  max_pages: 1            # hard invariant - the render FAILS rather than spilling
  margin: {top: 32, right: 34, bottom: 32, left: 34}
```

Typical CV-builder output uses 40pt margins. 32-34pt is noticeably tighter while
still printing safely on consumer printers. Below ~28pt the page reads cramped and
some printers clip.

---

## `theme`

```yaml
theme:
  family: Lora            # resolves assets/fonts/<family>-<weight>[Italic].ttf
  leading: 1.52           # line pitch as a multiple of font size
  rule_height: 0.8        # thickness of the horizontal rule under a heading
  bullet_size: 3.0        # bullet dot diameter
  bullet_indent: 15.0     # marker column -> text column offset

  size:                   # pt
    name: 16.0            # the person's name
    contact: 10.0         # phone | email | location line
    summary: 9.0
    section: 12.0         # "Work Experience", "Skills"
    entry: 11.0           # "Senior AI Engineer  •  Acme Corp"
    meta: 10.0            # "November 2024 - Present  |  Jakarta"
    body: 9.0             # intro paragraphs and bullets
    column: 9.0           # grid items

  weight:                 # 400 | 500 | 600 | 700 (whichever TTFs are vendored)
    name: 700
    section: 700
    entry: 700
    lead: 700             # the bold run at the head of a bullet
    contact: 400
    summary: 400
    meta: 400
    body: 400
    column: 400

  tracking:               # letter-spacing, em units; applies to these three only
    name: 0.045
    section: 0.045
    entry: 0.035

  color:                  # hex
    name: "#333333"
    heading: "#333333"
    entry: "#333333"
    body: "#555555"       # bullet and paragraph prose
    strong: "#1a1c1e"     # summary, degree labels, bold lead-ins
    muted: "#888888"      # dates, locations
    link: "#4f3a2f"       # underlined contact links
    rule: "#333333"
    bullet: "#555555"
```

`tracking` is drawn as individually positioned glyphs inside one text object. It
survives `pdftotext`/pdfminer extraction as whole words — verified — but keep it off
body text: there is no reason to risk it on the parts an ATS actually indexes.

---

## `space` — the vertical gap map

Each token is one specific gap. `--autofit` multiplies **all** of them by the chosen
ladder rung's `gap_scale`, so their *ratios* are what you tune here.

```yaml
space:
  header_contact:  9.0    # name          -> contact line
  contact_summary: 15.0   # contact line  -> summary paragraph
  section_top:     23.5   # above every section heading
  head_rule:        6.7   # heading text  -> its rule
  rule_body:       11.8   # rule          -> first content row
  entry_gap:       12.4   # between entries within a section
  title_meta:       9.0   # entry title   -> date/location line
  meta_body:       15.2   # date line     -> intro paragraph
  intro_bullets:   15.4   # intro         -> first bullet
  bullet_gap:       0.8   # EXTRA leading between bullets (on top of `leading`)
  sub_gap:          4.0   # between `rows` (e.g. two degrees at one university)
  column_item:     15.0   # vertical pitch of grid items
  column_gutter:   12.0   # horizontal gap between grid columns (never auto-scaled)
```

> "The two degree lines are too far apart" is always `sub_gap`.
> "Too much air above Education" is always `section_top`.

---

## `header`

```yaml
header:
  name: Ada Lovelace
  separator: " | "                     # between contact items
  contact:
    - "+62 800 0000 0000"              # plain string -> muted
    - {text: ada@example.com, style: link, link: "mailto:ada@example.com"}
    - Jakarta, Indonesia
```

An item with `link:` is underlined, coloured with `theme.color.link`, and gets a real
PDF link annotation.

## `summary`

```yaml
summary: >-
  Free prose. Rendered justified by default.
summary_justify: true                  # set false for ragged-right
```

## `sections`

A list, rendered in order. Two `type`s.

### `type: entries`

```yaml
- type: entries
  title: Work Experience
  entries:
    - role: Senior AI Engineer         # role + org are joined with "  •  "
      org: Acme Corp
      title: ...                       # OR set `title` directly, bypassing role/org
      period: November 2024 - Present  # period + location joined with "  |  "
      location: Jakarta, Indonesia
      meta: ...                        # OR set `meta` directly
      intro: >-                        # optional un-bulleted lead paragraph
        Architected ...
      bullets:
        - Plain string bullet.
        - lead: "Search Engine Development:"   # bold run
          text: >-
            ...rest of the bullet.
      rows:                            # single-line sub-rows (education degrees)
        - {label: "Master's Degree in Computer Science", detail: "2021 - 2023"}
```

`bullets` and `rows` may both appear; `rows` render after `bullets`.

### `type: columns`

A grid band. One or more `groups` sit side by side, each with its own heading and
rule segment; within a group, items flow **column-major** (down, then across).

```yaml
- type: columns
  groups:
    - title: Skills
      columns: 3
      items: [NLP & LLM, Python & Golang, ...]
```

Two groups sharing the band (the classic Skills + Languages row) — total width is
split by total column count, so a 2+1 split gives Skills two thirds:

```yaml
- type: columns
  groups:
    - {title: Skills,    columns: 2, items: [...]}
    - {title: Languages, columns: 1, items: [Indonesian (Native), English (Professional)]}
```

Deleting a group and raising the survivor's `columns` is what "extend Skills to the
rightmost edge" means: same items, fewer rows, less vertical space.

A shorthand form without `groups` is accepted for a single group:

```yaml
- type: columns
  title: Skills
  columns: 3
  items: [...]
```

---

## The fit ladder

`FIT_LADDER` in `cv_render.py` is a list of `(gap_scale, leading_scale, font_scale)`
triples, loosest first. `--autofit` measures at each rung and stops at the first that
fits `max_pages`. Consequences worth knowing:

- **The ladder never enlarges what the YAML asked for.** It is capped at `1.00`.
  Inflating rungs live in `EXPAND_RUNGS` and require `--expand`. This is deliberate:
  "loosest that fits" spends leftover room on padding, so a CV with space for two
  more bullets instead rendered with 8% fatter gaps *everywhere* — which reads as
  wasted page, not as generous typography. Leftover room is the author's to spend.
- When ≥2 body lines are unused the render prints a `note:` saying so. Treat it as
  a prompt to **add content**, not to reach for `--expand`.
- `font_scale` stays at 1.00 for the first nine rungs — spacing is squeezed before
  type is, because shrunk type is the most visible compromise.
- Reaching a rung near the bottom is a signal to **cut prose**, not a success.
- If nothing fits, the render exits `2` and reports the overflow in body lines.

## Calibration belongs in the tokens, never in the layout

Every `space.*` token is added raw: `Layout.y` already sits at the bottom of the last
thing drawn, so a token means exactly the whitespace it names. Do not reintroduce
per-font-size compensation like `sp["meta_body"] - size * 1.05 + size * 0.35`. An
earlier version did that to reproduce a source PDF's measured gaps; the expressions
went **negative** the moment the tokens were tightened, and the date line overprinted
the paragraph beneath it. `Layout.gap()` now clamps negatives and warns, but the rule
is the real protection.

## A tight, consistent rhythm

The defaults reproduce a typical CV-builder's airy spacing (1.66 leading, ~47pt of
whitespace above every section). If the brief is "tighter, and use the space for more
content", derive every token from the body line pitch instead:

```yaml
theme: {leading: 1.44}     # 12.96pt pitch at 9pt body
space:
  section_top:     16.0    # section break  > entry break > line break
  entry_gap:       12.0
  head_rule:        4.0
  rule_body:        7.0
  title_meta:       2.5    # a label and its date are one unit; keep them touching
  meta_body:        6.0
  intro_bullets:    6.0    # == meta_body, so an entry with an intro and one without
  bullet_gap:       2.0    #    put their first bullet the same distance below the date
  column_item:     13.0    # == the body line pitch
```

Consistency here means *same relationship, same gap* — not one uniform number. A
section break should outrank an entry break, which should outrank a line break; what
breaks the page is two instances of the **same** relationship measuring differently.
