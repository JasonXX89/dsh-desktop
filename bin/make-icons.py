#!/usr/bin/env python3
"""从上游 icon.png 生成 squircle（超椭圆）造型的 dsh 应用图标 8 档。

遮罩为 superellipse |x|^n + |y|^n <= 1（n=5，iOS 连续曲率观感），
8x 超采样后降采样以获得抗锯齿边缘。
源图自带的 alpha 与遮罩相乘，不破坏原有透明区。
"""
import math
import os
from PIL import Image, ImageDraw, ImageChops

SRC = os.path.expanduser("~/Project/dsh-desktop/dsh-src/apps/desktop/resources/icon.png")
OUT_ROOT = os.path.expanduser("~/Project/dsh-desktop/icons")
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
EXPONENT = 5.0          # 超椭圆指数：4≈微软 Fluent，5≈iOS，∞→直角
SUPER_SAMPLE = 8


def squircle_mask(size: int, n: float = EXPONENT) -> Image.Image:
    """生成 size x size 的超椭圆遮罩（L 模式），超采样多边形 + 降采样抗锯齿。"""
    big = size * SUPER_SAMPLE
    steps = 720
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        # 单位超椭圆参数方程：x = sign(cos t)|cos t|^(2/n)
        c, s = math.cos(t), math.sin(t)
        x = math.copysign(abs(c) ** (2.0 / n), c)
        y = math.copysign(abs(s) ** (2.0 / n), s)
        pts.append(((x + 1) / 2 * (big - 1), (y + 1) / 2 * (big - 1)))
    m = Image.new("L", (big, big), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m.resize((size, size), Image.LANCZOS)


def main() -> None:
    im = Image.open(SRC).convert("RGBA")
    w, h = im.size
    if w != h:
        side = min(w, h)
        im = im.crop(((w - side) // 2, (h - side) // 2,
                      (w - side) // 2 + side, (h - side) // 2 + side))
        w = h = side

    corners = [im.getpixel((2, 2)), im.getpixel((w - 3, 2)),
               im.getpixel((2, h - 3)), im.getpixel((w - 3, h - 3))]
    print(f"  源图 {w}x{h}  四角 alpha={[c[3] for c in corners]}")

    mask = squircle_mask(w)
    im.putalpha(ImageChops.multiply(im.getchannel("A"), mask))

    for s in SIZES:
        d = os.path.join(OUT_ROOT, f"{s}x{s}")
        os.makedirs(d, exist_ok=True)
        im.resize((s, s), Image.LANCZOS).save(
            os.path.join(d, "dsh.png"), "PNG", optimize=True
        )
    print(f"  ✅ 已重生成 {len(SIZES)} 档圆角图标 → {OUT_ROOT}")


if __name__ == "__main__":
    main()
