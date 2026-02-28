"""システムトレイアイコン (pystray)"""

import os
import sys
import logging
import threading
import winreg
from PIL import Image
import pystray

log = logging.getLogger(__name__)

from config import ASSETS_DIR, PROJECT_ROOT

# --- スタートアップ登録 ---
_STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_STARTUP_VALUE_NAME = "UsageMonitor"


def _get_startup_command() -> str:
    """レジストリに登録するコマンド文字列を返す。"""
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    # 開発モード: pythonw で起動
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'main.py'))
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, 'pythonw.exe')
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    return f'"{pythonw}" "{script}"'


def _is_startup_enabled() -> bool:
    """スタートアップが有効かどうかを返す。"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, _STARTUP_VALUE_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def _set_startup_enabled(enabled: bool):
    """スタートアップの有効/無効を切り替える。"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            if enabled:
                winreg.SetValueEx(key, _STARTUP_VALUE_NAME, 0, winreg.REG_SZ, _get_startup_command())
                log.info("Startup enabled: %s", _get_startup_command())
            else:
                try:
                    winreg.DeleteValue(key, _STARTUP_VALUE_NAME)
                except FileNotFoundError:
                    pass
                log.info("Startup disabled")
        finally:
            winreg.CloseKey(key)
    except Exception:
        log.exception("Failed to update startup registry")


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

    @staticmethod
    def _on_toggle_startup(icon, item):
        """スタートアップ登録をトグルする。"""
        _set_startup_enabled(not _is_startup_enabled())

    def _run(self):
        # スタートアップ有効なら現在のexeパスで再登録（バージョン更新に追従）
        if _is_startup_enabled():
            _set_startup_enabled(True)

        version = _load_version()
        menu = pystray.Menu(
            pystray.MenuItem(f"Usage Monitor v{version}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("ウィジェットを表示", self._on_show, default=True),
            pystray.MenuItem("画面中央に移動", self._on_center),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "スタートアップに登録",
                self._on_toggle_startup,
                checked=lambda item: _is_startup_enabled(),
            ),
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
