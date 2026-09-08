"""B 站开放平台 HTTP 客户端。

包含两部分：
1. OAuth2 client_credentials 拿 access_token（需 App ID + App Secret）
2. 直播间公开 API（房间信息、礼物价值表）

注：开放平台 OAuth2 接口要求注册"账号开放权限"或"直播开放平台"应用，
普通账号无法直接调通。当前版本留好完整调用链，凭证不全时返回空数据，
WebSocket 通道补齐后仍能完整工作。
"""
from __future__ import annotations
import time
import requests
from typing import Optional, Any
from config import BILI_OPEN


OPEN_PLATFORM_TOKEN_URL = "https://api.bilibili.com/x/account-oauth2/v1/token"
PUBLIC_ROOM_INFO_URL = "https://api.live.bilibili.com/room/v1/Room/get_info"
PUBLIC_USER_INFO_URL = "https://api.live.bilibili.com/live_user/v1/UserInfo/get_anchor_in_room"
PUBLIC_GIFT_LIST_URL = "https://api.live.bilibili.com/gift/v3/live/gift_config"


class BiliOpenClient:
    """B 站 HTTP API 客户端。"""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 BilibiliPraiser/1.0",
            "Referer": "https://live.bilibili.com/",
        })
        self._access_token: Optional[str] = None
        self._token_expire_at: float = 0.0

    # ---------- OAuth2 ----------
    def _refresh_access_token(self) -> Optional[str]:
        """client_credentials 流程换 access_token。"""
        if not BILI_OPEN.is_ready:
            return None
        try:
            resp = self._session.post(
                OPEN_PLATFORM_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "app_id": BILI_OPEN.app_id,
                    "app_secret": BILI_OPEN.app_secret,
                },
                timeout=10,
            )
            data = resp.json()
            if data.get("code") == 0:
                self._access_token = data["data"]["access_token"]
                self._token_expire_at = time.time() + data["data"].get("expires_in", 7200) - 60
                return self._access_token
        except Exception as e:
            print(f"[BiliOpen] token 刷新失败: {e}")
        return None

    def get_access_token(self) -> Optional[str]:
        if self._access_token and time.time() < self._token_expire_at:
            return self._access_token
        return self._refresh_access_token()

    # ---------- 公开 API（无需 access_token）----------
    def get_room_info(self, room_id: int) -> dict[str, Any]:
        """拉取直播间公开信息（标题、主播、关注数等）。"""
        try:
            resp = self._session.get(
                PUBLIC_ROOM_INFO_URL,
                params={"room_id": room_id},
                timeout=10,
            )
            return resp.json().get("data") or {}
        except Exception as e:
            print(f"[BiliOpen] get_room_info 失败: {e}")
            return {}

    def get_gift_config(self) -> list[dict[str, Any]]:
        """拉取直播间礼物配置（用于补充内置表）。失败返回空列表。"""
        try:
            resp = self._session.get(PUBLIC_GIFT_LIST_URL, params={"platform": "pc"}, timeout=10)
            data = resp.json().get("data") or {}
            return data.get("list", []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[BiliOpen] get_gift_config 失败: {e}")
            return []


if __name__ == "__main__":
    cli = BiliOpenClient()
    print("open platform ready:", BILI_OPEN.is_ready)
    if BILI_OPEN.is_ready:
        print("access_token:", (cli.get_access_token() or "")[:20] + "...")
    print("room 6 info:", cli.get_room_info(6))