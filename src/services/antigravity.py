"""Antigravity Language Server クォータ取得"""

import json
import logging
import re
import ssl
import subprocess
import urllib.request
from datetime import datetime, timezone
from typing import Optional

# Windows上でPowerShellのコンソールウィンドウを非表示にする
_CREATIONFLAGS = subprocess.CREATE_NO_WINDOW

from models import AntigravityUsageData, UsageBucket

log = logging.getLogger(__name__)

# --- 接続情報キャッシュ ---
_cached_pid: Optional[int] = None
_cached_port: Optional[int] = None
_cached_csrf: Optional[str] = None
_cached_email: str = ""
_cached_plan: str = ""


def _clear_cache():
    global _cached_pid, _cached_port, _cached_csrf
    _cached_pid = None
    _cached_port = None
    _cached_csrf = None


def _detect_process() -> Optional[tuple[int, str]]:
    """Antigravity Language Serverプロセスを検出する。

    (PID, csrf_token) または None を返す。
    """
    try:
        ps_cmd = (
            "Get-CimInstance Win32_Process -Filter \"name='language_server_windows_x64.exe'\" "
            "| Select-Object ProcessId, CommandLine | ConvertTo-Json"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10,
            creationflags=_CREATIONFLAGS,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        data = json.loads(result.stdout)
        # 結果が1つならdict、複数ならlistで返される
        if isinstance(data, dict):
            data = [data]

        for proc in data:
            cmd = proc.get("CommandLine", "") or ""
            if "antigravity" not in cmd.lower():
                continue
            m = re.search(r"--csrf_token\s+(\S+)", cmd)
            if not m:
                continue
            pid = proc.get("ProcessId")
            csrf = m.group(1)
            if pid and csrf:
                return int(pid), csrf

    except Exception:
        log.debug("Failed to detect Antigravity process", exc_info=True)
    return None


def _detect_port(pid: int, csrf_token: str) -> Optional[int]:
    """指定PIDのリスニングポートを検出し、応答を確認する。"""
    try:
        ps_cmd = (
            f"Get-NetTCPConnection -OwningProcess {pid} -State Listen -ErrorAction SilentlyContinue "
            "| Select-Object LocalPort | ConvertTo-Json"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10,
            creationflags=_CREATIONFLAGS,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        data = json.loads(result.stdout)
        if isinstance(data, dict):
            data = [data]

        ports = sorted(set(p["LocalPort"] for p in data if p.get("LocalPort")))

        for port in ports:
            if _probe_port(port, csrf_token):
                return port

    except Exception:
        log.debug("Failed to detect port for PID %s", pid, exc_info=True)
    return None


def _probe_port(port: int, csrf_token: str) -> bool:
    """ポートがGetUserStatusに応答するか簡易チェックする。"""
    try:
        _call_get_user_status(port, csrf_token, timeout=3)
        return True
    except Exception:
        return False


def _make_ssl_context() -> ssl.SSLContext:
    """SSL証明書検証をスキップするSSLコンテキストを作成する（localhost自己署名証明書用）。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _call_get_user_status(port: int, csrf_token: str, timeout: int = 5) -> dict:
    """Language ServerのGetUserStatusを呼び出す。"""
    url = f"https://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/GetUserStatus"
    body = json.dumps({
        "metadata": {
            "ideName": "antigravity",
            "extensionName": "antigravity",
            "locale": "en",
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
            "X-Codeium-Csrf-Token": csrf_token,
        },
    )
    ctx = _make_ssl_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ensure_connection() -> Optional[tuple[int, str]]:
    """有効な(port, csrf_token)ペアを取得する（キャッシュを優先使用）。

    (port, csrf_token) または None を返す。
    """
    global _cached_pid, _cached_port, _cached_csrf

    if _cached_port and _cached_csrf:
        return _cached_port, _cached_csrf

    proc = _detect_process()
    if not proc:
        _clear_cache()
        return None

    pid, csrf = proc
    _cached_pid = pid
    _cached_csrf = csrf

    port = _detect_port(pid, csrf)
    if not port:
        _clear_cache()
        return None

    _cached_port = port
    return port, csrf


def _parse_quota(response: dict) -> AntigravityUsageData:
    """GetUserStatusレスポンスをAntigravityUsageDataに変換する。"""
    global _cached_email, _cached_plan

    user_status = response.get("userStatus", {})

    # Extract profile info
    email = user_status.get("email", "")
    tier = user_status.get("userTier", {})
    plan = tier.get("name", "")
    # "Google AI Pro" → "Pro", "Google AI Ultra" → "Ultra"
    plan = re.sub(r"^Google\s+AI\s+", "", plan)
    if email:
        _cached_email = email
    if plan:
        _cached_plan = plan

    # モデル設定を抽出
    cascade = user_status.get("cascadeModelConfigData", {})
    configs = cascade.get("clientModelConfigs", [])

    gemini3: Optional[UsageBucket] = None
    third_party: Optional[UsageBucket] = None

    for model in configs:
        label = model.get("label", "")
        quota = model.get("quotaInfo", {})
        remaining_frac = quota.get("remainingFraction")
        if remaining_frac is None:
            continue

        utilization = (1.0 - float(remaining_frac)) * 100.0
        utilization = max(0.0, min(100.0, utilization))

        resets_at = None
        reset_time = quota.get("resetTime")
        if reset_time:
            try:
                resets_at = datetime.fromisoformat(reset_time.replace("Z", "+00:00"))
            except Exception:
                pass

        bucket = UsageBucket(
            name="",
            utilization=utilization,
            resets_at=resets_at,
            window_seconds=0,
        )

        if re.search(r"Gemini\s*3", label, re.I):
            if gemini3 is None:
                bucket.name = "G3"
                gemini3 = bucket
        else:
            if third_party is None:
                bucket.name = "3rd"
                third_party = bucket

    return AntigravityUsageData(
        gemini3=gemini3,
        third_party=third_party,
        timestamp=datetime.now(timezone.utc),
    )


# --- 外部公開API ---

def fetch_antigravity_usage() -> Optional[AntigravityUsageData]:
    """Antigravityのクォータデータを取得する。Antigravity未実行の場合はNoneを返す。"""
    try:
        conn = _ensure_connection()
        if not conn:
            return None

        port, csrf = conn
        try:
            response = _call_get_user_status(port, csrf)
        except Exception:
            # 接続失敗 - キャッシュをクリアして1回リトライ
            log.debug("Antigravity connection failed, retrying with fresh detection")
            _clear_cache()
            conn = _ensure_connection()
            if not conn:
                return None
            port, csrf = conn
            response = _call_get_user_status(port, csrf)

        return _parse_quota(response)

    except Exception as e:
        log.debug("Failed to fetch Antigravity usage", exc_info=True)
        return AntigravityUsageData.with_error(str(e)[:50])


def get_antigravity_profile() -> tuple[str, str]:
    """キャッシュされたプロフィール情報から(email, plan)を返す。"""
    return _cached_email, _cached_plan
