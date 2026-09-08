"""DeepSeek 夸赞生成器。

按礼物价值分级用不同 system prompt，调用 deepseek-chat 生成 1-2 句夸赞。
失败时降级到本地模板，保证悬浮窗不中断。"""