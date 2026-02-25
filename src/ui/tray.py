"""システムトレイアイコン (pystray)"""

import os
import logging
import threading
from PIL import Image
import pystray

log = logging.getLogger(__name__)

import sys
from config import ASSETS_DIR, PROJECT_ROOT


def _load_version() -> str:
    """VERSION ファイルからバージョン文字列を読み込む。"""
    base = sys._MEIPASS if getattr(sys, 'frozen', False) else PROJECT_ROOT
    try:
        with open(os.path.join(base, "VERSION"), "r") as f:
            return f.read().strip()
    except Exception:
        return "?"

_TRAY_ICON_PATH = os.path.join(ASSETS_DIR, "tray_icon.png")


def _load_tray_icon() -> Image.Image:
    """トレイアイコンを読み込む。"""
    try:
        img = Image.open(_TRAY_ICON_PATH)
        return img.resize((64, 64), Image.LANCZOS)
    except Exception:
        # フォールバック: シンプルな2色アイコン
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.pieslice([4, 4, 60, 60], start=90, end=270, fill="#D97757")
        draw.pieslice([4, 4, 60, 60], start=270, end=90, fill="#10A37F")
        return img


class TrayIcon:
    """メニュー付きシステムトレイアイコン。"""

    def __init__(self, on_show, on_refresh, on_center, on_exit):
        self._on_show = on_show
        self._on_refresh = on_refresh
        self._on_center = on_center
        self._on_exit = on_exit
        self._icon = None
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        version = _load_version()
        menu = pystray.Menu(
            pystray.MenuItem(f"Usage Monitor v{version}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("ウィジェットを表示", self._on_show, default=True),
            pystray.MenuItem("画面中央に移動", self._on_center),
            pystray.MenuItem("更新", self._on_refresh),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("終了", self._on_exit),
        )
        self._icon = pystray.Icon(
            "usage_monitor",
            _load_tray_icon(),
            "Usage Monitor",
            menu,
        )
        self._icon.run()

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
