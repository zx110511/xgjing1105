# -*- coding: utf-8-sig -*-
"""天机v10.0.1 每层独立配置体系 (CoreConfig)  [v10-ready]

P4-3: per-layer 配置体系
============================================================
为每个 MemoryCore 实例提供一份独立、可运行时 override、
可分布式同步的层级配置。

设计目标:
    1. CoreConfig          — 单层独立配置数据类 (替代裸 MemoryLayerConfig)
    2. CoreConfigRegistry  — 6 层配置注册表 (注册/获取/override/导出导入)
    3. DEFAULT_CONFIGS     — 默认 6 层配置常量 (源自 core/config.py:ICMEConfig)

分布式切换说明:
    本地模式: CoreConfigRegistry 持有进程内 6 层 CoreConfig。
    远程模式: export_config_tree()/import_config_tree() 提供配置树的
              序列化通道, 灵境侧可据此同步各节点的层级配置, 上层无感知。

向后兼容:
    本文件不修改 core/config.py。
    from_legacy() / from_icme_config() 负责从旧版 MemoryLayerConfig /
    ICMEConfig 平滑迁移, 保证 v9.1 单进程运行不受影响。

架构定位: core/memory_core/ — 六层记忆核心配置层
版本: 1.0.0
"""

from __future__ import annotations

import copy
import threading
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

try:
    from ..shared.protocols import MemoryLayer
except ImportError:  # pragma: no cover - 兼容绝对导入运行环境
    from core.shared.protocols import MemoryLayer  # type: ignore

if TYPE_CHECKING:  # 仅类型检查期引用, 运行期不强依赖, 避免循环导入
    from ..config import ICMEConfig, MemoryLayerConfig


# ============================================================================
# CoreConfig — 每层独立配置数据类
# ============================================================================


@dataclass
class CoreConfig:
    """每层独立配置  [v10-ready]

    每个 MemoryCore 实例持有一份独立的 CoreConfig,
    支持运行时 override 和分布式同步。

    本地实现: 进程内直接持有, 由 CoreConfigRegistry 统一装配。
    远程实现: 经 export_config_tree/import_config_tree 跨节点同步。

    Attributes:
        layer: 所属记忆层级 (MemoryLayer 枚举)。
        layer_index: 拓扑序 (0~5)。
        max_size_bytes: 单层容量上限 (字节)。
        max_entries: 单层条目数上限。
        capacity_threshold: 容量告急阈值 (0.0 ~ 1.0)。
        accumulation_threshold_bytes: 累积字节触发晋升阈值。
        accumulation_threshold_entries: 累积条目数触发晋升阈值。
        hard_cap_bytes: 硬上限 (字节, 0 表示不限)。
        min_consolidation_interval_seconds: 最小固结间隔 (秒)。
        priority: 优先级 (low/medium/high, 兼容 critical)。
        storage_backend: 存储后端 ('sqlite'|'json'|'tiered'|'remote')。
        description: 功能描述。
        custom_params: 自定义扩展参数。
    """

    layer: MemoryLayer
    layer_index: int = 0
    max_size_bytes: int = 10_000_000
    max_entries: int = 2000
    capacity_threshold: float = 0.8
    accumulation_threshold_bytes: int = 2_000_000
    accumulation_threshold_entries: int = 100
    hard_cap_bytes: int = 0
    min_consolidation_interval_seconds: int = 300
    priority: str = "medium"
    storage_backend: str = "sqlite"
    description: str = ""

    # 扩展配置
    custom_params: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ 派生属性
    @property
    def max_size_mb(self) -> float:
        """容量上限 (MB)  [v10-ready]"""
        return self.max_size_bytes / (1024 * 1024)

    @property
    def accumulation_threshold_mb(self) -> float:
        """累积晋升阈值 (MB)  [v10-ready]"""
        return self.accumulation_threshold_bytes / (1024 * 1024)

    @property
    def hard_cap_mb(self) -> float:
        """硬上限 (MB)  [v10-ready]"""
        return self.hard_cap_bytes / (1024 * 1024)

    # ------------------------------------------------------------------ 校验
    def validate(self) -> tuple[bool, str]:
        """验证配置合法性  [v10-ready]

        检查项:
            - layer 不为 None
            - max_size_bytes > 0
            - 0 < capacity_threshold <= 1.0
            - max_entries > 0
            - accumulation_threshold_bytes >= 0
            - hard_cap_bytes 为 0 或 >= max_size_bytes
            - storage_backend 在允许集合内

        Returns:
            (是否合法, 失败原因)。合法时原因为空字符串。
        """
        if self.layer is None:
            return False, "layer 不能为 None"
        if not isinstance(self.layer, MemoryLayer):
            return False, f"layer 必须为 MemoryLayer 枚举, 实际: {type(self.layer)!r}"
        if self.max_size_bytes <= 0:
            return False, f"max_size_bytes 必须 > 0, 实际: {self.max_size_bytes}"
        if not (0.0 < self.capacity_threshold <= 1.0):
            return False, (
                f"capacity_threshold 必须在 (0, 1.0] 区间, 实际: {self.capacity_threshold}"
            )
        if self.max_entries <= 0:
            return False, f"max_entries 必须 > 0, 实际: {self.max_entries}"
        if self.accumulation_threshold_bytes < 0:
            return False, (
                f"accumulation_threshold_bytes 不能为负, 实际: {self.accumulation_threshold_bytes}"
            )
        if self.hard_cap_bytes < 0:
            return False, f"hard_cap_bytes 不能为负, 实际: {self.hard_cap_bytes}"
        if self.hard_cap_bytes != 0 and self.hard_cap_bytes < self.max_size_bytes:
            return False, (
                f"hard_cap_bytes({self.hard_cap_bytes}) 须为 0 或 >= "
                f"max_size_bytes({self.max_size_bytes})"
            )
        allowed_backends = {"sqlite", "json", "tiered", "remote"}
        if self.storage_backend not in allowed_backends:
            return False, (
                f"storage_backend 非法: {self.storage_backend!r}, "
                f"允许: {sorted(allowed_backends)}"
            )
        return True, ""

    # ------------------------------------------------------------------ 序列化
    def to_dict(self) -> dict[str, Any]:
        """导出为可序列化字典 (分布式同步用)  [v10-ready]

        Returns:
            扁平字典, layer 以其字符串值表示。
        """
        data = asdict(self)
        data["layer"] = self.layer.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoreConfig":
        """从字典还原 CoreConfig (分布式同步用)  [v10-ready]

        Args:
            data: to_dict() 产出的字典。

        Returns:
            还原后的 CoreConfig 实例。
        """
        payload = dict(data)
        layer_value = payload.pop("layer")
        layer = (
            layer_value
            if isinstance(layer_value, MemoryLayer)
            else MemoryLayer(layer_value)
        )
        valid_keys = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in payload.items() if k in valid_keys}
        return cls(layer=layer, **kwargs)

    # ------------------------------------------------------------------ 旧版迁移
    @classmethod
    def from_legacy(cls, layer_config: "MemoryLayerConfig") -> "CoreConfig":
        """从旧版 MemoryLayerConfig 转换  [v10-ready]

        正确映射 core/config.py:MemoryLayerConfig 的全部字段,
        其中 name -> MemoryLayer 枚举, 并补齐 storage_backend 默认值。

        Args:
            layer_config: 旧版 MemoryLayerConfig 实例。

        Returns:
            等价的 CoreConfig 实例。
        """
        return cls(
            layer=MemoryLayer(layer_config.name),
            layer_index=layer_config.layer_index,
            max_size_bytes=layer_config.max_size_bytes,
            max_entries=layer_config.max_entries,
            capacity_threshold=layer_config.capacity_threshold,
            accumulation_threshold_bytes=layer_config.accumulation_threshold_bytes,
            accumulation_threshold_entries=layer_config.accumulation_threshold_entries,
            hard_cap_bytes=layer_config.hard_cap_bytes,
            min_consolidation_interval_seconds=int(
                layer_config.min_consolidation_interval_seconds
            ),
            priority=layer_config.priority,
            storage_backend="sqlite",
            description=layer_config.description,
        )


# ============================================================================
# DEFAULT_CONFIGS — 默认 6 层配置常量 (源自 core/config.py:ICMEConfig)
# ============================================================================

DEFAULT_CONFIGS: dict[MemoryLayer, CoreConfig] = {
    MemoryLayer.SENSORY: CoreConfig(
        layer=MemoryLayer.SENSORY,
        layer_index=0,
        max_size_bytes=10 * 1024 * 1024,
        max_entries=2000,
        capacity_threshold=0.85,
        accumulation_threshold_bytes=2 * 1024 * 1024,
        accumulation_threshold_entries=100,
        hard_cap_bytes=12 * 1024 * 1024,
        min_consolidation_interval_seconds=30,
        priority="low",
        storage_backend="sqlite",
        description="感知记忆层 | 即时输入捕获 → working",
    ),
    MemoryLayer.WORKING: CoreConfig(
        layer=MemoryLayer.WORKING,
        layer_index=1,
        max_size_bytes=50 * 1024 * 1024,
        max_entries=1000,
        capacity_threshold=0.80,
        accumulation_threshold_bytes=4 * 1024 * 1024,
        accumulation_threshold_entries=50,
        hard_cap_bytes=60 * 1024 * 1024,
        min_consolidation_interval_seconds=60,
        priority="medium",
        storage_backend="sqlite",
        description="工作记忆层 | 会话上下文管理 → short_term",
    ),
    MemoryLayer.SHORT_TERM: CoreConfig(
        layer=MemoryLayer.SHORT_TERM,
        layer_index=2,
        max_size_bytes=200 * 1024 * 1024,
        max_entries=5000,
        capacity_threshold=0.75,
        accumulation_threshold_bytes=2 * 1024 * 1024,
        accumulation_threshold_entries=50,
        hard_cap_bytes=250 * 1024 * 1024,
        min_consolidation_interval_seconds=120,
        priority="medium",
        storage_backend="sqlite",
        description="短期记忆层 | 关键信息保持 → episodic",
    ),
    MemoryLayer.EPISODIC: CoreConfig(
        layer=MemoryLayer.EPISODIC,
        layer_index=3,
        max_size_bytes=500 * 1024 * 1024,
        max_entries=5000,
        capacity_threshold=0.80,
        accumulation_threshold_bytes=10 * 1024 * 1024,
        accumulation_threshold_entries=50,
        hard_cap_bytes=600 * 1024 * 1024,
        min_consolidation_interval_seconds=300,
        priority="high",
        storage_backend="sqlite",
        description="情景记忆层 | 决策记录/AI经验 → semantic",
    ),
    MemoryLayer.SEMANTIC: CoreConfig(
        layer=MemoryLayer.SEMANTIC,
        layer_index=4,
        max_size_bytes=2 * 1024 * 1024 * 1024,
        max_entries=10000,
        capacity_threshold=0.85,
        accumulation_threshold_bytes=50 * 1024 * 1024,
        accumulation_threshold_entries=60,
        hard_cap_bytes=2500 * 1024 * 1024,
        min_consolidation_interval_seconds=600,
        priority="high",
        storage_backend="sqlite",
        description="语义记忆层 | 知识图谱/概念关系 → meta",
    ),
    MemoryLayer.META: CoreConfig(
        layer=MemoryLayer.META,
        layer_index=5,
        max_size_bytes=500 * 1024 * 1024,
        max_entries=100000,
        capacity_threshold=0.90,
        accumulation_threshold_bytes=10 * 1024 * 1024,
        accumulation_threshold_entries=50,
        hard_cap_bytes=600 * 1024 * 1024,
        min_consolidation_interval_seconds=900,
        priority="critical",
        storage_backend="sqlite",
        description="元记忆层 | 策略自优化 (顶端, 无晋升目标)",
    ),
}


# ============================================================================
# CoreConfigRegistry — 配置注册表
# ============================================================================


class CoreConfigRegistry:
    """配置注册表  [v10-ready]

    管理全部 6 层的 CoreConfig, 线程安全。支持:
        - 注册/获取单层配置
        - 运行时 override 单个参数 (并记录原值以支持 reset)
        - 导出/导入配置树 (分布式同步预留)
        - 从旧版 ICMEConfig 批量迁移

    本地实现: 进程内 dict + threading.Lock 守护。
    远程实现: export_config_tree/import_config_tree 作为灵境节点间
              配置同步的序列化契约。
    """

    def __init__(self) -> None:
        """初始化空注册表  [v10-ready]"""
        self._configs: dict[MemoryLayer, CoreConfig] = {}
        # 记录每层被 override 前的原始基线, 供 reset 还原
        self._baselines: dict[MemoryLayer, CoreConfig] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ 基本操作
    def register(self, layer: MemoryLayer, config: CoreConfig) -> None:
        """注册单层配置  [v10-ready]

        Args:
            layer: 目标记忆层级。
            config: 该层的 CoreConfig (其 layer 字段须与 layer 一致)。

        Raises:
            ValueError: 配置非法或 layer 不一致。
        """
        if config.layer != layer:
            raise ValueError(
                f"config.layer({config.layer}) 与注册 layer({layer}) 不一致"
            )
        ok, reason = config.validate()
        if not ok:
            raise ValueError(f"非法 CoreConfig: {reason}")
        with self._lock:
            self._configs[layer] = config
            self._baselines[layer] = copy.deepcopy(config)

    def get(self, layer: MemoryLayer) -> CoreConfig:
        """获取单层配置  [v10-ready]

        Args:
            layer: 目标记忆层级。

        Returns:
            该层 CoreConfig。

        Raises:
            KeyError: 该层未注册。
        """
        with self._lock:
            if layer not in self._configs:
                raise KeyError(f"层级未注册: {layer}")
            return self._configs[layer]

    def has(self, layer: MemoryLayer) -> bool:
        """判断某层是否已注册  [v10-ready]"""
        with self._lock:
            return layer in self._configs

    def all_configs(self) -> dict[MemoryLayer, CoreConfig]:
        """获取全部层配置的浅拷贝映射  [v10-ready]"""
        with self._lock:
            return dict(self._configs)

    # ------------------------------------------------------------------ 运行时 override
    def override(self, layer: MemoryLayer, key: str, value: Any) -> None:
        """运行时 override 单个参数  [v10-ready]

        修改指定层配置的某个字段, 修改后立即校验合法性。

        Args:
            layer: 目标记忆层级。
            key: 待修改的字段名。
            value: 新值。

        Raises:
            KeyError: 该层未注册。
            AttributeError: 字段不存在。
            ValueError: 修改后配置非法 (已自动回滚)。
        """
        with self._lock:
            if layer not in self._configs:
                raise KeyError(f"层级未注册: {layer}")
            config = self._configs[layer]
            if not hasattr(config, key):
                raise AttributeError(f"CoreConfig 无字段: {key}")
            old_value = getattr(config, key)
            setattr(config, key, value)
            ok, reason = config.validate()
            if not ok:
                setattr(config, key, old_value)  # 回滚
                raise ValueError(f"override 后配置非法, 已回滚: {reason}")

    def reset(self, layer: MemoryLayer) -> None:
        """重置某层配置到注册基线  [v10-ready]

        Args:
            layer: 目标记忆层级。

        Raises:
            KeyError: 该层未注册或无基线。
        """
        with self._lock:
            if layer not in self._baselines:
                raise KeyError(f"层级无基线可重置: {layer}")
            self._configs[layer] = copy.deepcopy(self._baselines[layer])

    # ------------------------------------------------------------------ 配置树导出导入
    def export_config_tree(self) -> dict:
        """导出配置树 (分布式同步预留)  [v10-ready]

        Returns:
            形如 {"version": ..., "layers": {layer_value: config_dict}} 的字典,
            可直接 JSON 序列化用于跨节点同步。
        """
        with self._lock:
            return {
                "version": "1.0.0",
                "layer_count": len(self._configs),
                "layers": {
                    layer.value: config.to_dict()
                    for layer, config in self._configs.items()
                },
            }

    def import_config_tree(self, tree: dict) -> None:
        """从配置树导入 (分布式同步预留)  [v10-ready]

        覆盖式导入: 每层配置经 validate 后注册并刷新基线。

        Args:
            tree: export_config_tree() 产出的字典。

        Raises:
            ValueError: 配置树结构非法或含非法层配置。
        """
        layers = tree.get("layers")
        if not isinstance(layers, dict):
            raise ValueError("配置树缺少合法的 'layers' 字段")
        parsed: dict[MemoryLayer, CoreConfig] = {}
        for layer_value, config_dict in layers.items():
            layer = MemoryLayer(layer_value)
            config = CoreConfig.from_dict(config_dict)
            if config.layer != layer:
                raise ValueError(
                    f"配置树层级不一致: key={layer_value}, config.layer={config.layer}"
                )
            ok, reason = config.validate()
            if not ok:
                raise ValueError(f"配置树含非法层配置 [{layer_value}]: {reason}")
            parsed[layer] = config
        with self._lock:
            for layer, config in parsed.items():
                self._configs[layer] = config
                self._baselines[layer] = copy.deepcopy(config)

    # ------------------------------------------------------------------ 工厂方法
    @classmethod
    def from_icme_config(cls, icme_config: "ICMEConfig") -> "CoreConfigRegistry":
        """从现有 ICMEConfig 批量创建  [v10-ready]

        遍历 ICMEConfig.layers, 逐层经 CoreConfig.from_legacy 转换并注册,
        正确映射全部字段, 不修改源 ICMEConfig。

        Args:
            icme_config: 旧版 ICMEConfig 实例。

        Returns:
            装配完成的 CoreConfigRegistry。
        """
        registry = cls()
        for layer_config in icme_config.layers:
            core_config = CoreConfig.from_legacy(layer_config)
            registry.register(core_config.layer, core_config)
        return registry

    @classmethod
    def create_default(cls) -> "CoreConfigRegistry":
        """创建默认 6 层配置  [v10-ready]

        基于 DEFAULT_CONFIGS 深拷贝装配, 避免外部修改污染常量。

        Returns:
            含默认 6 层配置的 CoreConfigRegistry。
        """
        registry = cls()
        for layer, config in DEFAULT_CONFIGS.items():
            registry.register(layer, copy.deepcopy(config))
        return registry


__all__ = [
    "CoreConfig",
    "CoreConfigRegistry",
    "DEFAULT_CONFIGS",
]
