"""Codex OAuth認証 + Usage API通信"""

import json
import os
import time
import base64
import logging

import requests

from models import CodexUsageData

log = logging.getLogger(__name__)

CODEX_AUTH_PATH = os.path.join(os.path.expanduser("~"), ".codex", "auth.json")
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"


def _decode_jwt_payload(token: str) -> dict:
    """JWTペイロードを検証なしでデコードする。"""
    try:
        payload = token.split(".")[1]
        # パディングを追加
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}


def _load_codex_tokens() -> dict | None:
    """~/.codex/auth.json からトークンを読み込む。"""
    try:
        if not os.path.exists(CODEX_AUTH_PATH):
            return None
        with open(CODEX_AUTH_PATH, "r") as f:
            data = json.load(f)
        if data.get("auth_mode") != "chatgpt":
            return None
        tokens = data.get("tokens", {})
        if not tokens.get("access_token"):
            return None
        return tokens
    except Exception:
        log.debug("Failed to load Codex tokens", exc_info=True)
        return None


def _is_token_expired(access_token: str) -> bool:
    """JWTアクセストークンの有効期限を確認する。"""
    payload = _decode_jwt_payload(access_token)
    exp = payload.get("exp", 0)
    return time.time() >= exp - 60  # 1分のマージン


def _refresh_codex_token(refresh_token: str) -> dict | None:
    """Codexのアクセストークンを更新する。"""
    try:
        resp = requests.post(
            CODEX_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CODEX_CLIENT_ID,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            _save_refreshed_tokens(data)
            return data
    except Exception:
        log.debug("Failed to refresh Codex token", exc_info=True)
    return None


def _save_refreshed_tokens(new_tokens: dict):
    """更新されたトークンをauth.jsonに保存する。"""
    try:
        with open(CODEX_AUTH_PATH, "r") as f:
            data = json.load(f)
        tokens = data.get("tokens", {})
        if "access_token" in new_tokens:
            tokens["access_token"] = new_tokens["access_token"]
        if "refresh_token" in new_tokens:
            tokens["refresh_token"] = new_tokens["refresh_token"]
        if "id_token" in new_tokens:
            tokens["id_token"] = new_tokens["id_token"]
        data["tokens"] = tokens
        data["last_refresh"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(CODEX_AUTH_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        log.debug("Failed to save refreshed Codex tokens", exc_info=True)


def _get_valid_codex_token() -> tuple[str, str] | None:
    """(access_token, account_id)を返す。Codex未設定の場合はNoneを返す。"""
    tokens = _load_codex_tokens()
    if not tokens:
        return None

    access_token = tokens["access_token"]
    account_id = tokens.get("account_id", "")

    if _is_token_expired(access_token):
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            return None
        new_tokens = _refresh_codex_token(refresh_token)
        if not new_tokens:
            return None
        access_token = new_tokens.get("access_token", access_token)
        # 必要に応じて新しいJWTからaccount_idを更新
        if not account_id:
            payload = _decode_jwt_payload(access_token)
            auth_info = payload.get("https://api.openai.com/auth", {})
            account_id = auth_info.get("chatgpt_account_id", "")

    return access_token, account_id


# --- 外部公開API ---

def fetch_codex_usage() -> CodexUsageData | None:
    """Codexの使用状況データを取得する。Codex未設定の場合はNoneを返す。"""
    try:
        result = _get_valid_codex_token()
        if not result:
            return None  # Codex not configured

        access_token, account_id = result
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "codex-cli",
        }
        if account_id:
            headers["ChatGPT-Account-Id"] = account_id

        resp = requests.get(CODEX_USAGE_URL, headers=headers, timeout=15)

        if resp.status_code == 401:
            log.warning("Codex 401, attempting token refresh")
            tokens = _load_codex_tokens()
            if tokens and tokens.get("refresh_token"):
                new_tokens = _refresh_codex_token(tokens["refresh_token"])
                if new_tokens:
                    headers["Authorization"] = f"Bearer {new_tokens['access_token']}"
                    resp = requests.get(CODEX_USAGE_URL, headers=headers, timeout=15)
                else:
                    log.info("Codex auth failed, hiding section")
                    return None
            else:
                log.info("Codex auth not configured, hiding section")
                return None
            if resp.status_code == 401:
                log.info("Codex auth still 401 after refresh, hiding section")
                return None

        if resp.status_code == 429:
            return CodexUsageData.with_error("Rate limited")

        resp.raise_for_status()
        data = resp.json()
        return CodexUsageData.from_dict(data)

    except requests.ConnectionError:
        return CodexUsageData.with_error("Network error")
    except requests.Timeout:
        return CodexUsageData.with_error("Timeout")
    except Exception as e:
        log.exception("Failed to fetch Codex usage")
        return CodexUsageData.with_error(str(e)[:50])


def get_codex_profile() -> tuple[str, str]:
    """JWTクレームから(email, plan_type)を返す。"""
    tokens = _load_codex_tokens()
    if not tokens:
        return "", ""
    payload = _decode_jwt_payload(tokens["access_token"])
    profile = payload.get("https://api.openai.com/profile", {})
    auth_info = payload.get("https://api.openai.com/auth", {})
    email = profile.get("email", "")
    plan = auth_info.get("chatgpt_plan_type", "")
    return email, plan
