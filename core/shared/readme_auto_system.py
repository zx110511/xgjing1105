r"""
天机v9.1 README自动化守护系统 v1.0
===================================
完全自动化的README索引维护机制
- 文件系统实时监控
- 自动触发README更新
- 与天机强制记录系统集成
- 配置化管理
"""

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List

try:
    from watchdog.events import (
        FileCreatedEvent,
        FileDeletedEvent,
        FileModifiedEvent,
        FileSystemEventHandler,
    )
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from .directory_index import (
    AIHookExecutor,
    DirectoryScanner,
    READMEGenerator,
    TianjiREADMEIntegrator,
)



from typing import Dict

class AutoTriggerType(Enum):
    """自动触发类型"""

    FILE_CREATE = "file_create"
    FILE_DELETE = "file_delete"
    FILE_MODIFY = "file_modify"
    DIR_CREATE = "dir_create"
    DIR_DELETE = "dir_delete"
    PERIODIC = "periodic"
    MANUAL = "manual"


@dataclass
class AutoTriggerConfig:
    """自动触发配置"""

    enabled: bool = True
    debounce_seconds: float = 2.0  # 防抖时间
    batch_size: int = 10  # 批量处理阈值
    batch_timeout: float = 5.0  # 批量超时
    exclude_patterns: List[str] = field(
        default_factory=lambda: [
            "*.pyc",
            "*.pyo",
            "__pycache__",
            ".git",
            "node_modules",
            "*.tmp",
            "*.bak",
            ".DS_Store",
            "Thumbs.db",
        ]
    )
    include_patterns: List[str] = field(default_factory=lambda: ["*"])


@dataclass
class READMEAutoConfig:
    """README自动化配置"""

    watch_dirs: List[str] = field(default_factory=list)
    trigger_config: AutoTriggerConfig = field(default_factory=AutoTriggerConfig)
    auto_commit: bool = False  # 是否自动提交到git
    auto_push: bool = False  # 是否自动推送
    store_to_tianji: bool = True  # 是否存储到天机
    notify_on_update: bool = True  # 是否通知更新
    max_depth: int = 3  # 最大扫描深度
    update_interval: float = 300.0  # 周期更新间隔(秒)

    def to_dict(self) -> dict:
        return {
            "watch_dirs": self.watch_dirs,
            "trigger_config": {
                "enabled": self.trigger_config.enabled,
                "debounce_seconds": self.trigger_config.debounce_seconds,
                "batch_size": self.trigger_config.batch_size,
                "batch_timeout": self.trigger_config.batch_timeout,
                "exclude_patterns": self.trigger_config.exclude_patterns,
                "include_patterns": self.trigger_config.include_patterns,
            },
            "auto_commit": self.auto_commit,
            "auto_push": self.auto_push,
            "store_to_tianji": self.store_to_tianji,
            "notify_on_update": self.notify_on_update,
            "max_depth": self.max_depth,
            "update_interval": self.update_interval,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "READMEAutoConfig":
        trigger_data = data.get("trigger_config", {})
        trigger_config = AutoTriggerConfig(
            enabled=trigger_data.get("enabled", True),
            debounce_seconds=trigger_data.get("debounce_seconds", 2.0),
            batch_size=trigger_data.get("batch_size", 10),
            batch_timeout=trigger_data.get("batch_timeout", 5.0),
            exclude_patterns=trigger_data.get("exclude_patterns", []),
            include_patterns=trigger_data.get("include_patterns", ["*"]),
        )
        return cls(
            watch_dirs=data.get("watch_dirs", []),
            trigger_config=trigger_config,
            auto_commit=data.get("auto_commit", False),
            auto_push=data.get("auto_push", False),
            store_to_tianji=data.get("store_to_tianji", True),
            notify_on_update=data.get("notify_on_update", True),
            max_depth=data.get("max_depth", 3),
            update_interval=data.get("update_interval", 300.0),
        )


class DebouncedTrigger:
    """防抖触发器"""

    def __init__(self, callback: Callable, debounce_seconds: float = 2.0):
        self._callback = callback
        self._debounce_seconds = debounce_seconds
        self._pending = {}
        self._lock = threading.Lock()
        self._timer = None

    def trigger(self, dir_path: str, event_type: AutoTriggerType):
        """触发更新（防抖）"""
        with self._lock:
            key = dir_path
            self._pending[key] = (dir_path, event_type, time.time())

            if self._timer is None:
                self._timer = threading.Timer(self._debounce_seconds, self._execute)
                self._timer.start()

    def _execute(self):
        """执行回调"""
        with self._lock:
            if not self._pending:
                self._timer = None
                return

            # 获取所有待处理的触发
            items = list(self._pending.values())
            self._pending.clear()

            # 按目录分组
            grouped = {}
            for dir_path, event_type, timestamp in items:
                if dir_path not in grouped:
                    grouped[dir_path] = []
                grouped[dir_path].append((event_type, timestamp))

            # 执行回调
            for dir_path, events in grouped.items():
                try:
                    self._callback(dir_path, events)
                except Exception as e:
                    print(f"[DebouncedTrigger] Error: {e}")

            # 重置定时器
            self._timer = None


class BatchProcessor:
    """批量处理器"""

    def __init__(
        self, callback: Callable, batch_size: int = 10, batch_timeout: float = 5.0
    ):
        self._callback = callback
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout
        self._batch: List[tuple] = []
        self._lock = threading.Lock()
        self._timer = None
        self._last_batch_time = time.time()

    def add(self, dir_path: str, event_type: AutoTriggerType):
        """添加到批次"""
        with self._lock:
            self._batch.append((dir_path, event_type))

            # 检查是否达到批次大小
            if len(self._batch) >= self._batch_size:
                self._flush()
            elif self._timer is None:
                self._timer = threading.Timer(self._batch_timeout, self._flush)
                self._timer.start()

    def _flush(self):
        """刷新批次"""
        with self._lock:
            if not self._batch:
                self._timer = None
                return

            batch = self._batch.copy()
            self._batch.clear()

            try:
                self._callback(batch)
            except Exception as e:
                print(f"[BatchProcessor] Error: {e}")

            self._timer = None
            self._last_batch_time = time.time()


class READMEFileSystemHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """文件系统事件处理器"""

    def __init__(self, auto_system: "READMEAutoSystem"):
        self._auto_system = auto_system

    def on_created(self, event):
        if event.is_directory:
            self._auto_system.trigger_update(
                os.path.dirname(event.src_path), AutoTriggerType.DIR_CREATE
            )
        else:
            self._auto_system.trigger_update(
                os.path.dirname(event.src_path), AutoTriggerType.FILE_CREATE
            )

    def on_deleted(self, event):
        if event.is_directory:
            self._auto_system.trigger_update(
                os.path.dirname(event.src_path), AutoTriggerType.DIR_DELETE
            )
        else:
            self._auto_system.trigger_update(
                os.path.dirname(event.src_path), AutoTriggerType.FILE_DELETE
            )

    def on_modified(self, event):
        if not event.is_directory:
            self._auto_system.trigger_update(
                os.path.dirname(event.src_path), AutoTriggerType.FILE_MODIFY
            )


class READMEAutoSystem:
    """README自动化系统 - 完全自动化核心"""

    def __init__(self, engine=None, registry=None, config: READMEAutoConfig = None):
        self._engine = engine
        self._registry = registry
        self._config = config or READMEAutoConfig()

        # 核心组件
        self._integrator = TianjiREADMEIntegrator(engine, registry)
        self._hook_executor = AIHookExecutor(engine)
        self._scanner = DirectoryScanner(registry=registry)
        self._generator = READMEGenerator()

        # 自动化组件
        self._debounced_trigger = DebouncedTrigger(
            self._handle_trigger, self._config.trigger_config.debounce_seconds
        )
        self._batch_processor = BatchProcessor(
            self._handle_batch,
            self._config.trigger_config.batch_size,
            self._config.trigger_config.batch_timeout,
        )

        # 文件监控
        self._observer = None
        self._watch_handlers: Dict[str, Any] = {}

        # 状态
        self._running = False
        self._update_count = 0
        self._last_update_time = 0.0
        self._periodic_thread = None

        # 配置文件
        self._config_file = None

    def initialize(self, config_file: str = None):
        """初始化自动化系统"""
        # 加载配置
        if config_file:
            self._load_config(config_file)
            self._config_file = config_file

        # 启动文件监控
        if WATCHDOG_AVAILABLE:
            self._start_file_watcher()

        # 启动周期更新
        if self._config.update_interval > 0:
            self._start_periodic_update()

        self._running = True
        print("[READMEAutoSystem] 初始化完成")
        print(f"  监控目录: {len(self._config.watch_dirs)}")
        print(f"  防抖时间: {self._config.trigger_config.debounce_seconds}s")
        print(f"  批量大小: {self._config.trigger_config.batch_size}")
        print(f"  周期间隔: {self._config.update_interval}s")

    def _load_config(self, config_file: str):
        """加载配置文件"""
        try:
            path = Path(config_file)
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self._config = READMEAutoConfig.from_dict(data)
                print(f"[READMEAutoSystem] 配置加载成功: {config_file}")
        except Exception as e:
            print(f"[READMEAutoSystem] 配置加载失败: {e}")

    def save_config(self, config_file: str = None):
        """保存配置文件"""
        path = Path(config_file or self._config_file)
        if not path:
            return

        try:
            path.write_text(
                json.dumps(self._config.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"[READMEAutoSystem] 配置保存成功: {path}")
        except Exception as e:
            print(f"[READMEAutoSystem] 配置保存失败: {e}")

    def _start_file_watcher(self):
        """启动文件监控"""
        if not WATCHDOG_AVAILABLE:
            print("[READMEAutoSystem] watchdog不可用，跳过文件监控")
            return

        self._observer = Observer()

        for watch_dir in self._config.watch_dirs:
            if Path(watch_dir).exists():
                handler = READMEFileSystemHandler(self)
                self._observer.schedule(handler, watch_dir, recursive=True)
                self._watch_handlers[watch_dir] = handler
                print(f"  监控: {watch_dir}")

        self._observer.start()
        print("[READMEAutoSystem] 文件监控启动成功")

    def _start_periodic_update(self):
        """启动周期更新"""

        def _periodic_loop():
            while self._running:
                time.sleep(self._config.update_interval)
                if not self._running:
                    break

                for watch_dir in self._config.watch_dirs:
                    try:
                        self.trigger_update(watch_dir, AutoTriggerType.PERIODIC)
                    except Exception as e:
                        print(f"[Periodic] Error: {e}")

        self._periodic_thread = threading.Thread(target=_periodic_loop, daemon=True)
        self._periodic_thread.start()
        print("[READMEAutoSystem] 周期更新启动成功")

    def trigger_update(self, dir_path: str, event_type: AutoTriggerType):
        """触发更新"""
        if not self._config.trigger_config.enabled:
            return

        # 检查排除模式
        if self._should_exclude(dir_path):
            return

        # 防抖触发
        self._debounced_trigger.trigger(dir_path, event_type)

        # 批量处理
        self._batch_processor.add(dir_path, event_type)

    def _should_exclude(self, path: str) -> bool:
        """检查是否应排除"""
        import fnmatch

        for pattern in self._config.trigger_config.exclude_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def _handle_trigger(self, dir_path: str, events: List[tuple]):
        """处理触发"""
        # 确定最重要的事件类型
        event_types = [e[0] for e in events]
        if AutoTriggerType.FILE_DELETE in event_types:
            primary_event = AutoTriggerType.FILE_DELETE
        elif AutoTriggerType.FILE_CREATE in event_types:
            primary_event = AutoTriggerType.FILE_CREATE
        elif AutoTriggerType.FILE_MODIFY in event_types:
            primary_event = AutoTriggerType.FILE_MODIFY
        else:
            primary_event = events[0][0]

        # 执行README更新
        self._update_readme(dir_path, primary_event)

    def _handle_batch(self, batch: List[tuple]):
        """处理批次"""
        # 按目录分组
        grouped: Dict[str, List[AutoTriggerType]] = {}
        for dir_path, event_type in batch:
            if dir_path not in grouped:
                grouped[dir_path] = []
            grouped[dir_path].append(event_type)

        # 批量更新
        for dir_path, events in grouped.items():
            self._handle_trigger(dir_path, [(e, time.time()) for e in events])

    def _update_readme(self, dir_path: str, event_type: AutoTriggerType):
        """更新README.md"""
        try:
            # 生成README
            readme_content = self._integrator.scan_and_generate(
                dir_path, max_depth=self._config.max_depth, save_to_file=True
            )

            # 执行钩子
            readme_path = Path(dir_path) / "README.md"
            if readme_path.exists():
                hooks = self._hook_executor.parse_hooks_from_readme(str(readme_path))
                for hook in hooks:
                    if hook.hook_name == event_type.value:
                        self._hook_executor.execute_hook(hook, {"dir_path": dir_path})

            # 存储到天机
            if self._config.store_to_tianji and self._engine:
                self._store_to_tianji(dir_path, event_type)

            # 自动提交
            if self._config.auto_commit:
                self._auto_commit(dir_path)

            # 更新统计
            self._update_count += 1
            self._last_update_time = time.time()

            # 通知
            if self._config.notify_on_update:
                print(f"[READMEAutoSystem] 更新成功: {dir_path} ({event_type.value})")

        except Exception as e:
            print(f"[READMEAutoSystem] 更新失败: {dir_path} - {e}")

    def _store_to_tianji(self, dir_path: str, event_type: AutoTriggerType):
        """存储到天机"""
        try:
            self._engine.remember(
                content=f"【README自动更新】{dir_path}\n触发类型: {event_type.value}\n时间: {datetime.now().isoformat()}",
                layer="episodic",
                tags=["README自动更新", event_type.value, Path(dir_path).name],
                priority="medium",
            )
        except Exception:
            pass

    def _auto_commit(self, dir_path: str):
        """自动提交到git"""
        try:
            import subprocess

            subprocess.run(
                ["git", "add", f"{dir_path}/README.md"], check=True, capture_output=True
            )
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"Auto-update README for {Path(dir_path).name}",
                ],
                check=True,
                capture_output=True,
            )

            if self._config.auto_push:
                subprocess.run(["git", "push"], check=True, capture_output=True)
        except Exception as e:
            print(f"[AutoCommit] Error: {e}")

    def add_watch_dir(self, dir_path: str):
        """添加监控目录"""
        if dir_path not in self._config.watch_dirs:
            self._config.watch_dirs.append(dir_path)

            if self._observer and Path(dir_path).exists():
                handler = READMEFileSystemHandler(self)
                self._observer.schedule(handler, dir_path, recursive=True)
                self._watch_handlers[dir_path] = handler

            print(f"[READMEAutoSystem] 添加监控: {dir_path}")

    def remove_watch_dir(self, dir_path: str):
        """移除监控目录"""
        if dir_path in self._config.watch_dirs:
            self._config.watch_dirs.remove(dir_path)
            print(f"[READMEAutoSystem] 移除监控: {dir_path}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "running": self._running,
            "watch_dirs": len(self._config.watch_dirs),
            "update_count": self._update_count,
            "last_update_time": self._last_update_time,
            "watchdog_available": WATCHDOG_AVAILABLE,
            "config": self._config.to_dict(),
        }

    def shutdown(self):
        """关闭自动化系统"""
        self._running = False

        if self._observer:
            self._observer.stop()
            self._observer.join()

        # 保存配置
        if self._config_file:
            self.save_config()

        print("[READMEAutoSystem] 已关闭")
        print(f"  总更新次数: {self._update_count}")


def create_default_config(project_root: str) -> READMEAutoConfig:
    """创建默认配置"""
    return READMEAutoConfig(
        watch_dirs=[
            f"{project_root}/core",
            f"{project_root}/indexing",
            f"{project_root}/server",
            f"{project_root}/agents",
            f"{project_root}/mcp",
        ],
        trigger_config=AutoTriggerConfig(
            enabled=True,
            debounce_seconds=2.0,
            batch_size=10,
            batch_timeout=5.0,
        ),
        store_to_tianji=True,
        notify_on_update=True,
        max_depth=2,
        update_interval=300.0,
    )
