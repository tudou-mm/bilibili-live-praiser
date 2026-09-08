"""配置加载层。统一从 .env 读取敏感凭证，禁止硬编码。"""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录 = 当前文件父目录的父目录
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    val = os.getenv(key, default).strip()
    return val


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str = _get("DEEPSEEK_API_KEY")
    base_url: str = _get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model: str = _get("DEEPSEEK_MODEL", "deepseek-chat")


@dataclass(frozen=True)
class BiliOpenPlatformConfig:
    """B 站开放平台 OAuth2 配置。需 App ID + App Secret 才能换 access_token。"""
    app_id: str = _get("BILI_APP_ID")
    app_secret: str = _get("BILI_APP_SECRET")
    access_key_id: str = _get("BILI_ACCESS_KEY_ID")
    access_key_secret: str = _get("BILI_ACCESS_KEY_SECRET")

    @property
    def is_ready(self) -> bool:
        return bool(self.app_id and self.app_secret)


@dataclass(frozen=True)
class BiliCookieConfig:
    """B 站 WebSocket 登录态 Cookie。"""
    sessdata: str = _get("BILI_SESSDATA")
    bili_jct: str = _get("BILI_BILI_JCT")

    @property
    def is_ready(self) -> bool:
        return bool(self.sessdata and self.bili_jct)


@dataclass(frozen=True)
class RuntimeConfig:
    default_room_id: int = int(_get("ROOM_ID", "0") or "0")
    log_level: str = _get("LOG_LEVEL", "INFO").upper()


DEEPSEEK = DeepSeekConfig()
BILI_OPEN = BiliOpenPlatformConfig()
BILI_COOKIE = BiliCookieConfig()
RUNTIME = RuntimeConfig()