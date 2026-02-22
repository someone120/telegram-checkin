"""
Telegram UserBot 自动签到脚本
通过 Telethon 以个人账号身份向指定目标发送签到消息
"""

import os
import sys
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

# 从环境变量读取配置
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
TARGET = os.environ.get("TARGET", "")  # 签到目标: @username 或数字ID
MESSAGE = os.environ.get("MESSAGE", "/checkin")  # 签到消息
WAIT_RESPONSE = int(os.environ.get("WAIT_RESPONSE", "10"))  # 等待回复的秒数


async def main():
    if not all([API_ID, API_HASH, SESSION_STRING, TARGET]):
        print("❌ 缺少必要的环境变量，请检查配置：")
        print("   API_ID, API_HASH, SESSION_STRING, TARGET")
        sys.exit(1)

    # 尝试将 TARGET 转为数字 ID
    target = TARGET
    try:
        target = int(TARGET)
    except ValueError:
        pass

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ Session 已失效，请重新生成 SESSION_STRING")
            sys.exit(1)

        me = await client.get_me()
        print(f"✅ 已登录: {me.first_name} (@{me.username})")

        # 发送签到消息
        await client.send_message(target, MESSAGE)
        print(f"✅ 已向 {TARGET} 发送消息: {MESSAGE}")

        # 等待并捕获回复
        if WAIT_RESPONSE > 0:
            print(f"⏳ 等待 {WAIT_RESPONSE} 秒以捕获回复...")
            await asyncio.sleep(WAIT_RESPONSE)

            # 获取最新消息查看回复
            messages = await client.get_messages(target, limit=3)
            for msg in messages:
                if msg.sender_id != me.id:
                    print(f"📩 收到回复: {msg.text}")
                    break

        print("🎉 签到完成!")

    except Exception as e:
        print(f"❌ 签到失败: {e}")
        sys.exit(1)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
