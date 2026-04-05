"""
Generates KPrompter's icon: a terminal-style 'K>' prompt mark.
Writes assets/icon.png and assets/icon.svg
"""
import struct
import zlib
import math
import os

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(ASSET_DIR, exist_ok=True)

SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#13161c"/>
      <stop offset="100%" stop-color="#0d0f13"/>
    </linearGradient>
    <linearGradient id="glow" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#4af0a0"/>
      <stop offset="100%" stop-color="#3dd8f0"/>
    </linearGradient>
    <filter id="blur">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- Background rounded rect -->
  <rect width="64" height="64" rx="14" fill="url(#bg)"/>

  <!-- Subtle border -->
  <rect width="63" height="63" x="0.5" y="0.5" rx="13.5"
        fill="none" stroke="#2a2f3d" stroke-width="1"/>

  <!-- Glow halo behind text -->
  <text x="32" y="41" text-anchor="middle"
        font-family="'JetBrains Mono','Menlo','Consolas',monospace"
        font-weight="700" font-size="26"
        fill="#4af0a0" opacity="0.18" filter="url(#blur)">K&gt;</text>

  <!-- Main K> text -->
  <text x="32" y="41" text-anchor="middle"
        font-family="'JetBrains Mono','Menlo','Consolas',monospace"
        font-weight="700" font-size="26"
        fill="url(#glow)">K&gt;</text>

  <!-- Cursor blink bar -->
  <rect x="43" y="31" width="5" height="3" rx="1" fill="#4af0a0" opacity="0.7"/>
</svg>
"""


def write_svg():
    path = os.path.join(ASSET_DIR, "icon.svg")
    with open(path, "w") as f:
        f.write(SVG)
    return path


def write_png_fallback():
    """
    Write a minimal 64x64 PNG without Pillow.
    Dark background with a white 'K' shape drawn pixel-by-pixel.
    Used only if cairosvg / Pillow not available.
    """
    size = 64
    pixels = [[(13, 15, 19)] * size for _ in range(size)]

    # Draw a simple 'K' at 20x20 starting at (14, 20)
    # Vertical bar of K
    for y in range(20, 44):
        pixels[y][14] = (74, 240, 160)
        pixels[y][15] = (74, 240, 160)

    # Upper diagonal of K (top-right)
    for i in range(12):
        y = 20 + i
        x = 17 + i
        if 0 <= x < size and 0 <= y < size:
            pixels[y][x] = (74, 240, 160)
            if x + 1 < size:
                pixels[y][x + 1] = (74, 240, 160)

    # Lower diagonal of K (bottom-right)
    for i in range(12):
        y = 32 + i
        x = 29 - i
        if 0 <= x < size and 0 <= y < size:
            pixels[y][x] = (74, 240, 160)
            if x + 1 < size:
                pixels[y][x + 1] = (74, 240, 160)

    # Draw '>' at x=36
    for i in range(6):
        pixels[26 + i][36 + i] = (61, 216, 240)
        pixels[26 + i][37 + i] = (61, 216, 240)
    for i in range(6):
        pixels[38 - i][36 + i] = (61, 216, 240)
        pixels[38 - i][37 + i] = (61, 216, 240)

    # Encode as PNG
    def make_png(pixels, size):
        def png_chunk(name, data):
            crc = zlib.crc32(name + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)

        raw = b""
        for row in pixels:
            raw += b"\x00"  # filter type none
            for r, g, b in row:
                raw += bytes([r, g, b])

        compressed = zlib.compress(raw, 9)
        ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
        png = b"\x89PNG\r\n\x1a\n"
        png += png_chunk(b"IHDR", ihdr)
        png += png_chunk(b"IDAT", compressed)
        png += png_chunk(b"IEND", b"")
        return png

    path = os.path.join(ASSET_DIR, "icon.png")
    with open(path, "wb") as f:
        f.write(make_png(pixels, size))
    return path


def generate():
    svg_path = write_svg()
    png_path = os.path.join(ASSET_DIR, "icon.png")

    # Try cairosvg first
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=64, output_height=64)
        return png_path
    except ImportError:
        pass

    # Try Pillow + aggdraw or just Pillow
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (64, 64), (13, 15, 19, 255))
        draw = ImageDraw.Draw(img)
        # Rounded rect border
        draw.rounded_rectangle([0, 0, 63, 63], radius=13,
                                outline=(42, 47, 61, 255), width=1)
        # Text (fallback font)
        try:
            font = ImageFont.truetype("Menlo.ttc", 22)
        except Exception:
            try:
                font = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 22)
            except Exception:
                font = ImageFont.load_default()
        draw.text((8, 18), "K>", fill=(74, 240, 160, 255), font=font)
        img.save(png_path, "PNG")
        return png_path
    except ImportError:
        pass

    # Pure fallback
    return write_png_fallback()


if __name__ == "__main__":
    p = generate()
    print(f"Icon written: {p}")
