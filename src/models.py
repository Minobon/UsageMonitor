"""データクラス"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone


@dataclass
class UsageBucket:
    name: str
    utilization: float
    resets_at: Optional[datetime]
    window_seconds: int = 0  # レート制限ウィンドウの期間（秒）

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "UsageBucket":
        resets_at = None
        if data.get("resets_at"):
            resets_at = datetime.fromisoformat(data["resets_at"].replace("Z", "+00:00"))
        return cls(name=name, utilization=data.get("utilization", 0.0), resets_at=resets_at)

    def resets_in_text(self) -> str:
        """リセットまでの残り時間を読みやすい形式で返す。"""
        if not self.resets_at:
            return ""
        now = datetime.now(timezone.utc)
        delta = self.resets_at - now
        total_sec = max(0, int(delta.total_seconds()))
        if total_sec < 60:
            return f"{total_sec}s"
        if total_sec < 3600:
            return f"{total_sec // 60}m"
        hours = total_sec // 3600
        mins = (total_sec % 3600) // 60
        if hours < 24:
            return f"{hours}h {mins:02d}m"
        days = total_sec // 86400
        rem_hours = (total_sec % 86400) // 3600
        rem_mins = (total_sec % 3600) // 60
        return f"{days}d {rem_hours}h {rem_mins:02d}m"

    def resets_at_short(self) -> str:
        """リセット時刻の短いラベルを返す（例: '14:30' や 'Thu'）。"""
        if not self.resets_at:
            return ""
        now = datetime.now(timezone.utc)
        delta = self.resets_at - now
        total_sec = int(delta.total_seconds())
        if total_sec < 86400:
            local = self.resets_at.astimezone()
            return local.strftime("%H:%M")
        return self.resets_at.astimezone().strftime("%a")

    def elapsed_ratio(self) -> float:
        """ウィンドウの経過割合を返す（0.0〜1.0）。"""
        if not self.resets_at:
            return 0.0
        # window_secondsがあればそれを使用、なければ名前から推定
        window_sec = self.window_seconds
        if window_sec == 0:
            if self.name == "5h":
                window_sec = 5 * 3600
            else:
                window_sec = 7 * 86400
        now = datetime.now(timezone.utc)
        remaining_sec = max(0, (self.resets_at - now).total_seconds())
        elapsed_sec = window_sec - remaining_sec
        return max(0.0, min(1.0, elapsed_sec / window_sec))


@dataclass
class UsageData:
    five_hour: Optional[UsageBucket] = None
    seven_day: Optional[UsageBucket] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "UsageData":
        five_hour = UsageBucket.from_dict("5h", data["five_hour"]) if "five_hour" in data else None
        seven_day = UsageBucket.from_dict("1w", data["seven_day"]) if "seven_day" in data else None
        return cls(five_hour=five_hour, seven_day=seven_day, timestamp=datetime.now(timezone.utc))

    @classmethod
    def with_error(cls, msg: str) -> "UsageData":
        return cls(error=msg, timestamp=datetime.now(timezone.utc))


@dataclass
class CodexUsageData:
    primary: Optional[UsageBucket] = None
    secondary: Optional[UsageBucket] = None
    plan_type: str = ""
    error: Optional[str] = None
    timestamp: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "CodexUsageData":
        plan_type = data.get("plan_type", "")
        primary = None
        secondary = None

        rate_limit = data.get("rate_limit") or {}
        if rate_limit:
            pw = rate_limit.get("primary_window")
            if pw:
                window_sec = pw.get("limit_window_seconds", 18000)
                name = _window_label(window_sec)
                resets_at = None
                if pw.get("reset_at"):
                    resets_at = datetime.fromtimestamp(pw["reset_at"], tz=timezone.utc)
                primary = UsageBucket(
                    name=name, utilization=float(pw.get("used_percent", 0)),
                    resets_at=resets_at, window_seconds=window_sec,
                )

            sw = rate_limit.get("secondary_window")
            if sw:
                window_sec = sw.get("limit_window_seconds", 604800)
                name = _window_label(window_sec)
                resets_at = None
                if sw.get("reset_at"):
                    resets_at = datetime.fromtimestamp(sw["reset_at"], tz=timezone.utc)
                secondary = UsageBucket(
                    name=name, utilization=float(sw.get("used_percent", 0)),
                    resets_at=resets_at, window_seconds=window_sec,
                )

        return cls(primary=primary, secondary=secondary, plan_type=plan_type,
                   timestamp=datetime.now(timezone.utc))

    @classmethod
    def with_error(cls, msg: str) -> "CodexUsageData":
        return cls(error=msg, timestamp=datetime.now(timezone.utc))


@dataclass
class AntigravityUsageData:
    gemini3: Optional[UsageBucket] = None      # Gemini 3 枠
    third_party: Optional[UsageBucket] = None  # サードパーティ枠（Claude/GPTプール）
    error: Optional[str] = None
    timestamp: Optional[datetime] = None

    @classmethod
    def with_error(cls, msg: str) -> "AntigravityUsageData":
        return cls(error=msg, timestamp=datetime.now(timezone.utc))


def _window_label(seconds: int) -> str:
    """ウィンドウの長さ（秒）を短いラベルに変換する。"""
    if seconds <= 3600:
        return f"{seconds // 60}m"
    if seconds <= 86400:
        return f"{seconds // 3600}h"
    days = seconds // 86400
    if days == 7:
        return "1w"
    return f"{days}d"


@dataclass
class ProfileData:
    email: str = ""
    plan: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ProfileData":
        account = data.get("account", {})
        email = account.get("email", "")
        if account.get("has_claude_max"):
            plan = "Max"
        elif account.get("has_claude_pro"):
            plan = "Pro"
        else:
            plan = ""
        return cls(email=email, plan=plan)


