"""タイマーインジケーター"""

import time

from config import (
    BG_BORDER, SUB_TEXT_COLOR, TIMER_DOT_ACTIVE, TIMER_DOT_SPENT,
    FONT_FAMILY, FONT_SIZE_TINY,
)
from ui.tray import _load_version


class TimerIndicator:
    """更新タイマーのドットインジケーターを管理するクラス。"""

    def __init__(self, widget):
        self.w = widget  # UsageWidget参照
        self._anim_id = None

    @staticmethod
    def _lerp_color(c1, c2, t):
        """2つのHEXカラーを補間する。t=0でc1、t=1でc2。"""
        t = max(0.0, min(1.0, t))
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def draw(self):
        """フルモード下部に更新タイマーのドットを描画する。"""
        w = self.w
        c = w.canvas
        us = w._us
        width = us(w._BASE_W)
        sep_y = us(w._timer_y_base)

        # 区切り線
        c.create_line(us(14), sep_y, width - us(14), sep_y,
                       fill=BG_BORDER, width=1, tags="timer")

        # ドット配置（左寄せ）
        num_dots = 10
        dot_r = us(3)
        center_gap = us(22)
        start_x = us(30)
        center_y = sep_y + us(12)

        # バージョン表示（右端）
        version = _load_version()
        c.create_text(width - us(14), center_y, text=f"v{version}",
                       fill=SUB_TEXT_COLOR, anchor="e",
                       font=(FONT_FAMILY, w._fs(FONT_SIZE_TINY)), tags="timer")

        now = time.time()

        if w._last_poll_time is None:
            # 初回ポーリング前 - 全ドットをアクティブ表示
            for i in range(num_dots):
                cx = start_x + i * center_gap
                c.create_oval(cx - dot_r, center_y - dot_r,
                               cx + dot_r, center_y + dot_r,
                               fill=TIMER_DOT_ACTIVE, outline="", tags="timer")
            return

        elapsed = now - w._last_poll_time
        interval = w._poll_interval_sec
        refill_dur = w._refill_duration

        # フェーズ1: 補充アニメーション（白→黄色）
        if elapsed < refill_dur:
            t = elapsed / refill_dur
            t = 1 - (1 - t) ** 2  # ease-out
            color = self._lerp_color(TIMER_DOT_SPENT, TIMER_DOT_ACTIVE, t)
            for i in range(num_dots):
                cx = start_x + i * center_gap
                c.create_oval(cx - dot_r, center_y - dot_r,
                               cx + dot_r, center_y + dot_r,
                               fill=color, outline="", tags="timer")
            return

        # フェーズ2: カウントダウン（黄色→白、左から右へ）
        countdown_elapsed = elapsed - refill_dur
        countdown_duration = max(1, interval - refill_dur)
        dot_duration = countdown_duration / num_dots

        for i in range(num_dots):
            cx = start_x + i * center_gap
            # 左から右へ: 左端のドットが最初に消える
            dot_start = i * dot_duration
            dot_end = (i + 1) * dot_duration

            if countdown_elapsed < dot_start:
                color = TIMER_DOT_ACTIVE
            elif countdown_elapsed >= dot_end:
                color = TIMER_DOT_SPENT
            else:
                t = (countdown_elapsed - dot_start) / dot_duration
                color = self._lerp_color(TIMER_DOT_ACTIVE, TIMER_DOT_SPENT, t)

            c.create_oval(cx - dot_r, center_y - dot_r,
                           cx + dot_r, center_y + dot_r,
                           fill=color, outline="", tags="timer")

    def start(self):
        """タイマードットのアニメーションループを開始する。"""
        if self._anim_id is None:
            self._tick()

    def stop(self):
        """タイマードットのアニメーションループを停止する。"""
        if self._anim_id is not None:
            self.w.root.after_cancel(self._anim_id)
            self._anim_id = None

    def _tick(self):
        """タイマードットを200msごとに更新する。"""
        w = self.w
        if w.mode != w.MODE_FULL or w._service_count() == 0 or not w._show_timer:
            self._anim_id = None
            return
        w.canvas.delete("timer")
        self.draw()
        self._anim_id = w.root.after(200, self._tick)

    def notify_poll_complete(self, interval_sec):
        """ポーリング完了を通知する。タイマーアニメーションを開始する。"""
        w = self.w
        w._poll_interval_sec = interval_sec
        w._last_poll_time = time.time()
        if w.mode == w.MODE_FULL and w._service_count() > 0 and w._show_timer:
            self.start()
