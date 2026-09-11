# -*- coding: utf-8 -*-
"""前端界面文件的静态检查测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "界面")


class TestFrontendFiles(unittest.TestCase):
    def test_files_exist(self):
        for name in ("index.html", "style.css", "main.js"):
            self.assertTrue(os.path.exists(os.path.join(UI_DIR, name)),
                            f"缺少前端文件: {name}")

    def test_index_has_core_elements(self):
        with open(os.path.join(UI_DIR, "index.html"), "r", encoding="utf-8") as f:
            content = f.read()
        expected = [
            'id="btn-kill-all"',      # 一键结束按钮
            'id="kill-results"',      # 结束结果区
            'id="rule-list"',         # 规则列表
            'id="btn-select-file"',   # 选择文件
            'id="btn-clear-all"',     # 清空
            'id="rule-count"',        # 规则计数
            'id="config-path"',       # 配置文件位置
            '<link rel="stylesheet" href="style.css">',
            '<script src="main.js">',
        ]
        for item in expected:
            self.assertIn(item, content, f"index.html 缺少元素: {item}")

    def test_style_has_core_classes(self):
        with open(os.path.join(UI_DIR, "style.css"), "r", encoding="utf-8") as f:
            content = f.read()
        expected = [
            ".app",
            ".card",
            ".btn-danger",
            ".btn-primary",
            ".rule-item",
            ".result-success",
            ".result-skip",
            ".result-fail",
        ]
        for item in expected:
            self.assertIn(item, content, f"style.css 缺少样式: {item}")

    def test_mainjs_calls_all_api(self):
        with open(os.path.join(UI_DIR, "main.js"), "r", encoding="utf-8") as f:
            content = f.read()
        expected_endpoints = [
            "('/api/delete'",
            "('/api/rules'",
            "('/api/select_file'",
            "('/api/add'",
            "('/api/clear'",
            "('/api/kill'",
            "('/api/shutdown'",
        ]
        for ep in expected_endpoints:
            self.assertIn(ep, content, f"main.js 缺少 API 调用: {ep}")
        # 关闭页面通知服务退出
        self.assertIn("pagehide", content, "main.js 应监听 pagehide 事件")


if __name__ == "__main__":
    unittest.main()