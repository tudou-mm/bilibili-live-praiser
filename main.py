"""主程序入口。

串联：
  UI 主线程 (PyQt6) + WebSocket 工作线程 + AI 兜底生成

事件流：
  B 站 WS -> on_gift -> GiftEvent.build -> Praiser.generate
  -> GiftBridge.gift_ready -> UI.FloatingOverlay.push
"""
from __future__ import annotations
import sys
import queue
import threading

from PyQt6.QtCore import QTimer

from bilibili import GiftEvent
from bilibili.api_client import BiliOpenClient
from bilibili.ws_client import BiliWsClient
from ai.praiser import Praiser
from config import RUNTIME, BILI_COOKIE
from ui import build_ui


def main() -> int:
    app, window, overlay, bridge = build_ui()

    # 后台工作线程：把礼物事件丢进队列，主线程 QTimer 拉取
    gift_queue: queue.Queue[GiftEvent] = queue.Queue()
    api = BiliOpenClient()
    praiser = Praiser()
    ws_client: BiliWsClient | None = None

    def on_gift_from_ws(raw: dict) -> None:
        """WebSocket 工作线程 -> 礼物队列。"""
        ev = GiftEvent.build(
            user_name=raw.get("user_name", ""),
            gift_id=raw.get("gift_id", 0),
            num=raw.get("num", 1),
            user_level=raw.get("user_level", 0),
            guard_level=raw.get("guard_level", 0),
            gift_name=raw.get("gift_name"),
        )
        gift_queue.put(ev)

    def on_status_from_ws(text: str) -> None:
        bridge.status_changed.emit(text)

    def pump_queue() -> None:
        """UI 主线程定时消费礼物队列。"""
        try:
            while True:
                ev = gift_queue.get_nowait()
                # 在 UI 线程同步调用 AI（DeepSeek 响应通常 <2s，可接受）
                # 如果要彻底异步，把这里改为丢到 ThreadPoolExecutor
                praiser.generate(ev)
                bridge.gift_ready.emit(ev)
        except queue.Empty:
            pass

    timer = QTimer()
    timer.timeout.connect(pump_queue)
    timer.start(150)  # 每 150ms 拉一次

    def start_listen(room_id: int) -> None:
        nonlocal ws_client
        bridge.status_changed.emit(f"解析房间号 {room_id}…")
        # 先用 API 拉一次房间信息确认有效
        info = api.get_room_info(room_id)
        if info and info.get("title"):
            bridge.status_changed.emit(
                f"房间 {info.get('room_id', room_id)}: {info['title']}"
            )
        else:
            bridge.status_changed.emit("API 拉取失败，尝试直接连 WebSocket")

        if not BILI_COOKIE.is_ready:
            bridge.status_changed.emit(
                "未配置 SESSDATA/bili_jct，WebSocket 已跳过。"
                "请编辑 .env 补齐后重启。"
            )
            return

        ws_client = BiliWsClient(on_gift=on_gift_from_ws, on_status=on_status_from_ws)
        ws_client.start(room_id)

    window.connect_requested.connect(start_listen)

    # 预填默认房间号
    if RUNTIME.default_room_id:
        window.room_input.setText(str(RUNTIME.default_room_id))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())