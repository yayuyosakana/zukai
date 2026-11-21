"""svglib — 標準ライブラリだけで、読みやすい SVG の図（ブロック図・グラフ）を作る小さなヘルパー。

使い方（このフォルダを PYTHONPATH に入れて実行）:
    from svglib import Fig

    f = Fig(900, 420, title="学習の流れ", place_mm=220)   # place_mm = 置く幅（mm）。字の pt を確かめる
    f.box(40, 80, 160, 60, "data", "入力\\n512×512")
    f.box(260, 80, 180, 60, "enc", "エンコーダ")
    f.arrow(200, 110, 256, 110)
    f.caption("点線は skip connection")
    f.save("figures/01_flow.svg", desc="入力からエンコーダまでの流れ")   # 警告を表示する

方針:
- 座標はすべて手で決める（自動レイアウトはしない）。そのかわり save() が
  「箱からはみ出した文字」「キャンバスの外に出た要素」「線（矢印・折れ線・箱の枠）が重なった文字」
  「最終の大きさで小さすぎる字」「背景との対比が低い文字」「白黒で見分けられない系列」などを
  警告するので、直してから描き直す。検査は check_svg.py と同じものを使う。
- 色は役割ごとに決まっている（KINDS / SERIES）。既定は Okabe-Ito の配色（2026-11-15）。
  前の配色は、スクリプトの先頭で 1 回 set_palette("legacy") を呼ぶと、そのあとの図すべてに効く
  1 枚だけなら Fig(..., palette="legacy")。
- 統計は計算しない。平均・区間・誤差は呼ぶ側（プロジェクトの解析）が渡す。
  dot_strip だけは、平均を渡さなければ点の算術平均を使う（区間は必ず渡す）。
"""

from __future__ import annotations

import math
import random
from pathlib import Path

FONT = "'Hiragino Sans','Noto Sans CJK JP','Noto Sans JP','Yu Gothic',sans-serif"
INK = "#222222"
MUTED = "#555555"
GRID = "#dddddd"

# Okabe & Ito (2008) の 8 色。色覚の違いがあっても見分けやすい。
OKABE_ITO = {
    "black": "#000000",
    "orange": "#E69F00",
    "sky_blue": "#56B4E9",
    "bluish_green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "reddish_purple": "#CC79A7",
}

# 配色。kinds は箱の役割 → (塗り, 線)、series はグラフの系列の順（主役のいないグラフで使う）、
# emph は主役の色、dim は主役でない棒の塗り、compare は主役でない線・点の色（None なら前の動き）。
# 主役は青、比較対象は灰、基準線は灰の破線。
PALETTES = {
    # 枠線より淡い塗りの上に濃い文字を置く。
    # 箱の中の文字は INK。線・点の色は Okabe-Ito。
    "okabe_ito": {
        "kinds": {
            "data": ("#E8E8E8", "#555555"),   # 入力・出力・データ・ファイル（灰）
            "enc": ("#E8F2F8", "#0072B2"),    # 前段・エンコーダ・自分たちの手法（青）
            "dec": ("#FBF1E8", "#D55E00"),    # 後段・デコーダ・比較相手（朱）
            "head": ("#E8F6F2", "#009E73"),   # 出口・損失・評価・結論（青緑）
            "hi": ("#F8F2A0", "#000000"),     # いちばん見てほしい所だけ（黄の塗り＋黒の線）。正解は黄でなく太い枠で
            "bad": ("#FAF3F7", "#CC79A7"),    # 失敗・注意・バグ（赤紫）
            "plain": ("#ffffff", "#888888"),  # 補足・未確定（点線と組み合わせるとよい）
        },
        # 主役のいないグラフ（条件を並べるだけ）の系列の順。白地との対比が 3 以上の 4 色を先に。
        # 橙と空色は輝度がほぼ同じなので、点の形・線の種類を必ず重ねる。
        "series": ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000"],
        "emph": "#0072B2",
        "dim": "#BBBBBB",     # 主役でない棒の塗り（対比 1.92。塗りなので数字は棒の上に INK で書く）
        "compare": "#888888",  # 主役でない線・点（対比 3.54。線に使える 3 以上）
    },
    # 過去の図を同じ配色で描き直すための設定。
    "legacy": {
        "kinds": {
            "data": ("#eeeeee", "#555555"),
            "enc": ("#dbe8fb", "#2b4c7e"),
            "dec": ("#fde9d2", "#d48a1f"),
            "head": ("#dcefd8", "#4a8a3c"),
            "hi": ("#fff3c4", "#b8901a"),
            "bad": ("#fbe3e0", "#c0392b"),
            "plain": ("#ffffff", "#888888"),
        },
        "series": ["#2b4c7e", "#d48a1f", "#4a8a3c", "#c0392b", "#7d5ba6", "#888888"],
        "emph": "#b8901a",
        "dim": None,
        "compare": None,
    },
}
_ALIAS = {"okabe": "okabe_ito", "okabe-ito": "okabe_ito", "oi": "okabe_ito", "old": "legacy"}
_DEFAULT = ["okabe_ito"]  # set_palette() で変える


def _palette_name(name: str | None) -> str:
    key = (name or _DEFAULT[0]).strip().lower()
    key = _ALIAS.get(key, key)
    if key not in PALETTES:
        raise ValueError(f"palette は {sorted(PALETTES)} のどれか（受け取った値: {name!r}）")
    return key


# 役割の色（いまの既定の配色）。set_palette() で中身が入れ替わる（import 済みの名前にも効く）。
KINDS = dict(PALETTES["okabe_ito"]["kinds"])
SERIES = list(PALETTES["okabe_ito"]["series"])


def set_palette(name: str) -> str:
    """このあと作る Fig すべての既定の配色を決める（"okabe_ito" か "legacy"）。スクリプトの先頭で 1 回呼ぶ。
    使用例:
        from svglib import Fig, set_palette; set_palette("legacy")
    1 枚だけ変えたいときは Fig(..., palette="legacy")。"""
    key = _palette_name(name)
    _DEFAULT[0] = key
    KINDS.clear()
    KINDS.update(PALETTES[key]["kinds"])
    SERIES[:] = PALETTES[key]["series"]
    return key

# 系列ごとの点の形と線の種類（marker_cycle）。1 番目は実線。
SHAPES = ["circle", "square", "triangle", "triangle_down", "diamond"]
DASHES = ["", "7 4", "2 3", "9 3 2 3", "4 2"]
# 誤差棒の種類（bar_chart の err_kind・dot_strip の err_kind）
ERR_KINDS = {"sd": "SD", "sem": "SEM", "ci95": "95% 信頼区間"}
# 配置後の文字サイズの目安（pt）。
MIN_PT = {"md": 7.0, "slide": 10.0}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _attr(s: str) -> str:
    return esc(str(s)).replace('"', "&quot;")


# ---------- 色の計算（WCAG 2.x の式） ----------

def _rgb(color: str) -> tuple[float, float, float]:
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[k:k + 2], 16) / 255 for k in (0, 2, 4))  # type: ignore[return-value]


def rel_lum(color: str) -> float:
    """相対輝度（WCAG）。白 = 1、黒 = 0。"""
    def lin(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str = "#ffffff") -> float:
    """2 色の対比（WCAG）。文字は 4.5 以上、線・塗りは 3 以上が目安。"""
    x, y = sorted((rel_lum(a), rel_lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def tint(color: str, amount: float = 0.91) -> str:
    """基準の色を白へ amount だけ混ぜた淡い色（新しい色相を足さずに塗りを作る）。"""
    return "#" + "".join(f"{round(v * 255 * (1 - amount) + 255 * amount):02X}" for v in _rgb(color))


def ink_for(fill: str) -> str:
    """塗りの上に書く文字の色。白と INK のうち、対比の高いほう（棒の中の数字など）。"""
    return "#ffffff" if contrast("#ffffff", fill) >= contrast(INK, fill) else INK


def text_color(color: str, bg: str = "#ffffff") -> str:
    """系列の色で文字を書きたいとき、対比が 4.5 未満なら INK を返す（色は小さな印で添える）。"""
    return color if contrast(color, bg) >= 4.5 else INK


def text_width(s: str, size: float, bold: bool = False) -> float:
    """文字幅のおおまかな見積もり（px）。全角 ≈ 1.0em、半角 ≈ 0.6em。"""
    w = 0.0
    for c in s:
        o = ord(c)
        if o >= 0x2E80 or c in "　（）「」、。・：":
            w += 1.0
        elif c in "il.,:;|'!":
            w += 0.32
        elif c in "mwMW@":
            w += 0.85
        elif c == " ":
            w += 0.3
        else:
            w += 0.6
    return w * size * (1.05 if bold else 1.0)


def nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=raw)
    start = math.ceil(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 1e-9:
        ticks.append(round(t, 10))
        t += step
    return ticks


def nice_lim(values, step: float | None = None, clamp: tuple[float, float] | None = None) -> tuple[float, float]:
    """値の範囲を step の倍数へ外向きに丸める。clamp で上下限を制限できる。"""
    vals = [v for v in values if v is not None]
    if not vals:
        raise ValueError("nice_lim に値が無い")
    lo, hi = min(vals), max(vals)
    if step is None:
        t = nice_ticks(lo, hi) if hi > lo else [lo]
        step = (t[1] - t[0]) if len(t) > 1 else (abs(hi) or 1.0)
    a = math.floor(lo / step) * step
    b = math.ceil(hi / step) * step
    if abs(a - lo) < step * 1e-9:
        a -= step
    if abs(b - hi) < step * 1e-9:
        b += step
    if clamp is not None:
        a, b = max(a, clamp[0]), min(b, clamp[1])
    return round(a, 10), round(b, 10)


def fmt_num(v: float) -> str:
    if v == 0:
        return "0"
    if abs(v) < 1e-3 or abs(v) >= 1e5:
        return f"{v:.2g}".replace("e-0", "e-").replace("e+0", "e")
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s


def _minus(s: str) -> str:
    """数字の前のハイフンを数学のマイナス（−）にする。"""
    return s.replace("-", "−")


def _shape(cx: float, cy: float, r: float, shape: str, fill: str, stroke: str = "#ffffff",
           sw: float = 1.0, opacity: float | None = None) -> str:
    """点の形（circle・square・triangle・triangle_down・diamond）。"""
    op = f' fill-opacity="{opacity}"' if opacity is not None else ""
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    if shape == "square":
        a = r * 0.9
        return f'<rect x="{cx - a:.1f}" y="{cy - a:.1f}" width="{2 * a:.1f}" height="{2 * a:.1f}" fill="{fill}"{op}{st}/>'
    if shape in ("triangle", "triangle_down"):
        s = 1 if shape == "triangle" else -1
        d = (f"M{cx:.1f},{cy - s * r * 1.15:.1f} L{cx + r * 1.05:.1f},{cy + s * r * 0.75:.1f} "
             f"L{cx - r * 1.05:.1f},{cy + s * r * 0.75:.1f} Z")
        return f'<path d="{d}" fill="{fill}"{op}{st}/>'
    if shape == "diamond":
        a = r * 1.2
        d = f"M{cx:.1f},{cy - a:.1f} L{cx + a:.1f},{cy:.1f} L{cx:.1f},{cy + a:.1f} L{cx - a:.1f},{cy:.1f} Z"
        return f'<path d="{d}" fill="{fill}"{op}{st}/>'
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"{op}{st}/>'


def _hit(a, b) -> bool:
    """2 つの箱 (x0, y0, x1, y1) が重なるか。"""
    return min(a[2], b[2]) - max(a[0], b[0]) > 0 and min(a[3], b[3]) - max(a[1], b[1]) > 0


def _seg_hit(seg, box) -> bool:
    """線分 seg = (x0, y0, x1, y1) が箱 (x0, y0, x1, y1) の中を通るか（線分の上の 24 点で調べる）。"""
    x0, y0, x1, y1 = seg
    for k in range(25):
        t = k / 24
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        if box[0] < x < box[2] and box[1] < y < box[3]:
            return True
    return False


class Fig:
    def __init__(self, width: int, height: int, title: str | None = None, title_size: int = 19,
                 place_mm: float | None = None, target: str = "md", display_px: float | None = None,
                 palette: str | None = None):
        """place_mm: 文書やスライドに置く幅（mm）。display_px: 画面に表示する幅（CSS px、96 dpi で mm に直す）。
        どちらかを渡すと、save() が最終の大きさで target の最小の字（md 7pt・slide 10pt）未満の字を警告する。"""
        self.W, self.H = width, height
        self.parts: list[str] = []
        self.warnings: list[str] = []
        self._markers: set[str] = set()
        self._text_boxes: list[tuple[float, float, float, float, str]] = []
        self.palette = _palette_name(palette)
        pal = PALETTES[self.palette]
        self.kinds = dict(pal["kinds"])
        self.series = list(pal["series"])
        self._emph, self._dim, self._compare = pal["emph"], pal["dim"], pal["compare"]
        if target not in MIN_PT:
            raise ValueError(f"target は {sorted(MIN_PT)} のどれか")
        if place_mm is None and display_px is not None:
            place_mm = display_px * 25.4 / 96
        self.place_mm = place_mm
        self.target = target
        self._title = title
        self._last: dict | None = None  # 直前のグラフ（ref_line・drop_arrows が使う）
        if title:
            self.text(width / 2, 34, title, size=title_size, bold=True)

    def pt(self, px: float) -> float | None:
        """図中の文字サイズ px を配置後の pt に換算する。配置幅が未指定なら None。"""
        if not self.place_mm:
            return None
        return px * self.place_mm / self.W / 25.4 * 72

    # ---------- 基本要素 ----------
    def _track(self, x0: float, y0: float, x1: float, y1: float, what: str) -> None:
        if x0 < -1 or y0 < -1 or x1 > self.W + 1 or y1 > self.H + 1:
            self.warnings.append(f"キャンバスの外に出ている: {what} ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f})")

    def raw(self, svg: str) -> None:
        self.parts.append(svg)

    def text(self, x, y, s, size=14, anchor="middle", color=INK, bold=False, italic=False, rotate=None,
             halo=False):
        """指定した座標にテキストを配置する。halo=True で白い縁取りを付ける。"""
        lines = str(s).split("\n")
        for i, line in enumerate(lines):
            yy = y + i * size * 1.35
            w = text_width(line, size, bold)
            x0 = x - (w / 2 if anchor == "middle" else (w if anchor == "end" else 0))
            if rotate is None:
                self._track(x0, yy - size, x0 + w, yy + 3, f"文字「{line[:16]}」")
                if line.strip():
                    self._text_boxes.append((x0, yy - size * 0.9, x0 + w, yy + size * 0.25, line))
            attrs = f'x="{x:.1f}" y="{yy:.1f}" font-size="{size}" text-anchor="{anchor}"'
            if color != INK:
                attrs += f' fill="{color}"'
            if bold:
                attrs += ' font-weight="bold"'
            if italic:
                attrs += ' font-style="italic"'
            if rotate is not None:
                attrs += f' transform="rotate({rotate} {x:.1f} {yy:.1f})"'
            if halo:
                attrs += ' stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke"'
            self.parts.append(f"<text {attrs}>{esc(line)}</text>")

    def box(self, x, y, w, h, kind="data", label="", size=15, bold_first=True, dashed=False,
            sub_size=None, rx=8, stroke_width=1.5):
        """役割 kind の角丸の箱と、中央ぞろえの文字。label の 2 行目以降は小さめ・灰色。"""
        fill, stroke = self.kinds[kind]
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"{dash}/>'
        )
        self._track(x, y, x + w, y + h, f"箱「{label[:16]}」")
        if not label:
            return
        lines = label.split("\n")
        sub_size = sub_size or max(11, size - 2)
        sizes = [size] + [sub_size] * (len(lines) - 1)
        total = sum(s * 1.3 for s in sizes)
        yy = y + (h - total) / 2 + sizes[0] * 1.0
        for i, (line, s) in enumerate(zip(lines, sizes)):
            bold = bold_first and i == 0 and len(lines) > 1
            tw = text_width(line, s, bold)
            if tw > w - 14:
                self.warnings.append(f"箱からはみ出しそう: 「{line}」 文字幅≈{tw:.0f}px > 箱の幅 {w:.0f}-14px")
            if total > h - 6:
                self.warnings.append(f"箱の高さが足りない: 「{label[:20]}」 必要≈{total:.0f}px > {h:.0f}-6px")
            color = INK if i == 0 else "#444444"
            self.text(x + w / 2, yy, line, size=s, bold=bold, color=color)
            yy += s * 1.3

    def _marker(self, color: str) -> str:
        mid = "a" + color.lstrip("#")
        if mid not in self._markers:
            self._markers.add(mid)
            self.parts.insert(0, (
                f'<defs><marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/>'
                f"</marker></defs>"
            ))
        return mid

    def arrow(self, x1, y1, x2, y2, color=MUTED, dashed=False, width=1.5, both=False, head=True):
        """直線の矢印。箱の辺から 2〜4px 離して終わらせると矢じりがきれいに見える。"""
        mid = self._marker(color)
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        end = f' marker-end="url(#{mid})"' if head else ""
        start = f' marker-start="url(#{mid})"' if both else ""
        self.parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
            f'stroke-width="{width}"{dash}{start}{end}/>'
        )

    def path_arrow(self, points, color=MUTED, dashed=False, width=1.5, head=True):
        """折れ線の矢印。points = [(x,y), ...]。箱を回り込ませたいときに使う。"""
        mid = self._marker(color)
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        end = f' marker-end="url(#{mid})"' if head else ""
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        self.parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"{dash}{end}/>')

    def line(self, x1, y1, x2, y2, color=GRID, width=1, dashed=False):
        dash = ' stroke-dasharray="4 4"' if dashed else ""
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"{dash}/>')

    def rect(self, x, y, w, h, fill="#ffffff", stroke="none", rx=0, opacity=None, dashed=False):
        self._track(x, y, x + w, y + h, "rect")
        op = f' opacity="{opacity}"' if opacity is not None else ""
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}"{op}{dash}/>')

    def circle(self, cx, cy, r, kind="enc", label="", size=13, dashed=False):
        fill, stroke = self.kinds[kind]
        dash = ' stroke-dasharray="4 3"' if dashed else ""
        self.parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.8"{dash}/>')
        if label:
            self.text(cx, cy + size * 0.36, label, size=size, bold=True)

    def legend(self, x, y, items, size=13, gap=26, horizontal=False, swatch="line"):
        """items = [(色 or kind, 名前), ...]。swatch="line"（線）か "box"（箱）。
        3 つ目に {"marker": "square", "dash": "7 4"} を渡すと、線に点の形と線の種類を付ける（line_chart と合わせる）。"""
        cx, cy = x, y
        for item in items:
            col, name = item[0], item[1]
            style = item[2] if len(item) > 2 else None
            fill, stroke = self.kinds.get(col, (col, col))
            if swatch == "box":
                self.parts.append(f'<rect x="{cx}" y="{cy-11}" width="16" height="12" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
            elif style:
                dash = f' stroke-dasharray="{style["dash"]}"' if style.get("dash") else ""
                if style.get("line", True):  # {"line": False} で点だけ（散布図の凡例）
                    self.parts.append(f'<line x1="{cx}" y1="{cy-5}" x2="{cx+20}" y2="{cy-5}" stroke="{stroke}" stroke-width="2.5"{dash}/>')
                if style.get("marker"):
                    self.parts.append(_shape(cx + 10, cy - 5, 4.5, style["marker"], stroke))
            else:
                self.parts.append(f'<line x1="{cx}" y1="{cy-5}" x2="{cx+20}" y2="{cy-5}" stroke="{stroke}" stroke-width="3"/>')
            self.text(cx + 26, cy, name, size=size, anchor="start")
            if horizontal:
                cx += 26 + text_width(name, size) + 28
            else:
                cy += gap

    def caption(self, s, size=13, y=None, color="#555555"):
        """図の下の注記（データの出どころ、「模式図」などの断り書き）。"""
        self.text(self.W / 2, y if y is not None else self.H - 16, s, size=size, color=color)

    def _note(self, x, y, s, size=12):
        """グラフの左上に注記を左寄せで置く。"""
        self.text(x, y, s, size=size, anchor="start", color=MUTED)

    # ---------- グラフ ----------
    def _axes(self, x, y, w, h, xlim, ylim, xticks, yticks, xlabel, ylabel, xfmt, yfmt, size=12):
        (x0, x1), (y0, y1) = xlim, ylim
        sx = lambda v: x + (v - x0) / (x1 - x0) * w
        sy = lambda v: y + h - (v - y0) / (y1 - y0) * h
        for t in yticks:
            self.line(x, sy(t), x + w, sy(t), GRID)
            self.text(x - 8, sy(t) + 4, yfmt(t), size=size, anchor="end", color=MUTED)
        for t in xticks:
            self.text(sx(t), y + h + 18, xfmt(t), size=size, color=MUTED)
        self.line(x, y + h, x + w, y + h, MUTED, 1.5)
        self.line(x, y, x, y + h, MUTED, 1.5)
        if xlabel:
            self.text(x + w / 2, y + h + 42, xlabel, size=13)
        if ylabel:
            self.text(x - 52, y + h / 2, ylabel, size=13, rotate=-90)
        return sx, sy

    @staticmethod
    def _better(better: str | None, horizontal: bool) -> str:
        """良い方向の印。縦の値の軸は「↑ 大きいほど良い」（立てた字で左上の 1 行に）、
        横の値の軸は「→ 大きいほど良い」（軸の名前に）。軸の名前は -90° 回すので、↑ を入れると ← に見える。"""
        if better is None:
            return ""
        if better not in ("up", "down"):
            raise ValueError('better は "up"（大きいほど良い）か "down"（小さいほど良い）')
        if horizontal:
            return "→ 大きいほど良い" if better == "up" else "← 小さいほど良い"
        return "↑ 大きいほど良い" if better == "up" else "↓ 小さいほど良い"

    def line_chart(self, x, y, w, h, series, xlim=None, ylim=None, xticks=None, yticks=None,
                   xlabel="", ylabel="", xfmt=fmt_num, yfmt=fmt_num, markers=False, label_last=True,
                   bands=None, traces=None, marker_cycle=None, main=0, better=None):
        """series = [{"name": str, "xs": [...], "ys": [...], "color": 任意, "dashed": 任意,
        "marker": 任意, "dash": 任意}]。値は実データか式から計算したものだけを入れる（作った数字を入れない）。

        main:   主役の系列の添字（既定 0）。主役だけ青、ほかは灰で、点の形と線の種類で分ける
                主役のいないグラフは main=None で
                Okabe-Ito の系列色を順に使う。legacy の配色では前と同じ（SERIES を順に使う）。
        bands:  {系列名: (下限のリスト, 上限のリスト)}。信頼区間の帯（不透明度 0.15）。区間は呼ぶ側で計算する。
        traces: {系列名: [ys, ys, ...]}（xs は系列と同じ）。seed や個体ごとの細い軌跡。
        marker_cycle: 系列ごとに点の形と線の種類を変える（白黒・色覚で見分けるため）。
            None なら、系列が 2 本以上で palette が legacy でないとき自動で付ける。
        better: "up" | "down"。左上の 1 行に「↑ 大きいほど良い」「↓ 小さいほど良い」。
        ylim には nice_lim(値, step, clamp) の結果を渡すと、目盛りの倍数へ外向きに丸めた範囲になる。
        """
        bands = bands or {}
        traces = traces or {}
        if isinstance(bands, (list, tuple)):
            bands = {s.get("name", i): b for i, (s, b) in enumerate(zip(series, bands)) if b}
        if isinstance(traces, (list, tuple)):
            traces = {s.get("name", i): t for i, (s, t) in enumerate(zip(series, traces)) if t}
        allx = [v for s in series for v in s["xs"]]
        ally = [v for s in series for v in s["ys"]]
        ally += [v for lo, hi in bands.values() for v in (*lo, *hi)]
        ally += [v for tr in traces.values() for ys in tr for v in ys]
        xlim = xlim or (min(allx), max(allx))
        if ylim is None:
            lo, hi = min(ally), max(ally)
            pad = (hi - lo) * 0.08 or 1
            ylim = (lo - pad if lo < 0 else min(0, lo), hi + pad)
        xticks = xticks if xticks is not None else nice_ticks(*xlim)
        yticks = yticks if yticks is not None else nice_ticks(*ylim)
        sx, sy = self._axes(x, y, w, h, xlim, ylim, xticks, yticks, xlabel, ylabel, xfmt, yfmt)
        if marker_cycle is None:
            marker_cycle = len(series) >= 2 and self.palette != "legacy"
        self.parts.append('<g data-chart="line">')
        labels = []
        use_main = self._compare is not None and main is not None and 0 <= main < len(series)
        order = [i for i in range(len(series)) if not (use_main and i == main)] + ([main] if use_main else [])
        for i in order:  # 主役は最後に描いて上に重ねる
            s = series[i]
            if use_main:
                col = s.get("color", self.series[0] if i == main else self._compare)
            else:
                col = s.get("color", self.series[i % len(self.series)])
            name = s.get("name", "")
            key = name if name in bands or name in traces else i
            # 主役は ○ と実線、ほかは □△▽◇ と破線の種類を順に
            rank = (0 if i == main else 1 + [j for j in range(len(series)) if j != main].index(i)) if use_main else i
            shape = s.get("marker", SHAPES[rank % len(SHAPES)] if marker_cycle else None)
            dash_v = s.get("dash", "6 4" if s.get("dashed") else (DASHES[rank % len(DASHES)] if marker_cycle else ""))
            self.parts.append(f'<g data-series="{_attr(name or i)}" data-marker="{shape or "none"}">')
            if key in bands:
                lo_l, hi_l = bands[key]
                pts = [(sx(a), sy(b)) for a, b in zip(s["xs"], hi_l)] + \
                      [(sx(a), sy(b)) for a, b in reversed(list(zip(s["xs"], lo_l)))]
                ptxt = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
                self.parts.append(f'<polygon points="{ptxt}" fill="{col}" fill-opacity="0.15" stroke="none"/>')
            for ys in traces.get(key, []):
                ptxt = " ".join(f"{sx(a):.1f},{sy(b):.1f}" for a, b in zip(s["xs"], ys))
                self.parts.append(f'<polyline points="{ptxt}" fill="none" stroke="{col}" stroke-width="1" stroke-opacity="0.3"/>')
            pts = " ".join(f"{sx(a):.1f},{sy(b):.1f}" for a, b in zip(s["xs"], s["ys"]))
            dash = f' stroke-dasharray="{dash_v}"' if dash_v else ""
            self.parts.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.5"{dash}/>')
            if markers and not shape:
                for a, b in zip(s["xs"], s["ys"]):
                    self.parts.append(f'<circle cx="{sx(a):.1f}" cy="{sy(b):.1f}" r="3" fill="{col}"/>')
            if shape:
                k = len(s["xs"])
                idx = range(k) if (markers or k <= 15) else sorted({round(j * (k - 1) / 7) for j in range(8)})
                for j in idx:
                    self.parts.append(_shape(sx(s["xs"][j]), sy(s["ys"][j]), 4.5, shape, col))
            self.parts.append("</g>")
            if label_last and name:
                labels.append((sx(s["xs"][-1]), sy(s["ys"][-1]), name, col, shape, dash_v))
        self.parts.append("</g>")
        for lx, ly, name, col, shape, dash_v in labels:
            tc = text_color(col)
            if tc == col:
                self.text(lx + 6, ly + 4, name, size=13, anchor="start", color=col, bold=True)
            else:
                # 対比が 4.5 未満の色は文字を INK にし、色の小さな印を添える
                dash = f' stroke-dasharray="{dash_v}"' if dash_v else ""
                self.parts.append(f'<line x1="{lx + 6:.1f}" y1="{ly:.1f}" x2="{lx + 22:.1f}" y2="{ly:.1f}" '
                                  f'stroke="{col}" stroke-width="2.5"{dash}/>')
                if shape:
                    self.parts.append(_shape(lx + 14, ly, 4, shape, col))
                self.text(lx + 27, ly + 4, name, size=13, anchor="start", bold=True)
        mark = self._better(better, False)
        if mark:
            self._note(x, y - 10, mark)
        self._last = dict(kind="line", horizontal=False, x=x, y=y, w=w, h=h, v2px=sy, sx=sx, vrange=ylim,
                          xrange=xlim, series=series, main=main if use_main else 0)
        return sx, sy

    def bar_chart(self, x, y, w, h, labels, values, colors=None, ylim=None, yticks=None, ylabel="",
                  value_fmt=fmt_num, label_size=12, horizontal=False, highlight=None,
                  errors=None, err_kind=None, n=None, unit="", label_row=False, better=None,
                  refs=None, value_inside=False, note=None):
        """棒グラフ。horizontal=True は横棒（項目名が長いとき・順位を見せるとき）。
        highlight に添字を渡すと、その棒だけ強調する（okabe_ito では他の棒を淡い灰にし、主役を青に）。

        errors:   誤差。数なら ±その値、(下限, 上限) の組なら区間の端の値。統計は呼ぶ側で計算する。
        err_kind: "sd" | "sem" | "ci95"。errors を渡すなら必須（無ければ ValueError）。
        n, unit:  何回分の平均か（n = 5、unit = "seed"）。errors を渡すなら n は必須。
                  図の左上に「平均 ± SD（n = 5 seed）」を自動で書く（note= で書き換えられる）。
        label_row: 数値のラベルを、全部の棒・誤差棒・基準線より上の 1 段にそろえる。
        better:   "up" | "down"。縦棒は左上の 1 行に「↑ 大きいほど良い」「↓ 小さいほど良い」、
                  横棒は軸の名前に「（→ 大きいほど良い）」「（← 小さいほど良い）」を付ける。
        refs:     [(値, 名前), ...]。基準の破線（ref_line と同じ）。label_row の高さにも入れる。
        value_inside: 数値を棒の中に書く（字の色は塗りの明るさで白か黒）。
        戻り値は 値 → 座標 の関数（縦棒は y、横棒は x）。
        """
        nb = len(values)
        given_colors = colors is not None
        colors = colors or [self.series[0]] * nb
        if highlight is not None:
            if self._dim and not given_colors:
                colors = [self._dim] * nb
            colors = [self._emph if i == highlight else c for i, c in enumerate(colors)]
        refs = [(r, "") if isinstance(r, (int, float)) else tuple(r) for r in (refs or [])]
        spans = None
        if errors is not None:
            if err_kind not in ERR_KINDS:
                raise ValueError('errors を渡すときは err_kind="sd" | "sem" | "ci95" を必ず指定する（SD と SEM の混在を防ぐ）')
            if n is None:
                raise ValueError("errors を渡すときは n（何回分の平均か。例 n=5, unit=\"seed\"）を必ず指定する")
            if len(errors) != nb:
                raise ValueError(f"errors の数（{len(errors)}）が values の数（{nb}）と違う")
            spans = []
            for v, e in zip(values, errors):
                lo_e, hi_e = (e[0], e[1]) if isinstance(e, (list, tuple)) else (v - e, v + e)
                if not lo_e <= v <= hi_e:
                    self.warnings.append(f"誤差の区間 ({lo_e}, {hi_e}) が値 {v} を含まない（(下限, 上限) は端の値で渡す）")
                spans.append((lo_e, hi_e))
            if not unit:
                self.warnings.append("n が何の数か（seed・fold・被験者）を unit= で書く")
        new_style = spans is not None or refs or label_row
        tops = [max(v, s[1]) if spans else v for v, s in zip(values, spans or [None] * nb)]
        lows = [min(v, s[0]) if spans else v for v, s in zip(values, spans or [None] * nb)]
        lo = min(0, min(lows))
        hi = max(tops + [r[0] for r in refs])
        if ylim is None:
            if not new_style:
                ylim = (lo, hi * 1.15 if hi > 0 else 1)
            else:
                k = (26 if label_row else 20) / (w if horizontal else h)
                top = max((hi - k * lo) / (1 - k), hi * 1.15 if hi > 0 else 1)
                ylim = (lo, top)
        yticks = yticks if yticks is not None else nice_ticks(*ylim)
        # 棒の付け根。軸が 0 から始まらないときは軸の下端から伸ばす（差が大きく見えるので注記を促す）
        base = 0 if ylim[0] <= 0 <= ylim[1] else ylim[0]
        if base != 0:
            self.warnings.append(f"棒グラフの軸が 0 から始まっていない（{ylim[0]}〜）。差が大きく見えるので caption で断る。点＋信頼区間（dot_strip）に変えることも考える")
        mark = self._better(better, horizontal)
        head = []
        if mark and horizontal:
            ylabel = f"{ylabel}（{mark}）" if ylabel else mark
        elif mark:
            head.append(mark)
        if spans is not None:
            head.append(note if note else f"平均 ± {ERR_KINDS[err_kind]}（n = {n}{' ' + unit if unit else ''}）")
        elif note:
            head.append(note)
        bars = []
        if horizontal:
            band = h / nb
            lab_w = max(text_width(l, label_size) for l in labels) + 12
            px, pw = x + lab_w, w - lab_w - 60
            sv = lambda v: px + (v - ylim[0]) / (ylim[1] - ylim[0]) * pw
            for t in yticks:
                self.line(sv(t), y, sv(t), y + h, GRID)
                self.text(sv(t), y + h + 18, value_fmt(t), size=12, color=MUTED)
            col_x = max([sv(t) for t in tops] + [sv(r[0]) for r in refs]) + 8 if label_row else None
            for i, (lab, v, c) in enumerate(zip(labels, values, colors)):
                by = y + i * band + band * 0.18
                bh = band * 0.64
                self.rect(min(sv(base), sv(v)), by, abs(sv(v) - sv(base)), bh, fill=c, rx=3)
                self.text(px - 10, by + bh / 2 + 5, lab, size=label_size, anchor="end")
                if spans:
                    self._errbar_h(sv(spans[i][0]), sv(spans[i][1]), by + bh / 2, min(bh * 0.5, 14))
                if value_inside and abs(sv(v) - sv(base)) >= text_width(value_fmt(v), 12, True) + 12:
                    self.text(sv(v) - 6, by + bh / 2 + 5, value_fmt(v), size=12, anchor="end", bold=True, color=ink_for(c))
                elif col_x is not None:
                    self.text(col_x, by + bh / 2 + 5, value_fmt(v), size=12, anchor="start", bold=True)
                else:
                    self.text(sv(tops[i]) + 6, by + bh / 2 + 5, value_fmt(v), size=12, anchor="start", bold=True)
                bars.append(dict(c=by + bh / 2, size=bh, v=v))
            self.line(sv(base), y, sv(base), y + h, MUTED, 1.5)
            if ylabel:
                self.text(px + pw / 2, y + h + 42, ylabel, size=13)
            self._last = dict(kind="bar", horizontal=True, x=px, y=y, w=pw, h=h, v2px=sv, bars=bars, base=base, vrange=ylim)
            for r in refs:
                self.ref_line(r[0], r[1] if len(r) > 1 else "")
            if head:
                self._note(px, y - 10, "　".join(head))
            return sv
        sx, sy = self._axes(x, y, w, h, (0, nb), ylim, [], yticks, "", ylabel, fmt_num, value_fmt)
        band = w / nb
        row_y = min([sy(t) for t in tops] + [sy(r[0]) for r in refs]) - 8 if label_row else None
        for i, (lab, v, c) in enumerate(zip(labels, values, colors)):
            bx = x + i * band + band * 0.2
            bw = band * 0.6
            self.rect(bx, min(sy(v), sy(base)), bw, abs(sy(base) - sy(v)), fill=c, rx=3)
            if spans:
                self._errbar_v(bx + bw / 2, sy(spans[i][0]), sy(spans[i][1]), min(bw * 0.4, 14))
            if value_inside and abs(sy(base) - sy(v)) >= 22:
                yy = sy(v) + 17 if v >= base else sy(v) - 7
                self.text(bx + bw / 2, yy, value_fmt(v), size=12, bold=True, color=ink_for(c))
            elif row_y is not None:
                self.text(bx + bw / 2, row_y, value_fmt(v), size=12, bold=True)
            elif spans:
                yy = sy(tops[i]) - 6 if v >= base else sy(lows[i]) + 16
                self.text(bx + bw / 2, yy, value_fmt(v), size=12, bold=True)
            else:
                self.text(bx + bw / 2, sy(v) - 6 if v >= base else sy(v) + 16, value_fmt(v), size=12, bold=True)
            for j, part in enumerate(lab.split("\n")):
                self.text(bx + bw / 2, y + h + 18 + j * 15, part, size=label_size)
            if text_width(max(lab.split("\n"), key=len), label_size) > band - 4:
                self.warnings.append(f"棒の項目名が隣と重なりそう: 「{lab}」（\\n で改行するか horizontal=True に）")
            bars.append(dict(c=bx + bw / 2, size=bw, v=v))
        self._last = dict(kind="bar", horizontal=False, x=x, y=y, w=w, h=h, v2px=sy, bars=bars, base=base, vrange=ylim,
                          lab_lines=max(len(l.split("\n")) for l in labels), lab_size=label_size)
        for r in refs:
            self.ref_line(r[0], r[1] if len(r) > 1 else "")
        if head:
            self._note(x, y - 10, "　".join(head))
        if new_style or value_inside:
            return sy
        return None

    def _errbar_v(self, cx, y_lo, y_hi, cap, color=INK, width=1.5):
        """縦の誤差棒（線と上下の横線）。"""
        self.parts.append(f'<line x1="{cx:.1f}" y1="{y_lo:.1f}" x2="{cx:.1f}" y2="{y_hi:.1f}" stroke="{color}" stroke-width="{width}"/>')
        for yy in (y_lo, y_hi):
            self.parts.append(f'<line x1="{cx - cap / 2:.1f}" y1="{yy:.1f}" x2="{cx + cap / 2:.1f}" y2="{yy:.1f}" stroke="{color}" stroke-width="{width}"/>')

    def _errbar_h(self, x_lo, x_hi, cy, cap, color=INK, width=1.5):
        """横の誤差棒（forest・横棒）。"""
        self.parts.append(f'<line x1="{x_lo:.1f}" y1="{cy:.1f}" x2="{x_hi:.1f}" y2="{cy:.1f}" stroke="{color}" stroke-width="{width}"/>')
        for xx in (x_lo, x_hi):
            self.parts.append(f'<line x1="{xx:.1f}" y1="{cy - cap / 2:.1f}" x2="{xx:.1f}" y2="{cy + cap / 2:.1f}" stroke="{color}" stroke-width="{width}"/>')

    def dot_strip(self, x, y, w, h, labels, groups, ci=None, means=None, unit="", err_kind="ci95",
                  colors=None, ylim=None, yticks=None, ylabel="", value_fmt=fmt_num, show_values=True,
                  jitter=0.13, seed=20260719, note=None, label_size=12, better=None, highlight=None):
        """群ごとに各点と、平均 ± 区間（白抜きの丸と線）を描く。

        groups: 群ごとの値のリスト（seed・fold・被験者ごとの結果）。空のリストなら点を描かない（差のパネル用）。
        ci:     群ごとの (下限, 上限)。必須。区間はこの関数では計算しない（bootstrap などはプロジェクト側で）。
        means:  群ごとの平均。渡さなければ点の算術平均を使う（点が無い群は必須）。
        unit:   n が何の数か（"seed"・"fold"・"被験者"）。左上の 1 行に「n = 5 seed」と書く。
        err_kind: 区間の種類（"ci95" | "sd" | "sem"）。左上の 1 行に書く。
        highlight: 主役の群の添字。主役の点だけ青、ほかは灰（無ければ全部の群を青）。
        点は半透明・白い縁・決まった seed で横にずらす（同じ図は何度描いても同じ）。
        戻り値は 値 → y 座標 の関数。
        """
        ng = len(labels)
        if len(groups) != ng:
            raise ValueError(f"groups の数（{len(groups)}）が labels の数（{ng}）と違う")
        if ci is None or len(ci) != ng:
            raise ValueError("dot_strip は区間を計算しない。ci=[(下限, 上限), ...] を群の数だけ渡す（プロジェクト側で計算した 95% 信頼区間など）")
        if err_kind not in ERR_KINDS:
            raise ValueError('err_kind は "ci95" | "sd" | "sem"')
        if means is None:
            if any(len(g) == 0 for g in groups):
                raise ValueError("点の無い群があるので means= を渡す")
            means = [sum(g) / len(g) for g in groups]
        if colors is None:
            gray = self._compare or MUTED
            colors = [self.series[0] if highlight in (None, i) else gray for i in range(ng)]
        allv = [v for g in groups for v in g] + [v for c in ci for v in c] + list(means)
        if ylim is None:
            lo, hi = min(allv), max(allv)
            pad = (hi - lo) * 0.1 or 1
            ylim = (lo - pad, hi + pad)
        yticks = yticks if yticks is not None else nice_ticks(*ylim)
        mark = self._better(better, False)
        sx, sy = self._axes(x, y, w, h, (0, ng), ylim, [], yticks, "", ylabel, fmt_num, value_fmt)
        band = w / ng
        rng = random.Random(seed)
        self.parts.append('<g data-chart="dot">')
        for i, (lab, g, (lo_c, hi_c), m, c) in enumerate(zip(labels, groups, ci, means, colors)):
            cx = x + band * (i + 0.5)
            px0 = cx - band * 0.06 if g else cx
            ex = cx + band * 0.2 if g else cx
            for v in g:
                dx = rng.uniform(-jitter, jitter) * band
                self.parts.append(_shape(px0 + dx, sy(v), 4.5, "circle", c, "#ffffff", 0.8, opacity=0.75))
            self._errbar_v(ex, sy(lo_c), sy(hi_c), 10)
            self.parts.append(f'<circle cx="{ex:.1f}" cy="{sy(m):.1f}" r="5" fill="#ffffff" stroke="{INK}" stroke-width="1.5"/>')
            if show_values:
                self.text(ex + 10, sy(m) + 4, _minus(value_fmt(m)), size=12, anchor="start", bold=True)
            for j, part in enumerate(lab.split("\n")):
                self.text(cx, y + h + 18 + j * 15, part, size=label_size)
        self.parts.append("</g>")
        ns = [len(g) for g in groups if g]
        if note is None and ns:
            nn = str(ns[0]) if min(ns) == max(ns) else f"{min(ns)}〜{max(ns)}"
            who = f"各 {unit}" if unit else "各回"
            note = f"点＝{who}　白丸と線＝平均 ± {ERR_KINDS[err_kind]}（n = {nn}{' ' + unit if unit else ''}）"
            if not unit:
                self.warnings.append("n が何の数か（seed・fold・被験者）を unit= で書く")
        elif note is None:
            self.warnings.append("区間の種類（95% 信頼区間など）と何の差かを note= で書く")
        note = "　".join(s for s in (mark, note) if s)
        if note:
            self._note(x, y - 10, note)
        self._last = dict(kind="dot", horizontal=False, x=x, y=y, w=w, h=h, v2px=sy, vrange=ylim,
                          bars=[dict(c=x + band * (i + 0.5), size=band * 0.6) for i in range(ng)],
                          lab_lines=max(len(l.split("\n")) for l in labels), lab_size=label_size)
        return sy

    def forest(self, x, y, w, h, labels, est, lo, hi, ref=0, xlim=None, xticks=None, xlabel="",
               value_fmt=None, col_title="推定値（95% 信頼区間）", color=None, label_size=13, better=None):
        """forest plot：項目ごとに推定値の点と区間の横線を縦に並べ、基準（ref、既定 0）の破線を引き、
        数値「0.84 (0.78–0.89)」は右の列に書き、区間を示す線との重なりを避ける。
        区間は呼ぶ側で計算する。戻り値は 値 → x 座標 の関数。"""
        nr = len(labels)
        if not (len(est) == len(lo) == len(hi) == nr):
            raise ValueError("labels・est・lo・hi の数をそろえる")
        fmt = value_fmt or (lambda v: f"{v:.2f}")
        # 負の端があると「−0.11–0.05」が読みにくいので、その列は全部「(−0.11, 0.05)」にする
        sep = ", " if min(lo) < 0 else "–"
        vals = [_minus(f"{fmt(e)} ({fmt(a)}{sep}{fmt(b)})") for e, a, b in zip(est, lo, hi)]
        lab_w = max(text_width(l, label_size) for l in labels) + 14
        val_w = max([text_width(v, 12) for v in vals] + [text_width(col_title, 12)]) + 4
        px0, px1 = x + lab_w, x + w - val_w - 18
        if xlim is None:
            a = min(list(lo) + ([ref] if ref is not None else []))
            b = max(list(hi) + ([ref] if ref is not None else []))
            pad = (b - a) * 0.08 or 1
            xlim = (a - pad, b + pad)
        sv = lambda v: px0 + (v - xlim[0]) / (xlim[1] - xlim[0]) * (px1 - px0)
        xticks = xticks if xticks is not None else nice_ticks(*xlim)
        for t in xticks:
            self.line(sv(t), y, sv(t), y + h, GRID)
            self.text(sv(t), y + h + 18, _minus(fmt_num(t)), size=12, color=MUTED)
        self.line(px0, y + h, px1, y + h, MUTED, 1.5)
        mark = self._better(better, True)
        if mark:
            xlabel = f"{xlabel}（{mark}）" if xlabel else mark
        if xlabel:
            self.text((px0 + px1) / 2, y + h + 42, xlabel, size=13)
        if ref is not None:
            self.parts.append(f'<line x1="{sv(ref):.1f}" y1="{y:.1f}" x2="{sv(ref):.1f}" y2="{y + h:.1f}" '
                              f'stroke="{MUTED}" stroke-width="1.2" stroke-dasharray="4 3"/>')
        self.text(px1 + 18, y - 8, col_title, size=12, anchor="start", color=MUTED)
        col = color or self.series[0]
        band = h / nr
        self.parts.append('<g data-chart="forest">')
        for i, (lab, e, a, b, v) in enumerate(zip(labels, est, lo, hi, vals)):
            cy = y + band * (i + 0.5)
            self.text(px0 - 12, cy + 5, lab, size=label_size, anchor="end")
            self._errbar_h(sv(a), sv(b), cy, 8)
            self.parts.append(_shape(sv(e), cy, 5.5, "square", col, "#ffffff", 1))
            self.text(px1 + 18, cy + 5, v, size=12, anchor="start")
        self.parts.append("</g>")
        self._last = dict(kind="forest", horizontal=True, x=px0, y=y, w=px1 - px0, h=h, v2px=sv, vrange=xlim)
        return sv

    def ref_line(self, value, label="", color=MUTED, width=1.5, dashed=True, size=12):
        """直前のグラフに基準の破線（ベースライン・チャンスレベル・完全なモデル）を引き、端にラベルを付ける。
        縦の値のグラフ（line_chart・bar_chart・dot_strip）は横線で右端の外にラベル、
        横の値のグラフ（横棒・forest）は縦線で上端の外にラベル。"""
        if not self._last:
            raise ValueError("ref_line は line_chart・bar_chart・dot_strip・forest のあとに呼ぶ")
        L = self._last
        lo, hi = sorted(L["vrange"])
        if not lo <= value <= hi:
            self.warnings.append(f"基準 {value} がグラフの範囲（{fmt_num(lo)}〜{fmt_num(hi)}）の外。ylim に入れる")
        p = L["v2px"](value)
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        if L["horizontal"]:
            self.parts.append(f'<line x1="{p:.1f}" y1="{L["y"]:.1f}" x2="{p:.1f}" y2="{L["y"] + L["h"]:.1f}" '
                              f'stroke="{color}" stroke-width="{width}"{dash}/>')
            if label:
                self.text(p, L["y"] - 6, label, size=size, color=text_color(color))
        else:
            self.parts.append(f'<line x1="{L["x"]:.1f}" y1="{p:.1f}" x2="{L["x"] + L["w"]:.1f}" y2="{p:.1f}" '
                              f'stroke="{color}" stroke-width="{width}"{dash}/>')
            if label:
                self.text(L["x"] + L["w"] + 6, p + 4, label, size=size, anchor="start", color=text_color(color))
        return p

    def drop_arrows(self, base=None, fmt=None, color=None, size=12):
        """アブレーション（部品を 1 つずつ外す実験）用。直前の縦棒グラフで、基準（既定は 1 本目の棒の値）から
        各棒の上端へ矢印を引き、基準線の上に「−0.06」を書く。
        数値を棒の上に書くと矢印と重なりやすいので、bar_chart(value_inside=True) と組み合わせる。
        矢印は灰（主役だけ色の決まり）。いちばん見てほしい下がり幅だけ色を変えたいときは color= を渡す。"""
        L = self._last
        if not L or L["kind"] != "bar" or L["horizontal"]:
            raise ValueError("drop_arrows は縦の bar_chart のあとに呼ぶ")
        bars = L["bars"]
        base = bars[0]["v"] if base is None else base
        fmt = fmt or (lambda v: f"{v:.2f}")
        col = color or MUTED
        sy = L["v2px"]
        for k, b in enumerate(bars):
            d = b["v"] - base
            if k == 0 and abs(d) < 1e-12:
                continue  # 基準そのものの棒
            y0, y1 = sy(base), sy(b["v"])
            if abs(y1 - y0) >= 4:  # 短すぎる矢印は描かず、数字だけ書く
                ax = b["c"] + b["size"] / 2 + 6
                s_ = 1 if y1 > y0 else -1  # 1 = 下向き
                tip = y1 - s_ * 1.5
                head = min(7.0, abs(tip - y0))
                if abs(tip - y0) > head + 1:
                    self.parts.append(f'<line x1="{ax:.1f}" y1="{y0:.1f}" x2="{ax:.1f}" y2="{tip - s_ * head:.1f}" '
                                      f'stroke="{col}" stroke-width="1.6"/>')
                self.parts.append(f'<path d="M{ax:.1f},{tip:.1f} L{ax - 4:.1f},{tip - s_ * head:.1f} '
                                  f'L{ax + 4:.1f},{tip - s_ * head:.1f} Z" fill="{col}"/>')
            s = ("+" if d > 0 else ("−" if d < 0 else "±")) + fmt(abs(d))
            self.text(b["c"], y0 - 7, s, size=size, bold=True, color=text_color(col))

    # ---------- 複数パネルとその他のグラフ ----------

    def _need_last(self, kinds: tuple[str, ...], what: str, vertical: bool | None = None) -> dict:
        L = self._last
        if not L or L["kind"] not in kinds or (vertical is not None and L["horizontal"] == vertical):
            raise ValueError(f"{what} は {'・'.join(kinds)} のグラフのあとに呼ぶ")
        return L

    def grid(self, x, y, w, h, nrows, ncols, gap_x=70, gap_y=80):
        """各パネルの (左上 x, 左上 y, 幅, 高さ) を行順で返す。"""
        pw = (w - gap_x * (ncols - 1)) / ncols
        ph = (h - gap_y * (nrows - 1)) / nrows
        if pw < 120 or ph < 80:
            self.warnings.append(f"パネルが小さすぎる（{pw:.0f}×{ph:.0f}px）。列を減らすかキャンバスを広げる")
        return [(x + c * (pw + gap_x), y + r * (ph + gap_y), pw, ph) for r in range(nrows) for c in range(ncols)]

    def panel_label(self, x, y, letter, title=None, size=19, title_size=15, band=False):
        """パネル記号と任意の見出しを置く。band=True で見出しに背景を付ける。"""
        if band and title:
            tw = text_width(title, title_size, True)
            self.rect(x + size + 2, y - title_size - 3, tw + 20, title_size + 10, fill="#F2F2F2", rx=6)
        self.text(x, y, letter, size=size, anchor="start", bold=True)
        if title:
            self.text(x + size + 12, y - 1, title, size=title_size, anchor="start", bold=True)

    def group(self, x, y, w, h, label="", kind="plain", size=13, dashed=True):
        """部品を囲む枠と見出しを描く。中の部品より先に描く。"""
        stroke = self.kinds[kind][1]
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="12" fill="none" '
                          f'stroke="{stroke}" stroke-width="1.5"{dash}/>')
        self._track(x, y, x + w, y + h, f"まとまり「{label[:16]}」")
        if label:
            self.text(x + 14, y + size * 0.35, label, size=size, anchor="start", bold=True, halo=True)

    def _seq_color(self, t: float, diverging: bool = False) -> str:
        """t（0〜1、diverging は −1〜1）を 1 色相の濃淡に。正は青、負は朱。0 は白に近い色。
        白の字も INK の字も対比 4.5 に届かない明るさ（相対輝度およそ 0.18〜0.25）は飛ばし、
        いちばん近い読める濃さに寄せる（色の帯に小さな段ができる。数値の字を必ず読めるようにするため）。"""
        t = max(-1.0, min(1.0, t))
        if diverging:
            if abs(t) <= 1e-9:
                return "#FFFFFF"
            base = self.series[0] if t >= 0 else OKABE_ITO["vermillion"]
            amt = 1 - 0.95 * abs(t)
        else:
            base = self.series[0]
            amt = 0.95 * (1 - max(0.0, t))

        def ok(a):
            c = tint(base, a)
            return max(contrast("#ffffff", c), contrast(INK, c)) >= 4.5
        if not ok(amt):
            for d in range(1, 40):
                for a in (amt - d * 0.01, amt + d * 0.01):
                    if 0 <= a <= 1 and ok(a):
                        return tint(base, a)
        return tint(base, amt)

    def heatmap(self, x, y, w, h, rows, cols, values, vmin=None, vmax=None, center=None, fmt=None,
                show_values=True, totals=False, scale="all", better=None, highlight_row=None, foot=None,
                cbar=True, cbar_label="", label_size=12, value_size=12, note=None):
        """行列の数値をセルに表示する。scale='all' は全体で共通の色の範囲、'col' は列ごとの範囲。"""
        nr, nc = len(rows), len(cols)
        if len(values) != nr or any(len(r) != nc for r in values):
            raise ValueError("values は rows の数の行、各行 cols の数の値にする")
        if scale not in ("all", "col"):
            raise ValueError('scale は "all" か "col"')
        fmt = fmt or fmt_num
        bet = better if isinstance(better, (list, tuple)) else [better] * nc
        if len(bet) != nc:
            raise ValueError("better のリストは列の数にそろえる")
        for b in bet:
            self._better(b, False)  # 値を確かめる
        col_vals = [[values[i][j] for i in range(nr) if values[i][j] is not None] for j in range(nc)]
        allv = [v for c in col_vals for v in c]
        if not allv:
            raise ValueError("値が 1 つも無い")
        rlab = list(rows)
        clab = list(cols)
        if totals:
            rlab = [f"{r}\n(n = {fmt_num(sum(v for v in values[i] if v is not None))})" for i, r in enumerate(rows)]
            clab = [f"{c}\n(n = {fmt_num(sum(col_vals[j]))})" for j, c in enumerate(cols)]
        lab_w = max([text_width(l, label_size, True) for r in rlab for l in r.split("\n")]
                    + ([text_width(foot[0], label_size)] if foot else [])) + 12
        foot_rows = 1 if foot else 0
        use_cbar = cbar and scale == "all"
        cx0 = x + lab_w
        cw = (w - lab_w - (74 if use_cbar else 0)) / nc
        ch = h / (nr + foot_rows)
        if scale == "all":
            lo = min(allv) if vmin is None else vmin
            hi = max(allv) if vmax is None else vmax
            ranges = [(lo, hi)] * nc
        else:
            ranges = [(min(c), max(c)) if c else (0, 1) for c in col_vals]

        def t_of(v, j):
            lo, hi = ranges[j]
            if center is not None:
                span = max(abs(hi - center), abs(lo - center)) or 1
                t = (v - center) / span
            else:
                t = (v - lo) / ((hi - lo) or 1)
            return t

        self.parts.append(f'<g data-chart="heatmap" data-scale="{scale}">')
        for i in range(nr):
            for j in range(nc):
                v = values[i][j]
                rx_, ry_ = cx0 + j * cw, y + i * ch
                if v is None:
                    fill = "#F2F2F2"
                    s, tc = "—", MUTED
                else:
                    t = t_of(v, j)
                    if bet[j] == "down" and center is None:
                        t = 1 - t
                    fill = self._seq_color(t, center is not None)
                    s, tc = _minus(fmt(v)), ink_for(fill)
                self.parts.append(f'<rect x="{rx_:.1f}" y="{ry_:.1f}" width="{cw:.1f}" height="{ch:.1f}" '
                                  f'fill="{fill}" stroke="#ffffff" stroke-width="2"/>')
                if show_values or v is None:
                    if text_width(s, value_size) > cw - 4:
                        self.warnings.append(f"色の表の数値「{s}」がセルの幅 {cw:.0f}px に入らない（fmt で桁を減らすか幅を広げる）")
                    self.text(rx_ + cw / 2, ry_ + ch / 2 + value_size * 0.36, s, size=value_size, color=tc,
                              bold=(i == highlight_row))
        self.parts.append("</g>")
        for i, r in enumerate(rlab):
            lines = r.split("\n")
            y0 = y + i * ch + ch / 2 - (len(lines) - 1) * label_size * 0.675 + label_size * 0.36
            for k, part in enumerate(lines):
                self.text(cx0 - 8, y0 + k * label_size * 1.35, part, size=label_size, anchor="end",
                          bold=(i == highlight_row and k == 0), color=INK if k == 0 else MUTED)
        if highlight_row is not None:
            self.parts.append(f'<rect x="{cx0:.1f}" y="{y + highlight_row * ch:.1f}" width="{cw * nc:.1f}" '
                              f'height="{ch:.1f}" fill="none" stroke="{self._emph if self._dim else INK}" stroke-width="2.5"/>')
        if foot:
            fname, ftexts = foot
            if len(ftexts) != nc:
                raise ValueError("foot の文字は列の数にそろえる")
            fy = y + nr * ch + ch / 2 + label_size * 0.36
            self.text(cx0 - 8, fy, fname, size=label_size, anchor="end", italic=True)
            for j, s in enumerate(ftexts):
                self.text(cx0 + j * cw + cw / 2, fy, _minus(str(s)), size=value_size, bold=True)
        # 列の名前は表の上（表として読むので見出しを先に）。複数行なら下の行がセルのすぐ上
        nl = max(len(c.split("\n")) for c in clab)
        for j, c in enumerate(clab):
            lines = c.split("\n")
            for k, part in enumerate(lines):
                if text_width(part, label_size) > cw - 4 and k == 0:
                    self.warnings.append(f"列の名前「{part}」がセルの幅に入らない（\\n で改行する）")
                self.text(cx0 + j * cw + cw / 2, y - 8 - (len(lines) - 1 - k) * 15, part, size=label_size,
                          color=INK if k == 0 else MUTED)
        if use_cbar:
            gid = f"hm{len(self.parts)}"
            bx, bh = cx0 + cw * nc + 16, ch * nr
            lo, hi = ranges[0]
            stops = []
            for k in range(10, -1, -1):  # offset は小さい順に並べる（上端 0% = 最大値）
                v = lo + (hi - lo) * k / 10
                t = t_of(v, 0)
                if bet[0] == "down" and center is None:
                    t = 1 - t
                stops.append(f'<stop offset="{100 - k * 10}%" stop-color="{self._seq_color(t, center is not None)}"/>')
            self.parts.insert(0, f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">{"".join(stops)}'
                                 f"</linearGradient></defs>")
            self.parts.append(f'<g data-colorbar="1"><rect x="{bx:.1f}" y="{y:.1f}" width="14" height="{bh:.1f}" '
                              f'fill="url(#{gid})" stroke="{MUTED}" stroke-width="0.8"/></g>')
            for tv in nice_ticks(lo, hi, 4):
                ty = y + bh - (tv - lo) / ((hi - lo) or 1) * bh
                self.line(bx + 14, ty, bx + 18, ty, MUTED, 1)
                self.text(bx + 21, ty + 4, _minus(fmt_num(tv)), size=12, anchor="start", color=MUTED)
            if cbar_label:
                self.text(bx, y - 18 - (nl - 1) * 15, cbar_label, size=12, anchor="start", color=MUTED)
        if note is None and scale == "col":
            note = "色は列ごとの範囲（列をまたいで色を比べない）"
        if any(b == "down" for b in bet):
            extra = "濃いほど良い（↓ の列は小さいほど濃い）"
            note = f"{note}　{extra}" if note else extra
        if note:
            self._note(x, y - 14 - nl * 15, note)
        self._last = None
        return lambda i, j: (cx0 + j * cw + cw / 2, y + i * ch + ch / 2)

    def stacked_bar(self, x, y, w, h, labels, parts, names, horizontal=True, colors=None, main=None, hatch=False,
                    percent=False, value_fmt=None, n=None, label_size=12, show_values=True, value_label=""):
        """内訳を積み上げ棒で比較する。hatch=True で区分に模様を付ける。"""
        nb, ns = len(labels), len(names)
        if len(parts) != nb or any(len(p) != ns for p in parts):
            raise ValueError("parts は labels の数の棒、各棒 names の数の値にする")
        if any(v < 0 for p in parts for v in p):
            raise ValueError("積み上げの棒に負の値は入れない（差は bar_chart か forest で）")
        fmt = value_fmt or ((lambda v: f"{v:.0f}%") if percent else fmt_num)
        if colors is None:
            if main is None:
                colors = [tint(self.series[0], 0.8 * k / max(1, ns - 1)) for k in range(ns)]
            else:
                grays = [tint("#555555", a) for a in (0.35, 0.6, 0.8, 0.45, 0.7, 0.9)]
                colors, gi = [], 0
                for k in range(ns):
                    if k == main:
                        colors.append(self.series[0])
                    else:
                        colors.append(grays[gi % len(grays)])
                        gi += 1
        hatch_ids = []
        if hatch:
            kinds = ["", "M0,8 L8,0", "M0,0 L8,8", "M0,4 L8,4", "M0,0 L8,8 M0,8 L8,0", "M4,0 L4,8"]
            defs = []
            for k in range(ns):
                d = kinds[k % len(kinds)]
                if not d:
                    hatch_ids.append(None)
                    continue
                pid = f"hatch{k}_{len(self.parts)}"
                defs.append(f'<pattern id="{pid}" patternUnits="userSpaceOnUse" width="8" height="8">'
                            f'<path d="{d}" stroke="{INK}" stroke-width="1" stroke-opacity="0.55"/></pattern>')
                hatch_ids.append(pid)
            self.parts.insert(0, f"<defs>{''.join(defs)}</defs>")
        totals = [sum(p) for p in parts]
        if percent:
            for lab, tot in zip(labels, totals):
                if abs(tot - 100) > 0.5:
                    self.warnings.append(f"「{lab}」の内訳の合計が {fmt_num(tot)}（100% にならない）")
            top = 100
        else:
            top = max(totals) * 1.05
        ticks = nice_ticks(0, top)
        lab_w = max(text_width(l, label_size) for l in labels) + 12 if horizontal else 0
        right = 70 if n is not None else 16
        name_h = 24  # 区分の名前の段
        self.parts.append('<g data-chart="stacked">')
        segs_first = []
        if horizontal:
            px, pw = x + lab_w, w - lab_w - right
            sv = lambda v: px + v / top * pw
            band = (h - name_h) / nb
            y0 = y + name_h
            for t in ticks:
                self.line(sv(t), y0, sv(t), y + h, GRID)
                self.text(sv(t), y + h + 18, fmt(t) if percent else fmt_num(t), size=12, color=MUTED)
            for i, (lab, p) in enumerate(zip(labels, parts)):
                by, bh = y0 + i * band + band * 0.18, band * 0.64
                acc = 0.0
                self.text(px - 10, by + bh / 2 + 5, lab, size=label_size, anchor="end")
                for k, v in enumerate(p):
                    a, b = sv(acc), sv(acc + v)
                    self.rect(a, by, b - a, bh, fill=colors[k], stroke="#ffffff")
                    if hatch_ids and hatch_ids[k]:
                        self.parts.append(f'<rect x="{a:.1f}" y="{by:.1f}" width="{b - a:.1f}" height="{bh:.1f}" fill="url(#{hatch_ids[k]})"/>')
                    s = fmt(v)
                    if show_values and v > 0 and b - a >= text_width(s, 12, True) + 8:
                        hat = bool(hatch_ids and hatch_ids[k])
                        self.text((a + b) / 2, by + bh / 2 + 5, s, size=12, bold=True,
                                  color=INK if hat else ink_for(colors[k]), halo=hat)
                    if i == 0:
                        segs_first.append((a, b))
                    acc += v
                if n is not None:
                    self.text(sv(totals[i]) + 8, by + bh / 2 + 5, f"n = {fmt_num(n[i])}", size=12, anchor="start", color=MUTED)
            if value_label:
                self.text(px + pw / 2, y + h + 42, value_label, size=13)
            first_top = y0 + band * 0.18
            v2px = sv
        else:
            sx_, sy_ = self._axes(x, y + name_h, w - right, h - name_h, (0, nb), (0, top), [], ticks, "", value_label,
                                  fmt_num, fmt if percent else fmt_num)
            band = (w - right) / nb
            for i, (lab, p) in enumerate(zip(labels, parts)):
                bx, bw = x + i * band + band * 0.2, band * 0.6
                acc = 0.0
                for k, v in enumerate(p):
                    a, b = sy_(acc), sy_(acc + v)
                    self.rect(bx, b, bw, a - b, fill=colors[k], stroke="#ffffff")
                    if hatch_ids and hatch_ids[k]:
                        self.parts.append(f'<rect x="{bx:.1f}" y="{b:.1f}" width="{bw:.1f}" height="{a - b:.1f}" fill="url(#{hatch_ids[k]})"/>')
                    s = fmt(v)
                    if show_values and v > 0 and a - b >= 18 and text_width(s, 12, True) <= bw - 6:
                        hat = bool(hatch_ids and hatch_ids[k])
                        self.text(bx + bw / 2, (a + b) / 2 + 5, s, size=12, bold=True,
                                  color=INK if hat else ink_for(colors[k]), halo=hat)
                    acc += v
                for j, part in enumerate(lab.split("\n")):
                    self.text(bx + bw / 2, y + h + 18 + j * 15, part, size=label_size)
                if n is not None:
                    self.text(bx + bw / 2, sy_(totals[i]) - 6, f"n = {fmt_num(n[i])}", size=12, color=MUTED)
            v2px = sy_
            self._last = dict(kind="stacked", horizontal=False, x=x, y=y + name_h, w=w - right, h=h - name_h, v2px=sy_,
                              bars=[dict(c=x + i * band + band * 0.5, size=band * 0.6) for i in range(nb)],
                              vrange=(0, top), lab_lines=max(len(l.split("\n")) for l in labels), lab_size=label_size)
        self.parts.append("</g>")
        # 区分の名前：横棒は 1 本目の棒の上に直接。重なるなら（縦棒はいつも）上に凡例の 1 行
        direct = horizontal and all(text_width(nm, 12) <= (b - a) + 30 for nm, (a, b) in zip(names, segs_first))
        if direct:
            cs = [((a + b) / 2, text_width(nm, 12)) for nm, (a, b) in zip(names, segs_first)]
            direct = all(c2 - w2 / 2 - (c1 + w1 / 2) >= 6 for (c1, w1), (c2, w2) in zip(cs, cs[1:]))
        if direct:
            for nm, (a, b) in zip(names, segs_first):
                self.text((a + b) / 2, first_top - 7, nm, size=12, color=INK)
        else:
            lx = x + lab_w
            for k, nm in enumerate(names):
                self.parts.append(f'<rect x="{lx:.1f}" y="{y + 2:.1f}" width="16" height="12" rx="2" fill="{colors[k]}" '
                                  f'stroke="{MUTED}" stroke-width="0.8"/>')
                if hatch_ids and hatch_ids[k]:
                    self.parts.append(f'<rect x="{lx:.1f}" y="{y + 2:.1f}" width="16" height="12" rx="2" fill="url(#{hatch_ids[k]})"/>')
                self.text(lx + 22, y + 13, nm, size=12, anchor="start")
                lx += 22 + text_width(nm, 12) + 18
            if lx > x + w + 1:
                self.warnings.append("内訳の凡例の 1 行が右にはみ出す（区分の名前を短く）")
        if horizontal:
            self._last = None
        return v2px

    def events(self, items, series=None, style="arrow", size=12, color=MUTED, max_levels=4, side="above"):
        """直前の折れ線グラフに指定した時点と注記を付ける。style='line' は縦線。"""
        L = self._need_last(("line",), "events")
        sx, sy = L["sx"], L["v2px"]
        s = L["series"][L["main"] if series is None else series]
        placed: list[tuple[float, float, float, float]] = []
        arrows: list[tuple[float, float, float, float]] = []  # 矢印の線（始点と終点）。名前と交わらせない

        def y_at(xv):
            xs, ys = s["xs"], s["ys"]
            for (a, ya), (b, yb) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
                if min(a, b) <= xv <= max(a, b):
                    return ya if b == a else ya + (yb - ya) * (xv - a) / (b - a)
            raise ValueError(f"x = {xv} は系列「{s.get('name', '')}」の範囲の外")

        for it in items:
            xv, name = it[0], it[1]
            px = sx(xv)
            tw = text_width(name, size)
            if style == "line":
                self.parts.append(f'<line x1="{px:.1f}" y1="{L["y"]:.1f}" x2="{px:.1f}" y2="{L["y"] + L["h"]:.1f}" '
                                  f'stroke="#BBBBBB" stroke-width="1.5"/>')
                lvl = 0
                while True:
                    ty = L["y"] + 14 + lvl * (size + 4)
                    box = (px + 4, ty - size, px + 4 + tw, ty + 3)
                    if lvl >= max_levels or not any(_hit(box, q) for q in placed):
                        break
                    lvl += 1
                placed.append(box)
                self.text(px + 4, ty, name, size=size, anchor="start", color=text_color(color), halo=True)
                continue
            if style != "arrow":
                raise ValueError('style は "arrow" か "line"')
            if side not in ("above", "below"):
                raise ValueError('side は "above" か "below"')
            py = sy(it[2] if len(it) > 2 else y_at(xv))
            sg = 1 if side == "above" else -1
            # 段（lvl）と横のずらし（0・右・左・右に 2 つ分・左に 2 つ分）を順に試し、ほかの名前とも、ほかの矢印とも交わらない所に置く。
            # ずらしたときは、名前の下（上）の端から点へ斜めの線で指す
            choice = None
            for lvl in range(max_levels):
                ty = py - 24 - lvl * (size + 6) if sg == 1 else py + 24 + size + lvl * (size + 6)
                for shift in (0, 1, -1, 2, -2):
                    cx = px + shift * (tw / 2 + 10)
                    box = (cx - tw / 2 - 3, ty - size, cx + tw / 2 + 3, ty + 3)
                    seg = (cx, ty + 4 if sg == 1 else ty - size - 2, px, py - 3 * sg)
                    if not (any(_hit(box, q) for q in placed) or any(_seg_hit(a, box) for a in arrows)
                            or any(_seg_hit(seg, q) for q in placed)):
                        choice = (ty, cx, box, seg)
                        break
                if choice:
                    break
            if choice is None:
                self.warnings.append(f"出来事「{name}」の名前が {max_levels} 段では収まらない（名前を短くするか、図を横に広げる）")
                ty = py - 24 - (max_levels - 1) * (size + 6) if sg == 1 else py + 24 + size + (max_levels - 1) * (size + 6)
                cx = px
                choice = (ty, cx, (cx - tw / 2 - 3, ty - size, cx + tw / 2 + 3, ty + 3),
                          (cx, ty + 4 if sg == 1 else ty - size - 2, px, py - 3 * sg))
            ty, cx, box, seg = choice
            placed.append(box)
            arrows.append(seg)
            x0, y0, x1, y1 = seg
            ln = math.hypot(x1 - x0, y1 - y0) or 1
            ux, uy = (x1 - x0) / ln, (y1 - y0) / ln
            hx, hy = x1 - ux * 6, y1 - uy * 6  # 矢じりの根元
            self.parts.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{hx:.1f}" y2="{hy:.1f}" stroke="{color}" stroke-width="1.2"/>')
            self.parts.append(f'<path d="M{x1:.1f},{y1:.1f} L{hx - uy * 3.5:.1f},{hy + ux * 3.5:.1f} '
                              f'L{hx + uy * 3.5:.1f},{hy - ux * 3.5:.1f} Z" fill="{color}"/>')
            self.text(cx, ty, name, size=size, color=text_color(color), halo=True)

    def gap(self, xv, a, b, label, color=INK, size=12, side="right"):
        """同じ横座標にある二つの値の差を示す。差の表記は呼び出し元が label に渡す。"""
        L = self._need_last(("line",), "gap")
        px, ya, yb = L["sx"](xv), L["v2px"](a), L["v2px"](b)
        top, bot = min(ya, yb), max(ya, yb)
        if bot - top < 16:
            self.warnings.append(f"差の矢印「{label}」が短すぎる（{bot - top:.0f}px）。題か注記で数字だけ書く")
        self.parts.append(f'<line x1="{px:.1f}" y1="{top + 6:.1f}" x2="{px:.1f}" y2="{bot - 6:.1f}" stroke="{color}" stroke-width="1.5"/>')
        for yy, s_ in ((top, 1), (bot, -1)):
            self.parts.append(f'<path d="M{px:.1f},{yy:.1f} L{px - 4:.1f},{yy + s_ * 7:.1f} L{px + 4:.1f},{yy + s_ * 7:.1f} Z" fill="{color}"/>')
        tx = px + 8 if side == "right" else px - 8
        self.text(tx, (top + bot) / 2 + size * 0.36, label, size=size, anchor="start" if side == "right" else "end",
                  bold=True, color=text_color(color), halo=True)

    def bracket(self, i0, i1, label, size=12, color=MUTED):
        """直前の縦グラフの i0 から i1 までを括弧でまとめ、見出しを付ける。"""
        L = self._need_last(("bar", "dot", "stacked"), "bracket", vertical=True)
        bars = L["bars"]
        if not 0 <= i0 <= i1 < len(bars):
            raise ValueError(f"i0・i1 は 0〜{len(bars) - 1}")
        a = bars[i0]["c"] - bars[i0]["size"] / 2
        b = bars[i1]["c"] + bars[i1]["size"] / 2
        yb = L["y"] + L["h"] + 18 + (L.get("lab_lines", 1) - 1) * 15 + 10
        self.parts.append(f'<path d="M{a:.1f},{yb - 5:.1f} L{a:.1f},{yb:.1f} L{b:.1f},{yb:.1f} L{b:.1f},{yb - 5:.1f}" '
                          f'fill="none" stroke="{color}" stroke-width="1.2"/>')
        self.text((a + b) / 2, yb + size + 4, label, size=size, color=text_color(color))
        return yb + size + 4

    def sankey(self, x, y, w, h, links, columns=None, node_w=16, gap=10, colors=None, main=None,
               value_fmt=None, label_size=12, col_labels=None, link_alpha=0.35, valign="center",
               iterations=10):
        """流れの図（サンキー）。全体が段ごとに何に分かれるかを、帯の太さ（値に比例）で見せる。
        links: [(元, 先, 値), ...]（4 つ目に色を足すとその帯だけ色を変えられる）。値は正。
        1 単位の太さ（px/単位）は全部の段で同じ 1 つだけ。段ごとに縮尺を変えない。
        columns: 段ごとの名前のリスト（左の段から。段の中は上から）。省略すると、元から先への最長の道の長さで段分けする。
        段の中の順番は渡した順のまま（並べ替えない）。帯が交わりにくいよう、上下の位置だけを動かす。
        main: 主役の名前のリスト。主役どうしをつなぐ帯だけ青、ほかは灰（虹色にしない）。colors: {名前: 色} で個別に上書き。
        名前は、最初の段が帯の左、最後の段が右、途中の段は帯の右（白い縁取りつき）に書く。左右に 130px ほど余白を取る。
        入る量と出る量が合わない名前、細すぎる帯（2px 未満）、段の中で重なった名前は警告する。
        戻り値: {名前: {"x0","y0","x1","y1","value","col"}}（注釈を足すときの座標）。
        使う: 100% が段ごとに分かれる図、お金・数量の流れ。避ける: 時間の変化、2 つの値の比べ、小さな差を読ませたい図。"""
        if not links:
            raise ValueError("links が空")
        order, ins, outs, spec = [], {}, {}, []
        for lk in links:
            s_, t_, v_, *rest = lk
            if v_ <= 0:
                raise ValueError(f"帯の値は正にする: {s_}→{t_} = {v_}")
            spec.append((s_, t_, v_, rest[0] if rest else None))
            for n in (s_, t_):
                if n not in ins:
                    ins[n], outs[n] = [], []
                    order.append(n)
            outs[s_].append((t_, v_))
            ins[t_].append((s_, v_))
        insum = {n: sum(v for _, v in ins[n]) for n in order}
        outsum = {n: sum(v for _, v in outs[n]) for n in order}
        val = {n: max(insum[n], outsum[n]) for n in order}
        fmt = value_fmt or fmt_num
        for n in order:
            if insum[n] and outsum[n] and abs(insum[n] - outsum[n]) > 0.005 * max(insum[n], outsum[n]):
                self.warnings.append(f"サンキー: 「{n}」に入る量 {fmt(insum[n])} と出る量 {fmt(outsum[n])} が合わない"
                                     "（太さは大きいほう。足りない分は「その他」の帯に）")
        if columns is None:
            layer = {n: 0 for n in order}
            for _ in range(len(order) + 1):
                changed = False
                for s_, t_, _v, _c in spec:
                    if layer[t_] < layer[s_] + 1:
                        layer[t_] = layer[s_] + 1
                        changed = True
                if not changed:
                    break
            else:
                raise ValueError("links に輪（循環）がある")
            columns = [[n for n in order if layer[n] == c] for c in range(max(layer.values()) + 1)]
        else:
            flat = [n for c in columns for n in c]
            if len(flat) != len(set(flat)) or set(flat) != set(order):
                raise ValueError("columns には links に出る名前を 1 回ずつ入れる")
        col_of = {n: c for c, names in enumerate(columns) for n in names}
        for s_, t_, _v, _c in spec:
            if col_of[t_] <= col_of[s_]:
                raise ValueError(f"帯は左の段から右の段へ: {s_}→{t_}")
        ncol = len(columns)
        k = min((h - gap * (len(c) - 1)) / sum(val[n] for n in c) for c in columns)
        if k <= 0:
            raise ValueError("高さ h が足りない（gap を小さくするか h を大きくする）")
        xs = [x + (w - node_w) * c / max(1, ncol - 1) for c in range(ncol)]
        ypos = {}
        for names in columns:
            col_h = sum(val[n] * k for n in names) + gap * (len(names) - 1)
            yy = y + (h - col_h) / 2 if valign == "center" else y
            for n in names:
                ypos[n] = yy
                yy += val[n] * k + gap

        def center(n):
            return ypos[n] + val[n] * k / 2

        def settle(names):
            prev = y - gap
            for n in names:
                ypos[n] = max(ypos[n], prev + gap)
                prev = ypos[n] + val[n] * k
            if prev > y + h:
                nxt = y + h + gap
                for n in reversed(names):
                    ypos[n] = min(ypos[n], nxt - gap - val[n] * k)
                    nxt = ypos[n]

        for _ in range(iterations):
            for cols_, side in ((range(1, ncol), ins), (range(ncol - 2, -1, -1), outs)):
                for c in cols_:
                    for n in columns[c]:
                        pairs = side[n]
                        if pairs:
                            ypos[n] = sum(center(m) * v for m, v in pairs) / sum(v for _, v in pairs) - val[n] * k / 2
                    settle(columns[c])
        slot_out, slot_in = {}, {}
        for n in order:
            off = 0.0
            for i, (s_, t_, v_, _c) in sorted([e for e in enumerate(spec) if e[1][0] == n],
                                              key=lambda e: (center(e[1][1]), e[0])):
                slot_out[i] = ypos[n] + off
                off += v_ * k
            off = 0.0
            for i, (s_, t_, v_, _c) in sorted([e for e in enumerate(spec) if e[1][1] == n],
                                              key=lambda e: (center(e[1][0]), e[0])):
                slot_in[i] = ypos[n] + off
                off += v_ * k
        accent, dim = self.series[0], self._dim or "#BBBBBB"
        main_set = set(main or [])

        def ncolor(n):
            if colors and n in colors:
                return colors[n]
            return accent if (not main_set or n in main_set) else dim

        for i, (s_, t_, v_, c_) in enumerate(spec):
            th = v_ * k
            x0, x1 = xs[col_of[s_]] + node_w, xs[col_of[t_]]
            ya, yb = slot_out[i], slot_in[i]
            xm = (x0 + x1) / 2
            if c_:
                col = c_
            elif main_set:
                col = accent if (s_ in main_set and t_ in main_set) else dim
            else:
                col = ncolor(s_)
            d = (f"M{x0:.1f},{ya:.1f} C{xm:.1f},{ya:.1f} {xm:.1f},{yb:.1f} {x1:.1f},{yb:.1f} "
                 f"L{x1:.1f},{yb + th:.1f} C{xm:.1f},{yb + th:.1f} {xm:.1f},{ya + th:.1f} {x0:.1f},{ya + th:.1f} Z")
            self.parts.append(f'<path d="{d}" fill="{col}" fill-opacity="{link_alpha}" stroke="none"/>')
        info = {}
        for c, names in enumerate(columns):
            for n in names:
                hn = val[n] * k
                x0 = xs[c]
                self.rect(x0, ypos[n], node_w, hn, fill=ncolor(n))
                self._track(x0, ypos[n], x0 + node_w, ypos[n] + hn, f"帯「{n}」")
                if hn < 2:
                    self.warnings.append(f"サンキー: 「{n}」の帯が細すぎる（{hn:.1f}px）。「その他」にまとめるか h を大きく")
                cy = ypos[n] + hn / 2
                if c == 0:
                    ax, anc, halo = x0 - 6, "end", False
                elif c == ncol - 1:
                    ax, anc, halo = x0 + node_w + 6, "start", False
                else:
                    ax, anc, halo = x0 + node_w + 6, "start", True
                bold = n in main_set
                if hn >= label_size * 2.7:
                    self.text(ax, cy - label_size * 0.2, n, size=label_size, anchor=anc, bold=bold, halo=halo)
                    self.text(ax, cy + label_size * 1.15, fmt(val[n]), size=label_size, anchor=anc, color=MUTED, halo=halo)
                else:
                    self.text(ax, cy + label_size * 0.35, f"{n}　{fmt(val[n])}", size=label_size, anchor=anc,
                              bold=bold, halo=halo)
                info[n] = {"x0": x0, "y0": ypos[n], "x1": x0 + node_w, "y1": ypos[n] + hn, "value": val[n], "col": c}
        if col_labels:
            for c, lab in enumerate(col_labels):
                self.text(xs[c] + node_w / 2, y - 10, lab, size=label_size, color=MUTED)
        return info

    def scatter(self, x, y, w, h, groups, xlim=None, ylim=None, xticks=None, yticks=None, xlabel="", ylabel="",
                xfmt=fmt_num, yfmt=fmt_num, diag=False, diag_label="y = x", main=0, alpha=None, r=4.5,
                unit="", note=None):
        """groups に name、xs、ys を持つ系列を渡す。diag=True で y = x の参照線を引く。"""
        allx = [v for g in groups for v in g["xs"]]
        ally = [v for g in groups for v in g["ys"]]
        ntot = len(allx)
        if any(len(g["xs"]) != len(g["ys"]) for g in groups):
            raise ValueError("各群の xs と ys の数をそろえる")
        if ntot > 2000:
            self.warnings.append(f"点が {ntot} 個。svglib ではなく matplotlib で描いて SVG/PNG を埋め込む（SKILL の決まり）")

        def pad(lo, hi):
            p = (hi - lo) * 0.06 or 1
            return lo - p, hi + p
        if diag and xlim is None and ylim is None:
            xlim = ylim = pad(min(allx + ally), max(allx + ally))
        xlim = xlim or pad(min(allx), max(allx))
        ylim = ylim or pad(min(ally), max(ally))
        xticks = xticks if xticks is not None else nice_ticks(*xlim)
        yticks = yticks if yticks is not None else nice_ticks(*ylim)
        sx, sy = self._axes(x, y, w, h, xlim, ylim, xticks, yticks, xlabel, ylabel, xfmt, yfmt)
        if diag:
            lo, hi = max(xlim[0], ylim[0]), min(xlim[1], ylim[1])
            self.parts.append(f'<line x1="{sx(lo):.1f}" y1="{sy(lo):.1f}" x2="{sx(hi):.1f}" y2="{sy(hi):.1f}" '
                              f'stroke="{MUTED}" stroke-width="1.2" stroke-dasharray="5 4"/>')
            if diag_label:
                self.text(sx(hi) + 6, sy(hi) + 4, diag_label, size=12, anchor="start", color=MUTED)  # 線の端の外（線と交わらない）
        use_main = self._compare is not None and main is not None and len(groups) > 1
        order = [i for i in range(len(groups)) if not (use_main and i == main)] + ([main] if use_main else [])
        self.parts.append('<g data-chart="scatter">')
        styles = {}
        for i in order:
            g = groups[i]
            k = len(g["xs"])
            op = alpha if alpha is not None else (0.8 if k <= 50 else 0.5 if k <= 500 else 0.15)
            if use_main:
                col = g.get("color", self.series[0] if i == main else self._compare)
                rank = 0 if i == main else 1 + [j for j in range(len(groups)) if j != main].index(i)
            else:
                col = g.get("color", self.series[i % len(self.series)])
                rank = i
            shape = g.get("marker", SHAPES[rank % len(SHAPES)])
            styles[i] = (col, shape)
            self.parts.append(f'<g data-series="{_attr(g.get("name", i))}" data-marker="{shape}">')
            for a, b in zip(g["xs"], g["ys"]):
                self.parts.append(_shape(sx(a), sy(b), r, shape, col, "#ffffff", 0.8, opacity=op))
            self.parts.append("</g>")
        self.parts.append("</g>")
        if len(groups) > 1:
            items = [(styles[i][0], f"{g.get('name', i)}（n = {len(g['xs'])}）", {"marker": styles[i][1], "line": False})
                     for i, g in enumerate(groups)]
            self.legend(x, y - 10, items, size=12, horizontal=True)
        elif note is None:
            note = f"点＝{'各 ' + unit if unit else '1 件'}（n = {ntot}{' ' + unit if unit else ''}）"
        if note:
            self._note(x, y - (28 if len(groups) > 1 else 10), note)
        self._last = dict(kind="scatter", horizontal=False, x=x, y=y, w=w, h=h, v2px=sy, sx=sx, vrange=ylim)
        return sx, sy

    # ---------- 出力 ----------
    def svg(self, title: str | None = None, desc: str | None = None) -> str:
        extra = ""
        if self.place_mm:
            extra = f' data-place-mm="{self.place_mm:g}" data-target="{self.target}"'
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.W} {self.H}" '
            f'width="{self.W}" height="{self.H}"{extra} font-family="{FONT}" fill="{INK}">'
        )
        meta = []
        t = title if title is not None else self._title
        if t:
            meta.append(f"<title>{esc(t)}</title>")
        if desc:
            meta.append(f"<desc>{esc(desc)}</desc>")
        return "\n".join([head, *meta, '<rect width="100%" height="100%" fill="#ffffff"/>', *self.parts, "</svg>"]) + "\n"

    def _check_text_overlap(self) -> None:
        b = self._text_boxes
        for i in range(len(b)):
            for j in range(i + 1, len(b)):
                ax0, ay0, ax1, ay1, at = b[i]
                bx0, by0, bx1, by1, bt = b[j]
                ox = min(ax1, bx1) - max(ax0, bx0)
                oy = min(ay1, by1) - max(ay0, by0)
                if ox > 2 and oy > 0.5:
                    self.warnings.append(f"文字どうしが重なっている: 「{at[:14]}」と「{bt[:14]}」")

    def _check_line_overlap(self, svg: str | None = None) -> None:
        """隣の check_svg.py の検査（線と文字の重なり・最終の字・対比・白黒の系列・字の大きさの種類・書き方）を、
        できあがった SVG にそのままかける。"""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("zukai_check_svg", Path(__file__).with_name("check_svg.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            svg = svg or self.svg()
            if hasattr(mod, "figure_warnings"):
                self.warnings.extend(mod.figure_warnings(svg))
            else:
                self.warnings.extend(mod.overlap_messages(svg))
        except Exception as e:  # noqa: BLE001  検査の失敗で保存を止めない
            self.warnings.append(f"SVG の検査ができなかった: {e}")

    def save(self, path: str | Path, quiet: bool = False, title: str | None = None, desc: str | None = None) -> Path:
        """保存して警告を表示する。title は <title>（無ければ Fig の title）、
        desc は <desc>（図の下に置く「何をどう可視化しているか」の 1 文を入れる）。"""
        out = self.svg(title, desc)
        self._check_text_overlap()
        self._check_line_overlap(out)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(out, encoding="utf-8")
        if not quiet:
            size = f"{self.W}x{self.H}"
            if self.place_mm:
                size += f"、置く幅 {self.place_mm:g}mm で 12px = {self.pt(12):.1f}pt"
            print(f"saved {p} ({size})")
            for wmsg in dict.fromkeys(self.warnings):
                print("  ⚠", wmsg)
        return p
