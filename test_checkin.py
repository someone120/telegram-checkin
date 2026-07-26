"""
测试 checkin.py 的核心功能，验证加密配置文件读取与话题功能支持
"""

import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from cryptography.fernet import Fernet

# 在导入 checkin 之前设置环境变量，避免模块级代码报错
os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "test_hash")
os.environ.setdefault("SESSION_STRING", "test_session")
os.environ.setdefault("WAIT_RESPONSE", "0")

import checkin


# ============================================================
# parse_targets 测试 (涵盖加密文件与环境变量)
# ============================================================

class TestParseTargets:
    """测试目标配置解析，涵盖本地 AES 加密文件读取及向下兼容"""

    def test_parse_targets_legacy_format_no_topic_id(self):
        """验证旧格式（TARGET/MESSAGE）没有 topic_id 字段"""
        env = {"TARGETS_CONFIG": "", "TARGET": "@old_bot", "MESSAGE": "/checkin"}
        # 确保不存在加密文件干扰测试
        with patch("os.path.exists", side_effect=lambda path: False):
            with patch.dict(os.environ, env, clear=False):
                targets = checkin.parse_targets()
        assert len(targets) == 1
        assert targets[0]["target"] == "@old_bot"
        assert "topic_id" not in targets[0]

    def test_parse_targets_env_json_without_topic_id(self):
        """验证环境变量 TARGETS_CONFIG JSON 中不指定 topic_id 时默认为 None"""
        config = json.dumps([
            {"target": "@bot1", "message": "/checkin"}
        ])
        with patch("os.path.exists", side_effect=lambda path: False):
            with patch.dict(os.environ, {"TARGETS_CONFIG": config}, clear=False):
                targets = checkin.parse_targets()
        assert len(targets) == 1
        assert targets[0]["topic_id"] is None

    def test_parse_targets_encrypted_file_with_env_key(self):
        """验证存在 targets.enc 且有环境变量 TARGETS_KEY 时能正确解密"""
        raw_config = [{"target": "@enc_bot", "message": "/secret", "interval_days": 2, "topic_id": 888}]
        key = Fernet.generate_key().decode()
        fernet = Fernet(key.encode())
        encrypted_data = fernet.encrypt(json.dumps(raw_config).encode()).decode()

        def exists_mock(path):
            if path == "targets.enc":
                return True
            return False

        with patch("os.path.exists", side_effect=exists_mock), \
             patch("builtins.open", mock_open(read_data=encrypted_data)), \
             patch.dict(os.environ, {"TARGETS_KEY": key}, clear=False):
            targets = checkin.parse_targets()

        assert len(targets) == 1
        assert targets[0]["target"] == "@enc_bot"
        assert targets[0]["message"] == "/secret"
        assert targets[0]["interval_days"] == 2
        assert targets[0]["topic_id"] == 888

    def test_parse_targets_encrypted_file_with_local_key(self):
        """验证环境变量为空，但存在本地 targets.key 时能正确解密"""
        raw_config = [{"target": "@local_bot", "message": "/local"}]
        key = Fernet.generate_key().decode()
        fernet = Fernet(key.encode())
        encrypted_data = fernet.encrypt(json.dumps(raw_config).encode()).decode()

        def exists_mock(path):
            if path in ("targets.enc", "targets.key"):
                return True
            return False

        def open_mock(path, *args, **kwargs):
            if "targets.key" in path:
                return mock_open(read_data=key).return_value
            elif "targets.enc" in path:
                return mock_open(read_data=encrypted_data).return_value
            return mock_open().return_value

        with patch("os.path.exists", side_effect=exists_mock), \
             patch("builtins.open", side_effect=open_mock), \
             patch.dict(os.environ, {"TARGETS_KEY": ""}, clear=False):
            targets = checkin.parse_targets()

        assert len(targets) == 1
        assert targets[0]["target"] == "@local_bot"
        assert targets[0]["message"] == "/local"

    def test_parse_targets_encrypted_file_missing_key_exits(self):
        """验证存在 targets.enc 但没有任何密钥时，程序会报错退出"""
        def exists_mock(path):
            if path == "targets.enc":
                return True
            return False

        with patch("os.path.exists", side_effect=exists_mock), \
             patch.dict(os.environ, {"TARGETS_KEY": ""}, clear=False), \
             pytest.raises(SystemExit) as excinfo:
            checkin.parse_targets()

        assert excinfo.value.code == 1

    def test_parse_targets_encrypted_file_corrupt_data(self):
        """验证解密失败（例如损坏的数据）时，程序会报错退出"""
        key = Fernet.generate_key().decode()

        def exists_mock(path):
            if path == "targets.enc":
                return True
            return False

        with patch("os.path.exists", side_effect=exists_mock), \
             patch("builtins.open", mock_open(read_data="corrupt_base64_data")), \
             patch.dict(os.environ, {"TARGETS_KEY": key}, clear=False), \
             pytest.raises(SystemExit) as excinfo:
            checkin.parse_targets()

        assert excinfo.value.code == 1


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


# ============================================================
# parse_target_id 测试
# ============================================================

class TestParseTargetId:
    def test_numeric_string(self):
        assert checkin.parse_target_id("-1001234567890") == -1001234567890

    def test_username_string(self):
        assert checkin.parse_target_id("@bot1") == "@bot1"


# ============================================================
# filter_by_interval 测试
# ============================================================

class TestFilterByInterval:
    """测试根据签到状态及天数间隔进行的过滤逻辑"""

    def test_send_all_returns_everything(self):
        targets = [
            {"target": "@a", "message": "/checkin", "interval_days": 1},
            {"target": "@b", "message": "/checkin", "interval_days": 3},
        ]
        result = checkin.filter_by_interval(targets, {}, send_all=True)
        assert len(result) == 2

    def test_no_status_always_matched(self):
        targets = [
            {"target": "@a", "message": "/checkin", "interval_days": 1},
        ]
        result = checkin.filter_by_interval(targets, {}, send_all=False)
        assert len(result) == 1

    def test_interval_not_reached(self):
        targets = [
            {"target": "@a", "message": "/checkin", "interval_days": 2},
        ]
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        status = {"@a|/checkin": today_str}
        result = checkin.filter_by_interval(targets, status, send_all=False)
        assert len(result) == 0

    def test_interval_reached(self):
        targets = [
            {"target": "@a", "message": "/checkin", "interval_days": 2},
        ]
        from datetime import datetime, timedelta, timezone
        last_date_str = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
        status = {"@a|/checkin": last_date_str}
        result = checkin.filter_by_interval(targets, status, send_all=False)
        assert len(result) == 1


# ============================================================
# solve_math_expression 测试
# ============================================================

class TestSolveMathExpression:
    def test_addition(self):
        text = "📍 签到验证\n请计算：89 + 32 = ?\n点击正确答案完成签到"
        expr, res = checkin.solve_math_expression(text)
        assert res == 121
        assert "89 + 32" in expr

    def test_fullwidth_symbols(self):
        text = "请计算： 89 ＋ 32 ＝ ?"
        expr, res = checkin.solve_math_expression(text)
        assert res == 121

    def test_subtraction(self):
        text = "验证码：15 - 7 = ?"
        expr, res = checkin.solve_math_expression(text)
        assert res == 8

    def test_multiplication(self):
        text = "请回答：12 × 4"
        expr, res = checkin.solve_math_expression(text)
        assert res == 48

    def test_division(self):
        text = "请计算：100 ÷ 5 = ?"
        expr, res = checkin.solve_math_expression(text)
        assert res == 20

    def test_no_math_expression(self):
        text = "欢迎使用签到机器人，签到成功！"
        result = checkin.solve_math_expression(text)
        assert result is None


# ============================================================
# process_verification 测试
# ============================================================

class TestProcessVerification:
    @pytest.mark.asyncio
    async def test_button_click_match(self):
        """验证匹配到数学公式时自动点击对应数字按钮"""
        msg = AsyncMock()
        msg.text = "📍 签到验证\n请计算：89 + 32 = ?\n点击正确答案完成签到"

        # Mock inline buttons
        btn1 = MagicMock()
        btn1.text = "123"
        btn1.click = AsyncMock()

        btn2 = MagicMock()
        btn2.text = "122"
        btn2.click = AsyncMock()

        btn3 = MagicMock()
        btn3.text = "131"
        btn3.click = AsyncMock()

        btn4 = MagicMock()
        btn4.text = "121"
        btn4.click = AsyncMock()

        msg.buttons = [[btn1, btn2], [btn3, btn4]]

        res = await checkin.process_verification(msg)

        assert res is True
        btn4.click.assert_called_once()
        btn1.click.assert_not_called()

    @pytest.mark.asyncio
    async def test_reply_fallback_when_no_buttons(self):
        """验证没有按钮时自动通过文本消息回复计算结果"""
        msg = AsyncMock()
        msg.text = "请计算：15 - 7 = ?"
        msg.buttons = None
        msg.reply = AsyncMock()

        res = await checkin.process_verification(msg)

        assert res is True
        msg.reply.assert_called_once_with("8")

    @pytest.mark.asyncio
    async def test_no_math_returns_false(self):
        """验证无数学公式时返回 False 且不进行任何操作"""
        msg = AsyncMock()
        msg.text = "签到成功"
        msg.buttons = None

        res = await checkin.process_verification(msg)
        assert res is False


