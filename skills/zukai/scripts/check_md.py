"""Markdown の図を点検する。SVG の内部の点検は check_svg.py。

使い方: python3 check_md.py README.md [report.md ...]

ローカル画像のファイル、リポジトリ内の相対パス、図の直下の説明文を確認する。
コードブロックで全角文字と空白を使って揃えた図にも警告する。
終了コードは 0 = 問題なし、1 = 画像ファイルの欠落、2 = 警告のみ。
"""
import pathlib, re, subprocess, sys

IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
FW = r"[　-ヿ㐀-鿿！-｠]"
ALIGN = re.compile(FW + r"[^\n]*?(?: {3,}|[─━]{3,}|-{3,}>?|={3,}>?)\s*\S")
DECOR = re.compile(r"[┌┐└┘│─━▶▼◀▲→←↓↑⇒]|-->|<--|==>|\+-{2,}")


def top_of(p):
    r = subprocess.run(["git", "-C", str(p.parent), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return pathlib.Path(r.stdout.strip()).resolve() if r.returncode == 0 and r.stdout.strip() else p.parent.resolve()


def check(path):
    p = pathlib.Path(path)
    top = top_of(p)
    text = p.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    broken, warns = [], []
    for i, line in enumerate(lines):
        for m in IMG.finditer(line):
            src = m.group(2)
            if src.startswith(("http://", "https://", "data:")):
                continue
            name = m.group(1)[:20] or src.split("/")[-1]
            target = pathlib.Path(src) if src.startswith("/") else p.parent / src
            inside = str(target.resolve()).startswith(str(top) + "/")
            if src.startswith("/") or not inside:
                warns.append(f"{i + 1}行目 {name}: 絶対パスか、リポジトリ（git の外ならこのフォルダ）の外を指している（{src}）。VS Code のプレビューで出ないことがある")
            if not target.exists():
                broken.append(f"{i + 1}行目 {name}: 図のファイルが無い（{src}）")
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = lines[j].strip() if j < len(lines) else ""
            no_caption = (not nxt or nxt.startswith(("#", "![", "|", "```", "<", "---"))
                          or len(re.sub(r"\s", "", nxt)) < 15)
            if no_caption and not IMG.search(line[m.end():]):
                warns.append(f"{i + 1}行目 {name}: 図のすぐ下に、何をどう可視化しているかの文が無い"
                             "（軸・1 つの点や棒や色が何か・どこを見ればよいかを 1〜3 行）")
    for m in re.finditer(r"```([^\n]*)\n(.*?)```", text, re.S):
        if m.group(1).strip() not in ("", "text", "txt", "plain"):
            continue
        body = m.group(2)
        n = sum(1 for l in body.splitlines() if ALIGN.search(l))
        if n >= 2 and DECOR.search(body):
            warns.append(f"{text[:m.start()].count(chr(10)) + 1}行目: 文字で描いた図（全角の後ろで桁をそろえた行が {n} 行）。"
                         "全角は 2 桁なのでずれる。SVG に描き直す")
    return broken, warns


def main(paths):
    worst = 0
    for f in paths:
        broken, warns = check(f)
        if not broken and not warns:
            print(f"✓ {f}")
            continue
        print(f"{'✗' if broken else '⚠'} {f}")
        for b in broken:
            print(f"  ✗ {b}")
        for w in warns:
            print(f"  ⚠ {w}")
        worst = max(worst, 1 if broken else 2) if worst != 1 else 1
    return worst


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
