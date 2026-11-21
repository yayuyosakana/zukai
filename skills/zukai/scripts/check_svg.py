#!/usr/bin/env python3
"""check_svg.py — できあがった SVG を機械的に確かめる。

usage: python3 check_svg.py figures/*.svg

確かめること（✗ = 直す。終了コード 1）:
- XML として読めるか
- viewBox・白背景・日本語フォント指定があるか（GitHub のダークモードや他の環境で読めるか）
- 文字に簡体字が混ざっていないか（日本語の図に「机」「这」などが入る事故を防ぐ）
- 外部画像・スクリプトを読み込んでいないか（GitHub では表示されない）
- 置く幅が書いてある図（svglib の Fig(place_mm=) が書く data-place-mm、または width="85mm"）で、
  最終の大きさの字が md 7pt・スライド 10pt 未満でないか（2026-11-15）
- url(#id) の参照先（矢じりの marker など）があるか（2026-11-15）

警告（⚠ = 見て判断する。終了コードは変えない）:
- 置く幅が書いていない図の 11px 未満の字（2026-11-15）
- 文字の色と、文字の下のいちばん近い塗り（無ければ白）の対比が 4.5 未満（WCAG の式。2026-11-15）
- 同じグラフの系列で、相対輝度の差が 0.025 未満、かつ点の形も線の種類も同じ組（白黒で見分けられない。2026-11-15）
- 字の大きさが 4 種類を超える（2026-11-15）
- IC50・log2・CO2・P=0.03 などの書き方（IC₅₀・log₂・CO₂・P = 0.03 と書く。2026-11-15）
- 色の表（svglib の heatmap、data-chart="heatmap"）に、セルの数値も色の帯（data-colorbar）も無い
- 線（line・polyline・path と、rect の枠線）が文字（text）に重なっていないか。文字の箱はフォントの
  大きさと文字数から見積もる。薄い灰色の線（目盛りの補助線）、文字より前・線より後に塗った不透明な
  rect・circle で隠れている線、白い縁取りのある文字、×・● などの記号だけの文字は数えない。
  文字の箱に、文字の大きさの 15% 以上（約 2px）入り込んだものだけを出す。
"""

from __future__ import annotations

import math
import re
import sys
import xml.dom.minidom
import xml.etree.ElementTree as ET

SIMPLIFIED = set("机这们个实现发计结据观对时动为过说门问间关书车东乐产务头")


# ---------- 線と文字の重なり ----------

# ヒラギノ角ゴの半角文字（U+0020〜U+007E）の幅（1/100 em）。Chrome で測った値（2026-11-04）。
_ASCII_W = {
    False: [33, 32, 37, 68, 67, 90, 82, 20, 37, 37, 36, 66, 25, 37, 25, 49, 67, 67, 67, 67, 68, 67, 67, 67, 67,
            67, 25, 25, 52, 66, 52, 58, 91, 77, 72, 77, 77, 66, 61, 76, 79, 26, 53, 73, 61, 96, 79, 81, 68, 81,
            74, 68, 66, 79, 74, 102, 75, 71, 68, 36, 49, 36, 55, 50, 50, 59, 66, 59, 66, 60, 43, 65, 63, 25, 28,
            60, 24, 95, 63, 64, 66, 66, 45, 55, 41, 63, 56, 89, 56, 57, 51, 37, 39, 37, 56],
    True: [33, 36, 43, 75, 74, 96, 89, 27, 43, 43, 40, 70, 29, 44, 29, 54, 74, 74, 74, 74, 74, 74, 74, 74, 74,
           74, 29, 29, 55, 70, 55, 65, 95, 84, 77, 82, 83, 71, 67, 81, 85, 32, 64, 82, 66, 101, 85, 86, 74, 86,
           80, 74, 74, 86, 82, 108, 86, 80, 73, 43, 54, 43, 62, 50, 50, 66, 74, 65, 74, 66, 51, 71, 70, 29, 33,
           69, 29, 105, 70, 69, 74, 74, 52, 62, 46, 70, 66, 89, 66, 67, 56, 44, 45, 44, 64],
}
# 記号だけの文字は、線の上にわざと置く印として数えない
MARKS = set("×✕✗✖●○◎★☆▲▼△▽◆◇■□▶◀→←↑↓⇒⇔+＋・")
# 字面が右半分だけ・左半分だけにある全角の字
OPEN_HALF = set("（「『【〔［｛〈《")
CLOSE_HALF = set("）」』】〕］｝〉》、。，．")
# 文字の箱の縦: ベースラインから上 0.8em、下 0.12em（日本語の字面に合わせた）
ASC, DESC = 0.8, 0.12
MIN_DEPTH = 0.15  # 文字の大きさに対する割合。これより浅い（かすっただけの）重なりは出さない
LIGHT = 0.82      # これより明るい線（#ddd など目盛りの補助線）は数えない

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_ID = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_SKIP = {"defs", "marker", "clipPath", "mask", "symbol", "pattern", "title", "desc", "metadata", "style",
         "linearGradient", "radialGradient", "filter"}
_INHERIT = ("font-size", "text-anchor", "font-weight", "stroke", "stroke-width", "fill", "stroke-opacity",
            "fill-opacity", "display", "visibility", "paint-order")


def _width(s: str, size: float, bold: bool) -> float:
    w = 0.0
    for c in s:
        o = ord(c)
        if 32 <= o < 127:
            w += _ASCII_W[bold][o - 32] / 100
        elif c in "×≒±":
            w += 0.66
        else:  # 日本語・全角記号・ギリシャ文字・矢印はヒラギノでは 1em
            w += 1.0
    return w * size


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * F + e, b * E + d * F + f)


def _ap(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _inv(m):
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(ia * e + ic * f), -(ib * e + id_ * f))


def _transform(s: str | None):
    m = _ID
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        v = [float(t) for t in re.findall(_NUM, args)]
        if name == "translate" and v:
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale" and v:
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate" and v:
            r = math.radians(v[0])
            t = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0, 0)
            if len(v) == 3:
                t = _mul(_mul((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif name == "matrix" and len(v) == 6:
            t = tuple(v)
        else:
            continue
        m = _mul(m, t)
    return m


def _num(s, default=0.0):
    mm = re.match(_NUM, (s or "").strip())
    return float(mm.group(0)) if mm else default


def _path_segments(d: str):
    """path の d を線分の列にする。直線（M L H V Z）はそのまま、曲線（C S Q T）は 12 本の線分で近似、円弧（A）は飛ばす。"""
    toks = re.findall(r"[MmLlHhVvZzCcSsQqTtAa]|" + _NUM, d)
    segs, i, cmd = [], 0, None
    cx = cy = sx = sy = 0.0
    ctrl = None

    def take(n):
        nonlocal i
        vals = [float(t) for t in toks[i:i + n]]
        if len(vals) < n:
            raise ValueError
        i += n
        return vals

    def curve(pts, deg):
        px, py = pts[0]
        for k in range(1, 13):
            s = k / 12
            u = 1 - s
            w = (u ** 3, 3 * u * u * s, 3 * u * s * s, s ** 3) if deg == 3 else (u * u, 2 * u * s, s * s)
            qx = sum(wi * p[0] for wi, p in zip(w, pts))
            qy = sum(wi * p[1] for wi, p in zip(w, pts))
            segs.append((px, py, qx, qy))
            px, py = qx, qy

    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                if (cx, cy) != (sx, sy):
                    segs.append((cx, cy, sx, sy))
                cx, cy, ctrl = sx, sy, None
                continue
        if cmd is None:
            break
        C, rel = cmd.upper(), cmd.islower()
        ox, oy = (cx, cy) if rel else (0.0, 0.0)
        try:
            if C == "M":
                x, y = take(2)
                cx, cy = sx, sy = x + ox, y + oy
                cmd, ctrl = ("l" if rel else "L"), None
            elif C == "L":
                x, y = take(2)
                segs.append((cx, cy, x + ox, y + oy))
                cx, cy, ctrl = x + ox, y + oy, None
            elif C == "H":
                (x,) = take(1)
                segs.append((cx, cy, x + ox, cy))
                cx, ctrl = x + ox, None
            elif C == "V":
                (y,) = take(1)
                segs.append((cx, cy, cx, y + oy))
                cy, ctrl = y + oy, None
            elif C in "CS":
                if C == "C":
                    x1, y1, x2, y2, x, y = take(6)
                    p1 = (x1 + ox, y1 + oy)
                else:
                    x2, y2, x, y = take(4)
                    p1 = (2 * cx - ctrl[0], 2 * cy - ctrl[1]) if ctrl else (cx, cy)
                p2, p3 = (x2 + ox, y2 + oy), (x + ox, y + oy)
                curve([(cx, cy), p1, p2, p3], 3)
                (cx, cy), ctrl = p3, p2
            elif C in "QT":
                if C == "Q":
                    x1, y1, x, y = take(4)
                    p1 = (x1 + ox, y1 + oy)
                else:
                    x, y = take(2)
                    p1 = (2 * cx - ctrl[0], 2 * cy - ctrl[1]) if ctrl else (cx, cy)
                p2 = (x + ox, y + oy)
                curve([(cx, cy), p1, p2], 2)
                (cx, cy), ctrl = p2, p1
            elif C == "A":
                v = take(7)
                cx, cy, ctrl = v[5] + ox, v[6] + oy, None
            else:
                break
        except (ValueError, TypeError):
            break
    return segs


def _clip(x0, y0, x1, y1, bx0, by0, bx1, by1):
    """線分のうち箱の中に入る部分（Liang–Barsky）。入らなければ None。"""
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - bx0), (dx, bx1 - x0), (-dy, y0 - by0), (dy, by1 - y0)):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    if t1 - t0 <= 1e-9:
        return None
    return (x0 + t0 * dx, y0 + t0 * dy, x0 + t1 * dx, y0 + t1 * dy)


def _lum(color: str | None) -> float | None:
    c = (color or "").strip().lower()
    c = {"white": "#ffffff", "black": "#000000", "gray": "#808080", "grey": "#808080"}.get(c, c)
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        c = "#" + "".join(ch * 2 for ch in c[1:])
    if re.fullmatch(r"#[0-9a-f]{6}", c):
        r, g, b = (int(c[k:k + 2], 16) / 255 for k in (1, 3, 5))
        return 0.299 * r + 0.587 * g + 0.114 * b
    return None


def _attrs(el) -> dict:
    d = dict(el.attrib)
    for kv in (el.get("style") or "").split(";"):
        if ":" in kv:
            k, v = kv.split(":", 1)
            d[k.strip()] = v.strip()
    return d


def _collect(root):
    texts, lines, covers = [], [], []
    n = [0]

    def walk(el, ctm, inh, op):
        tag = el.tag.split("}")[-1]
        if tag in _SKIP:
            return
        a = _attrs(el)
        ctm = _mul(ctm, _transform(a.get("transform")))
        inh = {**inh, **{k: a[k] for k in _INHERIT if k in a}}
        op *= _num(a.get("opacity"), 1.0)
        if inh.get("display") == "none" or inh.get("visibility") == "hidden":
            return
        n[0] += 1
        idx = n[0]
        if tag == "text":
            s = "".join(el.itertext()).strip()
            halo = (inh.get("paint-order", "").startswith("stroke") and (_lum(inh.get("stroke")) or 0) > 0.9
                    and _num(inh.get("stroke-width"), 1) >= 2)
            if s:
                size = _num(inh.get("font-size"), 16.0)
                x = _num(re.split(r"[\s,]+", (a.get("x") or "0").strip())[0]) + _num(a.get("dx"))
                y = _num(re.split(r"[\s,]+", (a.get("y") or "0").strip())[0]) + _num(a.get("dy"))
                w = _width(s, size, inh.get("font-weight") in ("bold", "bolder", "600", "700", "800", "900"))
                anc = inh.get("text-anchor", "start")
                x0 = x - (w / 2 if anc == "middle" else (w if anc == "end" else 0))
                # 全角のかっこ・句読点は字面が片側に寄っている。端にあれば空いた半分を箱から外す
                l = 0.5 * size if s[0] in OPEN_HALF else 0.0
                r = 0.5 * size if s[-1] in CLOSE_HALF else 0.0
                info = dict(fill=inh.get("fill", "#000000"), alpha=op * _num(inh.get("fill-opacity"), 1.0),
                            halo=halo, halo_color=inh.get("stroke") if halo else None,
                            marks=set(s) <= MARKS | {" "}, center=(x0 + w / 2, y - 0.35 * size))
                texts.append((idx, s, size, x, y, (x0 + l, y - ASC * size, x0 + w - r, y + DESC * size), ctm, info))
            return
        segs = []
        if tag == "line":
            segs = [(_num(a.get("x1")), _num(a.get("y1")), _num(a.get("x2")), _num(a.get("y2")))]
        elif tag == "polyline":
            v = [float(t) for t in re.findall(_NUM, a.get("points", ""))]
            pts = list(zip(v[0::2], v[1::2]))
            segs = [(p[0], p[1], q[0], q[1]) for p, q in zip(pts, pts[1:])]
        elif tag == "path":
            segs = _path_segments(a.get("d", ""))
        elif tag == "rect" and "%" not in a.get("width", "") + a.get("height", ""):
            # 箱の枠線も線として数える（角の丸みは無視する）
            x, y, w, h = (_num(a.get(k)) for k in ("x", "y", "width", "height"))
            segs = [(x, y, x + w, y), (x + w, y, x + w, y + h), (x + w, y + h, x, y + h), (x, y + h, x, y)]
        stroke = inh.get("stroke")
        sw = _num(inh.get("stroke-width"), 1.0)
        sop = op * _num(inh.get("stroke-opacity"), 1.0)
        lum = _lum(stroke)
        lum = 0.0 if lum is None else 1 - (1 - lum) * min(1.0, sop)  # 薄くした線は白に近づける
        if segs and stroke not in (None, "none") and sw > 0 and sop > 0.05 and lum <= LIGHT:
            g = [(*_ap(ctm, x0, y0), *_ap(ctm, x1, y1)) for x0, y0, x1, y1 in segs]
            scale = math.sqrt(abs(ctm[0] * ctm[3] - ctm[1] * ctm[2])) or 1.0
            lines.append((idx, tag, stroke, sw * scale, g))
        # 塗った形（rect・circle・ellipse。回転していないものだけ）。不透明なもの（0.9 以上）は後ろの線を隠す。
        # 文字の対比の検査では、文字の下の背景としても使う（0.3 より薄いものは数えない）
        fill = inh.get("fill")
        alpha = op * _num(inh.get("fill-opacity"), 1.0)
        if (tag in ("rect", "circle", "ellipse") and fill not in (None, "none")
                and alpha > 0.3 and abs(ctm[1]) < 1e-9 and abs(ctm[2]) < 1e-9):
            if tag == "rect" and "%" not in a.get("width", "") + a.get("height", ""):
                p = _ap(ctm, _num(a.get("x")), _num(a.get("y")))
                q = _ap(ctm, _num(a.get("x")) + _num(a.get("width")), _num(a.get("y")) + _num(a.get("height")))
                covers.append((idx, "rect", (min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1])),
                               fill, alpha))
            elif tag in ("circle", "ellipse"):
                c = _ap(ctm, _num(a.get("cx")), _num(a.get("cy")))
                rx = _num(a.get("r") if tag == "circle" else a.get("rx")) * abs(ctm[0])
                ry = _num(a.get("r") if tag == "circle" else a.get("ry")) * abs(ctm[3])
                covers.append((idx, "ellipse", (c[0], c[1], rx, ry), fill, alpha))
        for ch in el:
            walk(ch, ctm, inh, op)

    walk(root, _ID, {}, 1.0)
    return texts, lines, covers


def _covered(kind, g, x, y) -> bool:
    if kind == "rect":
        return g[0] - 0.5 <= x <= g[2] + 0.5 and g[1] - 0.5 <= y <= g[3] + 0.5
    cx, cy, rx, ry = g
    return rx > 0 and ry > 0 and ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0


def line_text_overlaps(svg: str, min_depth: float = MIN_DEPTH) -> list[dict]:
    """線（line・polyline・path・rect の枠線）が文字の箱に入り込んでいるところを返す。
    depth は、交わった部分が箱の縁からいちばん内側に入った距離（px、線の太さの半分を含む）。"""
    if re.search(r"<!(DOCTYPE|ENTITY)", svg):  # 実体の展開をさせない（check() と同じ理由）
        return []
    texts, lines, covers = _collect(ET.fromstring(svg))
    covers = [(cidx, kind, g) for cidx, kind, g, _fill, alpha in covers if alpha >= 0.9]
    found = []
    for tidx, s, size, tx, ty, (bx0, by0, bx1, by1), tctm, info in texts:
        if info["halo"] or info["marks"]:  # 白い縁取りの文字と、記号だけの文字は数えない
            continue
        im = _inv(tctm)
        if im is None:
            continue
        for lidx, tag, stroke, sw, segs in lines:
            pad = sw / 2
            box = (bx0 - pad, by0 - pad, bx1 + pad, by1 + pad)
            best = 0.0
            for sx0, sy0, sx1, sy1 in segs:
                p, q = _ap(im, sx0, sy0), _ap(im, sx1, sy1)
                c = _clip(p[0], p[1], q[0], q[1], *box)
                if not c:
                    continue
                pts = [(c[0] + (c[2] - c[0]) * k / 10, c[1] + (c[3] - c[1]) * k / 10) for k in range(11)]
                depth = max(min(x - box[0], box[2] - x, y - box[1], box[3] - y) for x, y in pts)
                gp = [_ap(tctm, x, y) for x, y in pts[::5]]
                hidden = any(lidx < cidx < tidx and all(_covered(kind, g, *pt) for pt in gp)
                             for cidx, kind, g in covers)
                if not hidden:
                    best = max(best, depth)
            if best >= max(min_depth * size, 1.0):
                found.append(dict(text=s, x=tx, y=ty, size=size, tag=tag, stroke=stroke, depth=best))
    return found


def overlap_messages(svg: str, limit: int = 12) -> list[str]:
    found = line_text_overlaps(svg)
    msgs = [f"線が文字に重なっている: 「{f['text'][:18]}」(x={f['x']:.0f}, y={f['y']:.0f}) に {f['tag']}"
            f"（{f['stroke']}）が {f['depth']:.0f}px 入り込む" for f in found[:limit]]
    if len(found) > limit:
        msgs.append(f"……ほか {len(found) - limit} か所")
    return msgs


# ---------- 科学図の検査（2026-11-15 に足した） ----------

MIN_PT = {"md": 7.0, "slide": 10.0}
MIN_PX_NO_PLACE = 11.0
CONTRAST_MIN = 4.5
GRAY_MIN = 0.025
SIZE_KINDS_MAX = 4
# SVG のラベルによく使う表記。
NOTATION = [
    (re.compile(r"(?<![A-Za-z0-9])(IC|EC|ED|LD)50(?![0-9])"), "IC₅₀ のように下付きで書く"),
    (re.compile(r"(?<![A-Za-z])log(2|10)(?![0-9])"), "log₂・log₁₀ のように下付きで書く"),
    (re.compile(r"(?<![A-Za-z0-9])CO2(?![0-9])"), "CO₂ と書く"),
    (re.compile(r"(?<![A-Za-z0-9_])[Pp](?:\s*=(?!\s)|=\s)"), "P = 0.03 のように = の前後に空白を入れる"),
]
_NAMED = {"white": "#ffffff", "black": "#000000", "gray": "#808080", "grey": "#808080", "red": "#ff0000",
          "blue": "#0000ff", "green": "#008000", "orange": "#ffa500", "yellow": "#ffff00", "none": None}


def _hex(color: str | None) -> str | None:
    c = (color or "").strip().lower()
    if c in _NAMED:
        return _NAMED[c]
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        return "#" + "".join(ch * 2 for ch in c[1:])
    if re.fullmatch(r"#[0-9a-f]{6}", c):
        return c
    m = re.fullmatch(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", c)
    if m:
        return "#" + "".join(f"{min(255, int(v)):02x}" for v in m.groups())
    return None


def rel_lum(color: str) -> float:
    """WCAG の sRGB 相対輝度。color は #RRGGBB。"""
    luminance = 0.0
    for index, weight in enumerate((0.2126, 0.7152, 0.0722)):
        start = 1 + 2 * index
        channel = int(color[start:start + 2], 16) / 255
        linear = (
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
        )
        luminance += weight * linear
    return luminance


def contrast(a: str, b: str) -> float:
    x, y = sorted((rel_lum(a), rel_lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def _blend(fg: str, bg: str, alpha: float) -> str:
    alpha = max(0.0, min(1.0, alpha))
    return "#" + "".join(f"{round(int(fg[k:k + 2], 16) * alpha + int(bg[k:k + 2], 16) * (1 - alpha)):02x}"
                         for k in (1, 3, 5))


def _root_info(root) -> tuple[float | None, float | None, str]:
    """（キャンバスの幅 px、置く幅 mm、target）。置く幅は data-place-mm か、width="85mm" から読む。"""
    vb = [float(t) for t in re.findall(_NUM, root.get("viewBox", ""))]
    W = vb[2] if len(vb) == 4 else None
    place = root.get("data-place-mm")
    width = root.get("width", "")
    place_mm = _num(place) if place else (_num(width) if width.strip().endswith("mm") else None)
    if W is None and width and not width.strip().endswith(("mm", "%")):
        W = _num(width)
    target = root.get("data-target", "md")
    return W, place_mm, target if target in MIN_PT else "md"


def _scale(ctm) -> float:
    return math.sqrt(abs(ctm[0] * ctm[3] - ctm[1] * ctm[2])) or 1.0


def _short(s: str, n: int = 16) -> str:
    return s if len(s) <= n else s[:n] + "…"


def size_findings(root, texts) -> tuple[list[str], list[str]]:
    """最終の大きさの最小の字。置く幅のある図は ✗、無い図は 11px 未満を ⚠。"""
    W, place_mm, target = _root_info(root)
    probs, warns = [], []
    seen = set()
    for _idx, s, size, *_rest in texts:
        info = _rest[-1]
        if info["marks"]:
            continue
        px = size * _scale(_rest[-2])
        if place_mm and W:
            pt = px * place_mm / W / 25.4 * 72
            if pt < MIN_PT[target] - 0.01 and (px, s) not in seen:
                seen.add((px, s))
                probs.append(f"最終の大きさで字が小さい: 「{_short(s)}」 {px:g}px → {pt:.1f}pt"
                             f"（置く幅 {place_mm:g}mm・{target} は {MIN_PT[target]:g}pt 以上）")
        elif px < MIN_PX_NO_PLACE - 0.01 and (px, s) not in seen:
            seen.add((px, s))
            warns.append(f"小さい字: 「{_short(s)}」 {px:g}px（置く幅が書いていない図は {MIN_PX_NO_PLACE:g}px 以上）")
    return probs, warns


def contrast_findings(texts, covers) -> list[dict]:
    """文字の色と、文字の下のいちばん近い塗り（無ければ白）の対比。"""
    out = []
    for tidx, s, size, _x, _y, _box, ctm, info in texts:
        if info["marks"]:
            continue
        fg = _hex(info["fill"])
        if fg is None:
            continue
        cx, cy = _ap(ctm, *info["center"])
        bg = "#ffffff"
        if info["halo"]:
            bg = _hex(info["halo_color"]) or bg
        else:
            for cidx, kind, g, fill, alpha in covers:
                if cidx < tidx and _covered(kind, g, cx, cy):
                    h = _hex(fill)
                    if h:
                        bg = _blend(h, "#ffffff", alpha)  # 下は白とみなす（重ね塗りは追わない）
        fg = _blend(fg, bg, info["alpha"])
        c = contrast(fg, bg)
        if c < CONTRAST_MIN - 1e-6:
            out.append(dict(text=s, fg=fg, bg=bg, ratio=c))
    return out


def _stroke_of(el) -> tuple[str | None, str]:
    a = _attrs(el)
    return _hex(a.get("stroke")), (a.get("stroke-dasharray") or "").strip()


def series_findings(root) -> list[dict]:
    """白黒で見分けられない系列。相対輝度の差が GRAY_MIN 未満で、点の形も線の種類も同じ組。
    svglib の図は <g data-chart> の中の <g data-series data-marker> を系列とみなす。
    それ以外の図は、同じ親の中の折れ線（3 点以上・太さ 2 以上・矢じり無し）を、線の色と線の種類で系列に分ける。"""
    out = []

    def compare(series, where):
        for i in range(len(series)):
            for j in range(i + 1, len(series)):
                (ca, da, ma, na), (cb, db, mb, nb) = series[i], series[j]
                if ca == cb and da == db and ma == mb:
                    continue  # 同じ系列を分けて描いただけ
                d = abs(rel_lum(ca) - rel_lum(cb))
                if d < GRAY_MIN and da == db and ma == mb:
                    out.append(dict(a=(ca, na), b=(cb, nb), diff=d, where=where))

    in_series = set()
    for chart in root.iter():
        if "data-chart" not in chart.attrib:
            continue
        ser = []
        for g in chart:
            if "data-series" not in g.attrib:
                continue
            for el in g.iter():
                in_series.add(el)
            main = [el for el in g if el.tag.split("}")[-1] == "polyline" and _attrs(el).get("stroke-opacity") is None]
            if not main:
                continue
            col, dash = _stroke_of(main[-1])
            if col:
                ser.append((col, dash, g.get("data-marker", "none"), g.get("data-series")))
        compare(ser, chart.get("data-chart"))
    for parent in root.iter():
        ser = {}
        for el in parent:
            if el.tag.split("}")[-1] != "polyline" or el in in_series:
                continue
            a = _attrs(el)
            if a.get("marker-end") or a.get("marker-start") or _num(a.get("stroke-width"), 1.0) < 2:
                continue
            if len(re.findall(_NUM, a.get("points", ""))) < 6:
                continue
            col, dash = _stroke_of(el)
            if not col or (_lum(col) or 0) > LIGHT:
                continue
            ser.setdefault((col, dash), (col, dash, "none", None))
        if len(ser) >= 2:
            compare(list(ser.values()), "折れ線")
    return out


def size_kind_findings(texts) -> list[str]:
    sizes = sorted({round(size * _scale(rest[-2]) * 2) / 2 for _i, _s, size, *rest in texts if not rest[-1]["marks"]},
                   reverse=True)
    if len(sizes) > SIZE_KINDS_MAX:
        return [f"字の大きさが {len(sizes)} 種類（{'・'.join(f'{v:g}' for v in sizes)}px）。"
                f"{SIZE_KINDS_MAX} 種類までにそろえる"]
    return []


def marker_ref_findings(svg: str) -> list[str]:
    ids = set(re.findall(r'\bid="([^"]+)"', svg))
    refs = set(re.findall(r"url\(#([^)\s]+)\)", svg))
    missing = sorted(refs - ids)
    return [f"壊れた参照: url(#{m}) の id が無い（矢じりなどが描かれない）" for m in missing[:8]]


def notation_findings(texts) -> list[str]:
    out = []
    for _i, s, *_rest in texts:
        for pat, how in NOTATION:
            m = pat.search(s)
            if m:
                out.append(f"書き方: 「{_short(s, 24)}」の「{m.group(0).strip()}」→ {how}")
    return list(dict.fromkeys(out))


def heatmap_findings(root) -> list[str]:
    """色の表に、セルの数値も色の帯も無いもの（色の濃さから値を読み取れない）。"""
    has_bar = any("data-colorbar" in el.attrib for el in root.iter())
    out = []
    for g in root.iter():
        if g.get("data-chart") != "heatmap":
            continue
        has_text = any(el.tag.split("}")[-1] == "text" and "".join(el.itertext()).strip() for el in g.iter())
        if not has_text and not has_bar:
            out.append("色の表に数値も色の帯も無い（色の濃さだけでは値が読めない）。"
                       "heatmap(show_values=True) か cbar=True にする")
    return out


def analyze(svg: str, limit: int = 8) -> tuple[list[str], list[str]]:
    """科学図の検査と線の重なりをまとめてかける。（直すべき問題, 警告）を返す。
    呼ぶ前に DOCTYPE / ENTITY が無いことを確かめておく（check() と svglib の save() は確かめてから呼ぶ）。"""
    if re.search(r"<!(DOCTYPE|ENTITY)", svg):
        return ["DOCTYPE / ENTITY を含む（解析しない）"], []
    root = ET.fromstring(svg)
    texts, _lines, covers = _collect(root)
    probs, warns = size_findings(root, texts)
    probs += marker_ref_findings(svg)
    warns = warns[:limit] + ([f"……小さい字はほか {len(warns) - limit} か所"] if len(warns) > limit else [])
    probs = probs[:limit + 8]
    try:
        warns += overlap_messages(svg)
    except Exception as e:  # noqa: BLE001
        warns.append(f"線と文字の重なりを調べられなかった: {e}")
    cf = contrast_findings(texts, covers)
    for f in cf[:limit]:
        warns.append(f"文字の色の対比が低い: 「{_short(f['text'])}」 {f['fg']} / 背景 {f['bg']} = {f['ratio']:.2f}"
                     f"（{CONTRAST_MIN:g} 以上に。文字は INK にして色は小さな印で添える）")
    if len(cf) > limit:
        warns.append(f"……対比の低い文字はほか {len(cf) - limit} か所")
    for f in series_findings(root):
        na = f"「{f['a'][1]}」" if f["a"][1] else ""
        nb = f"「{f['b'][1]}」" if f["b"][1] else ""
        warns.append(f"白黒で見分けにくい系列: {f['a'][0]}{na} と {f['b'][0]}{nb}（輝度の差 {f['diff']:.3f} < {GRAY_MIN}、"
                     "点の形と線の種類も同じ）。どちらかの点の形か線の種類を変える")
    warns += size_kind_findings(texts)
    warns += notation_findings(texts)
    warns += heatmap_findings(root)
    return probs, warns


def figure_warnings(svg: str) -> list[str]:
    """svglib の save() 用。問題も警告もまとめて警告として返す。"""
    p, w = analyze(svg)
    return p + w


# ---------- 全体 ----------

def check(path: str) -> tuple[list[str], list[str]]:
    """（直すべき問題, 警告）を返す。"""
    probs = []
    s = open(path, encoding="utf-8").read()
    if re.search(r"<!(DOCTYPE|ENTITY)", s):
        return ["DOCTYPE / ENTITY を含む（図には不要。外部実体の読み込みを避けるため解析しない）"], []
    try:
        xml.dom.minidom.parseString(s.encode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return [f"XML として読めない: {e}"], []
    head = s[: s.find(">") + 1]
    if "viewBox" not in head:
        probs.append("viewBox が無い（拡大縮小できない）")
    if not re.search(r'<rect[^>]*width="100%"[^>]*fill="#fff', s):
        probs.append("白背景の rect が無い（ダークモードで文字が見えなくなる）")
    if "font-family" not in s:
        probs.append("font-family が無い（日本語が豆腐になることがある）")
    texts = "".join(re.findall(r"<text[^>]*>(.*?)</text>", s, flags=re.S))
    bad = sorted({c for c in texts if c in SIMPLIFIED})
    if bad:
        probs.append(f"簡体字の疑い: {' '.join(bad)}（日本語の字に直す）")
    if re.search(r"<(image|script|foreignObject)\b", s):
        probs.append("image / script / foreignObject を使っている（GitHub では表示されない）")
    if re.search(r'href="https?://', s):
        probs.append("外部 URL を読み込んでいる")
    try:
        p2, warns = analyze(s)
        probs += p2
    except Exception as e:  # noqa: BLE001  検査の失敗で図を止めない
        warns = [f"検査の途中で失敗した: {e}"]
    return probs, warns


# 警告の文の頭 → 検査の名前（main の内訳に使う）
KIND_OF = [("線が文字に重なっている", "線と文字の重なり"), ("……ほか", "線と文字の重なり"),
           ("最終の大きさで字が小さい", "最終の字（✗）"), ("小さい字", "小さい字"), ("……小さい字", "小さい字"),
           ("文字の色の対比", "文字の対比"), ("……対比", "文字の対比"), ("白黒で見分けにくい系列", "白黒の系列"),
           ("字の大きさが", "字の大きさの種類"), ("壊れた参照", "壊れた参照（✗）"), ("書き方", "書き方"), ("色の表に", "色の表")]


def kind_of(msg: str) -> str:
    return next((k for head, k in KIND_OF if msg.startswith(head)), "その他")


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return 2
    n_bad = n_warn = 0
    per_kind: dict[str, int] = {}
    for p in paths:
        probs, warns = check(p)
        n_bad += bool(probs)
        n_warn += bool(warns)
        print(f"{'✗' if probs else '✓'} {p}")
        for q in probs:
            print(f"    - {q}")
        for w in warns:
            print(f"    ⚠ {w}")
        for k in dict.fromkeys(kind_of(m) for m in probs + warns):
            per_kind[k] = per_kind.get(k, 0) + 1
    if per_kind:
        print("\n内訳（枚数）: " + "・".join(f"{k} {v}" for k, v in per_kind.items()))
    if n_warn:
        print(f"⚠ {n_warn} 枚に警告。線と文字の重なりは PNG（scripts/svg2png.sh）で該当の所だけ見て、"
              "文字か線をずらす（わざと重ねたならそのまま）。対比・白黒の系列・書き方は直す。")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
