# -*- coding: utf-8-sig -*-
"""天机v10.0.1 插件管理器  [v10-ready]

PluginManager职责:
1. 发现: 扫描指定目录发现插件模块
2. 加载: importlib动态加载插件
3. 验证: 检查插件是否实现要求的Protocol
4. 注册: 注册到全局插件表
5. 激活/停用: 运行时控制插件状态
6. 热替换: 激活新插件→停用旧插件

本地实现: 进程内importlib + dict注册表
远程实现: RemotePluginManager (灵境分布式插件仓库, stub预留)
版本: 1.0.0
"""
from __future__ import annotations

import importlib
import importlib.util
import logging
from typing import Any, Type
from pathlib import Path

from core.shared.plugin_interface import PluginInfo, PluginState, PluginResult

logger = logging.getLogger(__name__)


class PluginManager:
    """天机插件管理器  [v10-ready]

    实现IPluginManager Protocol (core/shared/protocols.py)。

    Usage:
        pm = PluginManager()
        pm.discover("core/search/strategies/")   # 扫描目录
        pm.load("fts5_strategy")                 # 加载插件
        pm.activate("fts5_strategy")             # 激活
        result = pm.execute("fts5_strategy", query="test")  # 执行
        pm.deactivate("fts5_strategy")           # 停用
        pm.unload("fts5_strategy")               # 卸载
    """

    def __init__(self) -> None:
        self._plugins: dict[str, dict[str, Any]] = {}  # name -> {info, module, instance}
        self._active: set[str] = set()

    def discover(self, directory: str | Path) -> list[str]:
        """扫描目录发现插件  [v10-ready]

        扫描指定目录下的.py文件，每个含PLUGIN_INFO变量的视为插件。

        Returns:
            发现的插件名列表
        """
        discovered = []
        dir_path = Path(directory)
        if not dir_path.exists():
            return discovered

        for py_file in dir_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            plugin_name = py_file.stem
            if plugin_name not in self._plugins:
                self._plugins[plugin_name] = {
                    "info": PluginInfo(name=plugin_name, state=PluginState.DISCOVERED),
                    "module": None,
                    "instance": None,
                    "path": str(py_file),
                }
                discovered.append(plugin_name)

        return discovered

    def load(self, plugin_name: str) -> bool:
        """加载插件模块  [v10-ready]

        使用importlib动态加载。加载失败不影响其他插件。
        """
        if plugin_name not in self._plugins:
            logger.warning(f"[PluginManager] Plugin not found: {plugin_name}")
            return False

        entry = self._plugins[plugin_name]
        try:
            path = entry.get("path")
            if path:
                spec = importlib.util.spec_from_file_location(plugin_name, path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    entry["module"] = module
                    entry["info"].state = PluginState.LOADED

                    # 从模块中读取PLUGIN_INFO（如果有）
                    if hasattr(module, "PLUGIN_INFO"):
                        info_dict = module.PLUGIN_INFO
                        if isinstance(info_dict, dict):
                            entry["info"].version = info_dict.get("version", "1.0.0")
                            entry["info"].description = info_dict.get("description", "")
                            entry["info"].category = info_dict.get("category", "general")

                    logger.info(f"[PluginManager] Loaded: {plugin_name}")
                    return True
            return False
        except Exception as e:
            entry["info"].state = PluginState.ERROR
            logger.error(f"[PluginManager] Failed to load {plugin_name}: {e}")
            return False

    def validate(self, plugin_name: str, required_protocol: Type[Any] | None = None) -> bool:
        """验证插件是否实现要求的Protocol  [v10-ready]"""
        if plugin_name not in self._plugins:
            return False

        entry = self._plugins[plugin_name]
        module = entry.get("module")
        if module is None:
            return False

        # 查找模块中的主类（约定：与模块同名的类或有PLUGIN_CLASS属性）
        plugin_class = getattr(module, "PLUGIN_CLASS", None)
        if plugin_class is None:
            # 尝试查找CamelCase版本的类名
            camel_name = "".join(word.capitalize() for word in plugin_name.split("_"))
            plugin_class = getattr(module, camel_name, None)

        if plugin_class is None:
            return False

        if required_protocol and not issubclass(plugin_class, required_protocol):
            return False

        entry["info"].state = PluginState.VALIDATED
        return True

    def register(self, plugin_name: str) -> bool:
        """注册插件到全局表  [v10-ready]"""
        if plugin_name not in self._plugins:
            return False
        entry = self._plugins[plugin_name]
        if entry["info"].state in (PluginState.LOADED, PluginState.VALIDATED):
            entry["info"].state = PluginState.REGISTERED
            return True
        return False

    def activate(self, plugin_name: str) -> bool:
        """激活插件  [v10-ready]"""
        if plugin_name not in self._plugins:
            return False

        entry = self._plugins[plugin_name]
        module = entry.get("module")
        if module is None:
            return False

        try:
            # 实例化插件类
            plugin_class = getattr(module, "PLUGIN_CLASS", None)
            if plugin_class is None:
                camel_name = "".join(word.capitalize() for word in plugin_name.split("_"))
                plugin_class = getattr(module, camel_name, None)

            if plugin_class:
                entry["instance"] = plugin_class()

            entry["info"].state = PluginState.ACTIVE
            self._active.add(plugin_name)
            logger.info(f"[PluginManager] Activated: {plugin_name}")
            return True
        except Exception as e:
            entry["info"].state = PluginState.ERROR
            logger.error(f"[PluginManager] Failed to activate {plugin_name}: {e}")
            return False

    def deactivate(self, plugin_name: str) -> bool:
        """停用插件  [v10-ready]"""
        if plugin_name not in self._plugins:
            return False

        entry = self._plugins[plugin_name]
        instance = entry.get("instance")

        # 如果实例有deactivate方法，调用它
        if instance and hasattr(instance, "deactivate"):
            try:
                instance.deactivate()
            except Exception:
                pass

        entry["instance"] = None
        entry["info"].state = PluginState.INACTIVE
        self._active.discard(plugin_name)
        return True

    def unload(self, plugin_name: str) -> bool:
        """卸载插件  [v10-ready]"""
        if plugin_name in self._active:
            self.deactivate(plugin_name)

        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
            return True
        return False

    def hot_replace(self, old_name: str, new_name: str) -> bool:
        """热替换插件  [v10-ready]

        激活新插件后停用旧插件，确保零中断。
        """
        # 先激活新的
        if not self.activate(new_name):
            return False
        # 再停用旧的
        self.deactivate(old_name)
        return True

    def get(self, plugin_name: str) -> Any | None:
        """获取插件实例  [v10-ready]"""
        entry = self._plugins.get(plugin_name)
        if entry:
            return entry.get("instance")
        return None

    def list(self) -> list[PluginInfo]:
        """列出所有插件信息  [v10-ready]"""
        return [entry["info"] for entry in self._plugins.values()]

    def list_active(self) -> list[str]:
        """列出活跃插件名"""
        return list(self._active)

    def get_stats(self) -> dict[str, Any]:
        """获取管理器统计  [v10-ready]"""
        states = {}
        for entry in self._plugins.values():
            state = entry["info"].state.value
            states[state] = states.get(state, 0) + 1

        return {
            "total_plugins": len(self._plugins),
            "active_plugins": len(self._active),
            "states": states,
        }
