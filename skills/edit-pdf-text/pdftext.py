#!/usr/bin/env python3
"""
pdftext.py -- find and replace real text inside a PDF by editing the glyphs in
the content stream, so that every other object (background art, scans, stamps,
photos, annotations, structure tree) stays byte-identical.

    pdftext.py find    doc.pdf "Loading In" --new "Loading out"
    pdftext.py replace doc.pdf out.pdf --old "Loading In" --new "Loading out"
    pdftext.py verify  doc.pdf out.pdf --crops ./crops

Requires PyMuPDF (`pip install pymupdf`). numpy optional, speeds up verify.
Set PDFTEXT_DEBUG=1 to surface exceptions swallowed while walking a stream.
"""

import argparse
import os
import re
import shutil
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("pdftext.py needs PyMuPDF: pip install pymupdf")


# ---------------------------------------------------------------- tokenizer

WS = b"\x00\t\n\x0c\r "
DELIMS = b"()<>[]{}/%"
NUM_RE = re.compile(rb"[+-]?(?:\d+\.?\d*|\.\d+)\Z")


class Tok:
    __slots__ = ("kind", "val", "start", "end")

    def __init__(self, kind, val, start, end):
        self.kind, self.val, self.start, self.end = kind, val, start, end

    def __repr__(self):
        return "Tok(%s,%r)" % (self.kind, self.val[:24])


def tokenize(buf):
    """Yield Tok over a PDF content stream. Inline images come back whole."""
    i, n = 0, len(buf)
    while i < n:
        c = buf[i : i + 1]
        if c in WS:
            i += 1
            continue
        if c == b"%":
            j = i
            while j < n and buf[j : j + 1] not in b"\r\n":
                j += 1
            i = j
            continue
        start = i
        if c == b"(":
            depth, j = 1, i + 1
            while j < n:
                ch = buf[j : j + 1]
                if ch == b"\\":
                    j += 2
                    continue
                if ch == b"(":
                    depth += 1
                elif ch == b")":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            yield Tok("str", buf[start:j], start, j)
            i = j
            continue
        if c == b"<":
            if buf[i : i + 2] == b"<<":
                yield Tok("dict_open", b"<<", i, i + 2)
                i += 2
                continue
            j = buf.find(b">", i)
            j = n if j < 0 else j + 1
            yield Tok("hex", buf[start:j], start, j)
            i = j
            continue
        if c == b">":
            if buf[i : i + 2] == b">>":
                yield Tok("dict_close", b">>", i, i + 2)
                i += 2
                continue
            i += 1
            continue
        if c in b"[]{}":
            kind = {b"[": "arr_open", b"]": "arr_close"}.get(c, "brace")
            yield Tok(kind, c, i, i + 1)
            i += 1
            continue
        if c == b"/":
            j = i + 1
            while j < n and buf[j : j + 1] not in WS and buf[j : j + 1] not in DELIMS:
                j += 1
            yield Tok("name", buf[start:j], start, j)
            i = j
            continue
        j = i
        while j < n and buf[j : j + 1] not in WS and buf[j : j + 1] not in DELIMS:
            j += 1
        if j == i:
            j = i + 1
        raw = buf[start:j]
        if NUM_RE.match(raw):
            yield Tok("num", raw, start, j)
            i = j
            continue
        if raw == b"BI":
            # Inline image: the binary payload between ID and EI can contain
            # anything at all, so skip it as one opaque token.
            k = buf.find(b"ID", j)
            e = (k + 3) if k >= 0 else j
            while True:
                e = buf.find(b"EI", e)
                if e < 0:
                    e = n
                    break
                before_ok = e == 0 or buf[e - 1 : e] in WS
                after = buf[e + 2 : e + 3]
                if before_ok and (after == b"" or after in WS or after in DELIMS):
                    e += 2
                    break
                e += 2
            yield Tok("inline_image", buf[start:e], start, e)
            i = e
            continue
        yield Tok("op", raw, start, j)
        i = j


# ------------------------------------------------------------ string codecs

ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
           b"(": b"(", b")": b")", b"\\": b"\\"}


def decode_literal(raw):
    r"""b'(a\(b)' -> b'a(b'"""
    body, out, i, n = raw[1:-1], bytearray(), 0, len(raw) - 2
    while i < n:
        ch = body[i : i + 1]
        if ch != b"\\":
            out += ch
            i += 1
            continue
        nxt = body[i + 1 : i + 2]
        if nxt in ESCAPES:
            out += ESCAPES[nxt]
            i += 2
        elif nxt.isdigit():
            digits = b""
            j = i + 1
            while j < n and len(digits) < 3 and body[j : j + 1].isdigit():
                digits += body[j : j + 1]
                j += 1
            out.append(int(digits, 8) & 0xFF)
            i = j
        elif nxt in (b"\n", b"\r"):
            i += 2
            if nxt == b"\r" and body[i : i + 1] == b"\n":
                i += 1
        else:
            out += nxt
            i += 2
    return bytes(out)


def encode_literal(data):
    out = bytearray(b"(")
    for b in data:
        if b in (0x28, 0x29, 0x5C):  # ( ) backslash
            out += b"\\" + bytes([b])
        elif 32 <= b < 127:
            out.append(b)
        else:
            out += ("\\%03o" % b).encode()
    out += b")"
    return bytes(out)


def decode_hex(raw):
    h = re.sub(rb"[^0-9A-Fa-f]", b"", raw[1:-1])
    if len(h) % 2:
        h += b"0"
    return bytes.fromhex(h.decode())


def encode_hex(data):
    return b"<" + data.hex().upper().encode() + b">"


# ------------------------------------------------------------------- fonts

WINANSI_FIXUP = {
    0x80: "\u20ac", 0x82: "\u201a", 0x83: "\u0192", 0x84: "\u201e", 0x85: "\u2026",
    0x86: "\u2020", 0x87: "\u2021", 0x88: "\u02c6", 0x89: "\u2030", 0x8A: "\u0160",
    0x8B: "\u2039", 0x8C: "\u0152", 0x8E: "\u017d", 0x91: "\u2018", 0x92: "\u2019",
    0x93: "\u201c", 0x94: "\u201d", 0x95: "\u2022", 0x96: "\u2013", 0x97: "\u2014",
    0x98: "\u02dc", 0x99: "\u2122", 0x9A: "\u0161", 0x9B: "\u203a", 0x9C: "\u0153",
    0x9E: "\u017e", 0x9F: "\u0178",
}

GLYPHNAMES = {
    "space": " ", "exclam": "!", "quotedbl": '"', "numbersign": "#", "dollar": "$",
    "percent": "%", "ampersand": "&", "quotesingle": "'", "parenleft": "(",
    "parenright": ")", "asterisk": "*", "plus": "+", "comma": ",", "hyphen": "-",
    "period": ".", "slash": "/", "zero": "0", "one": "1", "two": "2", "three": "3",
    "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "colon": ":", "semicolon": ";", "less": "<", "equal": "=", "greater": ">",
    "question": "?", "at": "@", "bracketleft": "[", "backslash": "\\",
    "bracketright": "]", "asciicircum": "^", "underscore": "_", "grave": "`",
    "braceleft": "{", "bar": "|", "braceright": "}", "asciitilde": "~",
    "quoteleft": "\u2018", "quoteright": "\u2019", "quotedblleft": "\u201c",
    "quotedblright": "\u201d", "endash": "\u2013", "emdash": "\u2014",
    "bullet": "\u2022", "fi": "fi", "fl": "fl",
}


def glyphname_to_unicode(name):
    if name in GLYPHNAMES:
        return GLYPHNAMES[name]
    if len(name) == 1:
        return name
    m = re.fullmatch(r"uni([0-9A-Fa-f]{4})", name)
    if m:
        return chr(int(m.group(1), 16))
    m = re.fullmatch(r"u([0-9A-Fa-f]{4,6})", name)
    if m:
        return chr(int(m.group(1), 16))
    return ""


def _get(doc, xref, path):
    try:
        return doc.xref_get_key(xref, path)
    except Exception:
        return ("null", "null")


def _deref_obj(doc, kind, val):
    """Return (dict source string, xref or None) for a dict-ish value."""
    if kind == "xref":
        try:
            tgt = int(val.split()[0])
            return doc.xref_object(tgt, compressed=False), tgt
        except Exception:
            return "", None
    if kind == "dict":
        return val, None
    return "", None


def _has_fontfile(doc, xref):
    """True only when the glyph outlines actually travel inside the PDF."""
    for key in ("FontFile", "FontFile2", "FontFile3"):
        if _get(doc, xref, "FontDescriptor/" + key)[0] != "null":
            return True
    return False


def parse_tounicode(data):
    """CMap stream -> ({code: unicode}, code byte width)."""
    txt = data.decode("latin-1", "replace")
    out, widths = {}, set()

    def uni(h):
        try:
            if len(h) % 2:
                h += "0"
            return bytes.fromhex(h).decode("utf-16-be")
        except Exception:
            return ""

    for block in re.findall(r"beginbfchar(.*?)endbfchar", txt, re.S):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            widths.add(len(src) // 2)
            out[int(src, 16)] = uni(dst)
    for block in re.findall(r"beginbfrange(.*?)endbfrange", txt, re.S):
        for lo, hi, dst in re.findall(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block
        ):
            widths.add(len(lo) // 2)
            try:
                base = bytes.fromhex(dst if len(dst) % 2 == 0 else dst + "0")
            except ValueError:
                continue
            for k, code in enumerate(range(int(lo, 16), int(hi, 16) + 1)):
                b = bytearray(base)
                if b:
                    b[-1] = (b[-1] + k) & 0xFF
                try:
                    out[code] = bytes(b).decode("utf-16-be")
                except Exception:
                    pass
        for lo, hi, arr in re.findall(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", block, re.S
        ):
            widths.add(len(lo) // 2)
            items = re.findall(r"<([0-9A-Fa-f]*)>", arr)
            for k, code in enumerate(range(int(lo, 16), int(hi, 16) + 1)):
                if k < len(items):
                    out[code] = uni(items[k])
    return out, (max(widths) if widths else 1)


def parse_number_array(s):
    return [float(x) for x in re.findall(r"[-+]?\d*\.?\d+", s)]


class Font:
    """Everything needed to read and rewrite the codes of one PDF font."""

    _BASE14 = [
        (("times", "serif", "roman", "georgia", "garamond", "book"),
         ("tiro", "tibo", "tiit", "tibi")),
        (("courier", "mono", "consol"), ("cour", "cobo", "coit", "cobi")),
        (("symbol",), ("symb",) * 4),
        (("zapf", "dingbat"), ("zadb",) * 4),
    ]

    def __init__(self, doc, xref, resname):
        self.resname = resname
        self.xref = xref
        self.subtype = _get(doc, xref, "Subtype")[1].lstrip("/")
        self.basefont = _get(doc, xref, "BaseFont")[1].lstrip("/")
        self.is_cid = self.subtype == "Type0"
        self.code_bytes = 2 if self.is_cid else 1
        self.to_uni = {}
        self.embedded = False
        self.widths = {}
        self.default_width = 500.0
        self.note = ""

        enc_kind, enc_val = _get(doc, xref, "Encoding")
        self.encoding = enc_val.lstrip("/") if enc_kind == "name" else enc_val

        tk, tv = _get(doc, xref, "ToUnicode")
        if tk == "xref":
            try:
                data = doc.xref_stream(int(tv.split()[0]))
                self.to_uni, w = parse_tounicode(data)
                if self.is_cid and w > 1:
                    self.code_bytes = max(2, w)
            except Exception as exc:
                self.note += "ToUnicode unreadable (%s). " % exc

        if not self.to_uni and not self.is_cid:
            codec = "cp1252"
            if isinstance(self.encoding, str) and "MacRoman" in self.encoding:
                codec = "mac_roman"
            for code in range(32, 256):
                try:
                    self.to_uni[code] = bytes([code]).decode(codec)
                except Exception:
                    continue
            if codec == "cp1252":
                self.to_uni.update(WINANSI_FIXUP)
            self._apply_differences(doc, xref)

        self.rev = {}
        for code, text in sorted(self.to_uni.items()):
            if len(text) == 1 and text not in self.rev:
                self.rev[text] = code

        self._load_widths(doc, xref)

    # -- encoding -----------------------------------------------------------

    def _apply_differences(self, doc, xref):
        dk, dv = _get(doc, xref, "Encoding/Differences")
        if dk == "null":
            return
        cur = 0
        for num, name in re.findall(r"(\d+)|/([^\s/\]]+)", dv):
            if num:
                cur = int(num)
                continue
            ch = glyphname_to_unicode(name)
            if ch:
                self.to_uni[cur] = ch
            cur += 1

    def split_codes(self, data):
        cb = self.code_bytes
        return [int.from_bytes(data[i : i + cb], "big")
                for i in range(0, len(data), cb)]

    def code_to_bytes(self, code):
        return code.to_bytes(self.code_bytes, "big")

    def encode_text(self, text):
        """unicode -> (bytes, list of characters this font cannot express)"""
        out, missing = bytearray(), []
        for ch in text:
            code = self.rev.get(ch)
            if code is None:
                missing.append(ch)
                continue
            out += self.code_to_bytes(code)
        return bytes(out), missing

    # -- widths -------------------------------------------------------------

    def _load_widths(self, doc, xref):
        if self.is_cid:
            dk, dv = _get(doc, xref, "DescendantFonts")
            m = re.search(r"(\d+)\s+\d+\s+R", dv or "")
            dxref = int(m.group(1)) if m else _deref_obj(doc, dk, dv)[1]
            if dxref:
                self.embedded = _has_fontfile(doc, dxref)
                wk, wv = _get(doc, dxref, "W")
                if wk == "array":
                    self._parse_w(wv)
                dwk, dwv = _get(doc, dxref, "DW")
                self.default_width = float(dwv) if dwk in ("int", "float") else 1000.0
            else:
                self.default_width = 1000.0
            return

        self.embedded = _has_fontfile(doc, xref)
        fk, fv = _get(doc, xref, "FirstChar")
        first = int(fv) if fk == "int" else 0
        wk, wv = _get(doc, xref, "Widths")
        if wk == "xref":
            try:
                wv = doc.xref_object(int(wv.split()[0]), compressed=False)
                wk = "array"
            except Exception:
                wk = "null"
        if wk == "array":
            for i, w in enumerate(parse_number_array(wv)):
                self.widths[first + i] = w
        mk, mv = _get(doc, xref, "FontDescriptor/MissingWidth")
        if mk in ("int", "float"):
            self.default_width = float(mv)
        else:
            self.default_width = 0.0 if self.widths else 500.0
        if not self.widths:
            self.note += "no /Widths (standard metrics assumed). "

    def _parse_w(self, s):
        """/W [ c [w w w] cfirst clast w ... ]"""
        toks = re.findall(r"\[|\]|[-+]?\d*\.?\d+", s)
        i, n = 0, len(toks)
        while i < n:
            if toks[i] in ("[", "]"):
                i += 1
                continue
            try:
                c = int(float(toks[i]))
            except ValueError:
                i += 1
                continue
            if i + 1 < n and toks[i + 1] == "[":
                j, k = i + 2, c
                while j < n and toks[j] != "]":
                    self.widths[k] = float(toks[j])
                    k += 1
                    j += 1
                i = j + 1
            elif i + 2 < n:
                try:
                    c2, w = int(float(toks[i + 1])), float(toks[i + 2])
                    for k in range(c, min(c2, c + 65535) + 1):
                        self.widths[k] = w
                except ValueError:
                    pass
                i += 3
            else:
                break

    def width(self, code):
        return self.widths.get(code, self.default_width)

    def declared_width(self, ch):
        code = self.rev.get(ch)
        return None if code is None else self.widths.get(code, self.default_width)

    def _metrics_font(self, doc):
        """A real font program to ask for true advance widths."""
        if hasattr(self, "_mf"):
            return self._mf
        self._mf = None
        owner = self.xref
        if self.is_cid:
            dk, dv = _get(doc, self.xref, "DescendantFonts")
            m = re.search(r"(\d+)\s+\d+\s+R", dv or "")
            if m:
                owner = int(m.group(1))
        for key in ("FontFile2", "FontFile3", "FontFile"):
            k, v = _get(doc, owner, "FontDescriptor/" + key)
            if k == "xref":
                try:
                    self._mf = fitz.Font(fontbuffer=doc.xref_stream(int(v.split()[0])))
                    return self._mf
                except Exception:
                    pass
        low = (self.basefont or "").lower()
        bold = "bold" in low or "black" in low or "heavy" in low
        ital = "italic" in low or "oblique" in low
        names = ("helv", "hebo", "heit", "hebi")
        for keys, cand in self._BASE14:
            if any(k in low for k in keys):
                names = cand
                break
        try:
            self._mf = fitz.Font(names[(1 if bold else 0) + (2 if ital else 0)])
        except Exception:
            self._mf = None
        return self._mf

    def real_advance(self, doc, ch):
        """True advance for `ch` in 1/1000 text-space units, or None."""
        mf = self._metrics_font(doc)
        if mf is None:
            return None
        try:
            w = mf.glyph_advance(ord(ch)) * 1000.0
        except Exception:
            return None
        return w if w > 0 else None


# ------------------------------------------------------------- stream walk

SHOW_OPS = {b"Tj", b"TJ", b"'", b'"'}


def mat_mul(a, b):
    return [
        a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5],
    ]


class ShowOp:
    """One text-showing operator, with everything needed to rewrite it."""

    def __init__(self):
        self.unit = None          # StreamUnit it lives in
        self.start = 0            # byte offset of its first operand
        self.end = 0              # byte offset just past the operator
        self.operator = b"Tj"
        self.lead = b""           # the two numbers that precede a " string
        self.elements = []        # ('c', code:int) | ('k', raw number bytes)
        self.font = None
        self.size = 0.0
        self.origin = (0.0, 0.0)
        self.tm = [1, 0, 0, 1, 0, 0]
        self.fill = "unset (black)"
        self.tm_operand_span = None   # (start, end) of the six Tm operands
        self.text = ""

    def chars(self):
        return [e for e in self.elements if e[0] == "c"]

    def width_units(self):
        """Advance in 1/1000 text-space units, kerning included."""
        return sum(self.font.width(v) if k == "c" else -float(v)
                   for k, v in self.elements)

    def advance(self):
        return self.width_units() / 1000.0 * self.size

    def serialize(self, elements):
        """Rebuild the operator bytes from an element list."""
        hexmode = self.font.is_cid
        parts, run = [], bytearray()

        def emit(tok):
            # Two numbers in a row must stay separate tokens: [(a)5 7(b)], not 57.
            if parts and tok[:1] not in b"(<" and parts[-1][-1:] not in b")>":
                parts.append(b" ")
            parts.append(tok)

        def flush():
            if run:
                emit(encode_hex(bytes(run)) if hexmode else encode_literal(bytes(run)))
                run.clear()

        has_kern = any(k == "k" for k, _ in elements)
        for kind, val in elements:
            if kind == "c":
                run += self.font.code_to_bytes(val)
            else:
                flush()
                emit(val)
        flush()
        if not parts:
            parts = [encode_hex(b"") if hexmode else b"()"]

        if self.operator == b"TJ" or has_kern:
            body = b"[" + b"".join(parts) + b"] TJ"
            if self.operator == b"'":
                return b"T*\n" + body
            if self.operator == b'"':
                nums = self.lead.split()
                pre = (b"%s Tw %s Tc T*\n" % (nums[0], nums[1])) if len(nums) == 2 \
                    else b"T*\n"
                return pre + body
            return body
        body = b"".join(parts)
        if self.operator in (b"'", b'"'):
            return (self.lead + b" " if self.lead else b"") + body + b" " + self.operator
        return body + b" Tj"


class StreamUnit:
    """A content stream we can rewrite: a page stream or a Form XObject."""

    def __init__(self, xref, buf, fonts, owner, label):
        self.xref = xref
        self.buf = buf
        self.fonts = fonts
        self.owner = owner
        self.label = label


def _name_map(doc, owner_xref, path):
    """resource-name -> xref, for Resources/Font or Resources/XObject."""
    out = {}
    kind, val = _get(doc, owner_xref, path)
    if kind == "xref":
        fx = int(val.split()[0])
        try:
            for key in doc.xref_get_keys(fx):
                k2, v2 = doc.xref_get_key(fx, key)
                if k2 == "xref":
                    out[key] = int(v2.split()[0])
        except Exception:
            pass
        return out
    src, _ = _deref_obj(doc, kind, val)
    for name, num in re.findall(r"/([^\s/<>\[\]()]+)\s+(\d+)\s+\d+\s+R", src or ""):
        out[name] = int(num)
    return out


def font_resources(doc, owner_xref, cache):
    fonts = {}
    for name, fx in _name_map(doc, owner_xref, "Resources/Font").items():
        if fx not in cache:
            cache[fx] = Font(doc, fx, name)
        fonts[name] = cache[fx]
    return fonts


def walk_page(doc, page, font_cache, seen=None):
    """Return (units, show ops) for a page, descending into Form XObjects."""
    units, ops = [], []
    seen = set() if seen is None else seen
    debug = os.environ.get("PDFTEXT_DEBUG")

    def walk_unit(unit):
        state = {
            "tm": [1, 0, 0, 1, 0, 0], "tlm": [1, 0, 0, 1, 0, 0], "tm_span": None,
            "font": None, "size": 0.0, "tc": 0.0, "tw": 0.0, "tz": 100.0,
            "tl": 0.0, "fill": "unset (black)", "gs": [],
        }
        stack = []
        for tok in tokenize(unit.buf):
            if tok.kind != "op":
                stack.append(tok)
                if len(stack) > 64:
                    del stack[:-64]
                continue
            try:
                apply_op(unit, tok.val, stack, tok, state)
            except Exception:
                if debug:
                    import traceback
                    traceback.print_exc()
            stack = []

    def apply_op(unit, op, stack, tok, st):
        nums = [float(t.val) for t in stack if t.kind == "num"]
        if op == b"Tf" and len(stack) >= 2:
            st["font"] = unit.fonts.get(stack[-2].val[1:].decode("latin-1"))
            st["size"] = nums[-1] if nums else 0.0
        elif op == b"Tm" and len(nums) >= 6:
            st["tm"] = list(nums[-6:])
            st["tlm"] = list(st["tm"])
            st["tm_span"] = (stack[-6].start, stack[-1].end)
        elif op in (b"Td", b"TD") and len(nums) >= 2:
            if op == b"TD":
                st["tl"] = -nums[-1]
            st["tlm"] = mat_mul([1, 0, 0, 1, nums[-2], nums[-1]], st["tlm"])
            st["tm"] = list(st["tlm"])
            st["tm_span"] = None
        elif op == b"T*":
            st["tlm"] = mat_mul([1, 0, 0, 1, 0, -st["tl"]], st["tlm"])
            st["tm"] = list(st["tlm"])
            st["tm_span"] = None
        elif op == b"BT":
            st["tm"] = [1, 0, 0, 1, 0, 0]
            st["tlm"] = [1, 0, 0, 1, 0, 0]
            st["tm_span"] = None
        elif op == b"TL" and nums:
            st["tl"] = nums[-1]
        elif op == b"Tc" and nums:
            st["tc"] = nums[-1]
        elif op == b"Tw" and nums:
            st["tw"] = nums[-1]
        elif op == b"Tz" and nums:
            st["tz"] = nums[-1]
        elif op in (b"g", b"rg", b"k", b"sc", b"scn"):
            st["fill"] = op.decode() + " " + " ".join("%g" % v for v in nums)
        elif op == b"q":
            st["gs"].append(st["fill"])
        elif op == b"Q":
            if st["gs"]:
                st["fill"] = st["gs"].pop()
        elif op == b"Do" and stack and stack[-1].kind == "name":
            name = stack[-1].val[1:].decode("latin-1")
            fx = _name_map(doc, unit.owner, "Resources/XObject").get(name)
            if fx and fx not in seen and _get(doc, fx, "Subtype")[1].lstrip("/") == "Form":
                seen.add(fx)
                try:
                    sub = StreamUnit(
                        fx, doc.xref_stream(fx),
                        font_resources(doc, fx, font_cache) or unit.fonts,
                        fx, "%s > Form %s" % (unit.label, name))
                    units.append(sub)
                    walk_unit(sub)
                except Exception:
                    if debug:
                        import traceback
                        traceback.print_exc()
        elif op in SHOW_OPS:
            record_show(unit, op, stack, tok, st)

    def record_show(unit, op, stack, tok, st):
        so = ShowOp()
        so.unit, so.operator = unit, op
        so.font, so.size, so.fill = st["font"], st["size"], st["fill"]
        so.tm = list(st["tm"])
        so.origin = (st["tm"][4], st["tm"][5])
        so.tm_operand_span = st["tm_span"]
        if so.font is None:
            return
        if op == b"TJ":
            items, depth = [], 0
            for t in stack:
                if t.kind == "arr_open":
                    depth += 1
                    items = []
                elif t.kind == "arr_close":
                    depth -= 1
                elif depth > 0:
                    items.append(t)
            so.start = next((t.start for t in stack if t.kind == "arr_open"), tok.start)
        else:
            strings = [t for t in stack if t.kind in ("str", "hex")]
            items = strings[-1:]
            lead = [t for t in stack if t.kind == "num"]
            so.start = items[0].start if items else tok.start
            if op == b'"' and len(lead) >= 2:
                so.lead = b" ".join(t.val for t in lead[-2:])
                so.start = lead[-2].start
        so.end = tok.end
        for t in items:
            if t.kind == "str":
                data = decode_literal(t.val)
            elif t.kind == "hex":
                data = decode_hex(t.val)
            else:
                so.elements.append(("k", t.val))
                continue
            for code in so.font.split_codes(data):
                so.elements.append(("c", code))
        so.text = "".join(so.font.to_uni.get(v, "\ufffd")
                          for k, v in so.elements if k == "c")
        ops.append(so)
        # advance the text matrix so later Td-relative ops stay accurate
        w = so.advance() + st["tc"] * len(so.chars()) + st["tw"] * so.text.count(" ")
        st["tm"] = mat_mul([1, 0, 0, 1, w * (st["tz"] / 100.0), 0], st["tm"])

    for xref in page.get_contents():
        u = StreamUnit(xref, doc.xref_stream(xref),
                       font_resources(doc, page.xref, font_cache), page.xref,
                       "page %d stream %d" % (page.number + 1, xref))
        units.append(u)
        walk_unit(u)
    return units, ops


# --------------------------------------------------------------- searching

def build_index(ops):
    """Concatenate all shown text; map each char to (op index, element index)."""
    text, index = [], []
    for oi, so in enumerate(ops):
        for ei, (kind, val) in enumerate(so.elements):
            if kind != "c":
                continue
            text.append(so.font.to_uni.get(val, "\ufffd"))
            index.append((oi, ei))
    return "".join(text), index


def phrase_regex(phrase):
    """Spaces in the query match any run of whitespace, or none at all -- a PDF
    may position words without ever emitting a space character."""
    parts = [re.escape(p) for p in phrase.split()]
    return re.compile(r"\s*".join(parts)) if parts else re.compile(re.escape(phrase))


def minimal_edit(old, new):
    """Trim the common prefix/suffix so the edit touches as few glyphs as possible."""
    p = 0
    while p < len(old) and p < len(new) and old[p] == new[p]:
        p += 1
    s = 0
    while s < len(old) - p and s < len(new) - p and old[-1 - s] == new[-1 - s]:
        s += 1
    return p, len(old) - s, new[p : len(new) - s]


def anchor_for(index, a, p, q):
    """Where the replacement goes: (op index, element index to insert before).

    A pure insertion anchors on the character it *follows*, never on the one
    after the match -- that character may live in the next chunk at its own Tm.
    """
    if q > p:
        return index[a + p]
    if p == 0:
        return index[a]
    oi, ei = index[a + p - 1]
    return (oi, ei + 1)


def find_matches(doc, pages, phrase, font_cache):
    results = []
    rx = phrase_regex(phrase)
    for pno in pages:
        page = doc[pno]
        units, ops = walk_page(doc, page, font_cache)
        doctext, index = build_index(ops)
        for m in rx.finditer(doctext):
            results.append({
                "page": pno, "units": units, "ops": ops, "doctext": doctext,
                "index": index, "span": (m.start(), m.end()), "matched": m.group(0),
            })
    return results


# -------------------------------------------------------------- reporting

def describe(match, width=46):
    a, b = match["span"]
    t = match["doctext"]
    left = t[max(0, a - width) : a].replace("\n", " ")
    right = t[b : b + width].replace("\n", " ")
    ops, index = match["ops"], match["index"]
    touched = sorted({index[i][0] for i in range(a, b)})
    lines = ["  context : ...%s[%s]%s..." % (left, match["matched"], right)]
    for oi in touched:
        so = ops[oi]
        f = so.font
        lines.append(
            "  chunk   : %r  font=%s(%s %s%s) size=%.2f at x=%.2f y=%.2f fill=%s"
            % (so.text, f.resname, f.basefont, f.subtype,
               ", embedded" if f.embedded else ", not embedded",
               so.size, so.origin[0], so.origin[1], so.fill))
        lines.append("  raw     : %s" % so.unit.buf[so.start : so.end].decode("latin-1"))
    return "\n".join(lines)


def editability(match, new_text):
    """Return (ok, messages, touched op indices, (p, q, insert text))."""
    a, b = match["span"]
    ops, index = match["ops"], match["index"]
    p, q, ins = minimal_edit(match["matched"], new_text)
    if q > p:
        touched = sorted({index[i][0] for i in range(a + p, a + q)})
    else:
        touched = [anchor_for(index, a, p, q)[0]]
    msgs, ok = [], True

    if len(touched) > 1:
        msgs.append("spans %d separately positioned chunks - the replacement is "
                    "emitted from the first and the leftovers are re-anchored "
                    "after it" % len(touched))
    font = ops[touched[0]].font
    zero = sorted({c for c in ins if (font.declared_width(c) or 0) <= 0})
    if zero:
        msgs.append("%s declared with width 0 in this font (never used in the "
                    "original) - replace will patch /Widths with the real advance"
                    % ", ".join(repr(c) for c in zero))
    _, missing = font.encode_text(ins)
    if missing:
        ok = False
        msgs.append("font %s (%s) has no code for %s - the glyph is not in this "
                    "(subset) font"
                    % (font.resname, font.basefont,
                       ", ".join(repr(c) for c in sorted(set(missing)))))
    return ok, msgs, touched, (p, q, ins)


def ensure_widths(doc, font, text):
    """A glyph the producer never used often has width 0 declared, so it draws
    with no advance and the next letter lands on top of it. Declare the real one."""
    needed = {}
    for ch in set(text):
        code = font.rev.get(ch)
        if code is None:
            continue
        cur = font.widths.get(code, font.default_width)
        if cur and cur > 0:
            continue
        real = font.real_advance(doc, ch)
        if real:
            needed[code] = round(real, 2)
    if not needed:
        return []

    if font.is_cid:
        dk, dv = _get(doc, font.xref, "DescendantFonts")
        m = re.search(r"(\d+)\s+\d+\s+R", dv or "")
        if not m:
            return []
        dx = int(m.group(1))
        wv = _get(doc, dx, "W")[1] or "[]"
        body = wv.strip()[1:-1] if wv.strip().startswith("[") else ""
        extra = " ".join("%d [%g]" % (c, w) for c, w in sorted(needed.items()))
        doc.xref_set_key(dx, "W", "[%s %s]" % (body, extra))
    else:
        codes = set(font.widths) | set(needed)
        first, last = min(codes), max(codes)
        merged = dict(font.widths)
        merged.update(needed)
        arr = " ".join("%g" % merged.get(c, 0) for c in range(first, last + 1))
        doc.xref_set_key(font.xref, "FirstChar", str(first))
        doc.xref_set_key(font.xref, "LastChar", str(last))
        doc.xref_set_key(font.xref, "Widths", "[%s]" % arr)

    font.widths.update(needed)
    return [(font.to_uni.get(c, "?"), w) for c, w in sorted(needed.items())]


# ---------------------------------------------------------------- replace

def apply_replacement(doc, match, new_text, reflow="line"):
    """Rewrite the content stream bytes. Returns a report dict."""
    a, b = match["span"]
    ops, index = match["ops"], match["index"]
    ok, msgs, touched, (p, q, ins) = editability(match, new_text)
    if not ok:
        raise RuntimeError("; ".join(msgs))

    victims = {}
    for i in range(a + p, a + q):
        oi, ei = index[i]
        victims.setdefault(oi, []).append(ei)

    primary, insert_elem = anchor_for(index, a, p, q)
    if q > p:
        primary = touched[0]
        insert_elem = min(victims[primary])

    edits, notes, shifted = {}, list(msgs), []
    width_fixes = ensure_widths(doc, ops[primary].font, ins)
    last = ops[touched[-1]]
    original_end = last.origin[0] + last.advance()
    cursor = ops[primary].origin[0]

    for oi in touched:
        so = ops[oi]
        drop = set(victims.get(oi, []))
        if drop:
            # Kerning tuned for the glyph pairs we delete goes with them.
            lo, hi = min(drop), max(drop)
            drop |= {i for i in range(lo + 1, hi) if so.elements[i][0] == "k"}
        char_idx = [i for i, (k, _) in enumerate(so.elements) if k == "c"]
        kept_before = [i for i in char_idx if drop and i < min(drop)]

        new_elems, inserted = [], False

        def put():
            codes, _ = so.font.encode_text(ins)
            new_elems.extend(("c", c) for c in so.font.split_codes(codes))

        for ei, (kind, val) in enumerate(so.elements):
            if oi == primary and not inserted and ei == insert_elem:
                put()
                inserted = True
            if ei in drop:
                continue
            new_elems.append((kind, val))
        if oi == primary and not inserted:
            put()

        new_adv = sum(so.font.width(v) if k == "c" else -float(v)
                      for k, v in new_elems) / 1000.0 * so.size
        has_chars = any(k == "c" for k, _ in new_elems)

        if oi == primary:
            cursor = so.origin[0] + new_adv
        elif not has_chars:
            pass                                   # chunk emptied; cursor unmoved
        elif kept_before:
            # Text survives on BOTH sides of the cut inside one chunk: its start
            # is still correct, so leave the matrix alone and resume from its end.
            notes.append("chunk at x=%.2f kept its own position (text survives on "
                         "both sides of the cut)" % so.origin[0])
            cursor = so.origin[0] + new_adv
        elif so.tm_operand_span:
            m = list(so.tm)
            m[4] = cursor
            edits.setdefault(so.unit, []).append(
                (so.tm_operand_span[0], so.tm_operand_span[1],
                 ("%g %g %g %g %g %g" % tuple(m)).encode()))
            shifted.append(so)
            cursor += new_adv
        else:
            notes.append("chunk at x=%.2f is positioned relatively (Td/T*), not by "
                         "Tm - left in place" % so.origin[0])
            cursor = so.origin[0] + new_adv

        if has_chars:
            raw = so.serialize(new_elems)
        elif so.operator == b"'":
            raw = b"T*"
        elif so.operator == b'"':
            nums = so.lead.split()
            raw = (b"%s Tw %s Tc T*" % (nums[0], nums[1])) if len(nums) == 2 else b"T*"
        else:
            raw = b""
        edits.setdefault(so.unit, []).append((so.start, so.end, raw))

    delta = cursor - original_end

    # Shift whatever else sits to the right on the same baseline.
    if reflow == "line" and abs(delta) > 0.01:
        touched_set = set(touched)
        for oi, so in enumerate(ops):
            if oi in touched_set or so.tm_operand_span is None:
                continue
            if abs(so.origin[1] - last.origin[1]) > 0.5:
                continue
            if so.origin[0] <= last.origin[0] + 1e-6:
                continue
            m = list(so.tm)
            m[4] += delta
            edits.setdefault(so.unit, []).append(
                (so.tm_operand_span[0], so.tm_operand_span[1],
                 ("%g %g %g %g %g %g" % tuple(m)).encode()))
            shifted.append(so)

    for unit, items in edits.items():
        buf = unit.buf
        for s0, e0, raw in sorted(items, key=lambda t: -t[0]):
            buf = buf[:s0] + raw + buf[e0:]
        unit.buf = buf
        doc.update_stream(unit.xref, buf, compress=True)

    return {"delta": delta, "touched": touched, "shifted": shifted,
            "messages": notes, "minimal": (match["matched"][p:q], ins),
            "width_fixes": width_fixes}


# ----------------------------------------------------------------- verify

def diff_mask(pa, pb):
    """Differing-pixel mask: (ndarray, True) or (list of row x-lists, False)."""
    try:
        import numpy as np
        a = np.frombuffer(pa.samples, dtype=np.uint8).reshape(pa.height, pa.width, pa.n)
        b = np.frombuffer(pb.samples, dtype=np.uint8).reshape(pb.height, pb.width, pb.n)
        return (a != b).any(axis=2), True
    except ImportError:
        pass
    sa, sb, w, h, n = pa.samples, pb.samples, pa.width, pa.height, pa.n
    rows = []
    for y in range(h):
        off = y * w * n
        if sa[off : off + w * n] == sb[off : off + w * n]:
            rows.append([])
            continue
        rows.append([x for x in range(w)
                     if sa[off + x * n : off + x * n + n]
                     != sb[off + x * n : off + x * n + n]])
    return rows, False


def _bands(values, gap):
    out, start, prev = [], values[0], values[0]
    for v in values[1:]:
        if v - prev > gap:
            out.append((start, prev))
            start = v
        prev = v
    out.append((start, prev))
    return out


def diff_regions(pa, pb, row_gap=6, col_gap=24):
    """Cluster differing pixels into regions, so two edits on two lines read as
    two boxes rather than one union that looks alarmingly large."""
    mask, is_np = diff_mask(pa, pb)
    regions = []
    if is_np:
        import numpy as np
        total = int(mask.sum())
        ys = np.nonzero(mask.any(axis=1))[0]
        if not len(ys):
            return [], 0
        for y0, y1 in _bands(list(ys), row_gap):
            xs = np.nonzero(mask[y0 : y1 + 1].any(axis=0))[0]
            for x0, x1 in _bands(list(xs), col_gap):
                sub = mask[y0 : y1 + 1, x0 : x1 + 1]
                regions.append((int(x0), int(y0), int(x1), int(y1), int(sub.sum())))
        return regions, total
    total = sum(len(xs) for xs in mask)
    ys = [y for y, xs in enumerate(mask) if xs]
    if not ys:
        return [], 0
    for y0, y1 in _bands(ys, row_gap):
        xs = sorted({x for y in range(y0, y1 + 1) for x in mask[y]})
        for x0, x1 in _bands(xs, col_gap):
            cnt = sum(1 for y in range(y0, y1 + 1) for x in mask[y] if x0 <= x <= x1)
            regions.append((x0, y0, x1, y1, cnt))
    return regions, total


def cmd_verify(args):
    import hashlib

    a, b = fitz.open(args.old), fitz.open(args.new)
    rc = 0
    if len(a) != len(b):
        print("FAIL page count %d -> %d" % (len(a), len(b)))
        return 1
    print("pages: %d" % len(a))

    print("\nembedded images (xref, w, h, sha1):")
    for pno in range(len(a)):
        rows = []
        for doc in (a, b):
            sig = []
            for im in doc[pno].get_images(full=True):
                try:
                    raw = doc.extract_image(im[0])
                except Exception:
                    continue
                sig.append((im[0], raw["width"], raw["height"],
                            hashlib.sha1(raw["image"]).hexdigest()[:12]))
            rows.append(sig)
        same = rows[0] == rows[1]
        print("  page %d: %d image(s)  %s"
              % (pno + 1, len(rows[0]), "identical" if same else "CHANGED"))
        if not same:
            rc = 1
            print("    old %s\n    new %s" % (rows[0], rows[1]))

    print("\nrendered pixel diff at %d dpi" % args.dpi)
    print("  (boxes in PDF user space - the frame `find` prints, y up from the bottom)")
    if args.crops:
        os.makedirs(args.crops, exist_ok=True)
    for pno in range(len(a)):
        pa, pb = a[pno].get_pixmap(dpi=args.dpi), b[pno].get_pixmap(dpi=args.dpi)
        if (pa.width, pa.height) != (pb.width, pb.height):
            print("  page %d: SIZE CHANGED" % (pno + 1))
            rc = 1
            continue
        regions, total = diff_regions(pa, pb)
        if args.crops and total:
            for doc, tag in ((a, "before"), (b, "after")):
                doc[pno].get_pixmap(dpi=110).save(
                    os.path.join(args.crops, "page%d_full_%s.png" % (pno + 1, tag)))
        if not total:
            print("  page %d: identical" % (pno + 1))
            continue
        f, ph = 72.0 / args.dpi, a[pno].rect.height
        print("  page %d: %d px differ in %d region(s)" % (pno + 1, total, len(regions)))
        if args.crops:
            print("      whole page: %s/page%d_full_{before,after}.png"
                  % (args.crops, pno + 1))
        for i, (x0, y0, x1, y1, cnt) in enumerate(regions, 1):
            print("    region %d: %d px  x %.1f-%.1f  y %.1f-%.1f  (w %.1f, h %.1f)"
                  % (i, cnt, x0 * f, (x1 + 1) * f, ph - (y1 + 1) * f, ph - y0 * f,
                     (x1 + 1 - x0) * f, (y1 + 1 - y0) * f))
            if args.crops:
                clip = fitz.Rect(x0 * f - 40, y0 * f - 12,
                                 (x1 + 1) * f + 120, (y1 + 1) * f + 12)
                tag = "page%d_r%d" % (pno + 1, i)
                a[pno].get_pixmap(clip=clip, dpi=300).save(
                    os.path.join(args.crops, tag + "_before.png"))
                b[pno].get_pixmap(clip=clip, dpi=300).save(
                    os.path.join(args.crops, tag + "_after.png"))
                print("      crops: %s/%s_{before,after}.png" % (args.crops, tag))

    print("\ntext diff:")
    any_text = False
    for pno in range(len(a)):
        ta, tb = a[pno].get_text(), b[pno].get_text()
        if ta == tb:
            continue
        any_text = True
        la, lb = ta.splitlines(), tb.splitlines()
        for i in range(max(len(la), len(lb))):
            x = la[i] if i < len(la) else "<none>"
            y = lb[i] if i < len(lb) else "<none>"
            if x != y:
                print("  page %d line %d:\n    - %s\n    + %s" % (pno + 1, i + 1, x, y))
    if not any_text:
        print("  (no extracted-text differences)")
    return rc


# ------------------------------------------------------------------- CLI

def page_list(doc, spec):
    if not spec:
        return list(range(len(doc)))
    out = []
    for part in spec.split(","):
        if "-" in part:
            s, e = part.split("-")
            out.extend(range(int(s) - 1, int(e)))
        else:
            out.append(int(part) - 1)
    return [p for p in out if 0 <= p < len(doc)]


def cmd_find(args):
    doc = fitz.open(args.pdf)
    matches = find_matches(doc, page_list(doc, args.pages), args.text, {})
    if not matches:
        print("No match for %r." % args.text)
        print("\nThe text may be part of a scanned image rather than real text.")
        print("Check with:  pdftext.py dump %s" % args.pdf)
        return 1
    print("%d match(es) for %r\n" % (len(matches), args.text))
    for i, m in enumerate(matches, 1):
        print("[%d] page %d" % (i, m["page"] + 1))
        print(describe(m))
        if args.new is not None:
            ok, msgs, touched, (p, q, ins) = editability(m, args.new)
            print("  minimal : %r -> %r" % (m["matched"][p:q], ins))
            print("  editable: %s" % ("yes" if ok else "NO"))
            for msg in msgs:
                print("            - %s" % msg)
        print()
    return 0


def cmd_dump(args):
    doc = fitz.open(args.pdf)
    cache = {}
    for pno in page_list(doc, args.pages):
        units, ops = walk_page(doc, doc[pno], cache)
        text, _ = build_index(ops)
        print("=== page %d (%d show ops) ===" % (pno + 1, len(ops)))
        print(text)
    return 0


def cmd_replace(args):
    if os.path.abspath(args.pdf) == os.path.abspath(args.out):
        sys.exit("refusing to overwrite the source; give a different output path")
    if len(args.old) != len(args.new):
        sys.exit("--old and --new must be given the same number of times (%d vs %d)"
                 % (len(args.old), len(args.new)))
    if args.occurrence and len(args.old) > 1:
        sys.exit("--occurrence applies to a single --old/--new pair")

    shutil.copyfile(args.pdf, args.out)
    doc = fitz.open(args.out)
    pages = page_list(doc, args.pages)
    failed = None

    for old, new in zip(args.old, args.new):
        matches = find_matches(doc, pages, old, {})
        if not matches:
            failed = "No match for %r." % old
            break
        if args.occurrence:
            if args.occurrence > len(matches):
                failed = ("Only %d match(es) for %r; --occurrence %d is out of range."
                          % (len(matches), old, args.occurrence))
                break
            count = 1
        elif len(matches) > 1 and not args.all:
            print("%d matches for %r:\n" % (len(matches), old))
            for i, m in enumerate(matches, 1):
                print("[%d] page %d" % (i, m["page"] + 1))
                print(describe(m))
                print()
            failed = "Ambiguous: pick one with --occurrence N, or pass --all."
            break
        else:
            count = len(matches)

        print("%r -> %r" % (old, new))
        # Each edit rewrites a whole content stream, so offsets taken before it
        # are dead. Re-walk between replacements instead of patching them up.
        reintroduces = bool(phrase_regex(old).search(new))
        try:
            for n in range(count):
                if args.occurrence:
                    todo = matches[args.occurrence - 1]
                else:
                    fresh = find_matches(doc, pages, old, {})
                    skip = n if reintroduces else 0
                    if len(fresh) <= skip:
                        break
                    todo = fresh[skip]
                rep = apply_replacement(doc, todo, new, reflow=args.reflow)
                print("  page %d: %r -> %r  (%+.2f pt)"
                      % (todo["page"] + 1, rep["minimal"][0], rep["minimal"][1],
                         rep["delta"]))
                if rep["shifted"]:
                    print("    shifted %d chunk(s) on the same line"
                          % len(rep["shifted"]))
                for ch, w in rep["width_fixes"]:
                    print("    declared missing advance width for %r (%g/1000)"
                          % (ch, w))
                for msg in rep["messages"]:
                    print("    note: %s" % msg)
        except RuntimeError as exc:
            failed = "Cannot apply %r -> %r: %s" % (old, new, exc)
            break

    if failed:
        doc.close()
        os.remove(args.out)
        sys.exit("\n%s\nNothing written." % failed)

    if args.rewrite:
        doc.save(args.out, incremental=False, garbage=3, deflate=True)
    else:
        doc.save(args.out, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()
    print("\nwrote %s" % args.out)
    print("Verify against the ORIGINAL (not any intermediate):")
    print("  python3 %s verify %s %s --crops <dir>" % (sys.argv[0], args.pdf, args.out))
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("find", help="locate text and report whether it is editable")
    f.add_argument("pdf")
    f.add_argument("text")
    f.add_argument("--pages", help="e.g. 1 or 1-3 or 1,4")
    f.add_argument("--new", help="show the minimal edit and glyph availability")
    f.set_defaults(func=cmd_find)

    d = sub.add_parser("dump", help="print all real text, in content-stream order")
    d.add_argument("pdf")
    d.add_argument("--pages")
    d.set_defaults(func=cmd_dump)

    r = sub.add_parser("replace", help="rewrite the glyphs in place")
    r.add_argument("pdf")
    r.add_argument("out")
    r.add_argument("--old", required=True, action="append", metavar="TEXT",
                   help="text to find; repeat with --new for several edits at once")
    r.add_argument("--new", required=True, action="append", metavar="TEXT",
                   help="replacement, paired with the --old in the same position")
    r.add_argument("--pages")
    r.add_argument("--occurrence", type=int, help="1-based, when several match")
    r.add_argument("--all", action="store_true", help="replace every match")
    r.add_argument("--reflow", choices=["line", "none"], default="line",
                   help="shift the rest of the line when the width changes")
    r.add_argument("--rewrite", action="store_true",
                   help="full save instead of an append-only incremental save")
    r.set_defaults(func=cmd_replace)

    v = sub.add_parser("verify", help="prove only the intended pixels changed")
    v.add_argument("old")
    v.add_argument("new")
    v.add_argument("--dpi", type=int, default=150)
    v.add_argument("--crops", help="directory for before/after crop PNGs")
    v.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
