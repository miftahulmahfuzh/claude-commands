#!/usr/bin/env python3
"""cv_preview.py -- rasterise a PDF so the agent can LOOK at what it produced.

Renders each page to PNG and, with two PDFs, also writes a side-by-side sheet so
before/after can be compared in one glance.

Usage:
    cv_preview.py out.pdf                       -> out.page1.png
    cv_preview.py new.pdf --against old.pdf     -> also compare.png
"""

from __future__ import annotations

import argparse
import os
import sys

import fitz


def render(path, dpi):
    doc = fitz.open(path)
    return [p.get_pixmap(dpi=dpi) for p in doc], doc.page_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--against", help="second PDF to place side by side")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    outdir = args.outdir or os.path.dirname(os.path.abspath(args.pdf))
    stem = os.path.splitext(os.path.basename(args.pdf))[0]
    pages, n = render(args.pdf, args.dpi)
    for i, pm in enumerate(pages):
        p = os.path.join(outdir, f"{stem}.page{i + 1}.png")
        pm.save(p)
        print(p)
    print(f"pages={n}", file=sys.stderr)

    if args.against:
        old, _ = render(args.against, args.dpi)
        a, b = old[0], pages[0]
        gap = 24
        w, h = a.width + gap + b.width, max(a.height, b.height)
        canvas = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, w, h))
        canvas.clear_with(230)
        canvas.copy(a, fitz.IRect(0, 0, a.width, a.height))
        b.set_origin(a.width + gap, 0)
        canvas.copy(b, fitz.IRect(a.width + gap, 0, a.width + gap + b.width, b.height))
        p = os.path.join(outdir, f"{stem}.compare.png")
        canvas.save(p)
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
