"""Claude OAuth認証 + Usage API通信"""

import json
import os
import time
import logging
from dataclasses import dataclass, field

import requests

from config import CREDENTIALS_PATH, API_BASE_URL, TOKEN_BASE_URL, TOKEN_ENDPOINT, OAUTH_CLIENT_ID, USAGE_ENDPOINT, ANTHROPIC_BETA
from models import UsageData, ProfileData

PROFILE_ENDPOINT = "/api/oauth/profile"

log = logging.getLogger(__name__)


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    expires_at: int  # ミリ秒エポック
    scopes: list = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        return time.time() * 1000 >= self.expires_at - 60_000  # 1分のマージン

    @classmethod
    def from_dict(cls, data: dict) -> "AuthTokens":
        return cls(
            access_token=data["accessToken"],
            refresh_token=data["refreshToken"],
            expires_at=data["expiresAt"],
            scopes=data.get("scopes", []),
        )


def _load_tokens() -> AuthTokens:
    """~/.claude/.credentials.json からトークンを読み込む。"""
    with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    oauth = data["claudeAiOauth"]
    return AuthTokens.from_dict(oauth)


def _save_tokens(tokens: AuthTokens) -> None:
    """更新されたトークンを認証情報ファイルに保存する。"""
    with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["claudeAiOauth"]["accessToken"] = tokens.access_token
    data["claudeAiOauth"]["refreshToken"] = tokens.refresh_token
    data["claudeAiOauth"]["expiresAt"] = tokens.expires_at
    with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _refresh_access_token(tokens: AuthTokens) -> AuthTokens:
    """リフレッシュトークンを使ってアクセストークンを更新する。"""
    url = f"{TOKEN_BASE_URL}{TOKEN_ENDPOINT}"
    resp = requests.post(
        url,
        json={
            "grant_type": "refresh_token",
            "refresh_token": tokens.refresh_token,
            "client_id": OAUTH_CLIENT_ID,
        },
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    expires_in = body.get("expires_in", 3600)
    new_tokens = AuthTokens(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token", tokens.refresh_token),
        expires_at=int(time.time() * 1000) + expires_in * 1000,
        scopes=tokens.scopes,
    )
    _save_tokens(new_tokens)
    log.info("Token refreshed successfully")
    return new_tokens


def _get_valid_token() -> tuple[str, AuthTokens]:
    """有効なアクセストークンを返す。期限切れの場合は更新する。"""
    tokens = _load_tokens()
    if tokens.is_expired:
        log.info("Token expired, refreshing...")
        tokens = _refresh_access_token(tokens)
    return tokens.access_token, tokens


# --- 外部公開API ---

def fetch_usage() -> UsageData | None:
    """APIから使用状況データを取得する。認証情報ファイルがない場合はNoneを返す。"""
    if not os.path.exists(CREDENTIALS_PATH):
        return None
    try:
        access_token, tokens = _get_valid_token()
        resp = requests.get(
            f"{API_BASE_URL}{USAGE_ENDPOINT}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "anthropic-beta": ANTHROPIC_BETA,
            },
            timeout=15,
        )
        if resp.status_code == 401:
            log.warning("401 received, attempting token refresh")
            try:
                tokens = _refresh_access_token(tokens)
                resp = requests.get(
                    f"{API_BASE_URL}{USAGE_ENDPOINT}",
                    headers={
                        "Authorization": f"Bearer {tokens.access_token}",
                        "anthropic-beta": ANTHROPIC_BETA,
                    },
                    timeout=15,
                )
            except Exception:
                log.info("Claude auth failed, hiding section")
                return None
            if resp.status_code == 401:
                log.info("Claude auth still 401 after refresh, hiding section")
                return None

        if resp.status_code == 429:
            # レートリミットはアクセストークン単位。リフレッシュしてリトライ
            try:
                tokens = _refresh_access_token(tokens)
                resp = requests.get(
                    f"{API_BASE_URL}{USAGE_ENDPOINT}",
                    headers={
                        "Authorization": f"Bearer {tokens.access_token}",
                        "anthropic-beta": ANTHROPIC_BETA,
                    },
                    timeout=15,
                )
                if resp.status_code == 429:
                    return UsageData.with_error("Rate limited")
            except Exception:
                return UsageData.with_error("Rate limited")

        if resp.status_code == 404:
            # 有効な使用ウィンドウなし - 使用率0%として扱う
            return UsageData.from_dict({
                "five_hour": {"utilization": 0.0, "resets_at": None},
                "seven_day": {"utilization": 0.0, "resets_at": None},
            })

        resp.raise_for_status()
        data = resp.json()
        return UsageData.from_dict(data)

    except requests.ConnectionError:
        return UsageData.with_error("Network error")
    except requests.Timeout:
        return UsageData.with_error("Timeout")
    except (KeyError, json.JSONDecodeError):
        log.info("Claude credentials invalid, hiding section")
        return None
    except Exception as e:
        log.exception("Failed to fetch usage")
        return UsageData.with_error(str(e)[:50])


def fetch_profile() -> ProfileData | None:
    """アカウントプロフィール（メール、プラン）を取得する。認証情報ファイルがない場合はNoneを返す。"""
    if not os.path.exists(CREDENTIALS_PATH):
        return None
    try:
        access_token, _ = _get_valid_token()
        resp = requests.get(
            f"{API_BASE_URL}{PROFILE_ENDPOINT}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "anthropic-beta": ANTHROPIC_BETA,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return ProfileData.from_dict(resp.json())
    except Exception:
        log.debug("Failed to fetch profile", exc_info=True)
    return None
