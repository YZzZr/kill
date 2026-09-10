# -*- coding: utf-8 -*-
"""端到端集成测试：真实运行 kill_process.py 主流程。"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kill_process.py")


def run_script(cfg, child_env_utf8=True):
    """运行 kill_process.py，统一子进程为 UTF-8 输出，避免中文 Windows 的 GBK/UTF-8 编码冲突。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, SCRIPT, cfg],
        input="\n", text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=30, env=env,
    )


class TestEndToEnd(unittest.TestCase):
    def test_creates_config_when_missing(self):
        """直接运行脚本时，若 config 不存在应自动创建示例。"""
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            proc = run_script(cfg)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(os.path.exists(cfg), "应自动创建 config.json")
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data, ["C:\\Windows\\System32\\notepad.exe"])
            self.assertIn("按任意键退出", proc.stdout)

    def test_runs_and_reports_no_match(self):
        """配置中路径未运行时，报告跳过且正常退出。"""
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump([r"C:\Windows\System32\definitely_missing_app.exe"], f)
            proc = run_script(cfg)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("[跳过]", proc.stdout)
            self.assertIn("按任意键退出", proc.stdout)

    def test_full_flow_kills_real_process(self):
        """端到端：启动一个真实进程，配置其路径，运行脚本后进程被结束。"""
        import psutil
        # 1. 启动一个真实长驻进程
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        time.sleep(0.5)
        try:
            pid = child.pid
            self.assertTrue(psutil.pid_exists(pid), "子进程应存在")

            # 2. 构造配置，指向该进程的可执行文件路径
            exe = psutil.Process(pid).exe()
            with tempfile.TemporaryDirectory() as d:
                cfg = os.path.join(d, "config.json")
                with open(cfg, "w", encoding="utf-8") as f:
                    json.dump([exe], f)

                # 3. 运行脚本（注入 stdin 以跳过“按任意键退出”）
                proc = run_script(cfg)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("[成功]", proc.stdout)

            # 4. 验证进程确实已被结束
            try:
                child.wait(timeout=10)
                exited = True
            except subprocess.TimeoutExpired:
                exited = False
            self.assertTrue(exited, "真实进程应被脚本结束")
            self.assertFalse(psutil.pid_exists(pid), "进程应已不存在")
        finally:
            # 兜底清理
            try:
                if child.poll() is None:
                    psutil.Process(child.pid).kill()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()