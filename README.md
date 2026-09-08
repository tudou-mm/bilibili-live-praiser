# B 站直播间 AI 夸赞悬浮窗

通过 B 站 WebSocket + 开放平台 API 抓取直播间礼物事件，
按礼物价值分级调用 DeepSeek 生成夸赞文案，以 PyQt6 桌面悬浮窗实时展示。

## 安装

```bash
cd bilibili_praiser
python -m pip install -r requirements.txt
```

## 配置

复制 `.env` 并填入：

| 字段 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek 控制台创建 |
| `BILI_APP_ID` / `BILI_APP_SECRET` | B 站开放平台 OAuth2 应用（**当前账号只给了 access_key，请补 App ID/Secret**） |
| `BILI_ACCESS_KEY_ID` / `BILI_ACCESS_KEY_SECRET` | 已配置 |
| `BILI_SESSDATA` / `BILI_BILI_JCT` | 浏览器登录 bilibili.com -> F12 -> Application -> Cookies 复制 |
| `ROOM_ID` | 默认房间号，0 = 启动后手动输入 |

## 启动

```bash
python main.py
```

启动后：
1. 主窗口输入房间号点 **开始监听**
2. 右上角悬浮窗自动弹出，显示礼物事件
3. 单条展示包含 `用户名(Lv.XX) [舰长/提督/总督]` + 礼物名 + 数量 + AI 夸赞
4. 同用户 3 秒内合并，最多同时 5 条，单条 8 秒后自动消失

## 已知限制
- B 站开放平台 OAuth2 需要 **App ID + App Secret**，当前仅提供了 access_key_id/secret，
  App ID/Secret 留 `.env` 占位，补齐后 API 通道自动启用
- WebSocket 需登录态 Cookie（`SESSDATA` + `bili_jct`），未配置时跳过
- 礼物价值采用内置表（参考 B 站公开价格），遇变动可编辑 `bilibili/__init__.py` 的 `BUILTIN_GIFT_PRICE`

## 架构

```
bilibili_praiser/
├── main.py                # 入口：连接 UI / WS / AI
├── config.py              # 凭证加载
├── bilibili/
│   ├── api_client.py      # 开放平台 OAuth2 + 公开 API
│   ├── ws_client.py       # WebSocket 弹幕协议（op=5/7/8/2/3）
│   └── __init__.py        # GiftEvent 模型 + 内置礼物价值表
├── ai/
│   └── praiser.py         # DeepSeek 调用 + 本地模板兜底
└── ui/
    └── __init__.py        # PyQt6 主窗 + 悬浮展示窗
```