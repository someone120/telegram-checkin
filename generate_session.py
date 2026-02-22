"""
Telethon Session String 生成器
在本地运行此脚本以交互式生成 SESSION_STRING
生成后将其添加到 GitHub Secrets
"""

import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(input("请输入 API_ID: "))
API_HASH = input("请输入 API_HASH: ")


async def main():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()

    session_string = client.session.save()
    me = await client.get_me()

    print("\n" + "=" * 50)
    print(f"✅ 登录成功: {me.first_name} (@{me.username})")
    print("=" * 50)
    print("\n📋 你的 SESSION_STRING (请妥善保管):\n")
    print(session_string)
    print("\n⚠️  请将此字符串添加到 GitHub Secrets 的 SESSION_STRING 中")
    print("⚠️  切勿将此字符串提交到代码仓库或分享给他人！")
    print("=" * 50)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
