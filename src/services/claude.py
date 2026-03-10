"""Claude OAuth認証 + Usage API通信"""

import json
import os
import logging
from dataclasses import dataclass, field

import requests

from config import CREDENTIALS_PATH, API_BASE_URL, USAGE_ENDPOINT, ANTHROPIC_BETA
from models import UsageData, ProfileData

PROFILE_ENDPOINT = "/api/oauth/profile"

log = logging.getLogger(__name__)


@dataclass
class AuthTokens:
    access_token: str
    scopes: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "AuthTokens":
        return cls(
            access_token=data["accessToken"],
            scopes=data.get("scopes", []),
        )


def _load_tokens() -> AuthTokens:
    """~/.claude/.credentials.json からトークンを読み込む。"""
    with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    oauth = data["claudeAiOauth"]
    return AuthTokens.from_dict(oauth)


def _get_valid_token() -> tuple[str, AuthTokens]:
    """ファイルからトークンを読み込んで返す。リフレッシュはClaude Codeに任せる。"""
    tokens = _load_tokens()
    return tokens.access_token, tokens


def _reload_and_retry_request(old_tokens: AuthTokens, url: str, headers_extra: dict) -> tuple[requests.Response, AuthTokens] | None:
    """ファイルからトークンを再読み込みしてリトライ。他プロセスがリフレッシュ済みの場合のみ。"""
    reloaded = _load_tokens()
    if reloaded.access_token == old_tokens.access_token:
        # 誰もリフレッシュしていない → 諦める
        log.info("Token unchanged, waiting for Claude Code to refresh")
        return None
    log.info("Token updated by another process, reusing")
    resp = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {reloaded.access_token}",
            **headers_extra,
        },
        timeout=15,
    )
    return resp, reloaded


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
        if resp.status_code == 429:
            return UsageData.with_error("Rate limited")

        if resp.status_code == 401:
            log.warning("401 received, reloading token from file")
            try:
                usage_url = f"{API_BASE_URL}{USAGE_ENDPOINT}"
                result = _reload_and_retry_request(
                    tokens, usage_url, {"anthropic-beta": ANTHROPIC_BETA},
                )
            except Exception:
                result = None
            if result is None:
                return UsageData.with_error("Token expired")
            resp, tokens = result
            if resp.status_code == 401:
                return UsageData.with_error("Token expired")

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
