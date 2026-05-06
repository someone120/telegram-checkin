"""
Telegram UserBot 自动签到脚本
通过 Telethon 以个人账号身份向指定目标发送签到消息
支持多目标分别按间隔天数发送
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession

STATUS_FILE = "checkin_status.json"

def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_status(status):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

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
      {"target": "@bot1", "message": "/checkin", "interval_days": 1},
      {"target": "-1001234567890", "message": "/sign", "interval_days": 3}
    ]
    interval_days 为间隔天数，1表示每天，3表示每3天
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
                    "interval_days": t.get("interval_days", 1),
                    "topic_id": t.get("topic_id", None),
                })
            return parsed
        except json.JSONDecodeError as e:
            print(f"❌ TARGETS_CONFIG JSON 解析失败: {e}")
            sys.exit(1)

    # 向后兼容：使用旧的 TARGET / MESSAGE 环境变量
    target = os.environ.get("TARGET", "")
    message = os.environ.get("MESSAGE", "/checkin")
    if target:
        return [{"target": target, "message": message, "interval_days": 1}]

    return []


def filter_by_interval(targets, status, send_all=False):
    """根据状态文件和间隔天数过滤目标"""
    if send_all:
        return targets

    today = datetime.now(timezone.utc).date()
    matched = []
    
    for t in targets:
        interval_days = t.get("interval_days", 1)
        target_str = t["target"]
        
        last_date_str = status.get(target_str)
        if not last_date_str:
            matched.append(t)
            continue
            
        try:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            diff_days = (today - last_date).days
            if diff_days >= interval_days:
                matched.append(t)
        except ValueError:
            matched.append(t)

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
    topic_id = target_config.get("topic_id")
    target = parse_target_id(target_str)

    try:
        # 如果指定了话题 ID，则发送到特定话题
        if topic_id:
            await client.send_message(target, message, reply_to=topic_id)
            print(f"  ✅ 已向 {target_str} 的话题 {topic_id} 发送消息: {message}")
        else:
            await client.send_message(target, message)
            print(f"  ✅ 已向 {target_str} 发送消息: {message}")

        if WAIT_RESPONSE > 0:
            print(f"  ⏳ 等待 {WAIT_RESPONSE} 秒以捕获回复...")
            await asyncio.sleep(WAIT_RESPONSE)

            messages = await client.get_messages(target, limit=3)
            for msg in messages:
                # 如果指定了话题 ID，只获取该话题的回复
                if topic_id and hasattr(msg, 'reply_to') and msg.reply_to:
                    if getattr(msg.reply_to, 'reply_to_msg_id', None) == topic_id:
                        print(f"  📩 收到话题回复: {msg.text}")
                        break
                elif msg.sender_id != me.id:
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
    
    # 加载状态文件
    status = load_status()

    # 过滤目标
    if args.target:
        # 手动指定单个目标
        targets = [t for t in all_targets if t["target"] == args.target]
        if not targets:
            print(f"❌ 未找到目标: {args.target}")
            sys.exit(1)
    else:
        # 按间隔天数过滤
        targets = filter_by_interval(all_targets, status, send_all=args.all)

    if not targets:
        now = datetime.now(timezone.utc)
        print(f"⏭️  当前 UTC 时间 {now.strftime('%H:%M')}，没有符合间隔天数要求的目标，跳过")
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
            interval_days = target_config.get("interval_days", 1)
            target_str = target_config["target"]
            print(
                f"\n[{i}/{len(targets)}] 目标: "
                f"{target_str} (间隔: {interval_days}天)"
            )

            if await send_checkin(client, me, target_config):
                success_count += 1
                status[target_str] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            else:
                fail_count += 1
        
        # 保存新的状态
        save_status(status)

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
