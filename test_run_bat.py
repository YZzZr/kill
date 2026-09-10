# -*- coding: utf-8 -*-
"""run.bat 启动脚本的检查测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BAT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.bat")


class TestRunBat(unittest.TestCase):
    def test_bat_exists(self):
        """run.bat 应存在。"""
        self.assertTrue(os.path.exists(BAT_PATH), "run.bat 不存在")

    def test_bat_requests_admin(self):
        """应包含 UAC 提权逻辑。"""
        with open(BAT_PATH, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        self.assertIn("net session", content, "应使用 net session 检测管理员权限")
        self.assertIn("-Verb RunAs", content, "应通过 -Verb RunAs 请求管理员权限")

    def test_bat_checks_python(self):
        """应检查 Python 是否存在并支持 py/python 回退。"""
        with open(BAT_PATH, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        self.assertIn("where py", content, "应检测 py 启动器")
        self.assertIn("where python", content, "应检测 python 命令")

    def test_bat_installs_psutil_if_missing(self):
        """应检查并在缺失时安装 psutil。"""
        with open(BAT_PATH, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        self.assertIn("import psutil", content, "应检查 psutil 是否已安装")
        self.assertIn("pip install psutil", content, "缺失时应安装 psutil")

    def test_bat_calls_script(self):
        """应调用 kill_process.py。"""
        with open(BAT_PATH, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        self.assertIn("kill_process.py", content, "应调用 kill_process.py")


if __name__ == "__main__":
    unittest.main()
