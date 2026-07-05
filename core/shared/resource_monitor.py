"""
天机v9.1 系统资源监控仪表板 (TianjiV9-ResourceMonitor)
===========================================================
《天机·星枢运转》— 实时资源可视化引擎

功能:
    - CPU 使用率 (进程级 + 系统级)
    - 内存 使用量 (RSS/VMS + 系统总内存)
    - 磁盘 I/O (读写速率)
    - 网络 I/O (收发速率)
    - 进程树 (天机所有子进程统计)
    - 六层记忆容量趋势
    - 线程/句柄/GDI对象计数

输出:
    - JSON格式指标 (供API消费)
    - 托盘弹窗显示
    - 日志记录 (logs/perf.log)

用法:
    from core.shared.resource_monitor import ResourceMonitor
    monitor = ResourceMonitor()
    snapshot = monitor.snapshot()           # 瞬时快照
    trend = monitor.collect_interval(10)    # 10秒采样趋势
"""

import os
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────
# 路径配置
# ──────────────────────────────────────────────
MODULE_DIR = Path(__file__).resolve().parent
APP_DIR = MODULE_DIR.parent
PERF_LOG = APP_DIR / "logs" / "perf.log"
PERF_LOG.parent.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# 可选依赖降级
# ──────────────────────────────────────────────
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────
MAX_TREND_SAMPLES = 360  # 最多保留360个采样点 (1小时@10s间隔)


class ResourceMonitor:
    """天机系统资源监控器"""

    def __init__(self):
        self._process = self._get_current_process()
        self._sampling = False
        self._sampling_thread: threading.Thread | None = None
        self._trend: deque = deque(maxlen=MAX_TREND_SAMPLES)
        self._lock = threading.Lock()
        self._start_time = time.time()

    # ──────────────── 公开 API ────────────────

    def snapshot(self) -> dict[str, Any]:
        """获取瞬时资源快照"""
        if not HAS_PSUTIL:
            return self._fallback_snapshot()

        try:
            proc = self._process or psutil.Process(os.getpid())

            with proc.oneshot():
                cpu_percent = proc.cpu_percent(interval=0.1)
                mem_info = proc.memory_info()
                mem_full = (
                    proc.memory_full_info()
                    if hasattr(proc, "memory_full_info")
                    else None
                )
                io_counters = (
                    proc.io_counters() if hasattr(proc, "io_counters") else None
                )
                num_threads = proc.num_threads()
                connections = (
                    len(proc.connections()) if hasattr(proc, "connections") else 0
                )

            # 系统级指标
            sys_cpu = psutil.cpu_percent(interval=0.1)
            sys_mem = psutil.virtual_memory()
            sys_disk = psutil.disk_usage(str(APP_DIR))
            sys_net = psutil.net_io_counters()

            # 天机子进程统计
            child_processes = self._get_child_processes()

            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": round(time.time() - self._start_time, 1),
                "process": {
                    "pid": proc.pid,
                    "name": proc.name(),
                    "cpu_percent": round(cpu_percent, 1),
                    "memory_rss_mb": round(mem_info.rss / (1024 * 1024), 1),
                    "memory_vms_mb": round(mem_info.vms / (1024 * 1024), 1),
                    "memory_uss_mb": round(mem_full.uss / (1024 * 1024), 1)
                    if mem_full
                    else None,
                    "memory_pss_mb": round(mem_full.pss / (1024 * 1024), 1)
                    if mem_full
                    else None,
                    "threads": num_threads,
                    "connections": connections,
                    "io_read_mb": round(io_counters.read_bytes / (1024 * 1024), 1)
                    if io_counters
                    else None,
                    "io_write_mb": round(io_counters.write_bytes / (1024 * 1024), 1)
                    if io_counters
                    else None,
                },
                "system": {
                    "cpu_percent": round(sys_cpu, 1),
                    "memory_total_gb": round(sys_mem.total / (1024**3), 1),
                    "memory_available_gb": round(sys_mem.available / (1024**3), 1),
                    "memory_used_percent": round(sys_mem.percent, 1),
                    "disk_total_gb": round(sys_disk.total / (1024**3), 1),
                    "disk_used_percent": round(sys_disk.percent, 1),
                    "disk_free_gb": round(sys_disk.free / (1024**3), 1),
                    "net_sent_mb": round(sys_net.bytes_sent / (1024 * 1024), 1),
                    "net_recv_mb": round(sys_net.bytes_recv / (1024 * 1024), 1),
                },
                "children": {
                    "count": len(child_processes),
                    "total_memory_mb": round(
                        sum(p.get("memory_rss_mb", 0) for p in child_processes), 1
                    ),
                    "processes": child_processes,
                },
                "health": self._compute_health(
                    sys_cpu, sys_mem.percent, sys_disk.percent
                ),
            }

            return snapshot

        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    def get_trend(self, limit: int = 60) -> list[dict]:
        """获取趋势数据"""
        with self._lock:
            items = list(self._trend)[-limit:]
        return list(items)

    def collect_interval(self, seconds: int = 10) -> dict:
        """采集指定间隔的趋势数据"""
        snapshots = []
        start = time.time()
        while time.time() - start < seconds:
            snapshots.append(self.snapshot())
            time.sleep(1)

        if len(snapshots) > 1:
            first = snapshots[0].get("process", {})
            last = snapshots[-1].get("process", {})

            return {
                "duration_seconds": round(time.time() - start, 1),
                "samples": len(snapshots),
                "delta": {
                    "memory_rss_mb": round(
                        (last.get("memory_rss_mb", 0) or 0)
                        - (first.get("memory_rss_mb", 0) or 0),
                        2,
                    ),
                    "cpu_avg": round(
                        sum(
                            s.get("process", {}).get("cpu_percent", 0) or 0
                            for s in snapshots
                        )
                        / len(snapshots),
                        1,
                    ),
                },
                "snapshots": snapshots,
            }

        return {
            "duration_seconds": round(time.time() - start, 1),
            "samples": 1,
            "snapshots": snapshots,
        }

    def start_sampling(self, interval: int = 10):
        """启动后台采样 (每N秒一次)"""
        if self._sampling:
            return

        self._sampling = True

        def _sample_loop():
            while self._sampling:
                try:
                    snap = self.snapshot()
                    with self._lock:
                        self._trend.append(snap)
                except Exception:
                    pass
                time.sleep(interval)

        self._sampling_thread = threading.Thread(target=_sample_loop, daemon=True)
        self._sampling_thread.start()

    def stop_sampling(self):
        """停止后台采样"""
        self._sampling = False

    def get_layer_status(self) -> dict:
        """获取六层记忆存储状态"""
        memory_dir = APP_DIR / "data" / ".memory"
        layers = {
            "L0_Sensory": memory_dir / "sensory",
            "L1_Working": memory_dir / "working",
            "L2_ShortTerm": memory_dir / "short_term",
            "L3_Episodic": memory_dir / "episodic",
            "L4_Semantic": memory_dir / "semantic",
            "L5_Meta": memory_dir / "meta",
        }

        result = {}
        for layer_name, layer_path in layers.items():
            if layer_path.exists():
                files = list(layer_path.rglob("*"))
                entry_count = len([f for f in files if f.is_file()])
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                result[layer_name] = {
                    "status": "online",
                    "entries": entry_count,
                    "size_mb": round(total_size / (1024 * 1024), 1),
                }
            else:
                result[layer_name] = {"status": "offline", "entries": 0, "size_mb": 0}

        return result

    def get_stats(self) -> dict:
        """获取综合统计"""
        layer_status = self.get_layer_status()
        total_entries = sum(v["entries"] for v in layer_status.values())
        total_size_mb = sum(v["size_mb"] for v in layer_status.values())
        online_layers = sum(1 for v in layer_status.values() if v["status"] == "online")

        return {
            "layers": layer_status,
            "summary": {
                "total_entries": total_entries,
                "total_size_mb": round(total_size_mb, 1),
                "online_layers": online_layers,
                "offline_layers": 6 - online_layers,
            },
            "sampling": {
                "active": self._sampling,
                "trend_samples": len(self._trend),
            },
        }

    # ──────────────── 内部实现 ────────────────

    def _get_current_process(self):
        try:
            return psutil.Process(os.getpid()) if HAS_PSUTIL else None
        except Exception:
            return None

    def _get_child_processes(self) -> list[dict]:
        """获取天机所有子进程"""
        children = []
        try:
            proc = self._process or psutil.Process(os.getpid())
            for child in proc.children(recursive=True):
                try:
                    with child.oneshot():
                        children.append(
                            {
                                "pid": child.pid,
                                "name": child.name(),
                                "cpu_percent": round(
                                    child.cpu_percent(interval=0.05), 1
                                ),
                                "memory_rss_mb": round(
                                    child.memory_info().rss / (1024 * 1024), 1
                                ),
                                "status": child.status(),
                            }
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        return children

    def _fallback_snapshot(self) -> dict:
        """无psutil时的降级快照"""
        return {
            "timestamp": datetime.now().isoformat(),
            "warning": "psutil未安装, 资源监控受限",
            "process": {
                "pid": os.getpid(),
                "memory_rss_mb": "N/A (install psutil)",
            },
        }

    def _compute_health(self, cpu: float, mem: float, disk: float) -> str:
        """计算综合健康状态"""
        if cpu > 90 or mem > 95 or disk > 95:
            return "critical"
        if cpu > 75 or mem > 85 or disk > 90:
            return "warning"
        return "healthy"


# ──────────────────────────────────────────────
# 便捷函数 (托盘调用)
# ──────────────────────────────────────────────


def quick_health_check() -> str:
    """快速健康检查 (供托盘和API调用)"""
    monitor = ResourceMonitor()
    snap = monitor.snapshot()
    return snap.get("health", "unknown")
