#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoKill 一键结束脚本 v1.0

读取同目录下的 config.json（路径数组），结束所有
可执行文件完整路径完全匹配（不区分大小写）的进程。

用法：
    双击 run.bat 运行（会自动申请管理员权限）
    或命令行执行: py kill_process.py

配置：
    同目录下的 config.json，格式为 JSON 数组，例如：
    [
        "C:\\Windows\\System32\\notepad.exe",
        "D:\\Software\\WeChat\\WeChat.exe"
    ]
    若文件不存在，脚本会自动创建带示例的模板。
"""

import json
import os
import sys
import psutil

CONFIG_FILE = "config.json"
SAMPLE_PATHS = [r"C:\Windows\System32\notepad.exe"]


def script_dir():
    """返回脚本所在目录。"""
    return os.path.dirname(os.path.abspath(__file__))


def config_path():
    """返回配置文件完整路径。"""
    return os.path.join(script_dir(), CONFIG_FILE)


def load_config(path=None):
    """
    读取配置文件，返回路径列表 (list[str])。

    若文件不存在，则自动创建带示例的模板文件。
    若文件存在但格式非法，返回空列表。
    """
    if path is None:
        path = config_path()

    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(SAMPLE_PATHS, f, ensure_ascii=False, indent=4)
        except OSError:
            return []
        return SAMPLE_PATHS

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(data, list):
        return []

    # 只保留字符串且非空的路径，并统一规范化
    paths = []
    for item in data:
        if isinstance(item, str) and item.strip():
            p = item.strip()
            # 去掉可能的引号包裹
            if p.startswith('"') and p.endswith('"'):
                p = p[1:-1]
            paths.append(p)
    return paths


def ancestor_pids():
    """返回脚本自身及其父进程链的 PID 集合，避免误杀自己或启动者。"""
    try:
        proc = psutil.Process(os.getpid())
        pids = {proc.pid}
        while proc.parent():
            proc = proc.parent()
            pids.add(proc.pid)
        return pids
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {os.getpid()}


def collect_running_exes(scan=None, exclude_self=True):
    """
    枚举当前所有进程的可执行文件完整路径。

    scan 参数用于测试注入；默认使用 psutil.process_iter。
    exclude_self=True 时跳过脚本自身及其父进程链（避免自杀）。
    返回: [(pid, exe), ...]，仅包含能取得路径的进程。
    """
    if scan is not None:
        return scan

    skip = ancestor_pids() if exclude_self else set()
    result = []
    for proc in psutil.process_iter(["pid", "exe"]):
        try:
            pid = proc.info["pid"]
            if pid in skip:
                continue
            exe = proc.info["exe"]
            if exe:
                result.append((pid, exe))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return result


def find_matching(running, target_paths):
    """
    从运行中进程里找出路径完全匹配（不区分大小写）的进程。

    running:        [(pid, exe), ...]
    target_paths:   [str, ...]

    返回: [(pid, exe), ...]
    """
    target = {p.lower() for p in target_paths}
    matched = []
    for pid, exe in running:
        if exe and exe.lower() in target:
            matched.append((pid, exe))
    return matched


def kill_pid(pid):
    """
    结束指定 PID 的进程。
    返回: True 成功 / False 失败（权限不足、进程已退出等）。
    """
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False

    try:
        proc.terminate()
        proc.wait(timeout=5)
        return True
    except psutil.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=5)
            return True
        except Exception:
            return False
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    except Exception:
        return False


def run(paths=None, running=None):
    """
    核心执行：加载配置 → 匹配 → 结束 → 输出结果。

    paths:   要结束的路径列表（测试可注入）
    running: 运行中进程 [(pid, exe)]（测试可注入）

    返回结果字典，便于测试断言：
        {"matched": [(pid, exe)], "killed": [(pid, exe)], "failed": [(pid, exe)]}
    """
    if paths is None:
        paths = load_config()

    if running is None:
        running = collect_running_exes()

    matched = find_matching(running, paths)
    killed, failed = [], []

    for pid, exe in matched:
        if kill_pid(pid):
            killed.append((pid, exe))
        else:
            failed.append((pid, exe))

    return {"matched": matched, "killed": killed, "failed": failed}


def print_result(result, configured_paths):
    """按用户要求打印结果。"""
    killed, failed = result["killed"], result["failed"]

    print("\n=== AutoKill 一键结束脚本 v1.0 ===")
    print(f"配置了 {len(configured_paths)} 条路径")
    print(f"匹配到 {len(result['matched'])} 个进程\n")

    if not configured_paths:
        print("[注意] config.json 为空，未做任何结束操作。")

    for pid, exe in killed:
        print(f"[成功] 已结束: {exe} (PID {pid})")

    for pid, exe in failed:
        print(f"[失败] 结束失败: {exe} (PID {pid}) —— 可能权限不足或已退出")

    # 提示配置里存在但当前未运行的路径
    if configured_paths:
        running_exes = {exe.lower() for _, exe in result["matched"]}
        for p in configured_paths:
            if p.lower() not in running_exes:
                print(f"[跳过] 未运行: {p}")

    print(f"\n共成功结束 {len(killed)} 个进程，失败 {len(failed)} 个。")
    print("\n按任意键退出...")
    input()


def main(argv=None):
    """入口函数。支持可选参数：配置文件路径（默认使用脚本同目录的 config.json）。"""
    if argv is None:
        argv = sys.argv[1:]

    cfg = argv[0] if argv else None
    paths = load_config(cfg)
    result = run(paths=paths)
    print_result(result, paths)


if __name__ == "__main__":
    main()
