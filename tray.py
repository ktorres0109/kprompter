import platform
import threading
import os

SYSTEM = platform.system()


def build_tray(on_settings, on_log, on_quit):
    """Build and return a pystray Icon. Caller must call icon.run() in a thread."""
    try:
        import pystray
        from PIL import Image as PILImage
    except (ImportError, ValueError, OSError):
        return None

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if not os.path.exists(icon_path):
        from icon_gen import generate
        generate()

    try:
        img = PILImage.open(icon_path)
    except Exception:
        return None

    menu = pystray.Menu(
        pystray.MenuItem("KPrompter", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Settings", lambda icon, item: _call(on_settings)),
        pystray.MenuItem("View Log", lambda icon, item: _call(on_log)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda icon, item: _call(on_quit)),
    )

    try:
        icon = pystray.Icon("KPrompter", img, "KPrompter", menu)
    except Exception:
        return None
    return icon


def _call(fn):
    threading.Thread(target=fn, daemon=True).start()
