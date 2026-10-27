#!/usr/bin/env python3
"""Render a tmux pane to a PNG, or a sequence of captures to an animated GIF.

The README needs pictures of a terminal, and this machine has no browser, no vhs and
no asciinema -- but it does have PIL and a mono font, and `tmux capture-pane -e` already
emits the pane with its SGR colours intact. So the pane is parsed and drawn directly.

This lives in the repo rather than in a scratch directory because a screenshot nobody
can regenerate rots: the next person to change the deck's layout needs to be able to
re-shoot it, not hand-edit a PNG.

    python3 termshot.py shot  <target> out.png  [--title "..."]
    python3 termshot.py frames <target> out.gif [--count 12] [--interval 1.0]
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SIZE = 15
PAD = 18
TITLEBAR = 30

BG = (18, 20, 26)
FG = (205, 212, 224)
DIM = (120, 130, 148)

# xterm's first 16, warmed slightly so a screenshot does not read as a 1990s console.
ANSI16 = [
    (40, 44, 52), (224, 108, 117), (152, 195, 121), (229, 192, 123),
    (97, 175, 239), (198, 120, 221), (86, 182, 194), (171, 178, 191),
    (92, 99, 112), (233, 134, 143), (168, 204, 140), (235, 203, 139),
    (130, 170, 255), (209, 154, 227), (137, 221, 255), (229, 233, 240),
]

SGR = re.compile(r"\x1b\[([0-9;:]*)m")
# Everything EXCEPT the SGR (colour) sequences, which the pen reads.
# The final class deliberately omits `m`: an earlier version used [A-Za-z], which
# matched \x1b[38;5;220m and stripped every colour before the parser ever saw it --
# producing a perfectly readable, entirely grey screenshot of a UI whose colour IS the
# signal.
OTHER_CSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-ln-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][AB0]")


def cube(n):
    """xterm 256-colour index -> rgb."""
    if n < 16:
        return ANSI16[n]
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        return (steps[n // 36 % 6], steps[n // 6 % 6], steps[n % 6])
    v = 8 + (n - 232) * 10
    return (v, v, v)


class Pen:
    __slots__ = ("fg", "bg", "bold", "dim", "reverse")

    def __init__(self):
        self.reset()

    def reset(self):
        self.fg, self.bg, self.bold, self.dim, self.reverse = None, None, False, False, False

    def copy(self):
        p = Pen()
        p.fg, p.bg, p.bold, p.dim, p.reverse = self.fg, self.bg, self.bold, self.dim, self.reverse
        return p

    def apply(self, params):
        codes = [int(x) for x in params.split(";") if x.isdigit()] or [0]
        i = 0
        while i < len(codes):
            c = codes[i]
            if c == 0:
                self.reset()
            elif c == 1:
                self.bold = True
            elif c == 2:
                self.dim = True
            elif c == 7:
                self.reverse = True
            elif c in (22, 21):
                self.bold = self.dim = False
            elif c == 27:
                self.reverse = False
            elif 30 <= c <= 37:
                self.fg = ANSI16[c - 30]
            elif 90 <= c <= 97:
                self.fg = ANSI16[c - 90 + 8]
            elif 40 <= c <= 47:
                self.bg = ANSI16[c - 40]
            elif 100 <= c <= 107:
                self.bg = ANSI16[c - 100 + 8]
            elif c == 39:
                self.fg = None
            elif c == 49:
                self.bg = None
            elif c in (38, 48):
                target = "fg" if c == 38 else "bg"
                if i + 1 < len(codes) and codes[i + 1] == 5:
                    setattr(self, target, cube(codes[i + 2])) if i + 2 < len(codes) else None
                    i += 2
                elif i + 1 < len(codes) and codes[i + 1] == 2:
                    if i + 4 < len(codes):
                        setattr(self, target, (codes[i + 2], codes[i + 3], codes[i + 4]))
                    i += 4
            i += 1


def parse(text):
    """-> list of lines, each a list of (char, Pen)."""
    lines = []
    pen = Pen()
    for raw in text.split("\n"):
        raw = OTHER_CSI.sub("", raw)
        cells, pos = [], 0
        for m in SGR.finditer(raw):
            for ch in raw[pos:m.start()]:
                cells.append((ch, pen.copy()))
            pen.apply(m.group(1))
            pos = m.end()
        for ch in raw[pos:]:
            cells.append((ch, pen.copy()))
        lines.append(cells)
    return lines


def render(text, title=None):
    lines = parse(text)
    font = ImageFont.truetype(FONT, SIZE)
    bold = ImageFont.truetype(FONT_BOLD, SIZE)
    cw = int(round(font.getlength("M")))
    ch = SIZE + 6
    cols = max((len(l) for l in lines), default=1) or 1
    top = PAD + (TITLEBAR if title else 0)
    img = Image.new("RGB", (cols * cw + PAD * 2, len(lines) * ch + top + PAD), BG)
    d = ImageDraw.Draw(img)

    if title:
        d.rectangle([0, 0, img.width, TITLEBAR], fill=(30, 33, 41))
        for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            d.ellipse([PAD + i * 18, 11, PAD + i * 18 + 9, 20], fill=c)
        d.text((PAD + 68, 8), title, font=font, fill=DIM)

    for y, cells in enumerate(lines):
        for x, (c, pen) in enumerate(cells):
            if c == " " and pen.bg is None and not pen.reverse:
                continue
            fg = pen.fg or FG
            bg = pen.bg
            if pen.reverse:
                fg, bg = bg or BG, pen.fg or FG
            if pen.dim and not pen.bold:
                fg = tuple(int(v * 0.62) for v in fg)
            px, py = PAD + x * cw, top + y * ch
            if bg:
                d.rectangle([px, py, px + cw, py + ch], fill=bg)
            if c != " ":
                d.text((px, py), c, font=bold if pen.bold else font, fill=fg)
    return img


def capture(target):
    out = subprocess.run(["tmux", "capture-pane", "-p", "-e", "-t", target],
                         capture_output=True, text=True, timeout=20)
    if out.returncode != 0:
        sys.exit("capture-pane failed: " + out.stderr.strip())
    return out.stdout.rstrip("\n")


def plain(line):
    return OTHER_CSI.sub("", SGR.sub("", line))


def empty(line):
    """No readable content.

    A pane that draws a sidebar leaves rows holding nothing but the divider, which is
    not blank by `strip()` and would otherwise pad a screenshot with hundreds of pixels
    of empty frame. Anything without a letter or a digit is scenery.
    """
    return not re.search(r"[0-9A-Za-z]", plain(line))


def trim(text, keep_blank_runs=1):
    """Collapse empty stretches so a tall pane makes a readable picture."""
    kept, blanks = [], 0
    for line in text.split("\n"):
        if empty(line):
            blanks += 1
            if blanks > keep_blank_runs:
                continue
        else:
            blanks = 0
        kept.append(line)
    while kept and empty(kept[-1]):
        kept.pop()
    while kept and empty(kept[0]):
        kept.pop(0)
    return "\n".join(kept)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["shot", "frames"])
    ap.add_argument("target")
    ap.add_argument("out")
    ap.add_argument("--title")
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--no-trim", action="store_true")
    a = ap.parse_args()

    prep = (lambda t: t) if a.no_trim else trim
    if a.mode == "shot":
        render(prep(capture(a.target)), a.title).save(a.out)
        print("wrote", a.out)
        return

    frames = []
    for i in range(a.count):
        frames.append(render(prep(capture(a.target)), a.title))
        if i < a.count - 1:
            time.sleep(a.interval)
    w = max(f.width for f in frames)
    h = max(f.height for f in frames)
    padded = []
    for f in frames:
        canvas = Image.new("RGB", (w, h), BG)
        canvas.paste(f, (0, 0))
        padded.append(canvas.convert("P", palette=Image.ADAPTIVE, colors=128))
    padded[0].save(a.out, save_all=True, append_images=padded[1:],
                   duration=int(a.interval * 1000), loop=0, optimize=True)
    print("wrote", a.out, len(frames), "frames")


if __name__ == "__main__":
    main()
