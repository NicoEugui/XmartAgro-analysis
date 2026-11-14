#!/bin/sh
# Experiment log as PDF: Markdown -> standalone HTML (pandoc) -> PDF (headless Chrome). Usage: scripts/build_pdf.sh [reports/experiments.md]
set -e
SRC="${1:-reports/experiments.md}"; OUT="${SRC%.md}.pdf"; HERE="$(cd "$(dirname "$0")" && pwd)"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
(cd "$(dirname "$SRC")" && pandoc "$(basename "$SRC")" -f gfm -s --embed-resources --metadata pagetitle="XmartAgro experiment log" \
  -c "$HERE/report.css" -o "$TMP/log.html")
sed -i.bak 's/<details>/<details open>/g' "$TMP/log.html"
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")" "file://$TMP/log.html" 2>/dev/null
echo "written: $OUT"
