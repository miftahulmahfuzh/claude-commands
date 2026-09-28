#!/usr/bin/env python3
"""Build the PDFs run_tests.sh exercises, into the directory given as argv[1].

Each fixture isolates a trap seen in real files: kerned TJ arrays, hex strings,
2-byte CID codes, several matches sharing one content stream, and the plain
Tj / ' operators that PyMuPDF itself never emits.
"""
import os
import sys

import fitz

out = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(out, exist_ok=True)
J = lambda n: os.path.join(out, n)


def raw_pdf(path, content, width, height):
    """A PDF written by hand, so the operators are exactly what we intend."""
    objs = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            % (width, height)),
        4: b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        5: (b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"),
    }
    buf, off = bytearray(b"%PDF-1.4\n"), {}
    for n in sorted(objs):
        off[n] = len(buf)
        buf += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"
    x = len(buf)
    buf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for n in sorted(objs):
        buf += b"%010d 00000 n \n" % off[n]
    buf += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objs) + 1, x))
    open(path, "wb").write(bytes(buf))


# colored background + two identical phrases, each in its own content stream
d = fitz.open()
p = d.new_page(width=300, height=160)
p.draw_rect(fitz.Rect(0, 0, 300, 160), fill=(0.15, 0.35, 0.6))
p.draw_circle(fitz.Point(250, 130), 25, fill=(0.9, 0.6, 0.1))
p.insert_text((20, 50), "Status: Loading In", fontname="helv", fontsize=14,
              color=(1, 1, 1))
p.insert_text((20, 80), "Copy 2: Loading In", fontname="helv", fontsize=14,
              color=(1, 1, 1))
d.save(J("colored.pdf")); d.close()

# embedded TrueType -> Type0 / Identity-H, 2-byte glyph codes
ttf = next((c for c in (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
) if os.path.exists(c)), None)
if ttf:
    d = fitz.open()
    p = d.new_page(width=300, height=120)
    p.draw_rect(fitz.Rect(0, 0, 300, 120), fill=(0.95, 0.92, 0.85))
    p.insert_text((20, 60), "Invoice total: 1200 USD", fontname="emb",
                  fontfile=ttf, fontsize=13, color=(0.1, 0.1, 0.1))
    d.save(J("cid.pdf")); d.close()
else:
    sys.stderr.write("no TTF found - skipping cid.pdf (CID tests will fail)\n")

# colored header, an image, and several lines to edit
d = fitz.open()
p = d.new_page(width=420, height=240)
p.draw_rect(fitz.Rect(0, 0, 420, 60), fill=(0.10, 0.42, 0.30))
pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64))
for y in range(64):
    for x in range(64):
        pix.set_pixel(x, y, (x * 4 % 256, y * 4 % 256, (x * y) % 256))
p.insert_image(fitz.Rect(340, 180, 404, 240), pixmap=pix)
p.insert_text((18, 38), "ACME LOGISTICS", fontname="hebo", fontsize=18, color=(1, 1, 1))
p.insert_text((18, 100), "Shipment reference: SHP-2024-0117", fontname="helv", fontsize=12)
p.insert_text((18, 126), "Destination port: Surabaya", fontname="helv", fontsize=12)
p.insert_text((18, 152), "Status: Loading In", fontname="helv", fontsize=12)
d.save(J("shipment.pdf")); d.close()

# Tj, Td, TD, T* and the ' operator
raw_pdf(J("raw.pdf"), b"""q 0.9 0.2 0.2 rg 0 0 400 200 re f Q
BT
/F1 16 Tf
14 TL
1 0 0 1 30 150 Tm
(Order status: Loading In) Tj
0 -20 Td
(Second line here) Tj
(Third via quote) '
ET
""", 400, 200)

# three matches sharing ONE content stream
raw_pdf(J("shared.pdf"), b"""q 0.2 0.6 0.9 rg 0 0 400 220 re f Q
BT /F1 15 Tf
1 0 0 1 25 180 Tm (Bay A: Loading In now) Tj
1 0 0 1 25 150 Tm (Bay B: Loading In now) Tj
1 0 0 1 25 120 Tm (Bay C: Loading In now) Tj
ET
""", 400, 220)

print("fixtures written to %s" % os.path.abspath(out))
