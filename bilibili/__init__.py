"""礼物事件模型 + 价值分级。

B 站礼物价格经常变动，但常见礼物价值相对稳定。
保留一份内置表作为兜底，并按价值分 4 档用于切换 AI 文案风格。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GiftTier(str, Enum):
    """礼物价值分级，对应不同夸赞风格。"""
    SMALL = "small"        # < 10 元：短句调侃
    MEDIUM = "medium"      # 10-100 元：热情夸赞
    LARGE = "large"        # 100-1000 元：浮夸彩虹屁
    LEGENDARY = "legendary"  # > 1000 元：史诗级赞颂

    @classmethod
    def from_price(cls, price: float) -> "GiftTier":
        if price >= 1000:
            return cls.LEGENDARY
        if price >= 100:
            return cls.LARGE
        if price >= 10:
            return cls.MEDIUM
        return cls.SMALL


# 内置礼物价值表（单位：元）。
# 数据来源：B 站礼物面板常见公开价格；如有变动可在代码中更新。
BUILTIN_GIFT_PRICE: dict[int, float] = {
    1: 0.1,       # 辣条
    2: 1.0,       # 小心心
    3: 1.0,       # 告白气球
    4: 9.9,       # 盛世美颜
    5: 19.8,      # 摩天大楼
    6: 49.8,      # 城堡
    7: 99.0,      # 火箭
    8: 199.0,     # 飞船
    9: 999.0,     # 跑车
    10: 1999.0,   # 宇宙飞船
    25: 5.0,      # 粉丝团
    39: 100.0,    # 钻粉
    30607: 100.0, # 大航海（舰长）
    30608: 1000.0,  # 提督
    30609: 19998.0,  # 总督
}


@dataclass
class GiftEvent:
    """一条礼物事件，悬浮窗显示的基本单元。"""
    user_name: str                       # 送礼用户名
    user_level: int = 0                  # 用户等级
    guard_level: int = 0                 # 0=普通 1=总督 2=提督 3=舰长
    gift_name: str = "未知礼物"
    gift_id: int = 0
    num: int = 1                         # 数量
    price_per_unit: float = 0.0          # 单价（元）
    total_price: float = 0.0             # 总价（元）
    tier: GiftTier = GiftTier.SMALL
    praise: str = ""                    # AI 生成的夸赞，生成后回填
    timestamp: float = 0.0

    @classmethod
    def build(
        cls,
        user_name: str,
        gift_id: int,
        num: int = 1,
        user_level: int = 0,
        guard_level: int = 0,
        gift_name: Optional[str] = None,
    ) -> "GiftEvent":
        import time
        price = BUILTIN_GIFT_PRICE.get(gift_id, 1.0)
        total = price * num
        return cls(
            user_name=user_name or "神秘观众",
            user_level=user_level,
            guard_level=guard_level,
            gift_id=gift_id,
            gift_name=gift_name or f"礼物#{gift_id}",
            num=num,
            price_per_unit=price,
            total_price=total,
            tier=GiftTier.from_price(total),
            timestamp=time.time(),
        )

    def display_line(self) -> str:
        """悬浮窗展示行：用户名(Lv.XX) + 礼物 + 夸赞"""
        guard_tag = ""
        if self.guard_level == 3:
            guard_tag = " [舰长]"
        elif self.guard_level == 2:
            guard_tag = " [提督]"
        elif self.guard_level == 1:
            guard_tag = " [总督]"
        return f"{self.user_name}(Lv.{self.user_level}){guard_tag} 送出 {self.gift_name}x{self.num}"