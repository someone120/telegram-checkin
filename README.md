# Telegram UserBot 自动签到

利用 GitHub Actions 定时以个人 Telegram 账号（UserBot）身份发送签到消息。

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

| Secret 名称 | 说明 | 示例 |
|---|---|---|
| `API_ID` | Telegram API ID | `12345678` |
| `API_HASH` | Telegram API Hash | `abcdef1234567890...` |
| `SESSION_STRING` | Telethon Session String | `1BVtsO...` |
| `TARGET` | 签到目标（用户名或 ID） | `@some_bot` 或 `-1001234567890` |
| `MESSAGE` | 签到消息内容 | `/checkin` |

### 4. 触发签到

- **自动执行**：默认每天北京时间 9:00 自动运行
- **手动触发**：在仓库 Actions 页面点击 **Run workflow**

## 自定义配置

### 修改定时计划

编辑 `.github/workflows/checkin.yml` 中的 cron 表达式：

```yaml
schedule:
  - cron: '0 1 * * *'  # UTC 时间，北京时间 = UTC + 8
```

常用示例：
- `0 1 * * *` → 每天北京时间 9:00
- `0 0 * * *` → 每天北京时间 8:00
- `0 2 * * 1-5` → 工作日北京时间 10:00

### 等待回复时长

可添加 `WAIT_RESPONSE` Secret（单位：秒，默认 10）来控制等待机器人回复的时间。

## 项目结构

```
├── .github/workflows/
│   └── checkin.yml        # GitHub Actions 工作流
├── checkin.py             # 签到脚本
├── generate_session.py    # Session String 生成器（本地使用）
├── requirements.txt       # Python 依赖
└── README.md
```

## 注意事项

- Session String 包含完整的账号授权信息，**绝对不要**提交到代码仓库
- GitHub Actions 的 cron schedule 可能有几分钟的延迟，这是正常现象
- 如果 Session 失效，需要重新运行 `generate_session.py` 并更新 Secret
