# -*- coding: utf-8-sig -*-
"""配置 — 配置数据模型

从 config.py 拆分 (SSS-PhaseB)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from ..processors.evolution_loop import CausalPairRecorder, EvolutionLoop
    from .version import SYSTEM_IDENTITY as _VERSION_IDENTITY
    from .version import __edition__, __version__, get_version_string
except ImportError:
    _VERSION_IDENTITY = None
    __edition__ = "unknown"
    __version__ = "0.0.0"
    get_version_string = lambda: "0.0.0"
    CausalPairRecorder = None
    EvolutionLoop = None

import math
import sys

# 路径常量
AI_MEMORY_ROOT = Path(
    os.environ.get("AI_MEMORY_ROOT", str(Path(__file__).resolve().parent.parent.parent))
)
MEMORY_DATA_PATH = Path(
    os.environ.get("AI_MEMORY_DATA", str(AI_MEMORY_ROOT / "data" / ".memory"))
)
PYTHON_EXECUTABLE = AI_MEMORY_ROOT / "python" / "python.exe"


def get_python_executable() -> Path:
    if PYTHON_EXECUTABLE.exists():
        return PYTHON_EXECUTABLE
    return Path(sys.executable)


class CapacityPressureConfig:
    """容量压力权重配置 — 按存储压力而非时间衰减

    核心逻辑: 不经常使用AI时，时间流逝≠记忆衰减。
    真正的驱动力是容量压力: 层越满，低价值条目越应被驱逐/巩固。
    每个条目有"容量权重"，由访问密度+重要性+确信度决定，
    完全不含时间因子。

    与Ebbinghaus的本质区别:
      Ebbinghaus: R(t)=e^(-t/S) → 不用AI时所有记忆都衰减到0
      容量压力:   weight = density * salience * confidence → 不用AI时权重不变
    """

    # 各层容量压力系数 — 层越满，低权重条目越容易被驱逐
    pressure_coefficient_sensory: float = 0.8  # 感觉层: 高压力(快速淘汰)
    pressure_coefficient_working: float = 0.5  # 工作层: 中等压力
    pressure_coefficient_short_term: float = 0.3  # 短期层: 较低压力
    pressure_coefficient_episodic: float = 0.2  # 情景层: 低压力(保留经历)
    pressure_coefficient_semantic: float = 0.05  # 语义层: 极低压力(知识持久)
    pressure_coefficient_meta: float = 0.02  # 元枢层: 几乎无压力(策略不变)

    # 归档阈值: 容量权重低于此值时软归档
    archive_weight_threshold: float = 0.05

    def get_pressure_coefficient(self, layer: str) -> float:
        """根据层级返回容量压力系数"""
        mapping = {
            "sensory": self.pressure_coefficient_sensory,
            "working": self.pressure_coefficient_working,
            "short_term": self.pressure_coefficient_short_term,
            "episodic": self.pressure_coefficient_episodic,
            "semantic": self.pressure_coefficient_semantic,
            "meta": self.pressure_coefficient_meta,
        }
        return mapping.get(layer, 0.2)

    def compute_capacity_weight(self, entry, layer_usage_ratio: float = 0.0) -> float:
        """计算容量权重 — 纯粹基于存储状态，不含时间因子

        weight = (1 - pressure * usage) * density * salience * confidence

        - pressure: 层级压力系数(语义层几乎不压，感觉层高压)
        - usage: 当前层使用率(0~1)，层越满压力越大
        - density: 访问密度(访问次数的对数归一化)
        - salience: 重要性权重
        - confidence: 确信度
        """

        # 1. 容量压力因子: 层越满，低价值条目越容易被挤出
        pressure = self.get_pressure_coefficient(getattr(entry, "layer", "episodic"))
        pressure_factor = max(0.1, 1.0 - pressure * layer_usage_ratio)

        # 2. 访问密度: log归一化，与时间无关
        access_count = getattr(entry, "access_count", 0)
        if hasattr(entry, "metadata") and isinstance(entry.metadata, dict):
            access_count = access_count or entry.metadata.get("access_count", 0)
        density = math.log(1.0 + access_count) / math.log(1.0 + 100)  # 归一化到0~1
        density = max(density, 0.1)  # 最低0.1，新条目也有基础权重

        # 3. 重要性(salience)
        salience = 0.5
        if hasattr(entry, "metadata") and isinstance(entry.metadata, dict):
            salience = entry.metadata.get("salience", 0.5)
        priority_map = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.3}
        if hasattr(entry, "priority") and entry.priority in priority_map:
            salience = max(salience, priority_map[entry.priority])

        # 4. 确信度(confidence)
        confidence = 0.7
        if hasattr(entry, "metadata") and isinstance(entry.metadata, dict):
            confidence = entry.metadata.get("confidence", 0.7)

        weight = pressure_factor * density * salience * confidence
        return min(weight, 2.0)


@dataclass
class AccessDensityConfig:
    """访问密度配置 — 基于访问频率而非时间间隔

    核心逻辑: 记忆的"可及性"由访问次数决定，与时间无关。
    被频繁检索的记忆更重要，被从未检索的记忆可被驱逐。
    这比ACT-R的时间间隔激活更适合"不经常使用AI"的场景。

    与ACT-R的本质区别:
      ACT-R: B_i = ln(Σ t_j^(-d)) → 不用AI时所有间隔都很大，激活都低
      访问密度: density = f(access_count) → 不用AI时访问次数不变，密度不变
    """

    # 密度计算模式
    density_mode: str = "log"  # "log" | "linear" | "sqrt"
    max_access_for_normalization: int = 100  # 归一化上限
    retrieval_threshold: float = 0.1  # 密度低于此值时标记为"冷记忆"
    hot_threshold: float = 0.5  # 密度高于此值时标记为"热记忆"

    def compute_density(self, access_count: int) -> float:
        """计算访问密度 — 归一化到0~1，与时间无关"""

        if access_count <= 0:
            return 0.0
        if self.density_mode == "log":
            return math.log(1 + access_count) / math.log(
                1 + self.max_access_for_normalization
            )
        elif self.density_mode == "sqrt":
            return math.sqrt(access_count / self.max_access_for_normalization)
        else:  # linear
            return min(access_count / self.max_access_for_normalization, 1.0)

    def classify_memory(self, access_count: int) -> str:
        """分类记忆: hot/warm/cold"""
        density = self.compute_density(access_count)
        if density >= self.hot_threshold:
            return "hot"
        if density >= self.retrieval_threshold:
            return "warm"
        return "cold"


@dataclass
class MemGPTPagingConfig:
    """MemGPT虚拟上下文管理 — 分页换入换出策略

    核心思想(来自操作系统虚拟内存):
      - 上下文窗口 = RAM(稀缺、快速、直接访问)
      - 外部存储 = 磁盘(大容量、低速、按需加载)
      - 70%容量时发出eviction warning
      - 100%容量时强制flush + 递归摘要压缩

    这是纯容量驱动的，不含时间因子，完美适配"不经常使用AI"场景。

    参考: MemGPT (Packer et al., 2023), Letta (2024)
    """

    warning_threshold: float = 0.70  # 70%预警: 开始准备换出
    flush_threshold: float = 1.0  # 100%强制flush
    page_size_entries: int = 50  # 每页条目数
    summary_compression_ratio: float = 0.3  # 摘要压缩到30%
    recursive_summary_depth: int = 3  # 递归摘要深度
    enable_auto_paging: bool = True  # 自动分页开关

    def should_warn(self, usage_ratio: float) -> bool:
        return usage_ratio >= self.warning_threshold

    def should_flush(self, usage_ratio: float) -> bool:
        return usage_ratio >= self.flush_threshold


@dataclass
class InterferenceConfig:
    """干扰遗忘配置 — 相似记忆竞争 + Hebbian共检索强化

    干扰理论: 新记忆与旧记忆相似时，会产生前摄/倒摄干扰，
    导致检索困难。但频繁共检索的记忆对会通过Hebbian机制
    强化连接(一起激发的神经元连在一起)。

    注意: 此配置不含时间因子，仅基于相似度和共检索次数。

    参考: Human-Inspired Memory Architecture (Kerestecioglu et al., 2026)
    """

    similarity_threshold: float = 0.85  # 相似度>0.85视为竞争记忆
    interference_penalty: float = 0.1  # 每个竞争记忆的惩罚系数
    hebbian_learning_rate: float = 0.05  # Hebbian学习率
    hebbian_decay: float = 0.01  # Hebbian权重衰减
    max_competitors: int = 5  # 最大竞争记忆数
    enable_hebbian: bool = True  # 启用Hebbian共检索强化


@dataclass
class CapacityConsolidationConfig:
    """容量触发巩固配置 — 写入时/容量压力时触发巩固

    核心逻辑: 巩固由容量变化驱动，不是由时间驱动。
    - 写入新条目时: 如果层使用率>阈值，触发巩固
    - 容量变化量超阈值: 触发巩固
    - 访问时: 更新访问计数(用于密度计算)，不触发stability刷新

    与再巩固的本质区别:
      再巩固: 检索时刷新stability → 不用AI时stability永远不刷新
      容量巩固: 写入时/容量压力时触发 → 有写入就有巩固，与时间无关

    阈值校准(基于2026-06真实数据):
      sensory:  1597/2000=80%  → 需要敏感阈值
      episodic: 46/50=92%累积  → 需要敏感阈值
      semantic: 8436/10000=84% → 需要敏感阈值
    """

    # 写入触发巩固阈值 — 更敏感
    write_trigger_usage: float = 0.50  # 使用率>50%时写入触发巩固(原0.70)
    write_trigger_delta: float = 0.02  # 单次写入容量变化>2%时触发(原0.05)

    # 容量变化量触发 — 更敏感
    accumulation_trigger_entries: int = 20  # 累积20条新条目触发巩固(原50)
    accumulation_trigger_bytes: float = 0.05  # 累积容量增长5%触发巩固(原0.10)

    # 巩固策略
    consolidation_target_ratio: float = 0.70  # 巩固后目标使用率(原0.80)
    compression_ratio: float = 0.4  # 巩固压缩比(原0.5)
    max_consolidation_batch: int = 300  # 单次巩固最大批处理数(原200)

    def should_consolidate_on_write(
        self, usage_ratio: float, delta_ratio: float
    ) -> bool:
        """写入时是否触发巩固"""
        if usage_ratio >= self.write_trigger_usage:
            return True
        if delta_ratio >= self.write_trigger_delta:
            return True
        return False

    def should_consolidate_on_accumulation(
        self, new_entries: int, capacity_growth_ratio: float
    ) -> bool:
        """累积变化量是否触发巩固"""
        if new_entries >= self.accumulation_trigger_entries:
            return True
        if capacity_growth_ratio >= self.accumulation_trigger_bytes:
            return True
        return False


@dataclass
class MarginManagement:
    """容量变化量驱动的余量安全管理体系 — 完全消除时间管理

    核心设计原则:
      不经常使用AI时，时间流逝≠记忆衰减。
      真正的驱动力是容量压力和访问密度。

    四大容量驱动范式:
      范式1: 容量压力权重 — 层越满，低价值条目越容易被驱逐
      范式2: 访问密度 — 频繁检索的记忆更重要(与时间无关)
      范式3: MemGPT分页 — 纯容量驱动的换入换出
      范式4: 容量触发巩固 — 写入/容量压力时触发，不是时间触发

    与旧版(时间驱动)的核心区别:
      旧版: Ebbinghaus R(t)=e^(-t/S) → 不用AI时所有记忆衰减到0
      新版: weight = f(pressure, density, salience) → 不用AI时权重不变
    """

    # 四大容量驱动子配置
    capacity_pressure: CapacityPressureConfig = field(
        default_factory=CapacityPressureConfig
    )
    access_density: AccessDensityConfig = field(default_factory=AccessDensityConfig)
    memgpt: MemGPTPagingConfig = field(default_factory=MemGPTPagingConfig)
    capacity_consolidation: CapacityConsolidationConfig = field(
        default_factory=CapacityConsolidationConfig
    )

    # 干扰遗忘(不含时间因子，保留)
    interference: InterferenceConfig = field(default_factory=InterferenceConfig)

    # 容量阈值(兼容旧接口) — 更敏感
    green_threshold: float = 0.60  # 余量>60%才green(原0.50)
    yellow_threshold: float = 0.35  # 余量>35%才yellow(原0.25)
    orange_threshold: float = 0.15  # 余量>15%才orange(原0.10)
    target_margin: float = 0.20  # 目标余量20%(原0.15)
    safety_floor: float = 0.05  # 安全底线5%

    # 变化量阈值 — 更敏感
    delta_write_threshold: float = 0.03  # 写入变化量>3%拦截(原0.05)
    delta_consolidate_threshold: float = 0.05  # 巩固变化量>5%触发(原0.10)

    # ---- 容量权重计算 (核心: 纯容量驱动，零时间因子) ----

    def compute_memory_strength(self, entry, current_time: float = 0.0) -> float:
        """计算记忆强度 — 纯容量驱动，零时间因子

        strength = capacity_weight = f(pressure, density, salience, confidence)

        核心特性: 不经常使用AI时，strength不变。
        只有容量变化(写入/删除)或访问变化(检索)才会改变strength。
        """
        return self.capacity_pressure.compute_capacity_weight(entry, 0.0)

    def compute_memory_strength_with_usage(
        self, entry, layer_usage_ratio: float
    ) -> float:
        """计算记忆强度 — 含层使用率上下文

        strength = (1 - pressure * usage) * density * salience * confidence
        """
        return self.capacity_pressure.compute_capacity_weight(entry, layer_usage_ratio)

    # ---- 容量管理(兼容旧接口) ----

    def get_level(self, margin_ratio: float) -> str:
        """根据余量比返回等级"""
        if margin_ratio >= self.green_threshold:
            return "green"
        if margin_ratio >= self.yellow_threshold:
            return "yellow"
        if margin_ratio >= self.orange_threshold:
            return "orange"
        return "red"

    def should_auto_consolidate(self, margin_ratio: float) -> bool:
        """是否应触发自动固结 — 容量驱动"""
        usage_ratio = 1.0 - margin_ratio
        if self.memgpt.should_warn(usage_ratio):
            return True
        level = self.get_level(margin_ratio)
        return level in ("yellow", "orange", "red")

    def should_evict(self, margin_ratio: float) -> bool:
        """是否应触发驱逐"""
        level = self.get_level(margin_ratio)
        return level in ("orange", "red")

    def can_write(
        self, margin_ratio: float, delta_bytes: int = 0, max_bytes: int = 1
    ) -> tuple[bool, str]:
        """检查是否允许写入 — 容量变化量驱动"""
        usage_ratio = 1.0 - margin_ratio

        # MemGPT flush检查
        if self.memgpt.should_flush(usage_ratio):
            return False, "memgpt_flush_required"

        # 变化量阈值检查
        if max_bytes > 0 and delta_bytes > 0:
            delta_ratio = delta_bytes / max_bytes
            if delta_ratio > self.delta_write_threshold:
                return (
                    False,
                    f"delta_ratio={delta_ratio:.3f} exceeds {self.delta_write_threshold}",
                )

        level = self.get_level(margin_ratio)
        if level == "red":
            return False, "red_level_readonly"
        if level == "orange":
            return True, "orange_level_approved"
        return True, "ok"

    def get_consolidate_interval_multiplier(self, margin_ratio: float) -> float:
        """获取固结间隔倍率 — 容量压力越大越快"""
        usage_ratio = 1.0 - margin_ratio
        if self.memgpt.should_warn(usage_ratio):
            return 0.5
        level = self.get_level(margin_ratio)
        if level == "yellow":
            return 0.5
        if level in ("orange", "red"):
            return 0.25
        return 1.0

    def get_evict_config(self, margin_ratio: float) -> dict | None:
        """获取驱逐配置 — 按容量权重排序"""
        level = self.get_level(margin_ratio)
        if level == "orange":
            return {
                "evict_threshold": 0.3,
                "target_ratio": 0.85,
                "reason": "orange_capacity_pressure_evict",
                "sort_by": "capacity_weight",
            }
        if level == "red":
            return {
                "evict_threshold": 0.5,
                "target_ratio": 0.7,
                "reason": "red_force_evict",
                "sort_by": "capacity_weight",
            }
        return None

    def get_paging_action(self, usage_ratio: float) -> dict:
        """获取MemGPT分页动作建议 — 纯容量驱动"""
        if self.memgpt.should_flush(usage_ratio):
            pages = max(1, int(usage_ratio * 10) - 7)
            return {
                "action": "flush",
                "summary_needed": True,
                "page_count": pages,
                "compression_ratio": self.memgpt.summary_compression_ratio,
            }
        if self.memgpt.should_warn(usage_ratio):
            return {
                "action": "warn",
                "summary_needed": False,
                "page_count": 1,
                "compression_ratio": 1.0,
            }
        return {
            "action": "none",
            "summary_needed": False,
            "page_count": 0,
            "compression_ratio": 1.0,
        }


@dataclass
class MemoryLayerConfig:
    name: str
    layer_index: int
    max_size_bytes: int
    max_entries: int
    capacity_threshold: float
    accumulation_threshold_bytes: int
    accumulation_threshold_entries: int
    hard_cap_bytes: int
    min_consolidation_interval_seconds: float
    priority: str
    description: str
    margin_management: MarginManagement = field(default_factory=MarginManagement)

    @property
    def max_size_mb(self) -> float:
        return self.max_size_bytes / (1024 * 1024)

    @property
    def accumulation_threshold_mb(self) -> float:
        return self.accumulation_threshold_bytes / (1024 * 1024)

    @property
    def hard_cap_mb(self) -> float:
        return self.hard_cap_bytes / (1024 * 1024)


@dataclass
class QualityGateConfig:
    # [FIX-MCP-CONTENT-LENGTH] 降低最小内容长度限制，允许短内容写入（如测试数据）
    # 原限制: 10字符，新限制: 5字符（支持短内容写入）
    min_content_length: int = 5
    max_similarity_for_duplicate: float = 0.85
    minimum_value_score_for_direct_write: float = 0.3
    noise_patterns: list[str] = field(
        default_factory=lambda: [
            "嗯",
            "哦",
            "好",
            "行",
            "OK",
            "ok",
            "是的",
            "对",
        ]
    )
    require_tags_for_layers: list[str] = field(
        default_factory=lambda: ["episodic", "semantic", "meta"]
    )
    require_upstream_for_layers: list[str] = field(
        default_factory=lambda: ["semantic", "meta"]
    )
    auto_downgrade_noisy_to: str = "sensory"
    conflict_detection_enabled: bool = True
    max_conflict_retention: int = 5


@dataclass
class PromotionScoreWeights:
    priority_weight: float = 0.30
    effectiveness: float = 0.20
    recency: float = 0.10
    access_count: float = 0.10
    upstream_depth: float = 0.15
    connectedness: float = 0.15


@dataclass
class ICMEConfig:
    layers: list[MemoryLayerConfig] = field(
        default_factory=lambda: [
            MemoryLayerConfig(
                name="sensory",
                layer_index=0,
                max_size_bytes=10 * 1024 * 1024,
                max_entries=2000,
                capacity_threshold=0.85,
                accumulation_threshold_bytes=2 * 1024 * 1024,
                accumulation_threshold_entries=100,
                hard_cap_bytes=12 * 1024 * 1024,
                min_consolidation_interval_seconds=30.0,
                priority="low",
                description="感知记忆层 | 即时输入捕获 → working",
            ),
            MemoryLayerConfig(
                name="working",
                layer_index=1,
                max_size_bytes=50 * 1024 * 1024,
                max_entries=1000,
                capacity_threshold=0.80,
                accumulation_threshold_bytes=4 * 1024 * 1024,
                accumulation_threshold_entries=50,
                hard_cap_bytes=60 * 1024 * 1024,
                min_consolidation_interval_seconds=60.0,
                priority="medium",
                description="工作记忆层 | 会话上下文管理 → short_term",
            ),
            MemoryLayerConfig(
                name="short_term",
                layer_index=2,
                max_size_bytes=200 * 1024 * 1024,
                max_entries=5000,
                capacity_threshold=0.75,
                accumulation_threshold_bytes=2 * 1024 * 1024,
                accumulation_threshold_entries=50,
                hard_cap_bytes=250 * 1024 * 1024,
                min_consolidation_interval_seconds=120.0,
                priority="medium",
                description="短期记忆层 | 关键信息保持 → episodic",
            ),
            MemoryLayerConfig(
                name="episodic",
                layer_index=3,
                max_size_bytes=500 * 1024 * 1024,
                max_entries=5000,
                capacity_threshold=0.80,
                accumulation_threshold_bytes=10 * 1024 * 1024,
                accumulation_threshold_entries=50,
                hard_cap_bytes=600 * 1024 * 1024,
                min_consolidation_interval_seconds=300.0,
                priority="high",
                description="情景记忆层 | 决策记录/AI经验 → semantic",
            ),
            MemoryLayerConfig(
                name="semantic",
                layer_index=4,
                max_size_bytes=2 * 1024 * 1024 * 1024,
                max_entries=10000,
                capacity_threshold=0.85,
                accumulation_threshold_bytes=50 * 1024 * 1024,
                accumulation_threshold_entries=60,
                hard_cap_bytes=2500 * 1024 * 1024,
                min_consolidation_interval_seconds=600.0,
                priority="high",
                description="语义记忆层 | 知识图谱/概念关系 → meta",
            ),
            MemoryLayerConfig(
                name="meta",
                layer_index=5,
                max_size_bytes=500 * 1024 * 1024,
                max_entries=100000,
                capacity_threshold=0.90,
                accumulation_threshold_bytes=10 * 1024 * 1024,
                accumulation_threshold_entries=50,
                hard_cap_bytes=600 * 1024 * 1024,
                min_consolidation_interval_seconds=900.0,
                priority="critical",
                description="元记忆层 | 策略自优化 (顶端, 无晋升目标)",
            ),
        ]
    )

    data_path: Path = MEMORY_DATA_PATH
    auto_indexing_enabled: bool = True
    consolidation_interval_minutes: int = 5
    session_timeout_minutes: int = 60
    max_context_tokens: int = 16000
    embedding_model_name: str = "tfidf"  # 【MCP启动修复】默认TF-IDF避免网络阻塞
    embedding_cache_size: int = 5000
    embedding_dim: int = 2000  # TF-IDF维度
    ws_heartbeat_interval: int = 30
    quality_gate: QualityGateConfig = field(default_factory=QualityGateConfig)
    promotion_weights: PromotionScoreWeights = field(
        default_factory=PromotionScoreWeights
    )

    def get_layer(self, name: str) -> MemoryLayerConfig | None:
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def get_next_layer(self, current_layer_name: str) -> MemoryLayerConfig | None:
        for i, layer in enumerate(self.layers):
            if layer.name == current_layer_name and i < len(self.layers) - 1:
                return self.layers[i + 1]
        return None

    def get_prev_layer(self, current_layer_name: str) -> MemoryLayerConfig | None:
        for i, layer in enumerate(self.layers):
            if layer.name == current_layer_name and i > 0:
                return self.layers[i - 1]
        return None

    def get_layer_index(self, name: str) -> int:
        for layer in self.layers:
            if layer.name == name:
                return layer.layer_index
        return -1


DEFAULT_CONFIG = ICMEConfig()


_STORAGE_SUB_PATHS = [
    "causal_pairs",
    "evolution_history",
    "stats",
    "logs",
    "backups",
    "knowledge_graph",
    "cognition",
    "sessions",
    "queue",
    "cache",
    "embeddings",
    "audit_reports",
    "snapshots",
    "exports",
    "tmp",
]


@dataclass
class StoragePathConfig:
    root: Path = MEMORY_DATA_PATH
    sub_paths: list[str] = field(default_factory=lambda: _STORAGE_SUB_PATHS)

    def ensure(self) -> dict[str, Path]:
        created = {}
        self.root.mkdir(parents=True, exist_ok=True)
        for sub in self.sub_paths:
            p = self.root / sub
            p.mkdir(parents=True, exist_ok=True)
            created[sub] = p
        logger.info(f"[StoragePathConfig] 15个存储子路径就绪: {self.root}")
        return created

    def validate(self) -> dict[str, Any]:
        result = {
            "root": str(self.root),
            "root_readable": True,
            "root_writable": True,
            "issues": [],
            "sub_paths": {},
        }
        if not os.access(str(self.root), os.R_OK):
            result["root_readable"] = False
            result["issues"].append("root not readable")
        if not os.access(str(self.root), os.W_OK):
            result["root_writable"] = False
            result["issues"].append("root not writable")
        for sub in self.sub_paths:
            p = self.root / sub
            r, w = os.access(str(p), os.R_OK), os.access(str(p), os.W_OK)
            result["sub_paths"][sub] = {
                "exists": p.exists(),
                "readable": r,
                "writable": w,
            }
            if not r or not w:
                result["issues"].append(
                    f"{sub}: {'not readable' if not r else ''}{'not writable' if not w else ''}".strip()
                )
        return result

    def audit(self) -> dict[str, Any]:
        allowed = set(self.sub_paths)
        violations = []
        for item in self.root.iterdir():
            if item.is_file() and item.name not in allowed:
                violations.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "reason": "out of bounds file",
                    }
                )
            elif item.is_dir() and item.name not in allowed:
                violations.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "reason": "out of bounds dir",
                    }
                )
        return {
            "root": str(self.root),
            "allowed_paths": sorted(allowed),
            "violations": violations,
            "violation_count": len(violations),
            "clean": len(violations) == 0,
        }


# 协议模式开关
TIANJI_V91_PROTOCOL_MODE: bool = os.environ.get(
    "TIANJI_V91_PROTOCOL_MODE", "true"
).lower() in ("true", "1", "yes", "on")
TIANJI_V91_EVENT_WIRING: bool = os.environ.get(
    "TIANJI_V91_EVENT_WIRING", "true"
).lower() in ("true", "1", "yes", "on")


__all__ = [
    "CapacityPressureConfig",
    "AccessDensityConfig",
    "MemGPTPagingConfig",
    "InterferenceConfig",
    "CapacityConsolidationConfig",
    "MarginManagement",
    "MemoryLayerConfig",
    "QualityGateConfig",
    "PromotionScoreWeights",
    "ICMEConfig",
    "StoragePathConfig",
    "DEFAULT_CONFIG",
    "TIANJI_V91_PROTOCOL_MODE",
    "TIANJI_V91_EVENT_WIRING",
    "AI_MEMORY_ROOT",
    "MEMORY_DATA_PATH",
    "PYTHON_EXECUTABLE",
    "get_python_executable",
]
