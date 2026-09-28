#!/bin/bash
# Self-contained regression suite. Builds its own fixtures, runs in a temp dir.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S="$HERE/pdftext.py"
WORK="${1:-$(mktemp -d)}"
python3 "$HERE/make_fixtures.py" "$WORK" >/dev/null || exit 2
cd "$WORK" || exit 2
pass=0; fail=0
check () { # name  expected-substring  file  
  if python3 -c "
import fitz,sys
t=''.join(p.get_text() for p in fitz.open('$3'))
sys.exit(0 if '''$2''' in t else 1)" 2>/dev/null; then
    echo "  PASS  $1"; pass=$((pass+1))
  else
    echo "  FAIL  $1"; fail=$((fail+1))
  fi
}
rm -f out_*.pdf

REAL="${REAL_PDF:-}"
if [ -n "$REAL" ] && [ -f "$REAL" ]; then
python3 $S replace "$REAL" out_real.pdf --old "Loading In" --new "Loading out" >/dev/null 2>&1
check "real doc, kerned TJ, simple font" "Izin Loading out;" out_real.pdf

python3 $S replace "$REAL" out_multi.pdf --old "Izin Loading In" --new "Persetujuan Bongkar Muat" >/dev/null 2>&1
check "real doc, multi-chunk + zero-width glyph" "2. Persetujuan Bongkar Muat; " out_multi.pdf
else
  echo "  SKIP  real-document cases (set REAL_PDF=<path> to run them)"
fi

python3 $S replace colored.pdf out_col.pdf --old "Loading In" --new "Loading out" --all >/dev/null 2>&1
check "colored bg, hex string, --all (1/2)" "Status: Loading out" out_col.pdf
check "colored bg, hex string, --all (2/2)" "Copy 2: Loading out" out_col.pdf

python3 $S replace cid.pdf out_cid.pdf --old "1200 USD" --new "1500 USD" >/dev/null 2>&1
check "Type0 / Identity-H, 2-byte codes" "Invoice total: 1500 USD" out_cid.pdf

python3 $S replace raw.pdf out_tj.pdf --old "Loading In" --new "Loading out" >/dev/null 2>&1
check "hand-built PDF, Tj operator" "Order status: Loading out" out_tj.pdf

python3 $S replace raw.pdf out_q.pdf --old "Third via quote" --new "Third via apostrophe" >/dev/null 2>&1
check "hand-built PDF, ' operator preserved" "Third via apostrophe" out_q.pdf

python3 $S replace cid.pdf out_grow.pdf --old "1200 USD" --new "1200 USD (net 30 days)" >/dev/null 2>&1
check "growing replacement, CID" "1200 USD (net 30 days)" out_grow.pdf

python3 $S replace raw.pdf out_shrink.pdf --old "Order status: Loading In" --new "Done" >/dev/null 2>&1
check "shrinking replacement" "Done" out_shrink.pdf

python3 $S replace shared.pdf out_shared.pdf --old "Loading In" --new "Loading out" --all >/dev/null 2>&1
check "3 matches in ONE content stream, --all (A)" "Bay A: Loading out now" out_shared.pdf
check "3 matches in ONE content stream, --all (B)" "Bay B: Loading out now" out_shared.pdf
check "3 matches in ONE content stream, --all (C)" "Bay C: Loading out now" out_shared.pdf

timeout 60 python3 $S replace shared.pdf out_grow2.pdf --old "Loading In" --new "Loading Inbound" --all >/dev/null 2>&1
check "replacement re-contains the search text (no loop)" "Bay C: Loading Inbound now" out_grow2.pdf

python3 $S replace shipment.pdf out_two.pdf \
    --old "Loading In" --new "Loading out" \
    --old "Surabaya"   --new "Tanjung Priok" >/dev/null 2>&1
check "two edits in ONE invocation (a)" "Status: Loading out" out_two.pdf
check "two edits in ONE invocation (b)" "Destination port: Tanjung Priok" out_two.pdf

python3 $S replace raw.pdf out_ins.pdf --old "Loading In" --new "Loading Inbound" >/dev/null 2>&1
check "pure insertion lands in place" "Order status: Loading Inbound" out_ins.pdf

# negative cases
if python3 $S replace colored.pdf out_amb.pdf --old "Loading In" --new "x" >/dev/null 2>&1; then
  echo "  FAIL  ambiguous match should refuse"; fail=$((fail+1))
else
  echo "  PASS  ambiguous match refuses"; pass=$((pass+1))
fi
if [ -f out_amb.pdf ]; then echo "  FAIL  refusal left a file"; fail=$((fail+1));
else echo "  PASS  refusal wrote no file"; pass=$((pass+1)); fi

if python3 $S replace cid.pdf out_cjk.pdf --old "USD" --new "日本円" >/dev/null 2>&1; then
  echo "  FAIL  missing glyph should refuse"; fail=$((fail+1))
else
  echo "  PASS  missing glyph refuses"; pass=$((pass+1)); fi

if python3 $S replace raw.pdf out_bad.pdf --old "a" --new "b" --old "c" >/dev/null 2>&1; then
  echo "  FAIL  unpaired --old/--new should refuse"; fail=$((fail+1))
else
  echo "  PASS  unpaired --old/--new refuses"; pass=$((pass+1)); fi

if python3 $S replace shipment.pdf out_part.pdf --old "Surabaya" --new "Medan" --old "NOPE" --new "x" >/dev/null 2>&1; then
  echo "  FAIL  a failing later edit should abort the whole run"; fail=$((fail+1))
else
  if [ -f out_part.pdf ]; then echo "  FAIL  aborted run left a partial file"; fail=$((fail+1));
  else echo "  PASS  failing edit aborts run, writes nothing"; pass=$((pass+1)); fi
fi

if python3 $S find raw.pdf "nonexistent phrase" >/dev/null 2>&1; then
  echo "  FAIL  no-match should exit nonzero"; fail=$((fail+1))
else
  echo "  PASS  no-match exits nonzero"; pass=$((pass+1)); fi

echo
echo "  $pass passed, $fail failed"
exit $fail
