#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoKill 一键结束脚本 v1.0 - 本地服务端

启动一个只监听 127.0.0.1 的本地 HTTP 服务，提供网页界面。
功能：
- 查看 / 添加 / 删除 / 清空 config.json 中的规则
- 通过 Windows 原生文件选择框选取进程路径（完整路径）
- 一键结束所有匹配规则的进程并返回结果

用法：
    双击 run.bat（推荐，自动装依赖、提权、打开浏览器）
    或命令行: py server.py [port]
默认端口随机分配，浏览器自动打开。关闭浏览器网页后服务自动退出。
"""

import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import kill_process as kp


def default_picker():
    """
    调用 PowerShell 弹出 Windows 原生文件选择框，返回选中的完整路径。
    取消选择时返回 ""。仅用于 Windows。
    """
    ps_script = r'''
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Filter = "Executable (*.exe)|*.exe|All files (*.*)|*.*"
$d.CheckFileExists = $true
$d.Multiselect = $false
if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $d.FileName
} else {
    Write-Output ""
}
'''
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=60,
        )
        out = (proc.stdout or "").strip()
        lines = [ln for ln in out.splitlines() if ln.strip()]
        return lines[-1] if lines else ""
    except Exception:
        return ""


def default_ui_dir():
    """前端界面所在目录。"""
    return os.path.join(kp.script_dir(), "界面")


class AutoKillApp:
    """
    应用的业务逻辑容器。所有操作都可注入，便于单元测试。
    """

    def __init__(self, config_path=None, ui_dir=None, picker=None,
                 running=None, do_kill=None, save_config=None, load_config=None):
        # 需要紧密绑定当前脚本的函数供 import 引用
        self.config_path = config_path or kp.config_path()
        self.ui_dir = ui_dir or default_ui_dir()
        self.picker = picker or default_picker
        # 注入点：运行进程列表（测试用）
        self._running = running
        # 注入点：结束逻辑（默认走 kill_process.run）
        self._do_kill = do_kill
        self._save_config = save_config or self._default_save_config
        self._load_config = load_config or kp.load_config

    def _default_save_config(self, paths, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(paths, f, ensure_ascii=False, indent=4)

    def get_rules(self):
        """返回当前规则列表。"""
        return self._load_config(self.config_path)

    def add_rule(self, path):
        """添加一条规则（去重，不区分大小写）。返回更新后的规则列表。"""
        path = (path or "").strip()
        if not path:
            return self.get_rules()
        rules = self.get_rules()
        lower = path.lower()
        if any(r.lower() == lower for r in rules):
            return rules  # 已存在，不重复添加
        rules.append(path)
        self._save_config(rules, self.config_path)
        return rules

    def delete_rule(self, index, path=None):
        """按下标或按路径删除一条规则。返回更新后的规则列表。"""
        rules = self.get_rules()
        if path is not None:
            lower = path.lower()
            idx = next((i for i, r in enumerate(rules) if r.lower() == lower), None)
            if idx is None:
                return rules
            del rules[idx]
        else:
            try:
                i = int(index)
            except (TypeError, ValueError):
                return rules
            if i < 0 or i >= len(rules):
                return rules
            del rules[i]
        self._save_config(rules, self.config_path)
        return rules

    def clear_rules(self):
        """清空全部规则。"""
        self._save_config([], self.config_path)
        return []

    def select_file(self):
        """弹出原生文件选择框，返回完整路径。"""
        return self.picker()

    def kill_all(self):
        """
        一键结束所有匹配规则的进程。
        返回结果字典：
            {"killed": [...], "failed": [...], "skipped": [...]}
        """
        paths = self.get_rules()
        if self._do_kill is not None:
            result = self._do_kill(paths)
        else:
            running = self._running
            if running is None:
                running = kp.collect_running_exes()
            result = kp.run(paths=paths, running=running)

        matched_exes = {exe.lower() for _, exe in result["matched"]}
        killed = [{"pid": p, "exe": e} for p, e in result["killed"]]
        failed = [{"pid": p, "exe": e} for p, e in result["failed"]]
        skipped = [p for p in paths if p.lower() not in matched_exes]
        return {"killed": killed, "failed": failed, "skipped": skipped}


class Handler(BaseHTTPRequestHandler):
    """HTTP 请求处理。通过 self.server.app 访问应用。"""

    def log_message(self, fmt, *args):  # 静默日志，避免刷屏
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            self.send_error(404, "Not Found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        app = self.server.app
        if self.path == "/" or self.path == "/index.html":
            self._send_file(os.path.join(app.ui_dir, "index.html"), "text/html; charset=utf-8")
        elif self.path == "/style.css":
            self._send_file(os.path.join(app.ui_dir, "style.css"), "text/css; charset=utf-8")
        elif self.path == "/main.js":
            self._send_file(os.path.join(app.ui_dir, "main.js"), "application/javascript; charset=utf-8")
        elif self.path == "/api/rules":
            self._send_json({"rules": app.get_rules()})
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        app = self.server.app
        if self.path == "/api/add":
            body = self._read_body()
            rules = app.add_rule(body.get("path", ""))
            self._send_json({"rules": rules})
        elif self.path == "/api/delete":
            body = self._read_body()
            rules = app.delete_rule(body.get("index"), body.get("path") if "path" in body else None)
            self._send_json({"rules": rules})
        elif self.path == "/api/clear":
            rules = app.clear_rules()
            self._send_json({"rules": rules})
        elif self.path == "/api/select_file":
            path = app.select_file()
            self._send_json({"path": path})
        elif self.path == "/api/kill":
            self._send_json(app.kill_all())
        elif self.path == "/api/shutdown":
            # 浏览器关闭通知：延迟一小段让响应发出，然后停止服务
            self._send_json({"ok": True})
            threading.Timer(0.3, self.server.stop).start()
        else:
            self.send_error(404, "Not Found")


class AutoKillServer(ThreadingHTTPServer):
    """支持应用实例和优雅停机的服务。"""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, app):
        super().__init__(address, Handler)
        self.app = app
        self._stop_scheduled = False

    def stop(self):
        if self._stop_scheduled:
            return
        self._stop_scheduled = True
        threading.Thread(target=self.shutdown, daemon=True).start()


def create_server(app, port=0):
    """创建但不启动服务的实例（便于测试拿到实际端口）。"""
    server = AutoKillServer(("127.0.0.1", port), app)
    return server


def main(argv=None):
    """启动服务并打开浏览器。"""
    if argv is None:
        argv = sys.argv[1:]
    port = 0
    if argv:
        try:
            port = int(argv[0])
        except ValueError:
            port = 0

    app = AutoKillApp()
    server = create_server(app, port=port)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"

    # 稍后打开浏览器（避免卡在服务启动前）
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    print(f"AutoKill 服务已启动: {url}")
    print("关闭浏览器网页后服务将自动退出。")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("服务已停止。")


if __name__ == "__main__":
    main()