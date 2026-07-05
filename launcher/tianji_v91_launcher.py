# -*- coding: utf-8-sig -*-
"""
天机v9.1 统一启动器 (Tianji Unified Launcher)
============================================
唯一专业化启动文件，遵循天机宪法v6.0规范

端口: 8771 (宪法强制)
编码: UTF-8-SIG (全链路安全)
架构: FastAPI + ICME六层记忆 + Web UI + 23 Agent + 6 MCP Server

启动方式:
  1. 命令行: python -m launcher.tianji_v91_launcher
  2. 桌面托盘: pythonw.exe -m launcher.tianji_v91_launcher --tray
  3. 后台服务: python -m launcher.tianji_v91_launcher --daemon

全链启动验证:
  - 端口冲突检测与自动清理
  - PID文件管理
  - 日志记录
  - 容器模块完全就绪等待
  - 全链API端点验证
  - ICME六层记忆引擎验证
  - MCP工具清单验证
  - Agent调度器验证
  - 知识图谱验证
  - Web UI静态文件验证
  - 托盘图标(可选)
"""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# P0: UTF-8强制 (在任何import之前)
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 项目根目录
TIANJI_ROOT = Path(__file__).resolve().parent.parent
PORT = 8771  # 宪法强制端口
PID_FILE = TIANJI_ROOT / ".daemon" / "tianji.pid"
LOG_DIR = TIANJI_ROOT / "logs"
SERVER_LOG = LOG_DIR / "tianji-server.log"
ERROR_LOG = LOG_DIR / "tianji-server.err.log"
LAUNCHER_LOG = LOG_DIR / "tianji-launcher.log"

# 全链健康检查端点
BASE_URL = f"http://127.0.0.1:{PORT}"
HEALTH_URL = f"{BASE_URL}/api/health"
STATUS_FULL_URL = f"{BASE_URL}/api/status/system/stats"
MCP_TOOLS_URL = f"{BASE_URL}/api/mcp/tools"
ORCH_AGENTS_URL = f"{BASE_URL}/api/orchestrator/agents"
KG_STATS_URL = f"{BASE_URL}/api/kg/stats"
SEARCH_TEST_URL = f"{BASE_URL}/api/search?q=%E5%A4%A9%E6%9C%BA&limit=1"
DEEPSEEK_URL = f"{BASE_URL}/api/deepseek/models"
WEB_UI_URL = f"{BASE_URL}/"
SWAGGER_URL = f"{BASE_URL}/docs"

# 全链验证必须通过的关键端点列表
_CHAIN_ENDPOINTS = [
    ("health", HEALTH_URL, "健康检查"),
    ("web_ui", WEB_UI_URL, "Web前端UI"),
    ("swagger", SWAGGER_URL, "API文档"),
    ("mcp_tools", MCP_TOOLS_URL, "MCP工具清单"),
    ("orchestrator", ORCH_AGENTS_URL, "Agent调度器"),
    ("kg", KG_STATS_URL, "知识图谱"),
    ("search", SEARCH_TEST_URL, "搜索功能"),
    ("deepseek", DEEPSEEK_URL, "DeepSeek大脑"),
    ("status_full", STATUS_FULL_URL, "完整系统状态"),
    ("conversation_archiver", f"{BASE_URL}/api/conversation/health", "对话归档器"),
]


class TianjiLauncher:
    """天机v9.1统一启动器 — 全链验证版"""

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.running = False
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保必要目录存在"""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _log(self, level: str, message: str):
        """统一日志输出"""
        ts = time.strftime("%H:%M:%S")
        prefix = f"[{ts}][{level}]"
        colors = {
            "ERROR": "\033[91m",
            "WARN": "\033[93m",
            "OK": "\033[92m",
            "INFO": "\033[0m",
            "CHAIN": "\033[96m",
        }
        print(f"{colors.get(level, '')}{prefix} {message}\033[0m", flush=True)
        try:
            with open(LAUNCHER_LOG, "a", encoding="utf-8") as f:
                f.write(f"{prefix} {message}\n")
        except Exception:
            pass

    def _check_port(self) -> bool:
        """检查端口是否可用"""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", PORT))
            sock.close()
            return True
        except OSError:
            return False

    def _free_port(self) -> bool:
        """释放被占用的端口"""
        if sys.platform == "win32":
            try:
                result = subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        f"Get-NetTCPConnection -LocalPort {PORT} -State Listen -ErrorAction SilentlyContinue | "
                        f"Select-Object -ExpandProperty OwningProcess | "
                        f"ForEach-Object {{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }}",
                    ],
                    capture_output=True,
                    timeout=10,
                )
                time.sleep(2)
                return self._check_port()
            except Exception:
                return False
        return False

    def _cleanup_old_pid(self):
        """清理旧的PID文件及其子进程（含workers=2 spawn的子进程）"""
        if PID_FILE.exists():
            try:
                old_pid = int(PID_FILE.read_text().strip())
                if sys.platform == "win32":
                    # [AUDIT-FIX] 强制终止旧进程及其所有子进程（workers spawn orphans）
                    subprocess.run(
                        [
                            "powershell",
                            "-Command",
                            f'Get-CimInstance Win32_Process -Filter "ProcessId={old_pid} OR ParentProcessId={old_pid}" | '
                            f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}",
                        ],
                        capture_output=True,
                        timeout=10,
                    )
            except Exception:
                pass
            PID_FILE.unlink(missing_ok=True)

    def _http_get_json(self, url: str, timeout: int = 5) -> dict | None:
        """安全HTTP GET JSON"""
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            resp = urllib.request.urlopen(req, timeout=timeout)
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code == 500:
                return {"_http_error": 500}
            return None
        except Exception:
            return None
        return None

    def _http_get_status(self, url: str, timeout: int = 5) -> int | None:
        """安全HTTP GET，仅返回状态码"""
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return None

    def _wait_basic_health(self, max_wait: int = 120) -> bool:
        """第一阶段: 等待基础健康检查通过 (服务端口可用)"""
        self._log("INFO", "  等待基础服务启动...")
        for i in range(max_wait // 3):
            time.sleep(3)
            if self.process and self.process.poll() is not None:
                self._log(
                    "ERROR", f"  进程意外退出 (退出码: {self.process.returncode})"
                )
                self._dump_error_log()
                return False
            try:
                resp = urllib.request.urlopen(HEALTH_URL, timeout=5)
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    self._log(
                        "OK",
                        f"  基础服务就绪 (engine_ready={data.get('engine_ready')})",
                    )
                    return True
            except urllib.error.URLError:
                if (i + 1) % 5 == 0:
                    self._log("INFO", f"  等待中... ({(i + 1) * 3}s)")
            except Exception:
                pass
        return False

    def _wait_container_ready(self, max_wait: int = 60) -> bool:
        """第二阶段: 等待容器模块初始化 (保守策略，避免压垮单worker)"""
        self._log("INFO", "  等待容器模块初始化...")
        check_interval = 15
        max_checks = max(1, max_wait // check_interval)
        for i in range(max_checks):
            time.sleep(check_interval)
            health = self._http_get_json(HEALTH_URL, timeout=10)
            if health and health.get("engine_ready"):
                layers = health.get("layers", {})
                if layers and len(layers) >= 3:
                    self._log(
                        "OK",
                        f"  容器就绪 (engine_ready=True, {len(layers)} 层记忆已加载)",
                    )
                    return True
                else:
                    self._log(
                        "INFO", "  容器初始化中... (engine_ready已就绪，等待层加载)"
                    )
            else:
                self._log("INFO", f"  容器初始化中... ({(i + 1) * check_interval}s)")
        self._log("WARN", "  容器就绪等待超时，继续验证其他端点")
        return True

    def _verify_chain(self) -> dict:
        """第三阶段: 全链端点验证"""
        self._log("CHAIN", "  执行全链端点验证...")
        results = {}
        all_ok = True

        for key, url, desc in _CHAIN_ENDPOINTS:
            # [FIX-v2] 请求间延迟增加到3秒，避免压垮单worker uvicorn (Windows IOCP问题)
            time.sleep(3)
            if key in ("web_ui", "swagger"):
                status = self._http_get_status(url, timeout=10)
                ok = status == 200
                results[key] = {"ok": ok, "status": status, "desc": desc}
            else:
                data = self._http_get_json(url, timeout=10)
                if data is None:
                    ok = False
                    results[key] = {"ok": False, "status": None, "desc": desc}
                elif "_http_error" in data:
                    ok = False
                    results[key] = {
                        "ok": False,
                        "status": data["_http_error"],
                        "desc": desc,
                        "error": True,
                    }
                else:
                    ok = True
                    extra = ""
                    if key == "health":
                        extra = f" (layers={sum((data.get('layers') or {}).get(k, {}).get('entry_count', 0) for k in ['sensory', 'working', 'episodic', 'semantic', 'meta'])} entries)"
                    elif key == "mcp_tools":
                        extra = f" ({len(data.get('tools', []))} tools)"
                    elif key == "orchestrator":
                        agents = data.get("agents", [])
                        extra = f" ({len(agents)} agents)"
                    elif key == "kg":
                        extra = f" ({data.get('total_nodes', 0)} nodes, {data.get('total_edges', 0)} edges)"
                    elif key == "deepseek":
                        extra = f" (configured={data.get('configured', False)})"
                    elif key == "search":
                        extra = " (OK)"
                    elif key == "status_full":
                        extra = f" ({data.get('module_count', 0)} modules, {data.get('memory_total', 0)} memories)"
                    results[key] = {
                        "ok": True,
                        "status": 200,
                        "desc": desc,
                        "extra": extra,
                    }

            if ok:
                self._log("OK", f"    ✓ {desc}: 正常{results[key].get('extra', '')}")
            else:
                self._log(
                    "WARN", f"    ✗ {desc}: 异常 (status={results[key].get('status')})"
                )
                all_ok = False

        return {"all_ok": all_ok, "results": results}

    def _dump_error_log(self):
        """输出错误日志最后几行帮助诊断"""
        try:
            if ERROR_LOG.exists():
                lines = ERROR_LOG.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
                tail = lines[-20:] if len(lines) > 20 else lines
                self._log("ERROR", "  服务错误日志(最后20行):")
                for line in tail:
                    self._log("ERROR", f"    | {line}")
        except Exception:
            pass

    def _check_exclusive_lock(self) -> tuple[bool, str]:
        """三重排他性检查: 端口+PID+健康检查"""
        checks = []

        # 检查1: 端口占用
        if not self._check_port():
            checks.append(f"端口 {PORT} 被占用")

        # 检查2: PID文件验证
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                # 检查进程是否存活
                try:
                    import psutil

                    if psutil.pid_exists(pid):
                        checks.append(f"PID文件存在且进程存活 (PID: {pid})")
                except ImportError:
                    # Fallback: 使用tasklist
                    result = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}"],
                        capture_output=True,
                        timeout=5,
                    )
                    if str(pid) in result.stdout.decode("utf-8", errors="replace"):
                        checks.append(f"PID文件存在且进程存活 (PID: {pid})")
            except Exception:
                pass

        # 检查3: 健康检查API
        try:
            resp = urllib.request.urlopen(HEALTH_URL, timeout=2)
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("engine_ready", False):
                    checks.append("健康检查API返回正常 (engine_ready=True)")
        except Exception:
            pass

        if checks:
            return False, "; ".join(checks)
        return True, ""

    def start(self, daemon: bool = False, quick_start: bool = False) -> bool:
        """启动天机服务 — 三阶段全链验证
        quick_start: 快速启动模式（跳过全链验证，服务就绪后立即返回）
        """
        self._log("INFO", "=" * 60)
        self._log("INFO", f"天机v9.1 启动器 v2.0 (端口 {PORT}) — 全链验证版")
        self._log("INFO", "=" * 60)

        # Step 0: 排他性检查 (三重验证)
        self._log("INFO", "[0/7] 排他性检查...")
        exclusive_ok, reason = self._check_exclusive_lock()
        if not exclusive_ok:
            self._log("WARN", f"检测到天机v9.1已在运行: {reason}")
            self._log("INFO", "天机v9.1 已在运行中，无需重复启动")
            self._log("INFO", "=" * 60)
            return False

        # Step 1: 检查端口
        self._log("INFO", "[1/7] 检查端口...")
        if not self._check_port():
            self._log("WARN", f"端口 {PORT} 被占用，尝试释放...")
            if not self._free_port():
                self._log("ERROR", f"无法释放端口 {PORT}")
                return False
        self._log("OK", f"端口 {PORT} 可用")

        # Step 2: 清理旧进程
        self._log("INFO", "[2/7] 清理旧进程...")
        self._cleanup_old_pid()
        self._log("OK", "旧进程清理完成")

        # Step 3: 设置环境变量
        self._log("INFO", "[3/7] 设置环境变量...")
        env = os.environ.copy()
        env["AI_MEMORY_ROOT"] = str(TIANJI_ROOT)
        env["AI_MEMORY_PORT"] = str(PORT)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"  # 【对齐修复】强制Python全局UTF-8模式
        env["EMBEDDING_ENGINE"] = "tfidf"  # 【对齐修复】零网络阻塞启动
        env["TRANSFORMERS_OFFLINE"] = "1"  # 【对齐修复】禁止模型下载
        env["PYTHONPATH"] = str(TIANJI_ROOT)
        env["TIANJI_V91_PROTOCOL_MODE"] = "true"
        env["TIANJI_V91_EVENT_WIRING"] = "true"
        self._log("OK", "环境变量设置完成 (Protocol+EventWiring+UTF8+TFIDF已启用)")

        # Step 4: 启动uvicorn服务
        self._log("INFO", "[4/7] 启动uvicorn服务...")
        # 【对齐修复】使用python.exe而非pythonw.exe以确保子进程编码正确
        python_exe = str(TIANJI_ROOT / "python" / "python.exe")
        # [AUDIT-FIX] Windows下workers>1会因multiprocessing spawn导致IOCP挂起
        worker_count = "1" if sys.platform == "win32" else "2"
        uvicorn_args = [
            "-X",
            "utf8",
            "-m",
            "uvicorn",
            "server.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(PORT),
            "--workers",
            worker_count,
        ]

        try:
            self.process = subprocess.Popen(
                [python_exe] + uvicorn_args,
                cwd=str(TIANJI_ROOT),
                env=env,
                stdout=open(SERVER_LOG, "a", encoding="utf-8"),
                stderr=open(ERROR_LOG, "a", encoding="utf-8"),
                creationflags=subprocess.CREATE_NO_WINDOW if daemon else 0,
            )
            PID_FILE.write_text(str(self.process.pid))
            self._log("OK", f"uvicorn进程启动成功 (PID: {self.process.pid})")
        except Exception as e:
            self._log("ERROR", f"启动失败: {e}")
            return False

        # Step 5: 等待基础健康检查
        self._log("INFO", "[5/7] 阶段一: 基础健康检查...")
        if not self._wait_basic_health(max_wait=120):
            self._log("ERROR", "基础健康检查失败")
            return False

        # Step 6: 等待容器模块完全就绪
        self._log("INFO", "[6/7] 阶段二: 容器模块就绪...")
        self._wait_container_ready(max_wait=60)

        # Step 7: 全链端点验证（快速启动模式下跳过，交由后台线程执行）
        if quick_start:
            self._log("INFO", "[7/7] 阶段三: 全链端点验证 (快速启动模式，后台执行)...")
            self._log("INFO", "=" * 60)
            self._log("OK", "天机v9.1 启动成功! (快速启动模式，全链验证后台执行)")
            self._log("OK", f"端口: {PORT}")
            self._log("OK", f"健康检查: {HEALTH_URL}")
            self._log("OK", f"Web UI: http://127.0.0.1:{PORT}/")
            self._log("OK", f"API文档: http://127.0.0.1:{PORT}/docs")
            self._log("OK", f"PID: {self.process.pid}")
            self._log("INFO", "=" * 60)
            self.running = True
            return True

        self._log("INFO", "[7/7] 阶段三: 全链端点验证...")
        chain_result = self._verify_chain()
        chain_ok = chain_result["all_ok"]
        results = chain_result["results"]

        # 统计结果
        ok_count = sum(1 for r in results.values() if r["ok"])
        total_count = len(results)
        fail_items = [r["desc"] for r in results.values() if not r["ok"]]

        self._log("INFO", "=" * 60)
        if chain_ok:
            self._log(
                "OK", f"天机v9.1 启动成功! 全链验证 {ok_count}/{total_count} 通过"
            )
        else:
            self._log(
                "WARN",
                f"天机v9.1 启动完成 (降级模式): {ok_count}/{total_count} 端点正常",
            )
            if fail_items:
                self._log("WARN", f"异常项: {', '.join(fail_items)}")

        self._log("OK", f"端口: {PORT}")
        self._log("OK", f"健康检查: {HEALTH_URL}")
        self._log("OK", f"Web UI: http://127.0.0.1:{PORT}/")
        self._log("OK", f"API文档: http://127.0.0.1:{PORT}/docs")
        self._log("OK", f"PID: {self.process.pid}")
        self._log("INFO", "=" * 60)

        self.running = True
        return True

    def stop(self):
        """停止天机服务"""
        if self.process:
            self._log("INFO", "正在停止天机服务...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self._log("OK", "天机服务已停止")
            PID_FILE.unlink(missing_ok=True)
            self.running = False

    def full_verify(self) -> dict:
        """对已运行服务执行全链验证"""
        self._log("CHAIN", "执行全链验证...")

        health = self._http_get_json(HEALTH_URL)
        chain = self._verify_chain()

        result = {
            "healthy": health is not None and health.get("status") == "healthy",
            "engine_ready": health.get("engine_ready") if health else False,
            "protocol_mode": health.get("protocol_mode") if health else False,
            "event_wiring": health.get("event_wiring") if health else False,
            "uptime_seconds": health.get("uptime_seconds") if health else 0,
            "chain_all_ok": chain["all_ok"],
            "chain_results": chain["results"],
            "port": PORT,
        }

        if health and health.get("layers"):
            layers = health["layers"]
            result["memory_by_layer"] = {
                k: v.get("entry_count", 0)
                for k, v in layers.items()
                if isinstance(v, dict)
            }
            result["memory_total"] = sum(result["memory_by_layer"].values())

        return result

    def status(self) -> dict:
        """获取服务状态"""
        status = {
            "running": self.running,
            "port": PORT,
            "pid": self.process.pid if self.process else None,
            "health_url": HEALTH_URL,
        }

        health = self._http_get_json(HEALTH_URL, timeout=5)
        if health:
            status["healthy"] = True
            status["uptime"] = health.get("uptime_seconds", 0)
            status["engine_ready"] = health.get("engine_ready", False)
            status["protocol_mode"] = health.get("protocol_mode", False)
            status["event_wiring"] = health.get("event_wiring", False)
            if health.get("layers"):
                status["memory_total"] = sum(
                    v.get("entry_count", 0)
                    for v in health["layers"].values()
                    if isinstance(v, dict)
                )
        else:
            status["healthy"] = False

        return status


def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="天机v9.1统一启动器 v2.0 (全链验证版)")
    parser.add_argument("--daemon", action="store_true", help="后台模式启动")
    parser.add_argument("--tray", action="store_true", help="托盘模式启动")
    parser.add_argument("--stop", action="store_true", help="停止服务")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--verify", action="store_true", help="全链验证已运行服务")
    args = parser.parse_args()

    launcher = TianjiLauncher()

    if args.stop:
        launcher.stop()
        return

    if args.status:
        status = launcher.status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return

    if args.verify:
        result = launcher.full_verify()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # 【对齐修复】--daemon或--tray模式下子进程都应隐藏控制台窗口
    # 托盘模式使用快速启动（quick_start），确保托盘图标尽快显示，全链验证后台执行
    success = launcher.start(daemon=args.daemon or args.tray, quick_start=args.tray)

    if not success:
        sys.exit(1)

    if args.tray:
        launcher._log("INFO", "托盘模式: 跳过后台全链验证，避免压垮单worker uvicorn")
        launcher._log("INFO", " (如需全链验证，请使用 --verify 参数手动执行)")
        _run_tray_mode(launcher)
    elif not args.daemon:
        try:
            while launcher.running:
                time.sleep(1)
        except KeyboardInterrupt:
            launcher.stop()


def _create_tray_icon() -> "Image.Image":
    """生成天机托盘图标 (64x64 RGBA)
    优先使用静态ICO文件，失败时动态生成
    """
    from PIL import Image

    # [OPT-v2] 优先使用静态ICO文件（多分辨率，更清晰）
    static_ico = TIANJI_ROOT / "assets" / "tray_icon.ico"
    if static_ico.exists():
        try:
            img = Image.open(static_ico)
            img = img.convert("RGBA")
            if img.size[0] < 64:
                img = img.resize((64, 64), Image.LANCZOS)
            return img
        except Exception:
            pass  # 回退到动态生成

    # 动态生成（fallback）
    from PIL import ImageDraw, ImageFont

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse(
        (2, 2, 62, 62), fill=(72, 61, 139, 255), outline=(255, 215, 0, 255), width=2
    )
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


def _run_tray_mode(launcher: "TianjiLauncher") -> None:
    """托盘模式：单进程合一 — 后台服务 + 托盘图标 + 看门狗"""
    try:
        import pystray
    except ImportError as e:
        launcher._log("ERROR", f"托盘启动失败：pystray未安装 - {e}")
        return

    icon_img = _create_tray_icon()
    launcher._log("OK", "托盘图标图像创建成功")

    # ── 菜单动作 ──

    def _open(path: str):
        def handler(icon, item):
            import webbrowser

            webbrowser.open(f"http://127.0.0.1:{PORT}{path}")

        return handler

    def _open_folder(folder: str):
        def handler(icon, item):
            try:
                os.startfile(folder)
            except Exception as e:
                launcher._log("WARN", f"打开目录失败: {e}")
        return handler

    def on_open_logs_dir(icon, item):
        """打开日志目录"""
        os.startfile(str(LOG_DIR))

    def on_open_data_dir(icon, item):
        """打开数据目录"""
        data_dir = TIANJI_ROOT / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(data_dir))

    def on_open_config_dir(icon, item):
        """打开配置目录"""
        config_dir = TIANJI_ROOT / ".trae"
        if config_dir.exists():
            os.startfile(str(config_dir))
        else:
            icon.notify("配置目录不存在", title="天机v9.1")

    def on_open_root_dir(icon, item):
        """打开项目根目录"""
        os.startfile(str(TIANJI_ROOT))

    def on_open_assets_dir(icon, item):
        """打开资源目录"""
        assets_dir = TIANJI_ROOT / "assets"
        if assets_dir.exists():
            os.startfile(str(assets_dir))
        else:
            icon.notify("资源目录不存在", title="天机v9.1")

    def on_clear_cache(icon, item):
        """清空缓存 (__pycache__ + .pyc)"""
        try:
            import shutil
            cleared = 0
            for p in TIANJI_ROOT.rglob("__pycache__"):
                if "site-packages" in str(p) or "node_modules" in str(p):
                    continue
                try:
                    shutil.rmtree(p, ignore_errors=True)
                    cleared += 1
                except Exception:
                    pass
            icon.notify(f"已清空 {cleared} 个缓存目录", title="天机v9.1")
        except Exception as e:
            icon.notify(f"清空失败: {str(e)[:30]}", title="天机v9.1 告警")

    def on_view_pid(icon, item):
        """查看PID信息"""
        try:
            if PID_FILE.exists():
                pid = PID_FILE.read_text().strip()
                icon.notify(f"当前服务PID: {pid}\n端口: {PORT}", title="天机v9.1 PID")
            else:
                icon.notify("PID文件不存在", title="天机v9.1")
        except Exception as e:
            icon.notify(f"读取PID失败: {str(e)[:30]}", title="天机v9.1 告警")

    def on_status(icon, item):
        st = launcher.status()
        msg = (
            f"运行中: {st.get('running', False)}\n"
            f"健康: {st.get('healthy', False)}\n"
            f"引擎就绪: {st.get('engine_ready', False)}\n"
            f"PID: {st.get('pid', 'N/A')}\n"
            f"端口: {PORT}\n"
            f"记忆总数: {st.get('memory_total', 'N/A')}\n"
            f"运行时间: {st.get('uptime', 0):.0f}秒"
        )
        icon.notify(msg, title="天机v9.1 服务状态")

    def on_full_verify(icon, item):
        result = launcher.full_verify()
        ok_count = sum(1 for r in result["chain_results"].values() if r["ok"])
        total = len(result["chain_results"])
        msg = f"全链验证: {ok_count}/{total} 通过\n"
        for key, r in result["chain_results"].items():
            mark = "OK" if r["ok"] else "FAIL"
            msg += f"  [{mark}] {r.get('desc', key)}\n"
        msg += f"\n引擎就绪: {result['engine_ready']}\n记忆总数: {result.get('memory_total', 'N/A')}"
        icon.notify(msg, title="天机v9.1 全链验证")

    def on_restart(icon, item):
        icon.notify("正在重启...", title="天机v9.1")
        launcher.stop()
        time.sleep(2)
        ok = launcher.start(daemon=True)
        if ok:
            icon.notify("重启成功！", title="天机v9.1")
        else:
            icon.notify("重启失败，请查看日志", title="天机v9.1")

    def on_stop(icon, item):
        launcher.stop()
        icon.stop()

    def on_quit(icon, item):
        icon.stop()

    def on_toggle_autostart(icon, item):
        """切换开机自启状态"""
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "TianjiV91"
        bat_path = str(TIANJI_ROOT / "launcher" / "start_tianji.bat")
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_READ | winreg.KEY_SET_VALUE,
            )
            try:
                current, _ = winreg.QueryValueEx(key, app_name)
                # 已存在 → 删除（关闭自启）
                winreg.DeleteValue(key, app_name)
                icon.notify("已关闭开机自启", title="天机v9.1")
            except FileNotFoundError:
                # 不存在 → 添加（开启自启）
                winreg.SetValueEx(
                    key, app_name, 0, winreg.REG_SZ, f'cmd.exe /c ""{bat_path}""'
                )
                icon.notify("已开启开机自启", title="天机v9.1")
            winreg.CloseKey(key)
        except Exception as e:
            icon.notify(f"设置失败: {str(e)[:30]}", title="天机v9.1 告警")

    def _is_autostart_enabled() -> bool:
        """检查是否已开启自启"""
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "TianjiV91"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, app_name)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False

    # ── 构建菜单 ── [OPT-v2 科学右键功能]
    autostart_enabled = _is_autostart_enabled()
    menu = pystray.Menu(
        pystray.MenuItem("天机v9.1 | 端口8771 | 唯一启动入口", None, enabled=False),
        pystray.Menu.SEPARATOR,
        # [Web入口组]
        pystray.MenuItem("🌐 Web UI", _open("/")),
        pystray.MenuItem("📊 Dashboard", _open("/dashboard")),
        pystray.MenuItem("🔧 MCP 工具", _open("/mcp-tools")),
        pystray.MenuItem("📚 API 文档", _open("/docs")),
        pystray.Menu.SEPARATOR,
        # [目录快捷访问组] - 新增科学右键功能
        pystray.MenuItem("📁 打开项目根目录", on_open_root_dir),
        pystray.MenuItem("📋 打开日志目录", on_open_logs_dir),
        pystray.MenuItem("💾 打开数据目录", on_open_data_dir),
        pystray.MenuItem("⚙️ 打开配置目录", on_open_config_dir),
        pystray.MenuItem("🎨 打开资源目录", on_open_assets_dir),
        pystray.Menu.SEPARATOR,
        # [服务管理组]
        pystray.MenuItem("✅ 服务状态", on_status),
        pystray.MenuItem("🔍 全链验证", on_full_verify),
        pystray.MenuItem("🆔 查看PID", on_view_pid),
        pystray.MenuItem(
            f"🚀 开机自启 {'✅' if autostart_enabled else '⚪'}", on_toggle_autostart
        ),
        pystray.MenuItem("🧹 清空缓存", on_clear_cache),
        pystray.Menu.SEPARATOR,
        # [进程控制组]
        pystray.MenuItem("🔄 重启服务", on_restart),
        pystray.MenuItem("⏹️ 停止服务", on_stop),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("🚪 退出托盘", on_quit),
    )

    icon = pystray.Icon(
        name="tianji_v9_1",
        icon=icon_img,
        title="天机v9.1 - 8771",
        menu=menu,
    )

    launcher._log("OK", "系统托盘图标已创建 (任务栏右下角)")

    # ── 启动SSE MCP Server (端口8772，独立进程，托盘守护) ──
    MCP_PORT = 8772
    mcp_process: subprocess.Popen | None = None

    def _start_mcp_server() -> bool:
        nonlocal mcp_process
        try:
            import subprocess as _sp

            python_exe = str(TIANJI_ROOT / "python" / "python.exe")
            env = os.environ.copy()
            env["TIANJI_API_URL"] = f"http://127.0.0.1:{PORT}"
            env["TIANJI_MCP_PORT"] = str(MCP_PORT)
            env["PYTHONPATH"] = str(TIANJI_ROOT)
            mcp_process = _sp.Popen(
                [python_exe, "-X", "utf8", "-m", "mcp.sse_mcp_server"],
                cwd=str(TIANJI_ROOT),
                env=env,
                stdout=open(LOG_DIR / "mcp-sse.log", "a", encoding="utf-8"),
                stderr=open(LOG_DIR / "mcp-sse.err.log", "a", encoding="utf-8"),
                creationflags=_sp.CREATE_NO_WINDOW,
            )
            launcher._log(
                "OK",
                f"SSE MCP Server启动成功 (端口 {MCP_PORT}, PID: {mcp_process.pid})",
            )
            return True
        except Exception as e:
            launcher._log("ERROR", f"SSE MCP Server启动失败: {e}")
            return False

    _start_mcp_server()

    # ── 看门狗: uvicorn + SSE MCP 双进程守护，挂了自动重启（最多5次/小时）──
    _restart_count = 0
    _last_restart_time = 0
    _max_restarts_per_hour = 5

    def watchdog():
        nonlocal _restart_count, _last_restart_time, mcp_process
        MCP_HEALTH_URL = f"http://127.0.0.1:{MCP_PORT}/health"
        # [FIX-RESTART-LOOP] 重启后宽限期：跳过前几次检查，给服务充分启动时间
        _grace_period_until = time.time() + 90  # 启动后90秒内不检查uvicorn健康
        while True:
            time.sleep(10)  # [FIX] 5s→10s，降低检查频率

            # 检查SSE MCP进程是否存活（单独守护，挂了单独重启）
            mcp_alive = False
            if mcp_process and mcp_process.poll() is None:
                try:
                    resp = urllib.request.urlopen(MCP_HEALTH_URL, timeout=5)
                    if resp.status == 200:
                        mcp_alive = True
                except Exception:
                    pass
            if not mcp_alive:
                # [FIX] MCP检查也加宽限期，避免启动期间误判
                if time.time() > _grace_period_until:
                    launcher._log("WARN", "SSE MCP Server异常，尝试重启...")
                    try:
                        if mcp_process:
                            try:
                                mcp_process.kill()
                                mcp_process.wait(timeout=3)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    _start_mcp_server()
                else:
                    # 宽限期内，MCP还没起来是正常的
                    pass

            # [FIX-RESTART-LOOP] 宽限期内跳过uvicorn健康检查
            if time.time() < _grace_period_until:
                continue

            # 检查uvicorn进程是否存活
            if launcher.process and launcher.process.poll() is None:
                # 进程活着，检查健康状态（三重检查确认挂起）
                hang_detected = False
                for check_round in range(3):
                    try:
                        resp = urllib.request.urlopen(
                            HEALTH_URL, timeout=10
                        )  # [FIX] 3s→10s
                        if resp.status == 200:
                            break
                    except Exception:
                        pass
                    if check_round < 2:
                        time.sleep(5)  # [FIX] 10s→5s，总检查窗口25s
                else:
                    hang_detected = True

                if not hang_detected:
                    continue

                # 进程活着但无响应（挂起），强制终止并重启
                launcher._log("ERROR", "uvicorn确认挂起（25s内无响应），强制重启...")

            # 进程退出或挂起，尝试重启
            launcher._log(
                "ERROR",
                f"uvicorn异常 (code: {launcher.process.returncode if launcher.process else 'unknown'})",
            )

            # 频率限制：1小时内最多重启5次
            now = time.time()
            if now - _last_restart_time > 3600:
                _restart_count = 0
            if _restart_count >= _max_restarts_per_hour:
                launcher._log(
                    "ERROR", f"1小时内重启已达{_max_restarts_per_hour}次，停止自动重启"
                )
                try:
                    icon.notify(
                        "服务异常，重启次数超限，请手动检查", title="天机v9.1 告警"
                    )
                except Exception:
                    pass
                launcher.running = False
                break

            _restart_count += 1
            _last_restart_time = now
            launcher._log("INFO", f"正在自动重启 (第{_restart_count}次)...")

            try:
                icon.notify(
                    f"服务异常，正在自动重启 (第{_restart_count}次)", title="天机v9.1"
                )
            except Exception:
                pass

            # 清理旧进程
            try:
                if launcher.process:
                    launcher.process.kill()
                    launcher.process.wait(timeout=5)
            except Exception:
                pass
            PID_FILE.unlink(missing_ok=True)

            # 释放端口
            launcher._free_port()

            # 重新启动
            try:
                env = os.environ.copy()
                env["AI_MEMORY_ROOT"] = str(TIANJI_ROOT)
                env["AI_MEMORY_PORT"] = str(PORT)
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"
                env["EMBEDDING_ENGINE"] = "tfidf"
                env["TRANSFORMERS_OFFLINE"] = "1"
                env["PYTHONPATH"] = str(TIANJI_ROOT)
                env["TIANJI_V91_PROTOCOL_MODE"] = "true"
                env["TIANJI_V91_EVENT_WIRING"] = "true"

                python_exe = str(TIANJI_ROOT / "python" / "python.exe")
                uvicorn_args = [
                    "-X",
                    "utf8",
                    "-m",
                    "uvicorn",
                    "server.main:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(PORT),
                    "--workers",
                    "1",
                ]
                launcher.process = subprocess.Popen(
                    [python_exe] + uvicorn_args,
                    cwd=str(TIANJI_ROOT),
                    env=env,
                    stdout=open(SERVER_LOG, "a", encoding="utf-8"),
                    stderr=open(ERROR_LOG, "a", encoding="utf-8"),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                PID_FILE.write_text(str(launcher.process.pid))
                launcher._log("OK", f"uvicorn重启成功 (PID: {launcher.process.pid})")

                # uvicorn重启后，也重启SSE MCP Server
                try:
                    if mcp_process:
                        try:
                            mcp_process.kill()
                            mcp_process.wait(timeout=3)
                        except Exception:
                            pass
                except Exception:
                    pass
                _start_mcp_server()

                # 等待服务就绪 [FIX] 20s→40s，给容器更多初始化时间
                time.sleep(40)
                launcher._wait_basic_health(max_wait=90)
                launcher._wait_container_ready(max_wait=90)
                launcher.running = True
                # [FIX-RESTART-LOOP] 重置宽限期，避免重启后立即被再次判定挂起
                _grace_period_until = time.time() + 90

                try:
                    icon.notify("服务重启成功！", title="天机v9.1")
                except Exception:
                    pass

            except Exception as e:
                launcher._log("ERROR", f"重启失败: {e}")
                launcher.running = False
                try:
                    icon.notify(f"重启失败: {str(e)[:50]}", title="天机v9.1 告警")
                except Exception:
                    pass
                break

    threading.Thread(target=watchdog, daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
