"""
平台适配配置管理器 — 支持Trae、Qoder等多平台差异化配置

功能:
- 加载平台配置文件
- 获取平台特定配置
- 应用平台策略到对话捕获
- 支持运行时配置更新
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


class PlatformAdapterConfig:
    """平台适配配置管理器"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化平台适配配置

        Args:
            config_path: 配置文件路径，默认为 config/platform_adapter.json
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "platform_adapter.json"

        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._loaded_at: float = 0.0

        # 自动加载配置
        self.reload()

    def reload(self) -> bool:
        """
        重新加载配置文件

        Returns:
            是否加载成功
        """
        try:
            if not self.config_path.exists():
                # 创建默认配置
                self._create_default_config()

            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)

            self._loaded_at = time.time()
            return True

        except Exception as e:
            print(f"[PlatformAdapter] 配置加载失败: {e}")
            self._config = self._get_builtin_default()
            return False

    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        default_config = self._get_builtin_default()

        # 确保目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)

        print(f"[PlatformAdapter] 已创建默认配置: {self.config_path}")

    def _get_builtin_default(self) -> Dict[str, Any]:
        """获取内置默认配置"""
        return {
            "version": "1.0.0",
            "default": {
                "display_name": "Default Platform",
                "default_agent": "yiku",
                "tag_prefix": "default",
                "session_prefix": "default_session",
                "layer_strategy": {
                    "user_input": "sensory",
                    "ai_response": "working",
                    "event": "episodic",
                },
                "capture_options": {
                    "max_content_length": 10000,
                    "include_mcp_calls": False,
                    "include_file_ops": False,
                    "auto_capture": False,
                },
            },
        }

    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        """
        获取指定平台的配置

        Args:
            platform: 平台名称 (trae/qoder/default)

        Returns:
            平台配置字典
        """
        platform_key = platform.lower()

        # 查找平台配置
        if platform_key in self._config:
            return self._config[platform_key]

        # 回退到默认配置
        if "default" in self._config:
            return self._config["default"]

        # 最后回退到内置默认
        return self._get_builtin_default()["default"]

    def get(self, platform: str, key: str, default: Any = None) -> Any:
        """
        获取平台配置项

        Args:
            platform: 平台名称
            key: 配置键 (支持点号分隔的嵌套键)
            default: 默认值

        Returns:
            配置值
        """
        config = self.get_platform_config(platform)

        # 支持嵌套键访问 (如 "capture_options.max_content_length")
        keys = key.split(".")
        value = config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_layer_for_content(self, platform: str, content_type: str) -> str:
        """
        获取内容类型对应的存储层级

        Args:
            platform: 平台名称
            content_type: 内容类型 (user_input/ai_response/event)

        Returns:
            层级名称
        """
        layer_strategy = self.get(platform, "layer_strategy", {})
        return layer_strategy.get(content_type, "episodic")

    def get_tags_with_prefix(self, platform: str, tags: list) -> list:
        """
        为标签添加平台前缀

        Args:
            platform: 平台名称
            tags: 原始标签列表

        Returns:
            带前缀的标签列表
        """
        tag_prefix = self.get(platform, "tag_prefix", "")

        if tag_prefix:
            prefixed_tags = [f"{tag_prefix}:{tag}" for tag in tags]
        else:
            prefixed_tags = tags

        # 添加平台标签
        prefixed_tags.append(f"platform:{platform}")

        return prefixed_tags

    def get_session_id(self, platform: str, original_session_id: str) -> str:
        """
        生成带平台前缀的会话ID

        Args:
            platform: 平台名称
            original_session_id: 原始会话ID

        Returns:
            带前缀的会话ID
        """
        session_prefix = self.get(platform, "session_prefix", "")

        if session_prefix:
            return f"{session_prefix}_{original_session_id}"
        else:
            return original_session_id

    def should_capture(self, platform: str) -> bool:
        """
        检查平台是否启用自动捕获

        Args:
            platform: 平台名称

        Returns:
            是否启用捕获
        """
        return self.get(platform, "capture_options.auto_capture", False)

    def get_max_content_length(self, platform: str) -> int:
        """
        获取平台最大内容长度限制

        Args:
            platform: 平台名称

        Returns:
            最大长度
        """
        return self.get(platform, "capture_options.max_content_length", 10000)

    def enrich_metadata(
        self, platform: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根据平台配置丰富元数据

        Args:
            platform: 平台名称
            metadata: 原始元数据

        Returns:
            丰富后的元数据
        """
        enriched = metadata.copy()
        config = self.get_platform_config(platform)

        # 添加平台信息
        if config.get("metadata_enrichment", {}).get("add_platform_info", True):
            enriched["platform"] = platform
            enriched["platform_display_name"] = config.get("display_name", platform)

        # 添加时间戳
        if config.get("metadata_enrichment", {}).get("add_timestamp", True):
            enriched["enriched_at"] = time.time()

        return enriched

    def list_platforms(self) -> list:
        """
        列出所有已配置的平台

        Returns:
            平台名称列表
        """
        platforms = []

        for key in self._config.keys():
            if key not in ["version", "description"]:
                platforms.append(key)

        return platforms

    def get_config_summary(self) -> Dict[str, Any]:
        """
        获取配置摘要

        Returns:
            配置摘要信息
        """
        return {
            "config_path": str(self.config_path),
            "loaded_at": self._loaded_at,
            "version": self._config.get("version", "unknown"),
            "platforms": self.list_platforms(),
            "platform_count": len(self.list_platforms()),
        }


# 全局单例
_platform_adapter_config: Optional[PlatformAdapterConfig] = None


def get_platform_adapter_config() -> PlatformAdapterConfig:
    """
    获取平台适配配置单例

    Returns:
        PlatformAdapterConfig实例
    """
    global _platform_adapter_config

    if _platform_adapter_config is None:
        _platform_adapter_config = PlatformAdapterConfig()

    return _platform_adapter_config


# 便捷函数
def get_platform_config(platform: str) -> Dict[str, Any]:
    """获取平台配置"""
    return get_platform_adapter_config().get_platform_config(platform)


def get_platform_setting(platform: str, key: str, default: Any = None) -> Any:
    """获取平台设置项"""
    return get_platform_adapter_config().get(platform, key, default)
