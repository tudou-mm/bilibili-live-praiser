"""PyQt6 桌面悬浮窗。

特性：
- 始终置顶 + 无边框 + 半透明
- 内置主窗口（房间号输入 + 连接状态）+ 独立悬浮展示窗
- 礼物队列：3s 内同用户合并，最多同时展示 5 条
- 线程安全：所有跨线程调用通过 Qt Signal 投递
"""
from __future__ import annotations
import time
from collections import deque
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
)

from bilibili import GiftEvent


# 不同礼物价值档位对应配色
TIER_COLORS = {
    "small": "#7dd3fc",        # 天蓝
    "medium": "#fbbf24",       # 金黄
    "large": "#fb7185",        # 玫红
    "legendary": "#c084fc",    # 紫金
}


# ---------- 跨线程通信桥 ----------
class GiftBridge(QObject):
    """工作线程 -> UI 线程的事件桥。"""
    gift_ready = pyqtSignal(object)        # GiftEvent
    status_changed = pyqtSignal(str)       # 文本


class FloatingOverlay(QWidget):
    """真正悬浮的展示窗。"""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(560, 360)
        # 默认贴屏幕右上角
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 40, geo.top() + 80)

        self._items: deque[tuple[float, QFrame]] = deque(maxlen=5)
        self._container_layout = QVBoxLayout()
        self._container_layout.setSpacing(8)
        self._container_layout.setContentsMargins(0, 0, 0, 0)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self._container_layout)
        outer.addStretch(1)

        # 每 0.5s 检查过期项（>8s 自动淡出）
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._gc)
        self._timer.start(500)

    def push(self, ev: GiftEvent) -> None:
        # 同用户 3s 内合并
        now = ev.timestamp
        for ts, frame in list(self._items):
            data = frame.property("ev")
            if data and data.user_name == ev.user_name and now - ts < 3.0:
                merged = GiftEvent(
                    user_name=ev.user_name,
                    user_level=ev.user_level,
                    guard_level=ev.guard_level,
                    gift_name=ev.gift_name,
                    gift_id=ev.gift_id,
                    num=data.num + ev.num,
                    price_per_unit=ev.price_per_unit,
                    total_price=data.total_price + ev.total_price,
                    tier=ev.tier,
                    praise=ev.praise or data.praise,
                    timestamp=now,
                )
                self._container_layout.removeWidget(frame)
                frame.deleteLater()
                self._items.remove((ts, frame))
                self._push_new(merged)
                return
        self._push_new(ev)

    def _push_new(self, ev: GiftEvent) -> None:
        frame = self._build_item(ev)
        self._container_layout.insertWidget(0, frame)
        self._items.append((ev.timestamp, frame))
        # 超出 5 条的最旧项移除
        while len(self._items) > 5:
            old_ts, old_frame = self._items.popleft()
            self._container_layout.removeWidget(old_frame)
            old_frame.deleteLater()

    def _build_item(self, ev: GiftEvent) -> QFrame:
        border = TIER_COLORS.get(ev.tier.value, "#94a3b8")
        card = QFrame()
        card.setProperty("ev", ev)
        card.setStyleSheet(
            f"""
            QFrame {{
                background: rgba(15, 23, 42, 220);
                border-left: 4px solid {border};
                border-radius: 8px;
            }}
            """
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        header = QLabel(ev.display_line())
        header.setStyleSheet(f"color: {border}; font-weight: bold; font-size: 13px;")
        header.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))

        body = QLabel(ev.praise or "")
        body.setWordWrap(True)
        body.setStyleSheet("color: #f1f5f9; font-size: 13px;")
        body.setFont(QFont("Microsoft YaHei", 10))

        layout.addWidget(header)
        layout.addWidget(body)
        return card

    def _gc(self) -> None:
        now = time.time()
        while self._items and now - self._items[0][0] > 8.0:
            ts, frame = self._items.popleft()
            self._container_layout.removeWidget(frame)
            frame.deleteLater()


class MainWindow(QWidget):
    """主控制窗：输入房间号 + 显示连接状态。"""

    connect_requested = pyqtSignal(int)

    def __init__(self, bridge: GiftBridge, overlay: FloatingOverlay) -> None:
        super().__init__()
        self._bridge = bridge
        self._overlay = overlay
        self.setWindowTitle("B 站直播间夸赞悬浮窗")
        self.resize(420, 180)

        root = QVBoxLayout(self)

        # 输入区
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("直播间房间号："))
        self.room_input = QLineEdit()
        self.room_input.setPlaceholderText("输入短号或真实 room_id")
        row1.addWidget(self.room_input, 1)
        self.btn_connect = QPushButton("开始监听")
        self.btn_connect.clicked.connect(self._on_connect)
        row1.addWidget(self.btn_connect)
        root.addLayout(row1)

        # 控制按钮
        row2 = QHBoxLayout()
        self.btn_overlay = QPushButton("显示/隐藏悬浮窗")
        self.btn_overlay.clicked.connect(self._toggle_overlay)
        row2.addWidget(self.btn_overlay)
        row2.addStretch(1)
        root.addLayout(row2)

        # 状态行
        self.status_label = QLabel("状态：等待启动")
        self.status_label.setStyleSheet("color: #475569; font-size: 12px;")
        root.addWidget(self.status_label)

        # 信号挂接
        self._bridge.status_changed.connect(self._on_status)
        self._bridge.gift_ready.connect(self._on_gift)
        self._overlay.show()

    def _on_connect(self) -> None:
        text = self.room_input.text().strip()
        if not text.isdigit():
            self._on_status("房间号必须为数字")
            return
        self.connect_requested.emit(int(text))
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("监听中…")

    def _toggle_overlay(self) -> None:
        if self._overlay.isVisible():
            self._overlay.hide()
        else:
            self._overlay.show()

    def _on_status(self, text: str) -> None:
        self.status_label.setText(f"状态：{text}")

    def _on_gift(self, ev: GiftEvent) -> None:
        self._overlay.push(ev)


def build_ui() -> tuple[QApplication, MainWindow, FloatingOverlay, GiftBridge]:
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    bridge = GiftBridge()
    overlay = FloatingOverlay()
    window = MainWindow(bridge, overlay)
    window.show()
    return app, window, overlay, bridge