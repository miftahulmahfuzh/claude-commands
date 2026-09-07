#!/usr/bin/env python3
"""cv_render.py -- render a cv.yaml content model into a pixel-controlled ATS PDF.

Every millimetre is under explicit control: page margins, per-token vertical gaps,
leading, letter-spacing, column geometry.  There is no HTML/CSS engine in the loop.

The single hard invariant is PAGE COUNT.  `--autofit` searches a ladder of
(gap_scale, leading, font_scale) triples from loosest to tightest and picks the
FIRST one whose content height fits the page.  If nothing on the ladder fits, the
run FAILS loudly rather than silently spilling onto page 2.

Text is emitted through fitz.TextWriter with real Lora weights (no synthetic
bold), so `pdftotext`/pdfminer/PDFBox -- i.e. every ATS parser -- get clean,
selectable, correctly-ordered text.

Usage:
    cv_render.py input.cv.yaml -o out.pdf [--autofit] [--report]
"""

from __future__ import annotations

import argparse
import copy
import os
import sys
from typing import cast

import fitz
import yaml

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")

PAGE_SIZES = {"A4": (595.28, 841.89), "LETTER": (612.0, 792.0)}

# Rungs that INFLATE the authored spacing.  Opt-in via --expand only.  They are not
# in the default ladder because "loosest that fits" spends leftover room on padding:
# a CV with space for two more bullets instead rendered with 8% fatter gaps
# everywhere, which reads as wasted page, not as generous typography.  Leftover room
# should go to content, and the author decides that -- so the default never enlarges
# what the YAML asked for.
EXPAND_RUNGS = [(1.15, 1.02, 1.00), (1.08, 1.00, 1.00)]

# (gap_scale, leading_scale, font_scale) -- loosest first, capped at the authored
# spacing.  Autofit walks this in order and stops at the first entry that fits.
# Font scale is touched last and never below 0.90, because shrinking type is the
# most visible compromise.
FIT_LADDER = [
    (1.00, 1.00, 1.00),
    (0.94, 1.00, 1.00), (0.88, 0.99, 1.00), (0.82, 0.98, 1.00),
    (0.76, 0.97, 1.00), (0.70, 0.96, 1.00), (0.64, 0.95, 1.00),
    (0.60, 0.94, 0.99), (0.56, 0.93, 0.98), (0.52, 0.92, 0.97),
    (0.48, 0.91, 0.96), (0.44, 0.90, 0.95), (0.40, 0.89, 0.94),
    (0.36, 0.88, 0.92), (0.32, 0.87, 0.90),
]

DEFAULT_THEME = {
    "family": "Lora",
    "color": {
        "name": "#333333", "heading": "#333333", "entry": "#333333",
        "body": "#555555", "strong": "#1a1c1e", "muted": "#888888",
        "link": "#4f3a2f", "rule": "#333333", "bullet": "#555555",
    },
    "size": {
        "name": 16.0, "contact": 10.0, "summary": 9.0, "section": 12.0,
        "entry": 11.0, "meta": 10.0, "body": 9.0, "column": 9.0,
    },
    "weight": {
        "name": 700, "contact": 400, "summary": 400, "section": 700,
        "entry": 700, "meta": 400, "body": 400, "lead": 700, "column": 400,
    },
    # letter-spacing in em; drawn as explicitly positioned glyphs inside a single
    # text object, which pdftotext and pdfminer both reassemble into words.
    "tracking": {"name": 0.045, "section": 0.045, "entry": 0.035},
    "rule_height": 0.8,
    "bullet_size": 3.0,      # diameter of the round bullet, pt
    "bullet_indent": 15.0,   # marker column -> text column offset, pt
    "leading": 1.66,         # multiple of font size
}

DEFAULT_SPACE = {
    "header_contact": 9.0,     # name block -> contact line
    "contact_summary": 15.0,   # contact line -> summary
    "section_top": 23.5,       # above every section heading
    "head_rule": 6.7,          # heading text bottom -> its rule
    "rule_body": 11.8,         # rule -> first content row
    "entry_gap": 12.4,         # between entries inside a section
    "title_meta": 9.0,         # entry title -> date/location line
    "meta_body": 15.2,         # date line -> intro paragraph
    "intro_bullets": 15.4,     # intro paragraph -> first bullet
    "bullet_gap": 0.8,         # extra leading between bullets
    "sub_gap": 4.0,            # between sub-rows (e.g. two degrees)
    "column_gutter": 12.0,     # horizontal gap between grid columns
    "column_item": 15.0,       # vertical pitch of grid items
}


# ---------------------------------------------------------------- helpers


def hexcolor(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def deep_merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class FontBook:
    """Lazily loads and caches the vendored Lora weights."""

    def __init__(self, family="Lora"):
        self.family = family
        self._cache = {}

    def get(self, weight=400, italic=False):
        key = (weight, italic)
        if key not in self._cache:
            name = f"{self.family}-{weight}{'Italic' if italic else ''}.ttf"
            path = os.path.join(FONT_DIR, name)
            if not os.path.exists(path):
                raise SystemExit(f"missing font {path}")
            self._cache[key] = (fitz.Font(fontfile=path), path, name[:-4])
        return self._cache[key]

    def width(self, text, weight, size, italic=False, tracking=0.0):
        font = self.get(weight, italic)[0]
        w = font.text_length(text, size)
        if tracking and len(text) > 1:
            w += tracking * size * (len(text) - 1)
        return w


# ---------------------------------------------------------------- inline runs

def runs_of(node, theme, default_weight_key="body"):
    """Normalise a bullet/paragraph node into a list of styled runs.

    Accepts a plain string, or a mapping with an optional bold `lead` prefix:
        - "plain text"
        - {lead: "Search Engine Development:", text: "Created robust ..."}
    """
    sz = theme["size"]
    wt = theme["weight"]
    col = theme["color"]
    if isinstance(node, str):
        return [(node, wt[default_weight_key], sz[default_weight_key], col["body"], False)]
    out = []
    lead = (node.get("lead") or "").strip()
    if lead:
        out.append((lead, wt["lead"], sz["body"], col["strong"], False))
    text = (node.get("text") or "").strip()
    if text:
        if out:
            text = " " + text
        out.append((text, wt["body"], sz["body"], col["body"], False))
    return out or [("", wt["body"], sz["body"], col["body"], False)]


def wrap_runs(runs, width, fonts):
    """Greedy word-wrap across styled runs. Returns list of lines; each line is a
    list of (text, weight, size, color, italic) fragments with no trailing space."""
    tokens = []  # (word, style, space_before)
    for text, w, s, c, it in runs:
        if not text:
            continue
        lead_space = text[:1].isspace()
        for i, word in enumerate(text.split()):
            tokens.append((word, (w, s, c, it), (i > 0) or (i == 0 and lead_space and tokens)))
    lines, cur, cur_w = [], [], 0.0
    for word, style, sp in tokens:
        w, s, c, it = style
        piece = (" " if (sp and cur) else "") + word
        pw = fonts.width(piece, w, s, it)
        if cur and cur_w + pw > width + 0.01:
            lines.append(cur)
            cur, cur_w = [(word, w, s, c, it)], fonts.width(word, w, s, it)
        else:
            cur.append((piece, w, s, c, it))
            cur_w += pw
    if cur:
        lines.append(cur)
    return lines or [[]]


def merge_fragments(line):
    """Collapse adjacent fragments that share a style, so each emitted show-text
    op covers as many characters as possible (better for ATS text extraction)."""
    out = []
    for frag in line:
        if out and out[-1][1:] == frag[1:]:
            out[-1] = (out[-1][0] + frag[0],) + frag[1:]
        else:
            out.append(frag)
    return out


# ---------------------------------------------------------------- layout engine


class Layout:
    """Two-mode engine: measure (page=None) then draw. Identical code path both
    times, so the measured height is exactly what gets painted."""

    def __init__(self, cv, theme, space, fonts, geom, page=None):
        self.cv, self.theme, self.space, self.fonts = cv, theme, space, fonts
        self.x0, self.x1, self.y = geom["x0"], geom["x1"], geom["y0"]
        self.page = page
        self.ops = []       # (x, baseline_y, text, weight, size, color, italic, tracking)
        self.rects = []     # (fitz.Rect, color)
        self.dots = []      # (fitz.Point, radius, color)
        self.links = []     # (fitz.Rect, uri)
        self.top = geom["y0"]

    @property
    def width(self):
        return self.x1 - self.x0

    def lead(self, size):
        return size * self.theme["leading"]

    # -- primitives ------------------------------------------------------

    def text(self, x, size, weight, color, s, italic=False, tracking=0.0, advance=True):
        font = self.fonts.get(weight, italic)[0]
        baseline = self.y + font.ascender * size
        self.ops.append((x, baseline, s, weight, size, color, italic, tracking))
        if advance:
            self.y += self.lead(size)
        return self.fonts.width(s, weight, size, italic, tracking)

    def gap(self, amount):
        """Advance by a vertical gap.  Negative is always a bug -- it means glyphs
        overprint -- so it is clamped and reported rather than drawn."""
        if amount < 0:
            sys.stderr.write(f"warn: negative gap {amount:.2f}pt clamped to 0 (overlap avoided)\n")
            amount = 0.0
        self.y += amount

    def rule(self, x0, x1, color=None):
        h = self.theme["rule_height"]
        self.rects.append((fitz.Rect(x0, self.y, x1, self.y + h), color or self.theme["color"]["rule"]))
        self.y += h

    def dot(self, cx, cy, color):
        self.dots.append((fitz.Point(cx, cy), self.theme["bullet_size"] / 2.0, color))

    def paragraph(self, runs, x, width, justify=False, size_hint=None):
        lines = wrap_runs(runs, width, self.fonts)
        size = size_hint or (runs[0][2] if runs else self.theme["size"]["body"])
        for idx, line in enumerate(lines):
            line = merge_fragments(line)
            last = idx == len(lines) - 1
            if justify and not last and len(line) and sum(len(f[0].split()) for f in line) > 1:
                self._draw_justified(line, x, width)
                self.y += self.lead(size)
            else:
                cx = x
                for txt, w, s, c, it in line:
                    font = self.fonts.get(w, it)[0]
                    self.ops.append((cx, self.y + font.ascender * s, txt, w, s, c, it, 0.0))
                    cx += font.text_length(txt, s)
                self.y += self.lead(size)
        return len(lines)

    def _draw_justified(self, line, x, width):
        words = []
        for txt, w, s, c, it in line:
            for j, word in enumerate(txt.split()):
                words.append((word, w, s, c, it))
        if len(words) < 2:
            cx = x
            for txt, w, s, c, it in line:
                font = self.fonts.get(w, it)[0]
                self.ops.append((cx, self.y + font.ascender * s, txt, w, s, c, it, 0.0))
                cx += font.text_length(txt, s)
            return
        natural = sum(self.fonts.width(wd[0], wd[1], wd[2], wd[4]) for wd in words)
        gap = (width - natural) / (len(words) - 1)
        cx = x
        for word, w, s, c, it in words:
            font = self.fonts.get(w, it)[0]
            self.ops.append((cx, self.y + font.ascender * s, word, w, s, c, it, 0.0))
            cx += font.text_length(word, s) + gap

    def centered(self, runs, size):
        total = sum(self.fonts.width(t, w, s, it, tr) for t, w, s, c, it, tr in runs)
        cx = self.x0 + (self.width - total) / 2.0
        for t, w, s, c, it, tr in runs:
            font = self.fonts.get(w, it)[0]
            self.ops.append((cx, self.y + font.ascender * s, t, w, s, c, it, tr))
            cx += self.fonts.width(t, w, s, it, tr)
        self.y += self.lead(size)
        return cx

    # -- blocks ----------------------------------------------------------

    def section_heading(self, title, x0=None, x1=None):
        th, sp = self.theme, self.space
        x0 = self.x0 if x0 is None else x0
        x1 = self.x1 if x1 is None else x1
        font = self.fonts.get(th["weight"]["section"])[0]
        size = th["size"]["section"]
        self.ops.append((x0, self.y + font.ascender * size, title,
                         th["weight"]["section"], size, th["color"]["heading"], False,
                         th["tracking"]["section"]))
        self.y += size * 1.22 + sp["head_rule"]
        self.rule(x0, x1)
        self.gap(sp["rule_body"])

    def build(self):
        cv, th, sp = self.cv, self.theme, self.space
        hdr = cv.get("header", {})

        # --- name -------------------------------------------------------
        if hdr.get("name"):
            self.centered([(hdr["name"], th["weight"]["name"], th["size"]["name"],
                            th["color"]["name"], False, th["tracking"]["name"])],
                          th["size"]["name"])
            self.gap(sp["header_contact"] - self.lead(th["size"]["name"]) + th["size"]["name"] * 1.05)

        # --- contact ----------------------------------------------------
        contact = hdr.get("contact") or []
        if contact:
            sep = hdr.get("separator", " | ")
            runs, size = [], th["size"]["contact"]
            for i, item in enumerate(contact):
                if i:
                    runs.append((sep, th["weight"]["contact"], size, th["color"]["muted"], False, 0.0))
                if isinstance(item, dict):
                    runs.append((item["text"], th["weight"]["contact"], size,
                                 th["color"].get(item.get("style", "muted"), th["color"]["muted"]), False, 0.0))
                else:
                    runs.append((item, th["weight"]["contact"], size, th["color"]["muted"], False, 0.0))
            y_before = self.y
            self.centered(runs, size)
            self._underline_links(contact, sep, size, y_before)
            self.gap(sp["contact_summary"] - self.lead(size) + size * 1.05)

        # --- summary ----------------------------------------------------
        if cv.get("summary"):
            size = th["size"]["summary"]
            self.paragraph([(cv["summary"].strip(), th["weight"]["summary"], size,
                             th["color"]["strong"], False)],
                           self.x0, self.width,
                           justify=cv.get("summary_justify", True), size_hint=size)

        # --- sections ---------------------------------------------------
        for sec in cv.get("sections", []):
            kind = sec.get("type", "entries")
            if kind == "columns":
                self.gap(sp["section_top"])
                self._columns(sec)
            else:
                self.gap(sp["section_top"])
                self.section_heading(sec.get("title", ""))
                self._entries(sec)
        return self.y - self.top

    def _underline_links(self, contact, sep, size, y_before):
        """Underline + register a mailto/https link for contact items flagged as links."""
        th = self.theme
        font = self.fonts.get(th["weight"]["contact"])[0]
        total = 0.0
        parts = []
        for i, item in enumerate(contact):
            if i:
                parts.append((sep, None))
            parts.append((item["text"] if isinstance(item, dict) else item,
                          item if isinstance(item, dict) else None))
        total = sum(font.text_length(t, size) for t, _ in parts)
        cx = self.x0 + (self.width - total) / 2.0
        for t, meta in parts:
            w = font.text_length(t, size)
            if meta and meta.get("link"):
                uy = y_before + font.ascender * size + size * 0.16
                self.rects.append((fitz.Rect(cx, uy, cx + w, uy + 0.7),
                                   th["color"].get(meta.get("style", "link"), th["color"]["link"])))
                self.links.append((fitz.Rect(cx, y_before, cx + w, y_before + size * 1.2), meta["link"]))
            cx += w

    def _entries(self, sec):
        th, sp = self.theme, self.space
        for i, entry in enumerate(sec.get("entries", [])):
            if i:
                self.gap(sp["entry_gap"])
            title_bits = [b for b in (entry.get("role"), entry.get("org")) if b]
            title = entry.get("title") or "  •  ".join(title_bits)
            if title:
                self.text(self.x0, th["size"]["entry"], th["weight"]["entry"],
                          th["color"]["entry"], title, tracking=th["tracking"]["entry"],
                          advance=False)
                self.y += th["size"]["entry"] * 1.22
            meta_bits = [b for b in (entry.get("period"), entry.get("location")) if b]
            meta = entry.get("meta") or "  |  ".join(meta_bits)
            if meta:
                self.gap(sp["title_meta"])
                self.text(self.x0, th["size"]["meta"], th["weight"]["meta"],
                          th["color"]["muted"], meta, advance=False)
                self.y += th["size"]["meta"] * 1.05
            # Gaps are added raw: `self.y` already sits at the bottom of whatever was
            # drawn last, so a token means exactly the whitespace it names.  An earlier
            # version subtracted a fraction of the font size here to reproduce the
            # source PDF's measured gaps, which silently went NEGATIVE once the tokens
            # were tightened -- the date line then overprinted the text beneath it.
            # Any calibration belongs in the token values, never in the layout.
            if entry.get("intro"):
                self.gap(sp["meta_body"])
                self.paragraph([(entry["intro"].strip(), th["weight"]["body"], th["size"]["body"],
                                 th["color"]["body"], False)], self.x0, self.width,
                               justify=False, size_hint=th["size"]["body"])
            bullets = entry.get("bullets") or []
            if bullets:
                self.gap(sp["intro_bullets"] if entry.get("intro") else sp["meta_body"])
                self._bullets(bullets)
            for j, sub in enumerate(entry.get("rows") or []):
                if j:
                    self.gap(sp["sub_gap"])
                else:
                    self.gap(sp["title_meta"])
                self._row(sub)

    def _row(self, sub):
        """A degree line: bold-ish label + muted trailing date, on one line."""
        th = self.theme
        size = th["size"]["body"]
        font = self.fonts.get(th["weight"]["body"])[0]
        cx = self.x0
        base = self.y + font.ascender * size
        label = sub.get("label") if isinstance(sub, dict) else str(sub)
        self.ops.append((cx, base, label, th["weight"]["body"], size, th["color"]["strong"], False, 0.0))
        cx += font.text_length(label, size)
        detail = sub.get("detail") if isinstance(sub, dict) else None
        if detail:
            sep = "   •  "
            self.ops.append((cx, base, sep, th["weight"]["body"], size, th["color"]["body"], False, 0.0))
            cx += font.text_length(sep, size)
            self.ops.append((cx, base, detail, th["weight"]["body"], size, th["color"]["muted"], False, 0.0))
        self.y += size * 1.05

    def _bullets(self, bullets, x0=None, width=None, item_gap=None):
        th, sp = self.theme, self.space
        x0 = self.x0 if x0 is None else x0
        width = self.width if width is None else width
        tx = x0 + th["bullet_indent"]
        tw = width - th["bullet_indent"]
        for i, b in enumerate(bullets):
            if i:
                self.gap(sp["bullet_gap"] if item_gap is None else item_gap)
            runs = runs_of(b, th)
            size = th["size"]["body"]
            font = self.fonts.get(th["weight"]["body"])[0]
            self.dot(x0 + th["bullet_indent"] / 2.7,
                     self.y + font.ascender * size - size * 0.24, th["color"]["bullet"])
            self.paragraph(runs, tx, tw, justify=False, size_hint=size)

    def _columns(self, sec):
        """Grid section (Skills / Languages): N columns, each with its own heading
        rule segment.  `groups` lets several titled groups share one row band."""
        th, sp = self.theme, self.space
        groups = sec.get("groups")
        if not groups:
            groups = [{"title": sec.get("title", ""), "columns": sec.get("columns", 1),
                       "items": sec.get("items", [])}]
        gutter = sp["column_gutter"]
        weights = [g.get("width", g.get("columns", 1)) for g in groups]
        n_cols_total = sum(g.get("columns", 1) for g in groups)
        n_gaps = n_cols_total - 1
        unit = (self.width - gutter * n_gaps) / max(n_cols_total, 1)

        top = self.y
        cursor = self.x0
        bands = []
        for g in groups:
            ncol = g.get("columns", 1)
            gw = unit * ncol + gutter * (ncol - 1)
            bands.append((cursor, cursor + gw, g))
            cursor += gw + gutter

        # headings + rules, all on the same baseline
        head_y = top
        max_y = top
        for gx0, gx1, g in bands:
            self.y = head_y
            self.section_heading(g.get("title", ""), gx0, gx1)
            max_y = max(max_y, self.y)
        body_y = max_y

        for gx0, gx1, g in bands:
            self.y = body_y
            ncol = g.get("columns", 1)
            items = g.get("items", [])
            per = -(-len(items) // ncol) if ncol else len(items)
            colw = (gx1 - gx0 - gutter * (ncol - 1)) / ncol
            col_bottom = body_y
            for ci in range(ncol):
                chunk = items[ci * per:(ci + 1) * per]
                self.y = body_y
                cx = gx0 + ci * (colw + gutter)
                for k, item in enumerate(chunk):
                    if k:
                        self.gap(sp["column_item"] - th["size"]["column"] * th["leading"])
                    self._bullets([item], x0=cx, width=colw)
                col_bottom = max(col_bottom, self.y)
            max_y = max(max_y, col_bottom)
        self.y = max_y

    # -- paint -----------------------------------------------------------

    def paint(self, page):
        for rect, color in self.rects:
            page.draw_rect(rect, color=None, fill=hexcolor(color), width=0)
        for centre, radius, color in self.dots:
            page.draw_circle(centre, radius, color=None, fill=hexcolor(color), width=0)
        # Emit in DOCUMENT order, chunked into runs of one colour.  A TextWriter
        # carries a single colour, so batching all ops by colour would have been
        # cheaper -- but it scrambles the content-stream order, and ATS parsers
        # that read the stream rather than the geometry would then see every
        # heading before any body text.  Reading order is the whole point of the
        # document, so it wins over the extra writers.
        chunks = []
        for op in self.ops:
            if not op[2]:
                continue
            if chunks and chunks[-1][0] == op[5]:
                chunks[-1][1].append(op)
            else:
                chunks.append((op[5], [op]))
        for color, items in chunks:
            tw = fitz.TextWriter(page.rect)
            for x, y, text, w, size, _c, italic, tracking in items:
                font = self.fonts.get(w, italic)[0]
                if tracking:
                    cx = x
                    for ch in text:
                        tw.append(fitz.Point(cx, y), ch, font=font, fontsize=size)
                        cx += font.text_length(ch, size) + tracking * size
                else:
                    tw.append(fitz.Point(x, y), text, font=font, fontsize=size)
            tw.write_text(page, color=hexcolor(color))
        for rect, uri in self.links:
            page.insert_link({"kind": fitz.LINK_URI, "from": rect, "uri": uri})


# ---------------------------------------------------------------- driver


def scaled(theme, space, gap_s, lead_s, font_s):
    t = copy.deepcopy(theme)
    s = {k: v * gap_s for k, v in space.items()}
    s["column_gutter"] = space["column_gutter"]  # horizontal, never squeezed
    t["leading"] = theme["leading"] * lead_s
    t["size"] = {k: v * font_s for k, v in theme["size"].items()}
    t["bullet_size"] = theme["bullet_size"] * font_s
    return t, s


def measure(cv, theme, space, fonts, geom):
    return Layout(cv, theme, space, fonts, geom).build()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--autofit", action="store_true",
                    help="search the fit ladder for the loosest spacing that stays on one page, "
                         "never exceeding the spacing the YAML asked for")
    ap.add_argument("--expand", action="store_true",
                    help="also allow rungs that INFLATE the authored spacing, to fill a page a "
                         "short CV would otherwise leave half empty")
    ap.add_argument("--report", action="store_true", help="print fit diagnostics to stderr")
    args = ap.parse_args()

    with open(args.source) as fh:
        cv = yaml.safe_load(fh)

    page_cfg = cv.get("page", {})
    pw, ph = PAGE_SIZES[str(page_cfg.get("size", "A4")).upper()]
    m = deep_merge({"top": 36.0, "right": 36.0, "bottom": 36.0, "left": 36.0}, page_cfg.get("margin"))
    max_pages = int(page_cfg.get("max_pages", 1))

    theme = deep_merge(DEFAULT_THEME, cv.get("theme"))
    space = deep_merge(DEFAULT_SPACE, cv.get("space"))
    fonts = FontBook(theme.get("family", "Lora"))
    geom = {"x0": m["left"], "x1": pw - m["right"], "y0": m["top"]}
    avail = (ph - m["top"] - m["bottom"]) * max_pages

    ladder = FIT_LADDER if args.autofit else [(1.0, 1.0, 1.0)]
    if args.autofit and args.expand:
        ladder = EXPAND_RUNGS + ladder
    # height is read only after the `chosen is None` bail-out below returns, so the
    # initial value is never used -- it is a float so that the arithmetic there is one.
    chosen, height = None, 0.0
    for gap_s, lead_s, font_s in ladder:
        t, s = scaled(theme, space, gap_s, lead_s, font_s)
        h = measure(cv, t, s, fonts, geom)
        if h <= avail:
            chosen, height = (gap_s, lead_s, font_s, t, s), h
            break
    if chosen is None:
        gap_s, lead_s, font_s = ladder[-1]
        t, s = scaled(theme, space, gap_s, lead_s, font_s)
        h = measure(cv, t, s, fonts, geom)
        sys.stderr.write(
            f"FAIL: content does not fit {max_pages} page(s) even at the tightest ladder rung.\n"
            f"      needed {h:.1f}pt, available {avail:.1f}pt -> {h - avail:.1f}pt over "
            f"(~{(h - avail) / (theme['size']['body'] * theme['leading']):.1f} body lines).\n"
            f"      Cut content or raise page.max_pages; do NOT shrink type further.\n")
        return 2

    gap_s, lead_s, font_s, t, s = chosen
    doc = fitz.open()
    page = doc.new_page(width=pw, height=ph)
    lay = Layout(cv, t, s, fonts, geom, page=page)
    lay.build()
    lay.paint(page)
    doc.set_metadata({"title": cv.get("header", {}).get("name", ""), "author": cv.get("header", {}).get("name", ""),
                      "subject": cv.get("header", {}).get("headline", ""), "producer": "cv_render.py",
                      "creator": "cv_render.py"})
    doc.save(args.out, deflate=True, garbage=4)

    slack = avail - height
    lines_free = slack / (t["size"]["body"] * t["leading"])
    sys.stderr.write(
        f"fit: gap={gap_s:.2f} leading={lead_s:.2f} font={font_s:.2f} | "
        f"height={height:.1f}pt avail={avail:.1f}pt slack={slack:.1f}pt "
        f"(~{lines_free:.1f} body lines) | pages={doc.page_count}\n")
    if lines_free >= 2.0:
        sys.stderr.write(
            f"note: ~{lines_free:.1f} body lines of page are unused. Prefer ADDING content over "
            f"leaving it blank; --expand would pad the gaps instead.\n")
    if doc.page_count > max_pages:
        sys.stderr.write("FAIL: page count exceeded\n")
        return 2
    if args.report:
        txt = cast(str, fitz.open(args.out)[0].get_text()).split()
        sys.stderr.write(f"extract-check: {len(txt)} whitespace-separated tokens recovered\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
