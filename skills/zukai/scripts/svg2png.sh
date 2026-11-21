#!/bin/bash
# svg2png.sh — SVG を viewBox のサイズそのまま（2 倍解像度）で PNG にする。目視確認用。
# usage: svg2png.sh file.svg [out.png]
#   out.png を省くと /tmp/zukai_preview/<名前>.png に出す。
# macOS の qlmanage は横長の SVG の右側を切り落とすので使わない。Chrome headless を使う。
set -euo pipefail
svg="$1"
out="${2:-}"
if [ -z "$out" ]; then
  mkdir -p /tmp/zukai_preview
  out="/tmp/zukai_preview/$(basename "${svg%.svg}").png"
fi

read W H < <(python3 - "$svg" <<'EOF'
import re, sys
s = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)\s*"', s)
if not m:
    m = re.search(r'width="([\d.]+)"[^>]*height="([\d.]+)"', s)
print(int(float(m[1])), int(float(m[2])))
EOF
)

chrome=""
for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "/Applications/Chromium.app/Contents/MacOS/Chromium" \
         "$(command -v google-chrome 2>/dev/null || true)" \
         "$(command -v chromium 2>/dev/null || true)" \
         "$(command -v chromium-browser 2>/dev/null || true)"; do
  if [ -n "$c" ] && [ -x "$c" ]; then chrome="$c"; break; fi
done

abs="$(cd "$(dirname "$svg")" && pwd)/$(basename "$svg")"
if [ -n "$chrome" ]; then
  "$chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
    --window-size="${W},${H}" --screenshot="$out" "file://$abs" >/dev/null 2>&1
elif command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert -z 2 -o "$out" "$svg"
else
  echo "Chrome も rsvg-convert も見つからない。PNG にできないので、SVG を直接 Read で確認する。" >&2
  exit 1
fi
echo "$out ${W}x${H}"
