#!/usr/bin/env python3
"""cv_extract.py -- dump everything an agent needs to rebuild a CV PDF faithfully.

Prints, per page:
  * page geometry and derived content margins
  * every text span with bbox, font, size, colour  (so spacing tokens can be re-derived)
  * the vector rectangles (section rules, bullet dots, faux-bold overprints)
  * the plain reading-order text

Also reports the best-matching real typeface for the embedded fonts by comparing
advance widths against the vendored family -- flattened PDFs (iLovePDF, Chrome
print) expose Type3 fonts whose real names are gone.

Usage:
    cv_extract.py input.pdf [--text-only]
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import cast

import fitz

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--text-only", action="store_true")
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    if args.text_only:
        for p in doc:
            print(p.get_text())
        return 0

    print(f"# {os.path.basename(args.pdf)}  pages={doc.page_count}  producer={(doc.metadata or {}).get('producer')!r}")
    for pno, page in enumerate(doc.pages()):
        r = page.rect
        print(f"\n## page {pno + 1}  size={r.width:.2f} x {r.height:.2f}pt")
        d = cast(dict, page.get_text("dict"))
        spans = [s for b in d["blocks"] if b["type"] == 0 for l in b["lines"] for s in l["spans"]]
        if spans:
            xs0 = min(s["bbox"][0] for s in spans); xs1 = max(s["bbox"][2] for s in spans)
            ys0 = min(s["bbox"][1] for s in spans); ys1 = max(s["bbox"][3] for s in spans)
            print(f"   content box: L={xs0:.1f} R={xs1:.1f} T={ys0:.1f} B={ys1:.1f}  "
                  f"-> margins L={xs0:.1f} R={r.width - xs1:.1f} T={ys0:.1f} B={r.height - ys1:.1f}")
        print(f"\n### spans  (x0,y0,x1,y1 | font size #rgb | text)")
        for s in spans:
            b = s["bbox"]
            print(f"{b[0]:7.1f},{b[1]:7.1f},{b[2]:7.1f},{b[3]:7.1f} | "
                  f"{s['font']:22s} {s['size']:5.2f} #{s['color']:06x} | {s['text']!r}")
        drawings = page.get_drawings()
        print(f"\n### vector rects ({len(drawings)})")
        for g in drawings:
            q = g["rect"]
            print(f"  fill={g['fill']} w={q.width:8.2f} h={q.height:6.2f} "
                  f"at ({q.x0:.1f},{q.y0:.1f})")
        print(f"\n### reading-order text\n{page.get_text()}")

    print("\n## typeface identification (advance-width match vs vendored family)")
    refs = []
    for page in doc:
        for b in cast(dict, page.get_text("dict"))["blocks"]:
            if b["type"] != 0:
                continue
            for l in b["lines"]:
                if len(l["spans"]) != 1:
                    continue  # multi-span lines may be justified/kerned oddly
                s = l["spans"][0]
                t = s["text"].strip()
                if len(t) > 14:
                    refs.append((t, s["size"], s["bbox"][2] - s["bbox"][0]))
    refs = refs[:40]
    if refs:
        for f in sorted(os.listdir(FONT_DIR)):
            if not f.endswith(".ttf"):
                continue
            try:
                font = fitz.Font(fontfile=os.path.join(FONT_DIR, f))
            except Exception:
                continue
            errs = [abs(font.text_length(t, s) - w) / w * 100 for t, s, w in refs if w > 1]
            if errs:
                errs.sort()
                print(f"  {f:22s} median_err={errs[len(errs) // 2]:6.2f}%  min={errs[0]:5.2f}%")
        print("  (<1.5% median => same typeface & weight; >8% usually means letter-spacing or a bolder cut)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
