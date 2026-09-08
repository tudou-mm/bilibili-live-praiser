"""DeepSeek 夸赞生成器。

按礼物价值分级用不同 system prompt，调用 deepseek-chat 生成 1-2 句夸赞。
失败时降级到本地模板，保证悬浮窗不中断。
"""
from __future__ import annotations
import random
import threading
from typing import Optional

import requests

from config import DEEPSEEK
from bilibili import GiftEvent, GiftTier


STYLE_PROMPTS: dict[GiftTier, str] = {
    GiftTier.SMALL: (
        "你是直播间主播的捧场王，语气轻松活泼。"
        "为观众送出小额礼物写一句 8-20 字的中文夸赞，要有梗不油腻。"
    ),
    GiftTier.MEDIUM: (
        "你是直播间气氛组高手。"
        "为观众送出中等礼物写一句 15-30 字的中文夸赞，要热情有感染力。"
    ),
    GiftTier.LARGE: (
        "你是直播间天花板彩虹屁选手。"
        "为观众送出大额礼物写一句 20-40 字的中文夸赞，可以浮夸但不低俗。"
    ),
    GiftTier.LEGENDARY: (
        "你是直播间史诗级气氛组。"
        "为观众送出顶级礼物写一段 30-60 字的中文赞颂，气势拉满像写颁奖词。"
    ),
}

# 本地降级模板，按礼物价值档位备几套
FALLBACK_TEMPLATES: dict[GiftTier, list[str]] = {
    GiftTier.SMALL: [
        "{name} 小礼物大心意，谢谢捧场！",
        "感谢 {name} 的小支持，主播记在心里啦~",
        "{name} 又来啦，礼轻情意重！",
    ],
    GiftTier.MEDIUM: [
        "{name} 大气！这份心意主播收到了！",
        "老板 {name} 中等礼物到位，气氛组向你敬礼！",
        "{name} 这波属实慷慨，主播给你比心！",
    ],
    GiftTier.LARGE: [
        "{name} 老板大气！全场最强应援，主播都看呆了！",
        "感谢 {name} 的豪华礼物，今天的高光属于你！",
        "{name} 这波礼物直接把直播间气氛拉满！",
    ],
    GiftTier.LEGENDARY: [
        "{name} 史诗级礼物！今夜属于你，主播为你封神之巅！",
        "感谢 {name} 的顶级礼物，这是什么神仙观众，请收下主播的膝盖！",
        "{name} 的礼物闪耀全场，今日 MVP 非你莫属！",
    ],
}


class Praiser:
    """DeepSeek 夸赞生成器，线程安全。"""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._lock = threading.Lock()

    def _build_messages(self, ev: GiftEvent) -> list[dict]:
        sys_prompt = STYLE_PROMPTS[ev.tier]
        user_prompt = (
            f"观众昵称：{ev.user_name}\n"
            f"观众等级：Lv.{ev.user_level}\n"
            f"礼物：{ev.gift_name} x {ev.num}\n"
            f"礼物总价值：约 {ev.total_price:.1f} 元\n"
            "请只输出夸赞正文，不要加引号、不要加表情符号。"
        )
        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _call_deepseek(self, messages: list[dict]) -> Optional[str]:
        if not DEEPSEEK.api_key:
            return None
        try:
            resp = self._session.post(
                f"{DEEPSEEK.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": DEEPSEEK.model,
                    "messages": messages,
                    "temperature": 0.9,
                    "max_tokens": 120,
                },
                timeout=15,
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[Praiser] DeepSeek 调用失败: {e}")
            return None

    def _fallback(self, ev: GiftEvent) -> str:
        tmpl = random.choice(FALLBACK_TEMPLATES[ev.tier])
        return tmpl.format(name=ev.user_name)

    def generate(self, ev: GiftEvent) -> str:
        """生成夸赞文案。优先 DeepSeek，失败走模板。"""
        with self._lock:
            text = self._call_deepseek(self._build_messages(ev))
            if not text:
                text = self._fallback(ev)
            ev.praise = text
            return text


if __name__ == "__main__":
    from bilibili import GiftEvent
    p = Praiser()
    for tier in GiftTier:
        ev = GiftEvent.build(user_name=f"测试用户_{tier.value}", gift_id=7, num=1)
        ev.tier = tier
        ev.user_level = 30
        print(tier.value, "->", p.generate(ev))