"""デュアルモードウィジェット (tkinter)"""

import json
import os
import logging
import tkinter as tk
from PIL import Image, ImageTk

from config import (
    FLOATING_OPACITY, FLOATING_HOVER_OPACITY,
    FONT_FAMILY, FONT_SIZE_TINY,
    SETTINGS_PATH, DPI_SCALE, CREDENTIALS_PATH, ASSETS_DIR,
    TEXT_COLOR, BAR_BG_COLOR,
)
from models import UsageData, CodexUsageData, AntigravityUsageData, ProfileData
from ui.drawing import get_taskbar_rect, WidgetRenderer
from ui.timer import TimerIndicator

# アイコンパス
CLAUDE_ICON_PATH = os.path.join(ASSETS_DIR, "claude_icon.png")
CODEX_ICON_PATH = os.path.join(ASSETS_DIR, "codex_icon.png")
ANTIGRAVITY_ICON_PATH = os.path.join(ASSETS_DIR, "antigravity_icon.png")

# Codex認証パス（サービス層に依存しないローカル定義）
_CODEX_AUTH_PATH = os.path.join(os.path.expanduser("~"), ".codex", "auth.json")

log = logging.getLogger(__name__)


class UsageWidget:
    """デュアルモード使用状況モニターウィジェット。"""

    MODE_FULL = "full"
    MODE_COMPACT = "compact"

    # 基本サイズ（DPI/UIスケーリング前）
    _BASE_W = 310
    _BASE_H_NONE = 40         # サービス未設定時
    _SECTION_H_2BAR = 72      # 2バーサービスのセクション高さ
    _AG_NOTE_H = 14           # Antigravity注記の行高さ
    _COMPACT_ROW_H = 20       # コンパクトモードの行高さ
    _COMPACT_PAD = 6          # コンパクトモードの上下余白
    _BASE_H_COMPACT_NONE = 30 # コンパクト・サービス未設定時
    _TIMER_H = 22             # タイマーインジケーターの高さ

    def __init__(self, root: tk.Tk):
        self.root = root
        self.mode = self.MODE_FULL
        self.usage_data: UsageData | None = None
        self.codex_data: CodexUsageData | None = None
        self.antigravity_data: AntigravityUsageData | None = None
        self.profile: ProfileData | None = None
        self._codex_email = ""
        self._codex_plan = ""
        self._antigravity_email = ""
        self._antigravity_plan = ""
        self._hover = False
        self._opacity = FLOATING_OPACITY
        self._ui_scale = 1.0
        self._has_claude = os.path.exists(CREDENTIALS_PATH)
        self._has_codex = os.path.exists(_CODEX_AUTH_PATH)
        self._has_antigravity = os.path.exists(os.path.join(os.environ.get("APPDATA", ""), "Antigravity"))

        # タイマーインジケーターの状態
        self._show_timer = True
        self._last_poll_time = None
        self._poll_interval_sec = 60
        self._refill_duration = 1.0
        self._timer_y_base = 0

        # レンダラーとタイマーの初期化
        self.renderer = WidgetRenderer(self)
        self.timer = TimerIndicator(self)

        # ドラッグ状態
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._dragging = False

        # 透過キーカラー（角の抜き用）
        self._trans_color = "#F0F0F1"

        # ウィンドウの設定
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", FLOATING_OPACITY)
        self.root.attributes("-transparentcolor", self._trans_color)
        self.root.configure(bg=self._trans_color)

        # キャンバス（初期サイズ、_apply_modeでリサイズされる）
        self.canvas = tk.Canvas(
            self.root, highlightthickness=0, bg=self._trans_color,
            width=self._us(self._BASE_W), height=self._us(self._current_height_base()),
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # イベントバインド
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<Button-3>", self._on_right_click)

        # コンテキストメニュー
        self.ctx_menu = tk.Menu(self.root, tearoff=0)
        self.ctx_menu.add_command(label="更新", command=self._on_refresh)
        self.ctx_menu.add_command(label="コンパクト表示 切替", command=self._toggle_mode)
        self.ctx_menu.add_command(label="更新タイマー 切替", command=self._toggle_timer)
        self.ctx_menu.add_command(label="透明度...", command=self._show_opacity_slider)
        self.ctx_menu.add_command(label="表示スケール...", command=self._show_scale_slider)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="終了", command=self._on_exit)

        self._refresh_callback = None
        self._exit_callback = None
        self._center_callback = None

        # アイコン元画像（リスケール用に保持）
        self._claude_icon_src = None
        self._codex_icon_src = None
        self._antigravity_icon_src = None
        self._claude_icon_full = None
        self._claude_icon_compact = None
        self._codex_icon_full = None
        self._codex_icon_compact = None
        self._antigravity_icon_full = None
        self._antigravity_icon_compact = None
        try:
            self._claude_icon_src = Image.open(CLAUDE_ICON_PATH)
        except Exception:
            log.warning("Could not load Claude icon", exc_info=True)
        try:
            self._codex_icon_src = Image.open(CODEX_ICON_PATH)
        except Exception:
            log.warning("Could not load Codex icon", exc_info=True)
        try:
            self._antigravity_icon_src = Image.open(ANTIGRAVITY_ICON_PATH)
        except Exception:
            log.warning("Could not load Antigravity icon", exc_info=True)
        self._reload_icons()

        # タスクバー矩形をキャッシュ
        self._tb_rect = get_taskbar_rect()

        # 保存された設定を読み込み（_ui_scaleが更新される場合あり）
        self._load_settings()

        # 保存されたスケールでアイコンを再読み込み
        self._reload_icons()

        # 初期位置
        if not hasattr(self, "_saved_x"):
            screen_w = self.root.winfo_screenwidth()
            tb_top = self._tb_rect[1]
            self._saved_x = screen_w - self._us(self._BASE_W) - self._us(20)
            self._saved_y = tb_top - self._us(self._current_height_base()) - self._us(10)

        self._apply_mode()
        self.draw()

    # --- スケーリングヘルパー ---

    def _us(self, px) -> int:
        """ピクセル値をDPI係数とUIスケールで拡縮する。"""
        return int(px * DPI_SCALE * self._ui_scale)

    def _fs(self, base_pt) -> int:
        """フォントのポイントサイズをUIスケールで拡縮する。"""
        return max(1, int(base_pt * self._ui_scale))

    def _reload_icons(self):
        """現在のスケールでアイコンを再読み込みする。"""
        size_full = self._us(20)
        size_compact = self._us(18)
        if self._claude_icon_src:
            try:
                self._claude_icon_full = ImageTk.PhotoImage(
                    self._claude_icon_src.resize((size_full, size_full), Image.LANCZOS))
                self._claude_icon_compact = ImageTk.PhotoImage(
                    self._claude_icon_src.resize((size_compact, size_compact), Image.LANCZOS))
            except Exception:
                log.warning("Could not resize Claude icon", exc_info=True)
        if self._codex_icon_src:
            try:
                self._codex_icon_full = ImageTk.PhotoImage(
                    self._codex_icon_src.resize((size_full, size_full), Image.LANCZOS))
                self._codex_icon_compact = ImageTk.PhotoImage(
                    self._codex_icon_src.resize((size_compact, size_compact), Image.LANCZOS))
            except Exception:
                log.warning("Could not resize Codex icon", exc_info=True)
        if self._antigravity_icon_src:
            try:
                self._antigravity_icon_full = ImageTk.PhotoImage(
                    self._antigravity_icon_src.resize((size_full, size_full), Image.LANCZOS))
                self._antigravity_icon_compact = ImageTk.PhotoImage(
                    self._antigravity_icon_src.resize((size_compact, size_compact), Image.LANCZOS))
            except Exception:
                log.warning("Could not resize Antigravity icon", exc_info=True)

    def _service_count(self) -> int:
        """利用可能なサービス数を返す（0〜3）。"""
        return int(self._has_claude) + int(self._has_codex) + int(self._has_antigravity)

    def _current_height_base(self) -> int:
        """モードとサービス有無に応じた基本高さ（未スケール）を返す。"""
        count = self._service_count()
        if self.mode == self.MODE_COMPACT:
            if count == 0:
                return self._BASE_H_COMPACT_NONE
            return self._COMPACT_PAD * 2 + self._COMPACT_ROW_H * count
        if count == 0:
            return self._BASE_H_NONE
        # セクション高さの合計 + 2pxの余白
        total = 2
        if self._has_claude:
            total += self._SECTION_H_2BAR
        if self._has_codex:
            total += self._SECTION_H_2BAR
        if self._has_antigravity:
            total += self._SECTION_H_2BAR + self._AG_NOTE_H
        if self._show_timer:
            total += self._TIMER_H
        return total

    def set_refresh_callback(self, cb):
        self._refresh_callback = cb

    def set_exit_callback(self, cb):
        self._exit_callback = cb

    def set_center_callback(self, cb):
        self._center_callback = cb

    # --- 設定の永続化 ---

    def _load_settings(self):
        try:
            if os.path.exists(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r") as f:
                    s = json.load(f)
                self.mode = s.get("mode", self.MODE_FULL)
                self._saved_x = s.get("x", None)
                self._saved_y = s.get("y", None)
                self._opacity = s.get("opacity", FLOATING_OPACITY)
                self._ui_scale = s.get("ui_scale", 1.0)
                self._show_timer = s.get("show_timer", True)
                if self._saved_x is not None:
                    return
        except Exception:
            pass

    def _save_settings(self):
        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            data = {
                "mode": self.mode, "x": x, "y": y,
                "opacity": self._opacity, "ui_scale": self._ui_scale,
                "show_timer": self._show_timer,
            }
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, "w") as f:
                json.dump(data, f)
        except Exception:
            log.debug("Failed to save settings", exc_info=True)

    # --- モード切替 ---

    def _toggle_mode(self):
        self.timer.stop()
        if self.mode == self.MODE_FULL:
            self.mode = self.MODE_COMPACT
        else:
            self.mode = self.MODE_FULL
        self._apply_mode()
        self.draw()
        if self.mode == self.MODE_FULL and self._last_poll_time and self._service_count() > 0 and self._show_timer:
            self.timer.start()
        self._save_settings()

    def _toggle_timer(self):
        self._show_timer = not self._show_timer
        self.timer.stop()
        self._apply_mode()
        self.draw()
        if self._show_timer and self.mode == self.MODE_FULL and self._last_poll_time and self._service_count() > 0:
            self.timer.start()
        self._save_settings()

    def _apply_mode(self):
        if self.mode == self.MODE_COMPACT:
            self._apply_compact()
        else:
            self._apply_full()

    def _apply_full(self):
        self.mode = self.MODE_FULL
        w = self._us(self._BASE_W)
        h = self._us(self._current_height_base())
        self.canvas.config(width=w, height=h)
        self.root.geometry(f"{w}x{h}+{self._saved_x}+{self._saved_y}")
        self.root.attributes("-alpha", self._opacity)

    def _apply_compact(self):
        self.mode = self.MODE_COMPACT
        w = self._us(280)
        h = self._us(self._current_height_base())
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.canvas.config(width=w, height=h)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.attributes("-alpha", self._opacity)

    def _resize_for_services(self):
        """サービスの有無が変わった場合にウィンドウをリサイズする。"""
        h_new = self._us(self._current_height_base())
        if self.mode == self.MODE_FULL:
            w = self._us(self._BASE_W)
        else:
            w = self._us(280)
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.canvas.config(width=w, height=h_new)
        self.root.geometry(f"{w}x{h_new}+{x}+{y}")

    # --- メイン描画 ---

    def draw(self):
        self.canvas.delete("all")
        if self.mode == self.MODE_COMPACT:
            self.renderer.draw_compact()
        else:
            self.renderer.draw_full()

    # --- イベントハンドラー ---

    def _on_enter(self, event):
        self._hover = True
        self.root.attributes("-alpha", FLOATING_HOVER_OPACITY)

    def _on_leave(self, event):
        self._hover = False
        self.root.attributes("-alpha", self._opacity)

    def _on_press(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._dragging = False

    def _on_drag(self, event):
        self._dragging = True
        x = self.root.winfo_x() + (event.x - self._drag_start_x)
        y = self.root.winfo_y() + (event.y - self._drag_start_y)

        # タスクバー領域へのドラッグを防止
        tb_top = self._tb_rect[1]
        win_h = self.root.winfo_height()
        max_y = tb_top - win_h
        if y > max_y:
            y = max_y

        self.root.geometry(f"+{x}+{y}")

    def _on_release(self, event):
        if not self._dragging:
            return
        self._saved_x = self.root.winfo_x()
        self._saved_y = self.root.winfo_y()
        self._save_settings()

    def _show_opacity_slider(self):
        """透明度スライダーのポップアップを表示する。"""
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#2A2826")

        pw, ph = self._us(200), self._us(80)
        x = self.root.winfo_x() + (self.root.winfo_width() - pw) // 2
        y = self.root.winfo_y() - ph - self._us(8)
        popup.geometry(f"{pw}x{ph}+{x}+{y}")

        label = tk.Label(popup, text="マウスオーバーしていないときの透明度", fg=TEXT_COLOR, bg="#2A2826",
                          font=(FONT_FAMILY, self._fs(FONT_SIZE_TINY)))
        label.pack(pady=(self._us(4), 0))

        var = tk.IntVar(value=int(self._opacity * 100))

        def on_change(val):
            self._opacity = int(val) / 100
            if not self._hover:
                self.root.attributes("-alpha", self._opacity)

        slider = tk.Scale(popup, from_=20, to=100, orient=tk.HORIZONTAL,
                           variable=var, command=on_change, showvalue=True,
                           bg="#2A2826", fg=TEXT_COLOR, troughcolor=BAR_BG_COLOR,
                           highlightthickness=0, sliderrelief=tk.FLAT,
                           font=(FONT_FAMILY, self._fs(FONT_SIZE_TINY)))
        slider.pack(fill=tk.X, padx=self._us(8))

        def on_close():
            self._save_settings()
            popup.destroy()

        close_btn = tk.Button(popup, text="OK", command=on_close,
                               bg="#3D3836", fg=TEXT_COLOR, relief=tk.FLAT,
                               font=(FONT_FAMILY, self._fs(FONT_SIZE_TINY)),
                               padx=self._us(12), pady=0)
        close_btn.pack(pady=(self._us(2), self._us(4)))

        popup.bind("<Escape>", lambda e: on_close())

    def _show_scale_slider(self):
        """UIスケールスライダーのポップアップを表示する。"""
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#2A2826")

        pw, ph = self._us(200), self._us(80)
        x = self.root.winfo_x() + (self.root.winfo_width() - pw) // 2
        y = self.root.winfo_y() - ph - self._us(8)
        popup.geometry(f"{pw}x{ph}+{x}+{y}")

        label = tk.Label(popup, text="表示スケール", fg=TEXT_COLOR, bg="#2A2826",
                          font=(FONT_FAMILY, self._fs(FONT_SIZE_TINY)))
        label.pack(pady=(self._us(4), 0))

        var = tk.IntVar(value=int(self._ui_scale * 100))

        def on_change(val):
            self._ui_scale = int(val) / 100
            self._reload_icons()
            self._apply_mode()
            self.draw()

        slider = tk.Scale(popup, from_=50, to=300, orient=tk.HORIZONTAL,
                           variable=var, command=on_change, showvalue=True,
                           resolution=10,
                           bg="#2A2826", fg=TEXT_COLOR, troughcolor=BAR_BG_COLOR,
                           highlightthickness=0, sliderrelief=tk.FLAT,
                           font=(FONT_FAMILY, self._fs(FONT_SIZE_TINY)))
        slider.pack(fill=tk.X, padx=self._us(8))

        def on_close():
            self._save_settings()
            popup.destroy()

        close_btn = tk.Button(popup, text="OK", command=on_close,
                               bg="#3D3836", fg=TEXT_COLOR, relief=tk.FLAT,
                               font=(FONT_FAMILY, self._fs(FONT_SIZE_TINY)),
                               padx=self._us(12), pady=0)
        close_btn.pack(pady=(self._us(2), self._us(4)))

        popup.bind("<Escape>", lambda e: on_close())

    def _on_right_click(self, event):
        self.ctx_menu.tk_popup(event.x_root, event.y_root)

    def _on_refresh(self):
        if self._refresh_callback:
            self._refresh_callback()

    def _on_center(self):
        if self._center_callback:
            self._center_callback()

    def _on_exit(self):
        self.timer.stop()
        if self._exit_callback:
            self._exit_callback()
        else:
            self._save_settings()
            self.root.quit()

    # --- 外部公開API ---

    def update_profile(self, profile: ProfileData):
        self.profile = profile

    def update_codex_profile(self, email: str, plan: str):
        """Codexプロフィール情報を更新する（main.pyから呼ばれる）。"""
        self._codex_email = email
        self._codex_plan = plan

    def update_antigravity_profile(self, email: str, plan: str):
        """Antigravityプロフィール情報を更新する（main.pyから呼ばれる）。"""
        self._antigravity_email = email
        self._antigravity_plan = plan

    def notify_poll_complete(self, interval_sec):
        """ポーリング完了をウィジェットに通知する。タイマーアニメーションを開始する。"""
        self.timer.notify_poll_complete(interval_sec)

    def update_data(self, data: UsageData | None):
        """Claude使用状況データを更新する。Noneの場合はClaude未設定。"""
        had_claude = self._has_claude
        self._has_claude = data is not None
        self.usage_data = data
        if had_claude != self._has_claude:
            self._resize_for_services()
        self.draw()

    def update_codex_data(self, data: CodexUsageData | None):
        """Codex使用状況データを更新する。Noneの場合はCodex未設定。"""
        had_codex = self._has_codex
        self._has_codex = data is not None
        self.codex_data = data
        # 有無が変わった場合リサイズ
        if had_codex != self._has_codex:
            self._resize_for_services()
        self.draw()

    def update_antigravity_data(self, data: AntigravityUsageData | None):
        """Antigravity使用状況データを更新する。Noneの場合はAntigravity未実行。"""
        had_ag = self._has_antigravity
        self._has_antigravity = data is not None
        self.antigravity_data = data
        # 有無が変わった場合リサイズ
        if had_ag != self._has_antigravity:
            self._resize_for_services()
