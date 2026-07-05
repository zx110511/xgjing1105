# -*- coding: utf-8-sig -*-
"""天机v9.1 智能托盘 — 全功能控制面板

右键菜单功能:
  - 一键打开 Web UI / Dashboard / MCP工具 / API文档
  - 健康检查 + 全链验证
  - 服务控制: 重启 / 停止
  - 状态实时通知
"""

import json
import os
import subprocess
import time
import urllib.request
import webbrowser
from pathlib import Path

PORT = 8771
BASE_URL = f"http://127.0.0.1:{PORT}"
HEALTH_URL = f"{BASE_URL}/api/health"
TIANJI_ROOT = Path(__file__).resolve().parent.parent
PID_FILE = TIANJI_ROOT / ".daemon" / "tianji.pid"

# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────


def _fetch(url: str, timeout: float = 3.0) -> dict:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8-sig", errors="replace"))
    except Exception:
        return {}


def check_health() -> dict:
    return _fetch(HEALTH_URL, timeout=2.0)


def get_service_pid() -> int | None:
    try:
        if PID_FILE.exists():
            return int(PID_FILE.read_text().strip())
    except Exception:
        pass
    return None


def is_port_listening() -> bool:
    try:
        import socket

        with socket.create_connection(("127.0.0.1", PORT), timeout=1.0):
            return True
    except Exception:
        return False


# ─────────────────────────────────────────────
# 图标生成
# ─────────────────────────────────────────────


def create_tray_image(status: str = "normal"):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    color_map = {
        "normal": (72, 61, 139, 255),
        "warning": (255, 165, 0, 255),
        "error": (220, 20, 60, 255),
        "stopped": (100, 100, 100, 255),
    }
    bg_color = color_map.get(status, color_map["normal"])

    draw.ellipse((2, 2, 62, 62), fill=bg_color, outline=(255, 215, 0, 255), width=2)
    try:
        font = ImageFont.truetype("msyh.ttc", 32)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", 32)
        except Exception:
            font = ImageFont.load_default()
    text = "天"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((64 - tw) / 2 - bbox[0], (64 - th) / 2 - bbox[1] - 2),
        text,
        fill=(255, 255, 255, 255),
        font=font,
    )
    return img


# ─────────────────────────────────────────────
# 菜单动作
# ─────────────────────────────────────────────


def _open_url(path: str):
    def handler(icon, item):
        webbrowser.open(f"{BASE_URL}{path}")

    return handler


def on_status(icon, item):
    data = check_health()
    if data.get("engine_ready"):
        msg = (
            f"状态: 运行中\n"
            f"端口: {PORT}\n"
            f"版本: {data.get('version', 'N/A')}\n"
            f"启动时间: {data.get('start_time', 'N/A')}"
        )
    else:
        msg = "状态: 加载中或未就绪"
    icon.notify(msg, title="天机v9.1 状态")


def on_full_check(icon, item):
    """全链验证 — 检测9个关键端点"""
    endpoints = [
        ("/api/health", "健康检查"),
        ("/", "Web UI"),
        ("/docs", "API文档"),
        ("/api/mcp/tools", "MCP工具"),
        ("/api/orchestrator/agents", "Agent调度"),
        ("/api/kg/stats", "知识图谱"),
        ("/api/search", "搜索服务"),
        ("/api/llm/status", "DeepSeek大脑"),
        ("/api/status/system/stats", "系统状态"),
    ]
    results = []
    ok_count = 0
    for path, name in endpoints:
        try:
            req = urllib.request.Request(
                f"{BASE_URL}{path}",
                headers={"Accept": "application/json"},
                method="HEAD",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                ok = resp.status == 200
        except Exception:
            ok = False
        results.append(f"{'✅' if ok else '❌'} {name}")
        if ok:
            ok_count += 1

    msg = f"全链验证: {ok_count}/{len(endpoints)} 通过\n" + "\n".join(results)
    icon.notify(msg, title="天机v9.1 全链验证")


def on_restart(icon, item):
    """重启服务"""
    icon.notify("正在重启天机服务...", title="天机v9.1")
    # 1. 停止旧服务
    pid = get_service_pid()
    if pid:
        try:
            os.kill(pid, 9)
        except Exception:
            pass
    # 2. 清理PID文件
    if PID_FILE.exists():
        PID_FILE.unlink()
    # 3. 启动新服务
    python_exe = str(TIANJI_ROOT / "python" / "python.exe")
    subprocess.Popen(
        [python_exe, "-m", "launcher.tianji_v91_launcher", "--daemon"],
        cwd=str(TIANJI_ROOT),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    # 4. 等待就绪后通知
    for _ in range(30):
        time.sleep(2)
        if check_health().get("engine_ready"):
            icon.notify("天机服务重启成功！", title="天机v9.1")
            return
    icon.notify("重启超时，请检查日志", title="天机v9.1")


def on_stop(icon, item):
    """停止服务"""
    pid = get_service_pid()
    stopped = False
    if pid:
        try:
            os.kill(pid, 9)
            stopped = True
        except Exception:
            pass
    if PID_FILE.exists():
        PID_FILE.unlink()
    icon.notify(
        "天机服务已停止" if stopped else "服务未运行或已停止",
        title="天机v9.1",
    )


def on_quit(icon, item):
    icon.stop()


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────


def _get_service_status() -> str:
    """获取服务状态: normal/warning/error/stopped"""
    if not is_port_listening():
        return "stopped"
    health = check_health()
    if health.get("engine_ready"):
        return "normal"
    return "warning"


def _update_icon_periodically(icon, stop_event):
    """定期更新托盘图标状态"""
    while not stop_event.is_set():
        try:
            status = _get_service_status()
            new_img = create_tray_image(status)
            icon.icon = new_img

            title = "天机v9.1 - 8771"
            status_text = {
                "normal": "运行中",
                "warning": "加载中",
                "error": "异常",
                "stopped": "已停止",
            }
            icon.title = f"{title} [{status_text.get(status, '未知')}]"
        except Exception:
            pass
        time.sleep(5)


def main():
    import threading

    import pystray

    # 等待服务就绪（最多60秒）
    print("[INFO] 等待天机v9.1服务就绪...", flush=True)
    for i in range(30):
        if check_health().get("engine_ready"):
            print("[OK] 服务已就绪！", flush=True)
            break
        time.sleep(2)
        if (i + 1) % 5 == 0:
            print(f"[INFO] 仍在等待... ({(i + 1) * 2}s)", flush=True)
    else:
        print("[WARN] 服务未就绪，托盘将持续检测", flush=True)

    initial_status = _get_service_status()
    icon_img = create_tray_image(initial_status)

    menu = pystray.Menu(
        pystray.MenuItem("🔮 天机v9.1 (端口8771)", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("🌐 打开 Web UI", _open_url("/")),
        pystray.MenuItem("📊 打开 Dashboard", _open_url("/dashboard")),
        pystray.MenuItem("🔧 MCP 工具面板", _open_url("/mcp-tools")),
        pystray.MenuItem("📖 API 文档", _open_url("/docs")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("📡 状态查看", on_status),
        pystray.MenuItem("🔍 全链验证", on_full_check),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("🔄 重启服务", on_restart),
        pystray.MenuItem("🛑 停止服务", on_stop),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("❌ 退出托盘", on_quit),
    )

    title = "天机v9.1 - 8771"
    status_text = {
        "normal": "运行中",
        "warning": "加载中",
        "error": "异常",
        "stopped": "已停止",
    }
    icon_title = f"{title} [{status_text.get(initial_status, '未知')}]"

    icon = pystray.Icon("tianji_v91", icon_img, icon_title, menu)

    # 启动状态更新线程
    stop_event = threading.Event()
    update_thread = threading.Thread(
        target=_update_icon_periodically,
        args=(icon, stop_event),
        daemon=True,
    )
    update_thread.start()

    print("[OK] 智能托盘已创建！右键任务栏图标展开功能面板。", flush=True)
    icon.run()

    # 停止更新线程
    stop_event.set()
    update_thread.join(timeout=2)


if __name__ == "__main__":
    main()
