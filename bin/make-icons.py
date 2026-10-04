#!/usr/bin/env python3
"""从上游 icon.png 生成带圆角的 dsh 应用图标 8 档。

圆角遮罩半径 23%（Ubuntu Yaru 观感），5x 超采样后降采样以获得抗锯齿边缘。
源图自带的 alpha 与遮罩相乘，不破坏原有透明区。
"""
import os
from PIL import Image, ImageDraw, ImageChops

SRC = os.path.expanduser("~/Project/dsh-desktop/dsh-src/apps/desktop/resources/icon.png")
OUT_ROOT = os.path.expanduser("~/Project/dsh-desktop/icons")
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
RADIUS_RATIO = 0.23
SUPER_SAMPLE = 5


def rounded_mask(size: int, radius_ratio: float) -> Image.Image:
    """生成 size x size 的圆角遮罩（L 模式），超采样后降采样抗锯齿。"""
    big = size * SUPER_SAMPLE
    r = int(big * radius_ratio)
    m = Image.new("L", (big, big), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [0, 0, big - 1, big - 1], radius=r, fill=255
    )
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

    mask = rounded_mask(w, RADIUS_RATIO)
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
