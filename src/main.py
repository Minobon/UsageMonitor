"""Claude Usage Monitor - エントリーポイント"""

import sys
import os
import logging
import threading
import ctypes

# tkinter importの前にモニターごとのDPI認識を有効化
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import POLL_INTERVAL_SEC, POLL_BACKOFF_MAX_SEC, bar_color
from services import (
    fetch_usage, fetch_profile, fetch_codex_usage, fetch_antigravity_usage,
    get_codex_profile, get_antigravity_profile,
)
from ui import UsageWidget, TrayIcon

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # デフォルトウィンドウを非表示

        # 実際のウィジェットをToplevelとして作成
        self.win = tk.Toplevel(self.root)
        self.win.withdraw()

        # ウィジェットの初期化
        self.widget = UsageWidget(self.win)
        self.widget.set_refresh_callback(self._trigger_refresh)
        self.widget.set_exit_callback(self._exit)
        self.widget.set_center_callback(self._center_widget)

        # トレイアイコンの初期化（コールバックはメインスレッドに転送）
        self.tray = TrayIcon(
            on_show=lambda: self.root.after(0, self._show_widget),
            on_refresh=lambda: self.root.after(0, self._trigger_refresh),
            on_center=lambda: self.root.after(0, self._center_widget),
            on_exit=lambda: self.root.after(0, self._exit),
        )

        # ポーリング状態
        self._poll_interval = POLL_INTERVAL_SEC
        self._poll_timer = None
        self._stop_event = threading.Event()
        self._profile_fetched = False
        self._codex_profile_fetched = False
        self._antigravity_profile_fetched = False

        # ウィンドウ閉じるハンドラ
        self.win.protocol("WM_DELETE_WINDOW", self._exit)

    def run(self):
        log.info("Starting Usage Monitor")

        # トレイアイコン起動
        self.tray.start()

        # ウィンドウを表示
        self.win.deiconify()

        # 初回データ取得を開始
        self._start_polling()

        # tkinterメインループ実行
        self.root.mainloop()

    def _start_polling(self):
        """ポーリングサイクルを開始する。"""
        self._do_poll()

    def _do_poll(self):
        """バックグラウンドスレッドでデータ取得し、UIを更新する。"""
        if self._stop_event.is_set():
            return

        def worker():
            data = fetch_usage()
            profile = None
            if data is not None and not self._profile_fetched:
                profile = fetch_profile()
            codex_data = fetch_codex_usage()
            antigravity_data = fetch_antigravity_usage()
            if not self._stop_event.is_set():
                self.root.after(0, lambda: self._on_data(data, profile, codex_data, antigravity_data))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_data(self, data, profile=None, codex_data=None, antigravity_data=None):
        """取得データでUIを更新する（メインスレッドで呼ばれる）。"""
        if profile:
            self.widget.update_profile(profile)
            self._profile_fetched = True

        # Codexプロフィール取得（JWTデコード、ネットワーク不要）
        if codex_data and not self._codex_profile_fetched:
            email, plan = get_codex_profile()
            if email:
                self.widget.update_codex_profile(email, plan)
                self._codex_profile_fetched = True

        self.widget.update_codex_data(codex_data)

        # Antigravityプロフィール取得（キャッシュ値、ネットワーク不要）
        if antigravity_data and not antigravity_data.error and not self._antigravity_profile_fetched:
            email, plan = get_antigravity_profile()
            if email:
                self.widget.update_antigravity_profile(email, plan)
                self._antigravity_profile_fetched = True

        self.widget.update_antigravity_data(antigravity_data)

        # ポーリング間隔の調整（Claudeデータ取得時のみ）
        if data and data.error and "Rate limited" in (data.error or ""):
            self._poll_interval = min(self._poll_interval * 2, POLL_BACKOFF_MAX_SEC)
        else:
            self._poll_interval = POLL_INTERVAL_SEC

        # 描画前にタイマーへ通知
        self.widget.notify_poll_complete(self._poll_interval)

        self.widget.update_data(data)

        # 次回ポーリングをスケジュール
        self._schedule_next_poll()

    def _schedule_next_poll(self):
        if not self._stop_event.is_set():
            self._poll_timer = self.root.after(
                self._poll_interval * 1000, self._do_poll
            )

    def _trigger_refresh(self):
        """ユーザーによる手動更新。"""
        if self._poll_timer:
            self.root.after_cancel(self._poll_timer)
        self._do_poll()

    def _show_widget(self):
        """ウィジェットウィンドウを表示・前面に移動する。"""
        self.win.deiconify()
        self.win.lift()

    def _center_widget(self):
        """ウィジェットを画面中央に移動して表示する。"""
        self.win.deiconify()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        ww = self.win.winfo_width()
        wh = self.win.winfo_height()
        x = (sw - ww) // 2
        y = (sh - wh) // 2
        self.win.geometry(f"+{x}+{y}")
        self.win.lift()
        self.widget._saved_x = x
        self.widget._saved_y = y
        self.widget._save_settings()

    def _exit(self):
        """安全なシャットダウン。"""
        log.info("Shutting down")
        self._stop_event.set()
        if self._poll_timer:
            self.root.after_cancel(self._poll_timer)
        self.widget._save_settings()
        self.tray.stop()
        self.root.quit()


def main():
    try:
        app = App()
        app.run()
    except Exception:
        log.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
