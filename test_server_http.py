# -*- coding: utf-8 -*-
"""server.py HTTP 接口集成测试：真实启动服务并验证各 API。"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import server as srv


class TestHTTPAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.cfg = os.path.join(cls.tmpdir.name, "config.json")
        cls.reset_config()
        # 在临时目录放一个最小的 index.html 供根路径测试
        with open(os.path.join(cls.tmpdir.name, "index.html"), "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html><html><head><title>test</title></head><body>ok</body></html>")

        # 注入 picker 和 do_kill，避免真实弹窗和真实杀进程
        cls.app = srv.AutoKillApp(
            config_path=cls.cfg,
            ui_dir=cls.tmpdir.name,
            picker=lambda: r"D:\Picked\app.exe",
            do_kill=lambda paths: {
                "matched": [(101, r"C:\Windows\System32\notepad.exe")],
                "killed": [(101, r"C:\Windows\System32\notepad.exe")],
                "failed": [],
            },
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

    def setUp(self):
        # 每个测试前重置配置，避免测试间依赖
        self.reset_config()

    @classmethod
    def reset_config(cls):
        with open(cls.cfg, "w", encoding="utf-8") as f:
            json.dump([r"C:\Windows\System32\notepad.exe"], f)

    def _get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")

    def _post(self, path, data=None):
        body = json.dumps(data).encode("utf-8") if data is not None else b"{}"
        req = urllib.request.Request(self.url + path, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")

    def test_root_returns_html(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("<!DOCTYPE html>", body)

    def test_get_rules(self):
        status, body = self._get("/api/rules")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["rules"], [r"C:\Windows\System32\notepad.exe"])

    def test_add_rule(self):
        status, body = self._post("/api/add", {"path": r"D:\New\app.exe"})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn(r"D:\New\app.exe", data["rules"])

    def test_delete_rule(self):
        status, body = self._post("/api/delete", {"index": 0})
        self.assertEqual(status, 200)
        data = json.loads(body)
        # notepad 和 D:\New 已加，删除 index 0 后不应再含 notepad
        self.assertNotIn(r"C:\Windows\System32\notepad.exe", data["rules"])

    def test_clear_rules(self):
        status, body = self._post("/api/clear")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["rules"], [])

    def test_select_file(self):
        status, body = self._post("/api/select_file")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["path"], r"D:\Picked\app.exe")

    def test_kill_all(self):
        status, body = self._post("/api/kill")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["killed"][0]["pid"], 101)
        self.assertEqual(data["failed"], [])

    def test_shutdown(self):
        status, body = self._post("/api/shutdown")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()