"""描画ロジック"""

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone

from config import (
    BG_COLOR, BG_BORDER, TEXT_COLOR, SUB_TEXT_COLOR, BAR_BG_COLOR,
    FONT_FAMILY, FONT_FAMILY_BOLD, COLOR_GRAY,
    FONT_SIZE_NORMAL, FONT_SIZE_SMALL, FONT_SIZE_TINY,
    bar_color, ANTIGRAVITY_BAR_COLOR,
)

CODEX_BAR_COLOR = "#10A37F"

_AG_WINDOW_SEC = 5 * 3600  # Antigravityの推定ウィンドウ: 5時間


def _ag_elapsed_ratio(bucket) -> float:
    """Antigravityバケットの経過割合を計算する。

    残り時間が5時間以下の場合のみ黄色マーカーを表示する。
    """
    if not bucket or not bucket.resets_at:
        return 0.0
    remaining = max(0, (bucket.resets_at - datetime.now(timezone.utc)).total_seconds())
    if remaining > _AG_WINDOW_SEC:
        return 0.0
    elapsed = _AG_WINDOW_SEC - remaining
    return max(0.0, min(1.0, elapsed / _AG_WINDOW_SEC))


# Windows API（タスクバー検出用）
class APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uCallbackMessage", wintypes.UINT),
        ("uEdge", wintypes.UINT),
        ("rc", wintypes.RECT),
        ("lParam", wintypes.LPARAM),
    ]

ABM_GETTASKBARPOS = 5


def get_taskbar_rect() -> tuple[int, int, int, int]:
    """Windowsタスクバーの矩形(left, top, right, bottom)を返す。"""
    try:
        shell32 = ctypes.windll.shell32
        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(APPBARDATA)
        shell32.SHAppBarMessage(ABM_GETTASKBARPOS, ctypes.byref(abd))
        return abd.rc.left, abd.rc.top, abd.rc.right, abd.rc.bottom
    except Exception:
        return 0, 1040, 1920, 1080


class WidgetRenderer:
    """UsageWidgetの描画を担当するクラス。"""

    def __init__(self, widget):
        self.w = widget  # UsageWidget参照

    # --- 描画プリミティブ ---

    def _draw_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        c = self.w.canvas
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return c.create_polygon(points, smooth=True, splinesteps=32, **kw)

    def _draw_progress_bar(self, x, y, w, h, pct, elapsed_ratio=0.0, color=None, radius=None):
        """指定位置(x, y)にプログレスバーを描画する。"""
        us = self.w._us
        if radius is None:
            radius = us(4)
        if color is None:
            color = bar_color(pct)
        c = self.w.canvas
        self._draw_rounded_rect(x, y, x + w, y + h, radius, fill=BAR_BG_COLOR, outline="")
        if pct > 0:
            fill_w = max(h, w * min(pct, 100) / 100)
            self._draw_rounded_rect(x, y, x + fill_w, y + h, radius, fill=color, outline="")
        # 経過時間マーカー（黄色線）
        if elapsed_ratio > 0:
            marker_x = x + int(w * min(elapsed_ratio, 1.0))
            marker_x = max(x + radius, min(marker_x, x + w - radius))
            c.create_line(marker_x, y, marker_x, y + h, fill="#E8D44D", width=us(2))

    def _draw_icon(self, cx, cy, icon_img):
        """指定の中心座標(cx, cy)にアイコンを描画する。"""
        if icon_img:
            self.w.canvas.create_image(cx, cy, image=icon_img, anchor="center")

    # --- フルモード描画 ---

    def draw_full(self):
        w = self.w
        c = w.canvas
        us = w._us
        width = us(w._BASE_W)
        h = us(w._current_height_base())
        count = w._service_count()

        # 背景
        self._draw_rounded_rect(1, 1, width - 1, h - 1, us(10), fill=BG_COLOR, outline=BG_BORDER)

        if count == 0:
            c.create_text(width // 2, h // 2, text="No credentials configured",
                           fill=COLOR_GRAY, anchor="center",
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_NORMAL)))
            return

        # セクションを動的に描画（区切り線付き）
        y_offset = 0
        drawn = 0

        if w._has_claude:
            if drawn > 0:
                sep_y = us(y_offset)
                c.create_line(us(14), sep_y, width - us(14), sep_y,
                               fill=BG_BORDER, width=1)
            base_y = y_offset
            self._draw_service_header(
                y=us(base_y + 17), label="Claude",
                icon=w._claude_icon_full, profile=w.profile, w_px=width,
            )
            self._draw_service_bars_full(
                data=w.usage_data,
                row1_y=us(base_y + 37), row2_y=us(base_y + 57),
                w_px=width, bar_color_override=None,
            )
            y_offset += w._SECTION_H_2BAR
            drawn += 1

        if w._has_codex:
            if drawn > 0:
                sep_y = us(y_offset)
                c.create_line(us(14), sep_y, width - us(14), sep_y,
                               fill=BG_BORDER, width=1)
            base_y = y_offset
            self._draw_codex_header_full(y=us(base_y + 17), w_px=width)
            self._draw_codex_bars_full(
                data=w.codex_data,
                row1_y=us(base_y + 37), row2_y=us(base_y + 57), w_px=width,
            )
            y_offset += w._SECTION_H_2BAR
            drawn += 1

        if w._has_antigravity:
            if drawn > 0:
                sep_y = us(y_offset)
                c.create_line(us(14), sep_y, width - us(14), sep_y,
                               fill=BG_BORDER, width=1)
            base_y = y_offset
            self._draw_antigravity_header_full(y=us(base_y + 17), w_px=width)
            self._draw_antigravity_bars_full(
                data=w.antigravity_data,
                row1_y=us(base_y + 37), row2_y=us(base_y + 57),
                w_px=width,
            )
            note_y = us(base_y + w._SECTION_H_2BAR + 3)
            c.create_text(width // 2, note_y,
                           text="*Antigravity quota is shown in 20% increments due to API limitations",
                           fill=SUB_TEXT_COLOR, anchor="center",
                           font=(FONT_FAMILY, w._fs(6)))
            y_offset += w._SECTION_H_2BAR + w._AG_NOTE_H

        # タイマーインジケーター
        if count > 0 and w._show_timer:
            w._timer_y_base = y_offset
            w.timer.draw()

    def _draw_codex_header_full(self, y, w_px):
        """フルモード用のCodexサービスヘッダーを描画する。"""
        w = self.w
        codex_info_parts = []
        if w._codex_email:
            codex_info_parts.append(w._codex_email)
        plan = w._codex_plan or (w.codex_data.plan_type if w.codex_data else "")
        if plan:
            codex_info_parts.append(plan.capitalize())
        self._draw_service_header(
            y=y, label="Codex",
            icon=w._codex_icon_full,
            plan_text=" \u00B7 ".join(codex_info_parts) if codex_info_parts else "",
            w_px=w_px,
        )

    def _draw_service_header(self, y, label, icon, w_px, profile=None, plan_text=None):
        """サービスヘッダー行を描画する（アイコン＋名前＋プロフィール/プラン）。"""
        w = self.w
        c = w.canvas
        us = w._us
        self._draw_icon(us(16), y, icon)
        c.create_text(us(30), y, text=label, fill=TEXT_COLOR, anchor="w",
                       font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_NORMAL)))

        # 右寄せ情報
        if profile and profile.email:
            parts = [profile.email]
            if profile.plan:
                parts.append(profile.plan)
            c.create_text(w_px - us(10), y, text=" \u00B7 ".join(parts),
                           fill=SUB_TEXT_COLOR, anchor="e", font=(FONT_FAMILY, w._fs(FONT_SIZE_TINY)))
        elif plan_text:
            c.create_text(w_px - us(10), y, text=plan_text,
                           fill=SUB_TEXT_COLOR, anchor="e", font=(FONT_FAMILY, w._fs(FONT_SIZE_TINY)))

    def _draw_service_bars_full(self, data, row1_y, row2_y, w_px, bar_color_override=None):
        """フルモード用の使用状況バー2本（Claude形式）を描画する。"""
        w = self.w
        c = w.canvas
        us = w._us
        label_x = us(14)
        bar_x = us(40)
        bar_w = us(170)
        bar_h = us(8)
        pct_x = bar_x + bar_w + us(6)
        reset_x = w_px - us(10)
        bar_nudge = us(1)

        if data and data.error:
            c.create_text(w_px // 2, (row1_y + row2_y) // 2, text=data.error, fill=COLOR_GRAY,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_NORMAL)), anchor="center")
            return

        if not data or not data.five_hour:
            c.create_text(w_px // 2, (row1_y + row2_y) // 2, text="Loading...", fill=SUB_TEXT_COLOR,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_NORMAL)), anchor="center")
            return

        # 行1: 5時間枠
        pct5 = data.five_hour.utilization
        c.create_text(label_x, row1_y, text="5h", fill=SUB_TEXT_COLOR, anchor="w",
                       font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
        self._draw_progress_bar(bar_x, row1_y - bar_h // 2 + bar_nudge,
                                 bar_w, bar_h, pct5,
                                 elapsed_ratio=data.five_hour.elapsed_ratio(),
                                 color=bar_color_override)
        c.create_text(pct_x, row1_y, text=f"{pct5:.0f}%", fill=TEXT_COLOR, anchor="w",
                       font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_SMALL)))
        reset_txt = data.five_hour.resets_in_text()
        if reset_txt:
            c.create_text(reset_x, row1_y, text=reset_txt, fill=SUB_TEXT_COLOR,
                           anchor="e", font=(FONT_FAMILY, w._fs(FONT_SIZE_TINY)))

        # 行2: 1週間枠
        if data.seven_day:
            pct7 = data.seven_day.utilization
            c.create_text(label_x, row2_y, text="1w", fill=SUB_TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
            self._draw_progress_bar(bar_x, row2_y - bar_h // 2 + bar_nudge,
                                     bar_w, bar_h, pct7,
                                     elapsed_ratio=data.seven_day.elapsed_ratio(),
                                     color=bar_color_override)
            c.create_text(pct_x, row2_y, text=f"{pct7:.0f}%", fill=TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_SMALL)))
            reset_txt7 = data.seven_day.resets_in_text()
            if reset_txt7:
                c.create_text(reset_x, row2_y, text=reset_txt7, fill=SUB_TEXT_COLOR,
                               anchor="e", font=(FONT_FAMILY, w._fs(FONT_SIZE_TINY)))

    def _draw_codex_bars_full(self, data, row1_y, row2_y, w_px):
        """フルモード用のCodex使用状況バーを描画する。"""
        w = self.w
        c = w.canvas
        us = w._us
        label_x = us(14)
        bar_x = us(40)
        bar_w = us(170)
        bar_h = us(8)
        pct_x = bar_x + bar_w + us(6)
        reset_x = w_px - us(10)
        bar_nudge = us(1)

        if data and data.error:
            c.create_text(w_px // 2, (row1_y + row2_y) // 2, text=data.error, fill=COLOR_GRAY,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_NORMAL)), anchor="center")
            return

        if not data or not data.primary:
            c.create_text(w_px // 2, (row1_y + row2_y) // 2, text="Loading...", fill=SUB_TEXT_COLOR,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_NORMAL)), anchor="center")
            return

        # プライマリウィンドウ
        pct1 = data.primary.utilization
        c.create_text(label_x, row1_y, text=data.primary.name, fill=SUB_TEXT_COLOR, anchor="w",
                       font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
        self._draw_progress_bar(bar_x, row1_y - bar_h // 2 + bar_nudge,
                                 bar_w, bar_h, pct1,
                                 elapsed_ratio=data.primary.elapsed_ratio(),
                                 color=CODEX_BAR_COLOR)
        c.create_text(pct_x, row1_y, text=f"{pct1:.0f}%", fill=TEXT_COLOR, anchor="w",
                       font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_SMALL)))
        reset_txt = data.primary.resets_in_text()
        if reset_txt:
            c.create_text(reset_x, row1_y, text=reset_txt, fill=SUB_TEXT_COLOR,
                           anchor="e", font=(FONT_FAMILY, w._fs(FONT_SIZE_TINY)))

        # セカンダリウィンドウ
        if data.secondary:
            pct2 = data.secondary.utilization
            c.create_text(label_x, row2_y, text=data.secondary.name, fill=SUB_TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
            self._draw_progress_bar(bar_x, row2_y - bar_h // 2 + bar_nudge,
                                     bar_w, bar_h, pct2,
                                     elapsed_ratio=data.secondary.elapsed_ratio(),
                                     color=CODEX_BAR_COLOR)
            c.create_text(pct_x, row2_y, text=f"{pct2:.0f}%", fill=TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_SMALL)))
            reset_txt2 = data.secondary.resets_in_text()
            if reset_txt2:
                c.create_text(reset_x, row2_y, text=reset_txt2, fill=SUB_TEXT_COLOR,
                               anchor="e", font=(FONT_FAMILY, w._fs(FONT_SIZE_TINY)))

    def _draw_antigravity_header_full(self, y, w_px):
        """フルモード用のAntigravityサービスヘッダーを描画する。"""
        w = self.w
        info_parts = []
        if w._antigravity_email:
            info_parts.append(w._antigravity_email)
        if w._antigravity_plan:
            info_parts.append(w._antigravity_plan)
        self._draw_service_header(
            y=y, label="Antigravity",
            icon=w._antigravity_icon_full,
            plan_text=" \u00B7 ".join(info_parts) if info_parts else "",
            w_px=w_px,
        )

    def _draw_antigravity_bars_full(self, data, row1_y, row2_y, w_px):
        """Antigravityの使用状況バー2本（G3, 3rd）を描画する。"""
        w = self.w
        c = w.canvas
        us = w._us
        label_x = us(14)
        bar_x = us(40)
        bar_w = us(170)
        bar_h = us(8)
        pct_x = bar_x + bar_w + us(6)
        reset_x = w_px - us(10)
        bar_nudge = us(1)

        if data and data.error:
            c.create_text(w_px // 2, (row1_y + row2_y) // 2, text=data.error, fill=COLOR_GRAY,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_NORMAL)), anchor="center")
            return

        if not data or not data.gemini3:
            c.create_text(w_px // 2, (row1_y + row2_y) // 2, text="Loading...", fill=SUB_TEXT_COLOR,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_NORMAL)), anchor="center")
            return

        for row_y, bucket in [(row1_y, data.gemini3), (row2_y, data.third_party)]:
            if bucket is None:
                continue
            pct = bucket.utilization
            c.create_text(label_x, row_y, text=bucket.name, fill=SUB_TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
            elapsed = _ag_elapsed_ratio(bucket)
            self._draw_progress_bar(bar_x, row_y - bar_h // 2 + bar_nudge,
                                     bar_w, bar_h, pct,
                                     elapsed_ratio=elapsed,
                                     color=ANTIGRAVITY_BAR_COLOR)
            c.create_text(pct_x, row_y, text=f"{pct:.0f}%", fill=TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_SMALL)))
            reset_txt = bucket.resets_in_text()
            if reset_txt:
                c.create_text(reset_x, row_y, text=reset_txt, fill=SUB_TEXT_COLOR,
                               anchor="e", font=(FONT_FAMILY, w._fs(FONT_SIZE_TINY)))

    # --- コンパクトモード描画 ---

    def draw_compact(self):
        w = self.w
        c = w.canvas
        us = w._us
        width = int(c.cget("width"))
        h = int(c.cget("height"))
        count = w._service_count()

        # 背景
        self._draw_rounded_rect(1, 1, width - 1, h - 1, us(6), fill=BG_COLOR, outline=BG_BORDER)

        if count == 0:
            c.create_text(width // 2, h // 2, text="No credentials configured",
                           fill=COLOR_GRAY, anchor="center",
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
            return

        # サービス描画関数のリストを構築
        rows = []
        if w._has_claude:
            rows.append(lambda y: self._draw_compact_row(y, w.usage_data, w._claude_icon_compact, bar_color_override=None))
        if w._has_codex:
            rows.append(lambda y: self._draw_compact_codex_row(y, w.codex_data, w._codex_icon_compact))
        if w._has_antigravity:
            rows.append(lambda y: self._draw_compact_antigravity_row(y, w.antigravity_data, w._antigravity_icon_compact))

        pad = us(w._COMPACT_PAD)
        row_h = us(w._COMPACT_ROW_H)
        for i, draw_fn in enumerate(rows):
            mid_y = pad + row_h * i + row_h // 2
            draw_fn(mid_y)

    def _draw_compact_row(self, mid_y, data, icon, bar_color_override=None):
        """Claude用のコンパクト行を描画する。"""
        w = self.w
        c = w.canvas
        us = w._us
        bar_h = us(6)
        bar_w = us(70)

        self._draw_icon(us(20), mid_y, icon)
        x = us(36)

        if data and data.error:
            c.create_text(x, mid_y, text=data.error, fill=COLOR_GRAY,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)), anchor="w")
            return

        if not data or not data.five_hour:
            c.create_text(x, mid_y, text="...", fill=SUB_TEXT_COLOR,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)), anchor="w")
            return

        # 5時間枠
        pct5 = data.five_hour.utilization
        c.create_text(x, mid_y, text="5h", fill=SUB_TEXT_COLOR, anchor="w",
                       font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
        x += us(18)
        self._draw_progress_bar(x, mid_y - bar_h // 2 + us(1), bar_w, bar_h, pct5,
                                 elapsed_ratio=data.five_hour.elapsed_ratio(),
                                 color=bar_color_override)
        x += bar_w + us(4)
        c.create_text(x, mid_y, text=f"{pct5:.0f}%", fill=TEXT_COLOR, anchor="w",
                       font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_SMALL)))

        # 1週間枠
        x += us(28)
        if data.seven_day:
            pct7 = data.seven_day.utilization
            c.create_text(x, mid_y, text="1w", fill=SUB_TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
            x += us(18)
            self._draw_progress_bar(x, mid_y - bar_h // 2 + us(1), bar_w, bar_h, pct7,
                                     elapsed_ratio=data.seven_day.elapsed_ratio(),
                                     color=bar_color_override)
            x += bar_w + us(4)
            c.create_text(x, mid_y, text=f"{pct7:.0f}%", fill=TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_SMALL)))

    def _draw_compact_codex_row(self, mid_y, data, icon):
        """Codex用のコンパクト行を描画する。"""
        w = self.w
        c = w.canvas
        us = w._us
        bar_h = us(6)
        bar_w = us(70)

        self._draw_icon(us(20), mid_y, icon)
        x = us(36)

        if data and data.error:
            c.create_text(x, mid_y, text=data.error, fill=COLOR_GRAY,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)), anchor="w")
            return

        if not data or not data.primary:
            c.create_text(x, mid_y, text="...", fill=SUB_TEXT_COLOR,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)), anchor="w")
            return

        # プライマリ
        pct1 = data.primary.utilization
        c.create_text(x, mid_y, text=data.primary.name, fill=SUB_TEXT_COLOR, anchor="w",
                       font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
        x += us(18)
        self._draw_progress_bar(x, mid_y - bar_h // 2 + us(1), bar_w, bar_h, pct1,
                                 elapsed_ratio=data.primary.elapsed_ratio(),
                                 color=CODEX_BAR_COLOR)
        x += bar_w + us(4)
        c.create_text(x, mid_y, text=f"{pct1:.0f}%", fill=TEXT_COLOR, anchor="w",
                       font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_SMALL)))

        # セカンダリ
        x += us(28)
        if data.secondary:
            pct2 = data.secondary.utilization
            c.create_text(x, mid_y, text=data.secondary.name, fill=SUB_TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
            x += us(18)
            self._draw_progress_bar(x, mid_y - bar_h // 2 + us(1), bar_w, bar_h, pct2,
                                     elapsed_ratio=data.secondary.elapsed_ratio(),
                                     color=CODEX_BAR_COLOR)
            x += bar_w + us(4)
            c.create_text(x, mid_y, text=f"{pct2:.0f}%", fill=TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_SMALL)))

    def _draw_compact_antigravity_row(self, mid_y, data, icon):
        """Antigravity用のコンパクト行を描画する（2バー、Codexと同形式）。"""
        w = self.w
        c = w.canvas
        us = w._us
        bar_h = us(6)
        bar_w = us(70)

        self._draw_icon(us(20), mid_y, icon)
        x = us(36)

        if data and data.error:
            c.create_text(x, mid_y, text=data.error, fill=COLOR_GRAY,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)), anchor="w")
            return

        if not data or not data.gemini3:
            c.create_text(x, mid_y, text="...", fill=SUB_TEXT_COLOR,
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)), anchor="w")
            return

        for bucket in [data.gemini3, data.third_party]:
            if bucket is None:
                continue
            pct = bucket.utilization
            c.create_text(x, mid_y, text=bucket.name, fill=SUB_TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY, w._fs(FONT_SIZE_SMALL)))
            x += us(18)
            elapsed = _ag_elapsed_ratio(bucket)
            self._draw_progress_bar(x, mid_y - bar_h // 2 + us(1), bar_w, bar_h, pct,
                                     elapsed_ratio=elapsed,
                                     color=ANTIGRAVITY_BAR_COLOR)
            x += bar_w + us(4)
            c.create_text(x, mid_y, text=f"{pct:.0f}%", fill=TEXT_COLOR, anchor="w",
                           font=(FONT_FAMILY_BOLD, w._fs(FONT_SIZE_SMALL)))
            x += us(28)
