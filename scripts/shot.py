#!/usr/bin/env python3
"""shot.py — 用本地 Chrome 无头模式给 HTML 截图（不依赖 playwright）。

用法：
  python scripts/shot.py <html_path> <out_png> [width] [height] [--no-trim]

说明：
  - 给足窗口高度再裁掉四周纯色空白，避免内容被截断
  - 需要 Pillow 才能裁剪；无 Pillow 则保留原始尺寸
  - 使用 --force-device-scale-factor=2 输出 2x 高清图
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome() -> str:
    for p in CHROME_CANDIDATES:
        if Path(p).exists():
            return p
    raise SystemExit("no Chrome/Edge found")


def shoot(chrome: str, html_path: Path, out_png: Path, width: int, height: int) -> bool:
    out_png = out_png.resolve()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    url = "file:///" + str(html_path.resolve()).replace("\\", "/")
    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=2",
        f"--screenshot={out_png}",
        f"--window-size={width},{height}",
        "--virtual-time-budget=2000",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not out_png.exists():
        print(f"  FAIL: {r.stderr[:300]}")
        return False
    return True


def trim(png: Path, pad: int = 24) -> None:
    """裁掉四周纯色空白（以左上角像素为背景色）。需 Pillow。"""
    try:
        from PIL import Image
    except ImportError:
        return

    im = Image.open(png).convert("RGB")
    w, h = im.size
    bg = im.getpixel((1, 1))
    px = im.load()

    def is_bg(x: int, y: int) -> bool:
        c = px[x, y]
        return abs(c[0] - bg[0]) <= 3 and abs(c[1] - bg[1]) <= 3 and abs(c[2] - bg[2]) <= 3

    def scan_row_reversed(top: bool):
        """返回第一个非背景行（从顶或底向内扫）。"""
        rng = range(h) if top else range(h - 1, -1, -1)
        for y in rng:
            for x in range(0, w, 5):
                if not is_bg(x, y):
                    return y
        return 0 if top else h - 1

    top = scan_row_reversed(True)
    bottom = scan_row_reversed(False)
    if bottom <= top:
        return

    def scan_col_in_range(y0: int, y1: int, left: bool):
        rng = range(w) if left else range(w - 1, -1, -1)
        for x in rng:
            for y in range(y0, y1, 5):
                if not is_bg(x, y):
                    return x
        return 0 if left else w - 1

    left = scan_col_in_range(top, bottom, True)
    right = scan_col_in_range(top, bottom, False)
    if right <= left:
        return

    box = (
        max(0, left - pad), max(0, top - pad),
        min(w, right + pad + 1), min(h, bottom + pad + 1),
    )
    im.crop(box).save(png)


def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    do_trim = "--no-trim" not in args
    args = [a for a in args if a != "--no-trim"]

    if len(args) < 2:
        print("usage: shot.py <html_path> <out_png> [width] [height] [--no-trim]")
        return 2

    html_path = Path(args[0])
    out_png = Path(args[1])
    width = int(args[2]) if len(args) > 2 else 900
    height = int(args[3]) if len(args) > 3 else 3200

    if not html_path.exists():
        print(f"html not found: {html_path}")
        return 1

    chrome = find_chrome()
    if not shoot(chrome, html_path, out_png, width, height):
        return 1

    if do_trim:
        trim(out_png)

    from PIL import Image  # noqa: F401  (optional, for size report)
    try:
        w, h = Image.open(out_png).size
    except Exception:
        w = h = -1

    print(json.dumps({
        "ok": True, "file": str(out_png),
        "bytes": out_png.stat().st_size, "size": f"{w}x{h}",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
