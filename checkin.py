"""
Telegram UserBot 自动签到脚本
通过 Telethon 以个人账号身份向指定目标发送签到消息
支持多目标分别定时发送
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession

# 从环境变量读取配置
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
WAIT_RESPONSE = int(os.environ.get("WAIT_RESPONSE", "10"))


def parse_targets():
    """解析目标配置，支持两种格式：
    1. 新格式：TARGETS_CONFIG 环境变量（JSON 数组）
    2. 旧格式：TARGET + MESSAGE 环境变量（单目标，向后兼容）

    新格式示例：
    [
      {"target": "@bot1", "message": "/checkin", "schedule": "01:00"},
      {"target": "-1001234567890", "message": "/sign", "schedule": "14:00"}
    ]
    schedule 为 UTC 时间，格式 HH:MM
    """
    targets_json = os.environ.get("TARGETS_CONFIG", "")

    if targets_json:
        try:
            targets = json.loads(targets_json)
            if not isinstance(targets, list):
                print("❌ TARGETS_CONFIG 必须是 JSON 数组")
                sys.exit(1)

            parsed = []
            for i, t in enumerate(targets):
                if "target" not in t:
                    print(f"❌ 第 {i+1} 个目标缺少 'target' 字段")
                    sys.exit(1)
                parsed.append({
                    "target": t["target"],
                    "message": t.get("message", "/checkin"),
                    "schedule": t.get("schedule", ""),
                })
            return parsed
        except json.JSONDecodeError as e:
            print(f"❌ TARGETS_CONFIG JSON 解析失败: {e}")
            sys.exit(1)

    # 向后兼容：使用旧的 TARGET / MESSAGE 环境变量
    target = os.environ.get("TARGET", "")
    message = os.environ.get("MESSAGE", "/checkin")
    if target:
        return [{"target": target, "message": message, "schedule": ""}]

    return []


def filter_by_schedule(targets, send_all=False):
    """根据当前 UTC 时间过滤应该发送的目标
    使用 ±5 分钟容差来应对 GitHub Actions cron 延迟
    """
    if send_all:
        return targets

    now = datetime.now(timezone.utc)
    current_minutes = now.hour * 60 + now.minute

    matched = []
    for t in targets:
        schedule = t.get("schedule", "").strip()
        if not schedule:
            # 没有设置 schedule 的目标始终发送
            matched.append(t)
            continue

        try:
            parts = schedule.split(":")
            sched_hour = int(parts[0])
            sched_minute = int(parts[1]) if len(parts) > 1 else 0
            sched_minutes = sched_hour * 60 + sched_minute

            # ±5 分钟容差，处理 GitHub Actions 延迟
            diff = abs(current_minutes - sched_minutes)
            # 处理跨午夜的情况 (如 23:58 vs 00:02)
            diff = min(diff, 1440 - diff)

            if diff <= 5:
                matched.append(t)
        except (ValueError, IndexError):
            print(f"⚠️  目标 {t['target']} 的 schedule 格式无效: {schedule}，跳过")

    return matched


def parse_target_id(target_str):
    """尝试将目标字符串转为数字 ID"""
    try:
        return int(target_str)
    except ValueError:
        return target_str


async def send_checkin(client, me, target_config):
    """向单个目标发送签到消息并捕获回复"""
    target_str = target_config["target"]
    message = target_config["message"]
    target = parse_target_id(target_str)

    try:
        await client.send_message(target, message)
        print(f"  ✅ 已向 {target_str} 发送消息: {message}")

        if WAIT_RESPONSE > 0:
            print(f"  ⏳ 等待 {WAIT_RESPONSE} 秒以捕获回复...")
            await asyncio.sleep(WAIT_RESPONSE)

            messages = await client.get_messages(target, limit=3)
            for msg in messages:
                if msg.sender_id != me.id:
                    print(f"  📩 收到回复: {msg.text}")
                    break

        return True
    except Exception as e:
        print(f"  ❌ 向 {target_str} 发送失败: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Telegram 自动签到")
    parser.add_argument(
        "--all", action="store_true",
        help="向所有目标发送，忽略定时设置"
    )
    parser.add_argument(
        "--target", type=str, default="",
        help="仅向指定目标发送（目标名或 ID）"
    )
    args = parser.parse_args()

    if not all([API_ID, API_HASH, SESSION_STRING]):
        print("❌ 缺少必要的环境变量，请检查配置：")
        print("   API_ID, API_HASH, SESSION_STRING")
        sys.exit(1)

    # 解析目标配置
    all_targets = parse_targets()
    if not all_targets:
        print("❌ 未配置任何签到目标")
        print("   请设置 TARGETS_CONFIG 或 TARGET 环境变量")
        sys.exit(1)

    print(f"📋 已加载 {len(all_targets)} 个签到目标")

    # 过滤目标
    if args.target:
        # 手动指定单个目标
        targets = [t for t in all_targets if t["target"] == args.target]
        if not targets:
            print(f"❌ 未找到目标: {args.target}")
            sys.exit(1)
    else:
        # 按定时规则过滤
        targets = filter_by_schedule(all_targets, send_all=args.all)

    if not targets:
        now = datetime.now(timezone.utc)
        print(f"⏭️  当前 UTC 时间 {now.strftime('%H:%M')}，没有匹配的定时目标，跳过")
        return

    print(f"🎯 本次将向 {len(targets)} 个目标发送签到消息")

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ Session 已失效，请重新生成 SESSION_STRING")
            sys.exit(1)

        me = await client.get_me()
        print(f"✅ 已登录: {me.first_name} (@{me.username})")

        success_count = 0
        fail_count = 0

        for i, target_config in enumerate(targets, 1):
            schedule_info = (
                f" (定时: UTC {target_config['schedule']})"
                if target_config.get("schedule")
                else ""
            )
            print(
                f"\n[{i}/{len(targets)}] 目标: "
                f"{target_config['target']}{schedule_info}"
            )

            if await send_checkin(client, me, target_config):
                success_count += 1
            else:
                fail_count += 1

        print(f"\n🎉 签到完成! 成功: {success_count}, 失败: {fail_count}")

        if fail_count > 0:
            sys.exit(1)

    except Exception as e:
        print(f"❌ 签到失败: {e}")
        sys.exit(1)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
