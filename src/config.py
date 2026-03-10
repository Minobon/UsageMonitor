"""定数・設定値"""

import os
import sys
import ctypes

# API設定
API_BASE_URL = "https://api.anthropic.com"
USAGE_ENDPOINT = "/api/oauth/usage"
ANTHROPIC_BETA = "oauth-2025-04-20"

# ポーリング設定
POLL_INTERVAL_SEC = 60
POLL_BACKOFF_MAX_SEC = 600

# 認証情報パス
CREDENTIALS_PATH = os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".claude", "usage_monitor_settings.json")

# プロジェクトルート (PyInstaller frozen EXE ではバンドル先)
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    PROJECT_ROOT = sys._MEIPASS
else:
    # src/ の親 = プロジェクトルート
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")

# DPIスケール係数（実行時に計算）
try:
    _dpi = ctypes.windll.user32.GetDpiForSystem()
except Exception:
    _dpi = 96
DPI_SCALE = _dpi / 96.0

# --- Claude テーマカラー ---
BG_COLOR = "#1C1B1A"          # ダークベース
BG_BORDER = "#3D3836"         # ボーダー
ACCENT_COLOR = "#D97757"      # Claudeテラコッタオレンジ
TEXT_COLOR = "#F5F0EB"         # テキスト（白系）
SUB_TEXT_COLOR = "#8B7E74"     # サブテキスト（グレー系）
BAR_BG_COLOR = "#3D3836"      # バー背景

# プログレスバーの色
COLOR_CLAUDE = "#D97757"       # Claudeオレンジ
COLOR_ORANGE = "#E8A838"       # 警告アンバー
COLOR_RED = "#E05252"          # 危険レッド
COLOR_GRAY = "#5C534D"        # 無効・エラー用グレー
ANTIGRAVITY_BAR_COLOR = "#4285F4"  # Googleブルー

# タイマーインジケーターのドット
TIMER_DOT_ACTIVE = "#E8D44D"   # 黄色（残り時間）
TIMER_DOT_SPENT = "#F5F0EB"    # 白（経過時間）

# ウィジェット設定
FLOATING_OPACITY = 0.75
FLOATING_HOVER_OPACITY = 1.0

# フォント設定（ポイントサイズ。tkinterがDPI処理するためスケーリング不要）
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_BOLD = "Segoe UI Semibold"
FONT_SIZE_NORMAL = 9
FONT_SIZE_SMALL = 8
FONT_SIZE_TINY = 7


def bar_color(percent: float) -> str:
    """使用率に応じたバーの色を返す。"""
    return COLOR_CLAUDE
