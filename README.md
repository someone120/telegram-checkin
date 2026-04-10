# Telegram UserBot 自动签到

利用 GitHub Actions 定时以个人 Telegram 账号（UserBot）身份发送签到消息。

支持**多个目标分别定时发送**。

## 快速开始

### 1. 获取 Telegram API 凭据

1. 访问 [my.telegram.org](https://my.telegram.org)
2. 登录你的 Telegram 账号
3. 进入 **API development tools**
4. 创建应用，获取 `API_ID` 和 `API_HASH`

### 2. 生成 Session String

```bash
pip install telethon
python generate_session.py
```

按提示输入 API_ID、API_HASH、手机号码和验证码，脚本会输出你的 Session String。

> ⚠️ **Session String 等同于账号密码，请妥善保管，切勿泄露！**

### 3. 配置 GitHub Secrets

在仓库 **Settings → Secrets and variables → Actions** 中添加以下 Secrets：

| Secret 名称 | 说明 | 必填 |
|---|---|---|
| `API_ID` | Telegram API ID | 是 |
| `API_HASH` | Telegram API Hash | 是 |
| `SESSION_STRING` | Telethon Session String | 是 |
| `TARGETS_CONFIG` | 多目标配置（JSON 数组，见下方说明） | 是（二选一） |
| `TARGET` | 单目标签到（向后兼容） | 是（二选一） |
| `MESSAGE` | 单目标签到消息（配合 TARGET 使用） | 否 |
| `WAIT_RESPONSE` | 等待回复秒数（默认 10） | 否 |

### 4. 配置多目标签到（TARGETS_CONFIG）

`TARGETS_CONFIG` 是一个 JSON 数组，每个元素代表一个签到目标：

```json
[
  {
    "target": "@bot1",
    "message": "/checkin",
    "schedule": "01:00"
  },
  {
    "target": "-1001234567890",
    "message": "/sign",
    "schedule": "06:00"
  },
  {
    "target": "@another_bot",
    "message": "/checkin",
    "schedule": "14:00"
  }
]
```

| 字段 | 说明 | 必填 | 默认值 |
|---|---|---|---|
| `target` | 签到目标（`@username` 或数字 ID） | 是 | - |
| `message` | 签到消息内容 | 否 | `/checkin` |
| `schedule` | 发送时间（UTC，格式 `HH:MM`） | 否 | 不限时间，每次触发都发送 |
| `topic_id` | 话题 ID（用于支持话题的超级群组） | 否 | None |

> `schedule` 使用 **UTC 时间**，北京时间需要 **减 8 小时**。例如北京时间 09:00 对应 UTC `01:00`，北京时间 22:00 对应 UTC `14:00`。

> 没有设置 `schedule` 的目标在每次 cron 触发时都会发送。

### 5. 配置话题功能（可选）

如果您的目标是支持话题功能的超级群组，可以在配置中添加 `topic_id` 字段来指定消息发送到特定话题：

```json
[
  {
    "target": "-1001234567890",
    "message": "/sign",
    "schedule": "06:00",
    "topic_id": 1234
  }
]
```

其中 `topic_id` 是您要发送消息到的话题 ID。您可以在 Telegram 客户端中通过以下方式获取话题 ID：
1. 打开支持话题的群组
2. 点击特定话题
3. 查看 URL 中的 ID 参数（在 Telegram Web 中可见）

### 6. 配置 workflow cron 时间

编辑 `.github/workflows/checkin.yml` 中的 `schedule`，确保覆盖所有目标的发送时间：

```yaml
schedule:
  - cron: '0 1 * * *'   # UTC 01:00 → 覆盖 schedule 为 01:00 的目标
  - cron: '0 6 * * *'   # UTC 06:00 → 覆盖 schedule 为 06:00 的目标
  - cron: '0 14 * * *'  # UTC 14:00 → 覆盖 schedule 为 14:00 的目标
```

脚本在每次被 cron 触发时，会自动判断当前 UTC 时间，只向匹配的目标发送消息（±5 分钟容差）。

### 6. 触发签到

- **自动执行**：按 cron 定时自动运行，根据每个目标的 `schedule` 匹配发送
- **手动触发**：在仓库 Actions 页面点击 **Run workflow**
  - 勾选 **"向所有目标发送"** 可一次性向所有目标发送（忽略定时设置）
  - 填写 **"仅向指定目标发送"** 可只向某一个目标发送

## 使用示例

### 示例 1：两个群不同时间签到

```json
[
  {"target": "@checkin_bot", "message": "/checkin", "schedule": "01:00"},
  {"target": "-1001999888777", "message": "/sign", "schedule": "14:00"}
]
```

对应 workflow 配置：

```yaml
schedule:
  - cron: '0 1 * * *'
  - cron: '0 14 * * *'
```

效果：
- 每天北京时间 09:00 向 `@checkin_bot` 发送 `/checkin`
- 每天北京时间 22:00 向群 `-1001999888777` 发送 `/sign`

### 示例 4：向支持话题的群组发送消息

```json
[
  {
    "target": "-1001234567890",
    "message": "/checkin",
    "schedule": "01:00",
    "topic_id": 1234
  }
]
```

效果：
- 每天北京时间 09:00 向群组 `-1001234567890` 的话题 `1234` 发送 `/checkin` 消息

### 示例 2：多个群同一时间签到

```json
[
  {"target": "@bot_a", "message": "/checkin", "schedule": "01:00"},
  {"target": "@bot_b", "message": "/checkin", "schedule": "01:00"},
  {"target": "@bot_c", "message": "/sign", "schedule": "01:00"}
]
```

对应 workflow 只需一个 cron：

```yaml
schedule:
  - cron: '0 1 * * *'
```

效果：每天北京时间 09:00 同时向三个目标发送签到消息。

### 示例 3：向后兼容（单目标）

如果不想使用新的 JSON 配置，仍然可以使用原来的方式：

| Secret | 值 |
|---|---|
| `TARGET` | `@some_bot` |
| `MESSAGE` | `/checkin` |

## 本地调试

```bash
# 设置环境变量
export API_ID=12345678
export API_HASH=abcdef1234567890
export SESSION_STRING=1BVtsO...
export TARGETS_CONFIG='[{"target":"@bot1","message":"/checkin","schedule":"01:00"}]'

# 向所有目标发送（忽略定时）
python checkin.py --all

# 仅向指定目标发送
python checkin.py --target @bot1

# 按定时规则自动匹配（正常 cron 运行模式）
python checkin.py
```

## 项目结构

```
├── .github/workflows/
│   └── checkin.yml        # GitHub Actions 工作流（多 cron 定时）
├── checkin.py             # 签到脚本（支持多目标 + 定时）
├── generate_session.py    # Session String 生成器（本地使用）
├── requirements.txt       # Python 依赖
└── README.md
```

## 注意事项

- Session String 包含完整的账号授权信息，**绝对不要**提交到代码仓库
- GitHub Actions 的 cron schedule 可能有几分钟的延迟，脚本设置了 ±5 分钟容差
- 如果 Session 失效，需要重新运行 `generate_session.py` 并更新 Secret
- `TARGETS_CONFIG` 中的 `schedule` 时间必须和 workflow 的 cron 时间对应，否则不会触发
- 手动触发时默认向所有目标发送，无需关心 schedule 设置
