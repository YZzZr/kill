# -*- coding: utf-8 -*-
"""kill_process 核心逻辑单元测试。"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kill_process as kp


class TestLoadConfig(unittest.TestCase):
    def test_missing_config_creates_sample(self):
        """config 不存在时，自动创建带示例的文件并返回示例路径。"""
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            paths = kp.load_config(cfg)
            self.assertEqual(paths, kp.SAMPLE_PATHS)
            self.assertTrue(os.path.exists(cfg))
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data, kp.SAMPLE_PATHS)

    def test_valid_list(self):
        """合法的 JSON 数组返回去引号、去空白的路径列表。"""
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump([r"C:\Windows\System32\notepad.exe",
                           '"D:\\Tools\\App.exe"',
                           "",
                           123,
                           r"E:\Game\game.exe"], f)
            paths = kp.load_config(cfg)
            self.assertEqual(paths, [r"C:\Windows\System32\notepad.exe",
                                     r"D:\Tools\App.exe",
                                     r"E:\Game\game.exe"])

    def test_invalid_json_returns_empty(self):
        """文件存在但 JSON 非法时返回空列表，不抛异常。"""
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write("not a json {{{")
            self.assertEqual(kp.load_config(cfg), [])

    def test_not_list_returns_empty(self):
        """JSON 不是数组时返回空列表。"""
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write('{"path": "x"}')
            self.assertEqual(kp.load_config(cfg), [])


class TestFindMatching(unittest.TestCase):
    def test_exact_match_case_insensitive(self):
        """完全匹配且不区分大小写。"""
        running = [
            (1, r"C:\Windows\System32\notepad.exe"),
            (2, r"D:\Other\notepad.exe"),      # 路径不同 → 不匹配
            (3, r"C:\windows\system32\NOTEPAD.EXE"),  # 大小写不同 → 匹配
        ]
        targets = [r"C:\Windows\System32\notepad.exe"]
        matched = kp.find_matching(running, targets)
        self.assertEqual(sorted(p[0] for p in matched), [1, 3])

    def test_no_match(self):
        """无匹配时返回空。"""
        running = [(1, r"C:\Windows\explorer.exe")]
        matched = kp.find_matching(running, [r"C:\Windows\System32\notepad.exe"])
        self.assertEqual(matched, [])

    def test_empty_running(self):
        """进程列表为空。"""
        self.assertEqual(kp.find_matching([], [r"C:\x.exe"]), [])


class TestKillPid(unittest.TestCase):
    def test_success(self):
        fake = mock.MagicMock()
        fake.terminate.return_value = None
        fake.wait.return_value = None
        with mock.patch("psutil.Process", return_value=fake) as m:
            self.assertTrue(kp.kill_pid(1234))
            m.assert_called_once_with(1234)
            fake.terminate.assert_called_once()

    def test_access_denied(self):
        fake = mock.MagicMock()
        fake.terminate.side_effect = __import__("psutil").AccessDenied()
        with mock.patch("psutil.Process", return_value=fake):
            self.assertFalse(kp.kill_pid(1234))

    def test_process_not_found(self):
        with mock.patch("psutil.Process", side_effect=__import__("psutil").NoSuchProcess(1)):
            self.assertFalse(kp.kill_pid(1))

    def test_timeout_then_kill(self):
        fake = mock.MagicMock()
        fake.terminate.side_effect = __import__("psutil").TimeoutExpired(1)
        fake.kill.return_value = None
        fake.wait.return_value = None
        with mock.patch("psutil.Process", return_value=fake):
            self.assertTrue(kp.kill_pid(1234))
            fake.kill.assert_called_once()


class TestRun(unittest.TestCase):
    def test_run_with_injected_data(self):
        """使用注入的路径和进程运行核心流程。"""
        paths = [r"C:\Windows\System32\notepad.exe"]
        running = [
            (101, r"C:\Windows\System32\notepad.exe"),
            (202, r"C:\Windows\explorer.exe"),
        ]
        # 只杀掉匹配进程的 PID 101
        with mock.patch.object(kp, "kill_pid", side_effect=lambda pid: pid == 101):
            result = kp.run(paths=paths, running=running)
        self.assertEqual([p[0] for p in result["matched"]], [101])
        self.assertEqual([p[0] for p in result["killed"]], [101])
        self.assertEqual(result["failed"], [])


class TestRealProcessKill(unittest.TestCase):
    """使用真实进程验证结束功能（集成测试）。"""

    @classmethod
    def setUpClass(cls):
        # 启动一个真实的长驻进程（python 睡眠 60 秒）
        cls.p = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        time.sleep(0.5)
        cls.pid = cls.p.pid

    @classmethod
    def tearDownClass(cls):
        # 兜底：如果进程还活着，强制结束
        try:
            if cls.p.poll() is None:
                __import__("psutil").Process(cls.pid).kill()
        except Exception:
            pass

    def test_really_kills_process(self):
        """kill_pid 能真正结束一个运行中的真实进程。"""
        import psutil
        # 确认进程确实在运行
        self.assertIsNone(self.p.poll(), "进程应处于运行状态")
        self.assertTrue(psutil.pid_exists(self.pid), "PID 应存在")

        # 结束它
        ok = kp.kill_pid(self.pid)
        self.assertTrue(ok, "kill_pid 应返回成功")

        # 等待退出
        try:
            self.p.wait(timeout=10)
            exited = True
        except subprocess.TimeoutExpired:
            exited = False
        self.assertTrue(exited, "进程应在超时前退出")
        self.assertFalse(psutil.pid_exists(self.pid), "进程应已不存在")


if __name__ == "__main__":
    unittest.main()
