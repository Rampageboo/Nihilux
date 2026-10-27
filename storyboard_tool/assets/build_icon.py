"""Build every app icon from the Nihilux master artwork.

The master (``icon_master.png``) is the square head-and-shoulders artwork.
This script rounds its corners and writes the desktop icon (``icon.ico`` /
``icon.png``), the backend favicons, and the React app's favicon and brand
mark. Re-run it after replacing the master.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
STATIC = ROOT.parent / "web" / "static"
FRONTEND_PUBLIC = REPO / "frontend" / "public"
SPLASH = REPO / "desktop" / "splash"
MASTER = ROOT / "icon_master.png"

CORNER_RATIO = 0.22
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def rounded(image: Image.Image, size: int) -> Image.Image:
    """Square-crop, resize and round the corners with 4x supersampled edges."""
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    square = image.crop((left, top, left + side, top + side)).convert("RGBA")
    square = square.resize((size, size), Image.LANCZOS)
    big = size * 4
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=int(big * CORNER_RATIO), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(square, mask=mask.resize((size, size), Image.LANCZOS))
    return out


def main() -> None:
    master = Image.open(MASTER)
    icon = rounded(master, 256)
    STATIC.mkdir(parents=True, exist_ok=True)
    FRONTEND_PUBLIC.mkdir(parents=True, exist_ok=True)

    icon.save(ROOT / "icon.png", format="PNG")
    icon.save(STATIC / "favicon.png", format="PNG")
    icon.save(SPLASH / "icon.png", format="PNG")  # desktop shell start-up page
    for target in (ROOT / "icon.ico", STATIC / "favicon.ico"):
        icon.save(target, format="ICO", sizes=ICO_SIZES)
    rounded(master, 64).save(FRONTEND_PUBLIC / "favicon.png", format="PNG")
    rounded(master, 128).save(FRONTEND_PUBLIC / "brand-mark.png", format="PNG")
    print(f"Wrote icons to {ROOT}, {STATIC}, {SPLASH} and {FRONTEND_PUBLIC}")


if __name__ == "__main__":
    main()
