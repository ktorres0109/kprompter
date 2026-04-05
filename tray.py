import platform
import threading
import os
import subprocess

SYSTEM = platform.system()


def build_tray(on_settings, on_log, on_quit):
    """Build and return a pystray Icon. Caller must call icon.run() in a thread."""
    try:
        import pystray
        from PIL import Image as PILImage
    except ImportError:
        return None

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if not os.path.exists(icon_path):
        from icon_gen import generate
        generate()

    img = PILImage.open(icon_path)

    menu = pystray.Menu(
        pystray.MenuItem("KPrompter", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Settings", lambda: _call(on_settings)),
        pystray.MenuItem("View Log", lambda: _call(on_log)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda: _call(on_quit)),
    )

    icon = pystray.Icon("KPrompter", img, "KPrompter", menu)
    return icon


def _call(fn):
    threading.Thread(target=fn, daemon=True).start()
