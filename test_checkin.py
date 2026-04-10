"""
测试 checkin.py 的核心功能，重点验证话题（Topics）功能支持
"""

import os
import json
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# 在导入 checkin 之前设置环境变量，避免模块级代码报错
os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "test_hash")
os.environ.setdefault("SESSION_STRING", "test_session")
os.environ.setdefault("WAIT_RESPONSE", "0")

import checkin


# ============================================================
# parse_targets 测试
# ============================================================

class TestParseTargets:
    """测试目标配置解析，特别是 topic_id 字段"""

    def test_parse_targets_with_topic_id(self):
        """验证 TARGETS_CONFIG 中包含 topic_id 时能正确解析"""
        config = json.dumps([
            {"target": "-1001234567890", "message": "/sign", "schedule": "06:00", "topic_id": 1234}
        ])
        with patch.dict(os.environ, {"TARGETS_CONFIG": config}, clear=False):
            targets = checkin.parse_targets()
        assert len(targets) == 1
        assert targets[0]["target"] == "-1001234567890"
        assert targets[0]["message"] == "/sign"
        assert targets[0]["schedule"] == "06:00"
        assert targets[0]["topic_id"] == 1234

    def test_parse_targets_without_topic_id(self):
        """验证不指定 topic_id 时默认为 None"""
        config = json.dumps([
            {"target": "@bot1", "message": "/checkin", "schedule": "01:00"}
        ])
        with patch.dict(os.environ, {"TARGETS_CONFIG": config}, clear=False):
            targets = checkin.parse_targets()
        assert len(targets) == 1
        assert targets[0]["topic_id"] is None

    def test_parse_targets_multiple_with_mixed_topic_id(self):
        """验证多个目标中部分有 topic_id、部分没有"""
        config = json.dumps([
            {"target": "@bot1", "message": "/checkin"},
            {"target": "-1001234567890", "message": "/sign", "topic_id": 999},
            {"target": "@bot2", "message": "/start", "topic_id": 42},
        ])
        with patch.dict(os.environ, {"TARGETS_CONFIG": config}, clear=False):
            targets = checkin.parse_targets()
        assert len(targets) == 3
        assert targets[0]["topic_id"] is None
        assert targets[1]["topic_id"] == 999
        assert targets[2]["topic_id"] == 42

    def test_parse_targets_legacy_format_no_topic_id(self):
        """验证旧格式（TARGET/MESSAGE）没有 topic_id 字段"""
        env = {"TARGETS_CONFIG": "", "TARGET": "@old_bot", "MESSAGE": "/checkin"}
        with patch.dict(os.environ, env, clear=False):
            targets = checkin.parse_targets()
        assert len(targets) == 1
        assert targets[0]["target"] == "@old_bot"
        assert "topic_id" not in targets[0]  # 旧格式不包含 topic_id

    def test_parse_targets_topic_id_zero(self):
        """验证 topic_id 为 0 时能正确解析（0 是有效值但 falsy）"""
        config = json.dumps([
            {"target": "@bot1", "message": "/checkin", "topic_id": 0}
        ])
        with patch.dict(os.environ, {"TARGETS_CONFIG": config}, clear=False):
            targets = checkin.parse_targets()
        assert targets[0]["topic_id"] == 0


# ============================================================
# send_checkin 测试
# ============================================================

class TestSendCheckin:
    """测试消息发送逻辑，特别是话题消息发送"""

    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.send_message = AsyncMock()
        client.get_messages = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def mock_me(self):
        me = MagicMock()
        me.id = 123456
        return me

    @pytest.mark.asyncio
    async def test_send_with_topic_id(self, mock_client, mock_me):
        """验证指定 topic_id 时调用 send_message 带 reply_to 参数"""
        config = {
            "target": "-1001234567890",
            "message": "/checkin",
            "topic_id": 1234,
        }
        with patch.object(checkin, 'WAIT_RESPONSE', 0):
            result = await checkin.send_checkin(mock_client, mock_me, config)

        assert result is True
        mock_client.send_message.assert_called_once_with(
            -1001234567890, "/checkin", reply_to=1234
        )

    @pytest.mark.asyncio
    async def test_send_without_topic_id(self, mock_client, mock_me):
        """验证不指定 topic_id 时正常调用 send_message（无 reply_to）"""
        config = {
            "target": "@bot1",
            "message": "/checkin",
            "topic_id": None,
        }
        with patch.object(checkin, 'WAIT_RESPONSE', 0):
            result = await checkin.send_checkin(mock_client, mock_me, config)

        assert result is True
        mock_client.send_message.assert_called_once_with("@bot1", "/checkin")

    @pytest.mark.asyncio
    async def test_send_without_topic_id_key(self, mock_client, mock_me):
        """验证 config 中完全没有 topic_id 键时也能正常工作"""
        config = {
            "target": "@bot1",
            "message": "/checkin",
        }
        with patch.object(checkin, 'WAIT_RESPONSE', 0):
            result = await checkin.send_checkin(mock_client, mock_me, config)

        assert result is True
        mock_client.send_message.assert_called_once_with("@bot1", "/checkin")

    @pytest.mark.asyncio
    async def test_send_with_topic_id_and_wait_response(self, mock_client, mock_me):
        """验证带 topic_id 时等待回复并正确过滤话题回复"""
        # 模拟一条来自话题的回复
        reply_to_mock = MagicMock()
        reply_to_mock.reply_to_msg_id = 1234

        topic_msg = MagicMock()
        topic_msg.sender_id = 999
        topic_msg.reply_to = reply_to_mock
        topic_msg.text = "签到成功！"

        mock_client.get_messages = AsyncMock(return_value=[topic_msg])

        config = {
            "target": "-1001234567890",
            "message": "/checkin",
            "topic_id": 1234,
        }
        with patch.object(checkin, 'WAIT_RESPONSE', 1):
            result = await checkin.send_checkin(mock_client, mock_me, config)

        assert result is True
        mock_client.send_message.assert_called_once_with(
            -1001234567890, "/checkin", reply_to=1234
        )

    @pytest.mark.asyncio
    async def test_send_with_topic_id_ignores_non_topic_reply(self, mock_client, mock_me):
        """验证带 topic_id 时忽略不属于该话题的回复"""
        # 模拟一条来自其他话题的回复
        reply_to_mock = MagicMock()
        reply_to_mock.reply_to_msg_id = 9999  # 不同的话题

        other_msg = MagicMock()
        other_msg.sender_id = 999
        other_msg.reply_to = reply_to_mock
        other_msg.text = "其他话题的消息"

        mock_client.get_messages = AsyncMock(return_value=[other_msg])

        config = {
            "target": "-1001234567890",
            "message": "/checkin",
            "topic_id": 1234,
        }
        with patch.object(checkin, 'WAIT_RESPONSE', 1):
            result = await checkin.send_checkin(mock_client, mock_me, config)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self, mock_client, mock_me):
        """验证发送失败时返回 False"""
        mock_client.send_message = AsyncMock(side_effect=Exception("网络错误"))

        config = {
            "target": "@bot1",
            "message": "/checkin",
            "topic_id": None,
        }
        with patch.object(checkin, 'WAIT_RESPONSE', 0):
            result = await checkin.send_checkin(mock_client, mock_me, config)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_with_numeric_target_and_topic(self, mock_client, mock_me):
        """验证数字目标 ID 与 topic_id 结合使用"""
        config = {
            "target": "-1001234567890",
            "message": "/sign",
            "topic_id": 5678,
        }
        with patch.object(checkin, 'WAIT_RESPONSE', 0):
            result = await checkin.send_checkin(mock_client, mock_me, config)

        assert result is True
        mock_client.send_message.assert_called_once_with(
            -1001234567890, "/sign", reply_to=5678
        )


# ============================================================
# parse_target_id 测试
# ============================================================

class TestParseTargetId:
    def test_numeric_string(self):
        assert checkin.parse_target_id("-1001234567890") == -1001234567890

    def test_username_string(self):
        assert checkin.parse_target_id("@bot1") == "@bot1"


# ============================================================
# filter_by_schedule 测试
# ============================================================

class TestFilterBySchedule:
    def test_send_all_returns_everything(self):
        targets = [
            {"target": "@a", "schedule": "01:00", "topic_id": 123},
            {"target": "@b", "schedule": "14:00", "topic_id": None},
        ]
        result = checkin.filter_by_schedule(targets, send_all=True)
        assert len(result) == 2

    def test_no_schedule_always_matched(self):
        targets = [
            {"target": "@a", "schedule": "", "topic_id": 123},
        ]
        result = checkin.filter_by_schedule(targets, send_all=False)
        assert len(result) == 1

    def test_topic_id_preserved_after_filter(self):
        """验证过滤后 topic_id 信息保留"""
        targets = [
            {"target": "@a", "schedule": "", "topic_id": 999},
        ]
        result = checkin.filter_by_schedule(targets, send_all=False)
        assert result[0]["topic_id"] == 999
