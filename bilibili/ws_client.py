"""B 站直播弹幕 WebSocket 客户端。

协议要点：
- 端点：wss://broadcastlv.chat.bilibili.com:2245/sub
- 包格式：header(16B) + body。header = [packetLen(4)][headerLen(16)][protoVer(2)][op(4)][seq(4)]
- 关键 op：
  7   客户端 -> 服务端：认证包
  8   服务端 -> 客户端：认证成功
  5   服务端 -> 客户端：通知（礼物/进场/弹幕等，body 为 JSON）
  2   客户端 -> 服务端：心跳
  3   服务端 -> 客户端：心跳应答

需要登录态 Cookie（SESSDATA + bili_jct）才能稳定连接，
未配置时连接会立即被服务端断开。
"""
from __future__ import annotations
import json
import struct
import threading
import time
from typing import Callable, Optional

import websocket  # websocket-client

from config import BILI_COOKIE
from .api_client import BiliOpenClient


WSS_HOST = "wss://broadcastlv.chat.bilibili.com:2245/sub"
HEARTBEAT_INTERVAL = 30  # 秒


def _pack(op: int, body: dict | str) -> bytes:
    """打包一个 B 站弹幕协议包。"""
    if isinstance(body, dict):
        body = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    body_bytes = body.encode("utf-8")
    header_len = 16
    packet_len = header_len + len(body_bytes)
    # [packetLen(4)][headerLen(2)][protoVer(2)][op(4)][seq(4)]
    return struct.pack(
        ">IHHII",
        packet_len,
        header_len,
        1,        # protoVer
        op,
        1,        # seq
    ) + body_bytes


def _parse(buf: bytes) -> list[dict]:
    """解一组 B 站弹幕协议包。"""
    results = []
    offset = 0
    while offset + 16 <= len(buf):
        packet_len = struct.unpack(">I", buf[offset:offset + 4])[0]
        op = struct.unpack(">I", buf[offset + 8:offset + 12])[0]
        body = buf[offset + 16:offset + packet_len]
        if packet_len <= 0 or offset + packet_len > len(buf):
            break
        try:
            body_str = body.decode("utf-8", errors="ignore")
            results.append({"op": op, "body": body_str})
        except Exception:
            results.append({"op": op, "body": ""})
        offset += packet_len
    return results


GiftCallback = Callable[[dict], None]
StatusCallback = Callable[[str], None]


class BiliWsClient:
    """B 站直播弹幕 WebSocket 客户端。"""

    def __init__(
        self,
        on_gift: Optional[GiftCallback] = None,
        on_status: Optional[StatusCallback] = None,
    ) -> None:
        self.on_gift = on_gift
        self.on_status = on_status or (lambda s: None)
        self._ws: Optional[websocket.WebSocket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._room_id: int = 0
        self._room_real_id: int = 0  # 短房间号 -> 真房间 ID（必须先解析）

    # ---------- 房间号解析 ----------
    def _resolve_real_room_id(self, room_id: int) -> int:
        """短号需要 get_info 拿真实 room_id。"""
        if room_id >= 10000:
            return room_id
        info = BiliOpenClient().get_room_info(room_id)
        return int(info.get("room_id") or room_id)

    # ---------- 主循环 ----------
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.on_status("连接中…")
                self._ws = websocket.create_connection(
                    WSS_HOST,
                    timeout=10,
                    header=[
                        f"Cookie: SESSDATA={BILI_COOKIE.sessdata}; bili_jct={BILI_COOKIE.bili_jct}",
                    ],
                )
                # 1. 发送认证包
                auth_body = {
                    "uid": 0,
                    "roomid": self._room_real_id,
                    "protover": 1,
                    "platform": "web",
                    "type": 2,
                    "key": "",
                }
                self._ws.send(_pack(7, auth_body))
                self.on_status("已认证")

                last_heartbeat = time.time()
                self._ws.settimeout(HEARTBEAT_INTERVAL + 5)
                while not self._stop.is_set():
                    if time.time() - last_heartbeat >= HEARTBEAT_INTERVAL:
                        self._ws.send(_pack(2, ""))
                        last_heartbeat = time.time()
                    try:
                        buf = self._ws.recv()
                    except Exception:
                        break
                    if not buf:
                        continue
                    if isinstance(buf, str):
                        buf = buf.encode("utf-8")
                    for msg in _parse(buf):
                        self._handle_msg(msg)
            except Exception as e:
                self.on_status(f"连接断开: {e}")
                time.sleep(3)
            finally:
                if self._ws:
                    try:
                        self._ws.close()
                    except Exception:
                        pass
                    self._ws = None

    def _handle_msg(self, msg: dict) -> None:
        op = msg["op"]
        body = msg["body"]
        if op == 8:
            self.on_status("已连接")
        elif op == 3:
            pass  # 心跳应答
        elif op == 5:
            try:
                payload = json.loads(body)
                cmd = payload.get("cmd", "")
                if cmd == "SEND_GIFT" and self.on_gift:
                    data = payload.get("data") or {}
                    self.on_gift({
                        "user_name": data.get("uname", ""),
                        "user_level": data.get("user_level", 0),
                        "guard_level": data.get("guard_level", 0),
                        "gift_id": data.get("giftId", 0),
                        "gift_name": data.get("giftName", ""),
                        "num": data.get("num", 1),
                    })
            except Exception as e:
                print(f"[BiliWs] 解析失败: {e}")

    # ---------- 控制 ----------
    def start(self, room_id: int) -> None:
        """启动连接。"""
        if self._thread and self._thread.is_alive():
            return
        if not BILI_COOKIE.is_ready:
            self.on_status("未配置 SESSDATA/bili_jct，WebSocket 无法连接")
            return
        self._stop.clear()
        self._room_id = room_id
        self._room_real_id = self._resolve_real_room_id(room_id)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass


if __name__ == "__main__":
    def on_gift(d):
        print("GIFT:", d)

    def on_status(s):
        print("STATUS:", s)

    cli = BiliWsClient(on_gift=on_gift, on_status=on_status)
    cli.start(6)
    time.sleep(5)
    cli.stop()