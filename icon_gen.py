"""
Generates KPrompter's icon: terminal-style 'K>' on a dark rounded background.
Produces:
  assets/icon.png   — 1024×1024 (used by PyInstaller on Linux/Windows)
  assets/icon.icns  — macOS icon set (16→1024px, used by PyInstaller on macOS)
"""
import os
import sys
import struct
import zlib


def _asset_dir():
    """Return the assets directory, bundle-aware."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets")
    return os.path.join(os.path.dirname(__file__), "assets")


ASSET_DIR = _asset_dir()
os.makedirs(ASSET_DIR, exist_ok=True)


# ── Pillow renderer ──────────────────────────────────────────────────────────

def _render_pillow(size: int):
    """Return a Pillow Image of the icon at `size`×`size`."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = int(size * 0.22)
    # Dark background
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius,
                            fill=(13, 15, 19, 255))
    # Subtle border
    draw.rounded_rectangle([1, 1, size - 2, size - 2], radius=radius - 1,
                            outline=(50, 58, 82, 255), width=max(1, size // 64))

    # Font size and position — draw centered
    font_size = int(size * 0.44)
    font = _best_font(font_size)

    # Measure text to center it and place cursor correctly
    bbox = draw.textbbox((0, 0), "K>", font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = (size - text_w) // 2 - bbox[0]
    text_y = (size - text_h) // 2 - bbox[1]

    # Glow layer
    draw.text((text_x + 3, text_y + 3), "K>", fill=(74, 240, 160, 35), font=font)
    # Main text
    draw.text((text_x, text_y), "K>", fill=(74, 240, 160, 255), font=font)

    # Cursor block — sits right after "K>" at baseline
    bar_w = max(3, size // 18)
    bar_h = max(4, size // 12)
    bar_x = text_x + text_w + max(2, size // 60)
    bar_y = text_y + text_h - bar_h
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                   fill=(74, 240, 160, 200))

    return img


def _best_font(size: int):
    from PIL import ImageFont
    import platform
    candidates = []
    if platform.system() == "Darwin":
        candidates = [
            "/System/Library/Fonts/Menlo.ttc",
            "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
            "/Library/Fonts/JetBrainsMono-Bold.ttf",
            "/System/Library/Fonts/Monaco.ttf",
            "/System/Library/Fonts/Courier.dfont",
        ]
    elif platform.system() == "Windows":
        candidates = [
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/cour.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


# ── .icns builder ────────────────────────────────────────────────────────────

# Canonical .icns OSType → pixel size mapping.
# Each entry produces one chunk in the .icns file.  We render the master at
# 1024px and resize down for each entry.
_ICNS_ENTRIES = [
    (b"icp4",  16),    # 16×16
    (b"icp5",  32),    # 32×32
    (b"icp6",  64),    # 64×64
    (b"ic07", 128),    # 128×128
    (b"ic08", 256),    # 256×256
    (b"ic09", 512),    # 512×512
    (b"ic10", 1024),   # 1024×1024 (512@2x)
    (b"ic11",  32),    # 16@2x
    (b"ic12",  64),    # 32@2x
    (b"ic13", 256),    # 128@2x
    (b"ic14", 512),    # 256@2x
]


def _png_bytes(img) -> bytes:
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_icns(out_path: str):
    """Build a proper .icns from Pillow-rendered frames."""
    from PIL import Image

    master = _render_pillow(1024)

    chunks = []
    for ostype, px in _ICNS_ENTRIES:
        img = master.resize((px, px), Image.LANCZOS)
        chunks.append((ostype, _png_bytes(img)))

    # Assemble icns file
    body = b""
    for ostype, data in chunks:
        chunk_len = 8 + len(data)
        body += ostype + struct.pack(">I", chunk_len) + data

    total = 8 + len(body)
    with open(out_path, "wb") as f:
        f.write(b"icns" + struct.pack(">I", total) + body)

    return out_path


# ── Pure-Python 1024×1024 PNG fallback (no Pillow) ──────────────────────────

def _make_raw_png(size: int) -> bytes:
    """Minimal 1024×1024 dark PNG with pixel-art K> — no deps."""
    pixels = [[(13, 15, 19)] * size for _ in range(size)]
    green = (74, 240, 160)
    cyan  = (61, 216, 240)

    # Scale factor relative to 64px original
    s = size // 64

    def dot(y, x, color):
        for dy in range(s):
            for dx in range(s):
                ry, rx = y * s + dy, x * s + dx
                if 0 <= ry < size and 0 <= rx < size:
                    pixels[ry][rx] = color

    # Vertical bar of K (col 14-15, rows 20-43)
    for row in range(20, 44):
        dot(row, 14, green)
        dot(row, 15, green)
    # Upper arm of K
    for i in range(12):
        dot(20 + i, 17 + i, green)
        dot(20 + i, 18 + i, green)
    # Lower arm of K
    for i in range(12):
        dot(32 + i, 29 - i, green)
        dot(32 + i, 30 - i, green)
    # > chevron
    for i in range(6):
        dot(26 + i, 36 + i, cyan)
        dot(38 - i, 36 + i, cyan)

    def png_chunk(tag, data):
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b""
    for row in pixels:
        raw += b"\x00"
        for r, g, b in row:
            raw += bytes([r, g, b])

    compressed = zlib.compress(raw, 1)   # level 1 = fast
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + png_chunk(b"IHDR", ihdr)
           + png_chunk(b"IDAT", compressed)
           + png_chunk(b"IEND", b""))
    return png


# ── Public entry point ───────────────────────────────────────────────────────

def generate():
    """
    Generate assets/icon.png (1024×1024) and assets/icon.icns.
    Returns path to icon.png.
    """
    png_path  = os.path.join(ASSET_DIR, "icon.png")
    icns_path = os.path.join(ASSET_DIR, "icon.icns")

    try:
        from PIL import Image  # noqa: F401
        img = _render_pillow(1024)
        img.save(png_path, "PNG")
        # Always build .icns when Pillow is available (needed for CI builds)
        build_icns(icns_path)
        return png_path
    except ImportError:
        pass

    # Fallback: pure-Python PNG
    png_data = _make_raw_png(1024)
    with open(png_path, "wb") as f:
        f.write(png_data)

    # Build a minimal .icns wrapping the PNG so the macOS build always has one
    body = b"ic10" + struct.pack(">I", 8 + len(png_data)) + png_data
    total = 8 + len(body)
    with open(icns_path, "wb") as f:
        f.write(b"icns" + struct.pack(">I", total) + body)

    return png_path


if __name__ == "__main__":
    p = generate()
    print(f"Icon written: {p}")
    import platform
    if platform.system() == "Darwin":
        icns = os.path.join(ASSET_DIR, "icon.icns")
        if os.path.exists(icns):
            print(f"icns written: {icns} ({os.path.getsize(icns)//1024} KB)")
