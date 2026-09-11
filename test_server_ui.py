# -*- coding: utf-8 -*-
"""真实界面集成测试：用真实的前端目录启动服务，验证网页资源可加载。"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import server as srv

BASE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(BASE, "界面")


class TestRealUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.cfg = os.path.join(cls.tmpdir.name, "config.json")
        with open(cls.cfg, "w", encoding="utf-8") as f:
            json.dump([], f)

        cls.app = srv.AutoKillApp(
            config_path=cls.cfg,
            ui_dir=UI_DIR,  # 使用真实前端目录
            picker=lambda: "",
            do_kill=lambda paths: {"matched": [], "killed": [], "failed": []},
        )
        cls.server = srv.create_server(cls.app, port=0)
        cls.port = cls.server.server_address[1]
        cls.url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.shutdown()
        except Exception:
            pass
        cls.server.server_close()
        cls.tmpdir.cleanup()

    def _fetch(self, path):
        with urllib.request.urlopen(self.url + path, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")

    def test_root_serves_real_index(self):
        status, body = self._fetch("/")
        self.assertEqual(status, 200)
        self.assertIn("AutoKill 进程守护者", body)
        self.assertIn('id="btn-kill-all"', body)

    def test_style_css_served(self):
        status, body = self._fetch("/style.css")
        self.assertEqual(status, 200)
        self.assertIn(".card", body)

    def test_main_js_served(self):
        status, body = self._fetch("/main.js")
        self.assertEqual(status, 200)
        self.assertIn("/api/kill", body)


if __name__ == "__main__":
    unittest.main()