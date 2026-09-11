# -*- coding: utf-8 -*-
"""server.py 业务逻辑单元测试。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import server as srv


def make_app(tmpdir, picker=None, running=None, do_kill=None):
    cfg = os.path.join(tmpdir, "config.json")
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump([r"C:\Windows\System32\notepad.exe"], f)
    app = srv.AutoKillApp(
        config_path=cfg,
        ui_dir=tmpdir,  # 不影响逻辑，只需目录存在
        picker=picker or (lambda: ""),
        running=running,
        do_kill=do_kill,
    )
    return app


class TestRules(unittest.TestCase):
    def test_get_rules(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d)
            self.assertEqual(app.get_rules(), [r"C:\Windows\System32\notepad.exe"])

    def test_add_rule(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d)
            app.add_rule(r"D:\Tools\App.exe")
            self.assertEqual(app.get_rules(),
                             [r"C:\Windows\System32\notepad.exe", r"D:\Tools\App.exe"])
            # 验证已写入文件
            with open(app.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data, app.get_rules())

    def test_add_duplicate_case_insensitive(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d)
            app.add_rule(r"c:\windows\system32\NOTEPAD.EXE")
            self.assertEqual(len(app.get_rules()), 1)

    def test_add_empty_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d)
            app.add_rule("   ")
            self.assertEqual(len(app.get_rules()), 1)

    def test_delete_by_index(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d)
            app.add_rule(r"D:\Tools\App.exe")
            app.delete_rule(1)
            self.assertEqual(app.get_rules(), [r"C:\Windows\System32\notepad.exe"])

    def test_delete_by_index_out_of_range(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d)
            app.delete_rule(99)
            self.assertEqual(len(app.get_rules()), 1)

    def test_delete_by_path(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d)
            app.add_rule(r"D:\Tools\App.exe")
            app.delete_rule(None, path=r"d:\tools\app.exe")  # 不区分大小写
            self.assertEqual(app.get_rules(), [r"C:\Windows\System32\notepad.exe"])

    def test_clear_rules(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d)
            app.clear_rules()
            self.assertEqual(app.get_rules(), [])


class TestSelectFile(unittest.TestCase):
    def test_picker_returns_path(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d, picker=lambda: r"C:\MyApp\app.exe")
            self.assertEqual(app.select_file(), r"C:\MyApp\app.exe")

    def test_picker_cancel(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d, picker=lambda: "")
            self.assertEqual(app.select_file(), "")


class TestKillAll(unittest.TestCase):
    def test_kill_all_report(self):
        with tempfile.TemporaryDirectory() as d:
            # 注入进程数据和 do_kill
            running = [
                (101, r"C:\Windows\System32\notepad.exe"),
                (202, r"C:\Windows\explorer.exe"),
            ]
            app = make_app(d, running=running,
                           do_kill=lambda paths: {
                               "matched": [(101, r"C:\Windows\System32\notepad.exe")],
                               "killed": [(101, r"C:\Windows\System32\notepad.exe")],
                               "failed": [],
                           })
            result = app.kill_all()
            self.assertEqual(result["killed"], [{"pid": 101, "exe": r"C:\Windows\System32\notepad.exe"}])
            self.assertEqual(result["failed"], [])
            # notepad 匹配，所以不被跳过；explorer 不在配置里不影响
            self.assertEqual(result["skipped"], [])

    def test_kill_all_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(d, running=[], do_kill=lambda paths: {
                "matched": [], "killed": [], "failed": [],
            })
            result = app.kill_all()
            self.assertEqual(result["skipped"], [r"C:\Windows\System32\notepad.exe"])

    def test_kill_all_failed(self):
        with tempfile.TemporaryDirectory() as d:
            running = [(101, r"C:\Windows\System32\notepad.exe")]
            app = make_app(d, running=running, do_kill=lambda paths: {
                "matched": [(101, r"C:\Windows\System32\notepad.exe")],
                "killed": [],
                "failed": [(101, r"C:\Windows\System32\notepad.exe")],
            })
            result = app.kill_all()
            self.assertEqual(result["failed"], [{"pid": 101, "exe": r"C:\Windows\System32\notepad.exe"}])
            self.assertEqual(result["killed"], [])


if __name__ == "__main__":
    unittest.main()