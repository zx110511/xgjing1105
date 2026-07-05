# -*- coding: utf-8-sig -*-
"""
天机v9.1 → CherryClaw 全量记忆接入适配器
========================================
将天机ICME六层记忆系统全量接入CherryClaw Agent，
实现完整记忆流水线: 感知捕获 → 工作记忆 → 短期暂存 → 情景记录 → 语义提炼 → 元认知优化。

架构路径:
    CherryClaw Agent (本适配器)
        ↕ 直接注入
    天机ICMEEngine (六层编排)
        ├── MemoryWriter     → remember / batch / 质量门禁 / 资产注册
        ├── PromotionEngine  → consolidate / promotion_score / 自动固结
        ├── ArchiveManager   → forget / 驱逐 / size tracking
        ├── MemoryIndex      → recall / 评分 / tag 索引
        └── v9.1增强能力
            ├── TemporalRecord    → 双时态戳记忆
            ├── CascadeInvalidator → 级联失效
            └── DualProcessConsolidator → 双过程固结

设计原则:
    - 直接注入ICMEEngine，零HTTP开销
    - 六层自动路由: 根据内容类型自动分派到合适层级
    - DeepSeek LLM桥接: 智能分层 + 自动标签 + 价值评估
    - QualityGate: 高质量写入门禁
    - 自进化: Evolution Loop 持续优化配置

使用方式:
    from adapters.cherryclaw_adapter import CherryClawAdapter

    adapter = CherryClawAdapter(data_path="D:\\元初系统\\天机v9.1\\data\\.memory")
    adapter.start()

    # 写入记忆
    adapter.remember("用户偏好日本語で応答すること", layer="working", tags=["preference", "language"])

    # 检索记忆
    results = adapter.recall("用户喜欢什么语言")

    # 获取状态
    stats = adapter.get_full_status()

版本: v10-ready
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("tianji.cherryclaw")

# ═══════════════════════════════════════════════════════════════════════════
# 数据类型定义
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class CherryClawMemoryEntry:
    """CherryClaw兼容的记忆条目"""
    id: str
    content: str
    layer: str
    tags: list[str] = field(default_factory=list)
    priority: str = "medium"
    value_score: float = 0.5
    access_count: int = 0
    created_at: float = 0.0
    last_accessed: float = 0.0
    size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    related_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "layer": self.layer,
            "tags": self.tags,
            "priority": self.priority,
            "value_score": round(self.value_score, 4),
            "access_count": self.access_count,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "size_bytes": self.size_bytes,
            "metadata": self.metadata,
            "related_ids": self.related_ids,
        }


@dataclass
class CherryClawMemoryStats:
    """记忆系统统计信息"""
    total_entries: int = 0
    total_accesses: int = 0
    total_consolidations: int = 0
    total_archivals: int = 0
    total_rejected: int = 0
    total_downgraded: int = 0
    total_conflicts: int = 0
    total_recall_calls: int = 0
    total_recall_hits: int = 0
    layers: dict[str, dict] = field(default_factory=dict)
    uptime_seconds: float = 0.0
    engine_health: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_entries": self.total_entries,
            "total_accesses": self.total_accesses,
            "total_consolidations": self.total_consolidations,
            "total_archivals": self.total_archivals,
            "total_rejected": self.total_rejected,
            "total_downgraded": self.total_downgraded,
            "total_conflicts": self.total_conflicts,
            "total_recall_calls": self.total_recall_calls,
            "total_recall_hits": self.total_recall_hits,
            "layers": self.layers,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "engine_health": self.engine_health,
        }


# ═══════════════════════════════════════════════════════════════════════════
# CherryClaw 适配器主类
# ═══════════════════════════════════════════════════════════════════════════

class CherryClawAdapter:
    """CherryClaw ← 天机v9.1 全量记忆桥接适配器  [v10-ready]

    将天机ICME六层记忆系统(含v9.1增强组件)无缝接入CherryClaw Agent。

    核心能力:
        - remember: 六层智能分层写入 (LLM增强 + QualityGate + 资产注册)
        - recall: 多维度检索 (标签/关键词/LLM语义重排)
        - consolidate: 触发层级晋升流水线
        - forget: 软删除+归档
        - get_full_status: 全量记忆系统健康报告
        - capture_conversation: 全量对话捕获→感官层
        - temporal_record: 双时态戳记录创建与查询
        - cascade_invalidate: 级联失效传播
        - dual_process_consolidation: 双过程固结

    Attributes:
        _engine: ICMEEngine实例 (六层编排核心)
        _config: ICMEConfig配置
        _dual_consolidator: DualProcessConsolidator (v9.1双过程固结器)
        _invalidator: CascadeInvalidator (v9.1级联失效器)
    """

    # ────────────────────────────────────────────────────────────────
    # 六层路由映射: CherryClaw操作 → ICME层级
    # ────────────────────────────────────────────────────────────────
    LAYER_SENSORY = "sensory"       # L0 感枢 - 原始对话捕获
    LAYER_WORKING = "working"       # L1 运枢 - 当前会话上下文
    LAYER_SHORT_TERM = "short_term" # L2 近枢 - 短期关键信息
    LAYER_EPISODIC = "episodic"     # L3 忆枢 - 决策记录/经历
    LAYER_SEMANTIC = "semantic"     # L4 知枢 - 知识/概念关系
    LAYER_META = "meta"             # L5 元枢 - 策略/元认知

    # 内容类型 → 推荐层级的路由表
    CONTENT_ROUTING = {
        "conversation": "sensory",
        "user_message": "sensory",
        "ai_response": "sensory",
        "context": "working",
        "note": "short_term",
        "decision": "episodic",
        "experience": "episodic",
        "knowledge": "semantic",
        "rule": "meta",
        "preference": "semantic",
        "strategy": "meta",
        "fact": "semantic",
        "instruction": "working",
    }

    def __init__(
        self,
        data_path: str | None = None,
        auto_start: bool = True,
        enable_llm: bool = True,
        enable_quality_gate: bool = True,
        enable_dual_process: bool = True,
        enable_cascade_invalidation: bool = True,
        protocol_mode: bool = False,
    ) -> None:
        """初始化CherryClaw天机适配器  [v10-ready]

        Args:
            data_path: 天机数据目录路径 (None时使用默认值)
            auto_start: 是否自动启动记忆系统
            enable_llm: 是否启用LLM增强 (DeepSeek驱动)
            enable_quality_gate: 是否启用质量门禁
            enable_dual_process: 是否启用双过程固结器 (v9.1)
            enable_cascade_invalidation: 是否启级联失效 (v9.1)
            protocol_mode: 是否启用v9.1 Protocol模式 (MemoryCore委派)
        """
        self._data_path = Path(data_path) if data_path else None
        self._enable_llm = enable_llm
        self._enable_quality_gate = enable_quality_gate
        self._enable_dual_process = enable_dual_process
        self._enable_cascade_invalidation = enable_cascade_invalidation
        self._protocol_mode = protocol_mode

        self._engine: Any = None
        self._config: Any = None
        self._dual_consolidator: Any = None
        self._invalidator: Any = None
        self._event_bus: Any = None
        self._started: bool = False
        self._start_time: float = 0.0
        self._lock = threading.RLock()

        if auto_start:
            self.start()

    # ═══════════════════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════════════════

    def start(self) -> bool:
        """启动天机记忆系统  [v10-ready]

        Returns:
            bool: 启动是否成功
        """
        if self._started:
            logger.info("天机记忆系统已在运行中")
            return True

        try:
            import sys
            from pathlib import Path as _Path

            # 添加天机项目路径到sys.path
            tianji_root = _Path(__file__).resolve().parent.parent
            if str(tianji_root) not in sys.path:
                sys.path.insert(0, str(tianji_root))

            # 导入核心组件
            from core.shared.config import DEFAULT_CONFIG, ICMEConfig
            from core.memory.engine import ICMEEngine

            # 解析数据路径
            if self._data_path is None:
                self._data_path = _Path(tianji_root) / "data" / ".memory"
            self._data_path = _Path(self._data_path)

            # 构建配置
            config = ICMEConfig() if hasattr(ICMEConfig, '__init__') and ICMEConfig.__init__.__code__.co_argcount <= 1 else None
            if config is None:
                config = DEFAULT_CONFIG

            # 确保协议模式标志
            try:
                from core.shared.config import TIANJI_V91_PROTOCOL_MODE
                import core.config as _cfg
                if self._protocol_mode:
                    _cfg.TIANJI_V91_PROTOCOL_MODE = True
            except Exception:
                pass

            # 构建依赖注入
            dependencies: dict[str, Any] = {}

            # LLM桥接 (DeepSeek驱动)
            if self._enable_llm:
                try:
                    from core.shared.llm_bridge import LLMBridge
                    dependencies["llm_bridge"] = LLMBridge()
                except Exception as e:
                    logger.warning(f"LLMBridge初始化失败: {e}")

            # 质量门禁
            if self._enable_quality_gate:
                try:
                    from core.processors.quality_gate import QualityGate
                    dependencies["quality_gate"] = QualityGate()
                except Exception as e:
                    logger.warning(f"QualityGate初始化失败: {e}")

            # 创建ICME引擎 (编排层)
            self._engine = ICMEEngine(config=config, dependencies=dependencies)
            # FIX: 强制关闭protocol_mode以使用真实MemoryIndex检索
            # Protocol模式下的MemoryCores为空且不会降级，导致recall返回空
            self._engine._protocol_mode = False
            self._config = config
            self._started = True
            self._start_time = time.time()

            # v9.1增强: 双过程固结器
            if self._enable_dual_process:
                self._init_dual_process_consolidator()

            # v9.1增强: 级联失效器
            if self._enable_cascade_invalidation:
                self._init_cascade_invalidator()

            # 事件总线
            try:
                from core.shared.deepseek_driver import EventBus
                self._event_bus = EventBus()
            except Exception:
                pass

            logger.info(
                "天机v9.1记忆系统启动成功 | 数据路径=%s | LLM=%s | QualityGate=%s | "
                "DualProcess=%s | CascadeInvalidation=%s | Protocol=%s",
                self._data_path,
                self._enable_llm,
                self._enable_quality_gate,
                self._enable_dual_process,
                self._enable_cascade_invalidation,
                self._protocol_mode,
            )
            return True

        except Exception as e:
            logger.error(f"天机记忆系统启动失败: {e}", exc_info=True)
            self._started = False
            return False

    def stop(self) -> None:
        """停止天机记忆系统"""
        self._started = False
        self._engine = None
        logger.info("天机记忆系统已停止")

    def _init_dual_process_consolidator(self) -> None:
        """初始化双过程固结器 (v9.1增强)"""
        try:
            from core.memory.dual_process import (
                ConsolidationConfig,
                DualProcessConsolidator,
            )
            from core.memory_core import (
                EpisodicCore,
                SemanticCore,
            )

            episodic = EpisodicCore() if hasattr(EpisodicCore, '__init__') else None
            semantic = SemanticCore() if hasattr(SemanticCore, '__init__') else None

            self._dual_consolidator = DualProcessConsolidator(
                episodic_core=episodic,
                semantic_core=semantic,
                llm_driver=None,  # 将在后续注入DeepSeek
                gate=None,
                event_bus=self._event_bus,
                config=ConsolidationConfig(),
            )
            logger.info("DualProcessConsolidator (双过程固结器) 初始化成功")
        except Exception as e:
            logger.warning(f"DualProcessConsolidator初始化失败: {e}")
            self._dual_consolidator = None

    def _init_cascade_invalidator(self) -> None:
        """初始化级联失效器 (v9.1增强)"""
        try:
            from core.memory.cascade_invalidator import CascadeInvalidator

            self._invalidator = CascadeInvalidator(
                graph=None,  # Phase 4-2注入图存储
                event_bus=self._event_bus,
                llm_driver=None,
                max_depth=10,
                max_affected=100,
            )
            logger.info("CascadeInvalidator (级联失效器) 初始化成功")
        except Exception as e:
            logger.warning(f"CascadeInvalidator初始化失败: {e}")
            self._invalidator = None

    # ═══════════════════════════════════════════════════════════════════
    # 核心记忆操作
    # ═══════════════════════════════════════════════════════════════════

    def remember(
        self,
        content: str,
        layer: str | None = None,
        tags: list[str] | None = None,
        priority: str = "medium",
        metadata: dict[str, Any] | None = None,
        use_llm: bool = True,
        auto_route: bool = True,
    ) -> dict:
        """写入记忆到ICME六层系统  [v10-ready]

        Args:
            content: 记忆内容
            layer: 目标层级 (None时自动路由)
            tags: 标签列表
            priority: 优先级 (critical/high/medium/low)
            metadata: 元数据 (session_id, source等)
            use_llm: 是否启用LLM增强智能分层和标签
            auto_route: 是否自动路由到合适层级

        Returns:
            dict: {id, status, actual_layer, size_bytes, llm_enriched, ...}
        """
        if not self._started or self._engine is None:
            return {"id": None, "status": "not_started", "reason": "engine not started"}

        with self._lock:
            # 自动路由: 根据metadata中的content_type选择层级
            if auto_route and (layer is None or layer == "working"):
                actual_layer = self._route_layer(metadata or {}, layer or "working")
            else:
                actual_layer = layer or "working"

            result = self._engine.remember(
                content=content,
                layer=actual_layer,
                tags=tags or [],
                priority=priority,
                metadata=metadata or {},
                use_llm=use_llm and self._enable_llm,
            )

            # 发布事件
            if self._event_bus and result.get("id"):
                try:
                    from core.shared.deepseek_driver import EventType, TianjiEvent
                    self._event_bus.publish(TianjiEvent(
                        event_type=EventType.MEMORY_STORED,
                        source="cherryclaw",
                        payload={"memory_id": result["id"], "layer": actual_layer},
                        timestamp=time.time(),
                    ))
                except Exception:
                    pass

            return result

    def remember_conversation_turn(
        self,
        user_message: str,
        ai_response: str,
        session_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        """捕获一轮完整对话 - 双写入到感官层和工作层  [v10-ready]

        对话同时写入:
        - L0 sensory (感枢): 原始对话文本，供后续提炼
        - L1 working (运枢): 结构化上下文，供当前检索

        Args:
            user_message: 用户消息
            ai_response: AI响应
            session_id: 会话ID
            tags: 标签
            metadata: 元数据

        Returns:
            dict: {sensory_result, working_result, turn_summary}
        """
        if not self._started or self._engine is None:
            return {"status": "not_started"}

        turn_metadata = {
            **(metadata or {}),
            "session_id": session_id or f"cc-{int(time.time())}",
            "content_type": "conversation",
            "source": "cherryclaw",
            "turn_timestamp": time.time(),
        }

        # L0 感官层: 完整对话文本
        sensory_content = f"[用户]: {user_message}\n[AI]: {ai_response}"
        sensory_result = self.remember(
            content=sensory_content,
            layer="sensory",
            tags=["conversation", "cherryclaw", *(tags or [])],
            priority="medium",
            metadata=turn_metadata,
        )

        # L1 工作层: 结构化摘要
        working_content = json.dumps(
            {
                "user_intent": user_message[:200],
                "ai_response_type": (
                    "answer" if len(ai_response) < 500 else "discussion"
                ),
                "timestamp": time.time(),
                "session_id": turn_metadata["session_id"],
            },
            ensure_ascii=False,
        )
        working_result = self.remember(
            content=working_content,
            layer="working",
            tags=["working_context", "cherryclaw", *(tags or [])],
            priority="high",
            metadata=turn_metadata,
        )

        return {
            "sensory_result": sensory_result,
            "working_result": working_result,
            "session_id": turn_metadata["session_id"],
        }

    def recall(
        self,
        query: str | None = None,
        layers: list[str] | None = None,
        tags: list[str] | None = None,
        priority: list[str] | None = None,
        limit: int = 20,
        min_score: float = 0.1,
        include_related: bool = True,
        include_archived: bool = False,
        use_llm: bool = True,
    ) -> list[CherryClawMemoryEntry]:
        """多维度检索记忆  [v10-ready]

        检索策略:
        1. 标签索引快速筛选
        2. 关键词/内容匹配评分
        3. LLM语义重排 (可选)
        4. 关联记忆扩展

        Args:
            query: 查询文本
            layers: 搜索层级范围 (None=全部)
            tags: 标签过滤
            priority: 优先级过滤
            limit: 返回上限
            min_score: 最低评分阈值
            include_related: 是否包含关联记忆
            include_archived: 是否包含归档记忆
            use_llm: 是否启用LLM重排

        Returns:
            list[CherryClawMemoryEntry]: 检索结果
        """
        if not self._started or self._engine is None:
            return []

        with self._lock:
            entries = self._engine.recall(
                query=query,
                layers=layers,
                tags=tags,
                priority=priority,
                limit=limit,
                min_score=min_score,
                include_related=include_related,
                include_archived=include_archived,
                use_llm=use_llm and self._enable_llm,
            )

            return [
                CherryClawMemoryEntry(
                    id=e.id,
                    content=e.content,
                    layer=e.layer,
                    tags=e.tags,
                    priority=e.priority,
                    value_score=e.value_score(),
                    access_count=e.access_count,
                    created_at=e.created_at,
                    last_accessed=e.last_accessed,
                    size_bytes=e.size_bytes,
                    metadata=e.metadata,
                    related_ids=e.related_ids,
                )
                for e in entries
            ]

    def forget(self, entry_id: str) -> bool:
        """删除记忆 (软删除→归档)  [v10-ready]"""
        if not self._started or self._engine is None:
            return False
        with self._lock:
            return self._engine.forget(entry_id)

    def consolidate(
        self,
        from_layer: str,
        to_layer: str | None = None,
        threshold: float = 0.6,
        max_entries: int = 50,
    ) -> dict:
        """触发层级晋升固结  [v10-ready]

        Args:
            from_layer: 源层级
            to_layer: 目标层级 (None=自动推断)
            threshold: 晋升评分阈值
            max_entries: 单批最大晋升数

        Returns:
            dict: {status, from_layer, to_layer, consolidated, ...}
        """
        if not self._started or self._engine is None:
            return {"status": "not_started", "consolidated": 0}

        with self._lock:
            return self._engine.consolidate_batch(
                from_layer=from_layer,
                to_layer=to_layer,
                threshold=threshold,
                max_entries=max_entries,
            )

    def consolidate_all(self, threshold: float = 0.6) -> dict:
        """逐层全部晋升  [v10-ready]"""
        if not self._started or self._engine is None:
            return {"status": "not_started", "total_consolidated": 0}

        with self._lock:
            return self._engine.consolidate_all_layers(threshold=threshold)

    def purge_layer(self, layer_name: str) -> int:
        """清空指定记忆层  [v10-ready]"""
        if not self._started or self._engine is None:
            return 0
        with self._lock:
            return self._engine.purge_layer(layer_name)

    # ═══════════════════════════════════════════════════════════════════
    # v9.1 时序记忆能力
    # ═══════════════════════════════════════════════════════════════════

    def create_temporal_record(
        self,
        content: str,
        layer: str = "working",
        tags: list[str] | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        confidence: float = 1.0,
        source: str = "cherryclaw",
        **kwargs,
    ) -> dict | None:
        """创建带双时态戳的时序记忆记录  [v10-ready]

        Args:
            content: 记忆内容
            layer: 层级
            tags: 标签
            valid_from: 有效起始时间
            valid_to: 有效截止时间 (None=永久有效)
            confidence: 置信度
            source: 来源

        Returns:
            dict: 时序记录字典 或 None
        """
        try:
            from core.memory.temporal_record import create_temporal_record

            record = create_temporal_record(
                content=content,
                layer=layer,
                tags=tags or [],
                confidence=confidence,
                source=source,
                valid_from=valid_from or datetime.now(),
                valid_to=valid_to,
                metadata=kwargs.get("metadata", {}),
            )
            return record.model_dump() if hasattr(record, "model_dump") else record.dict()
        except Exception as e:
            logger.warning(f"创建时序记录失败: {e}")
            return None

    def invalidate_temporal_record(
        self, record_id: str, reason: str
    ) -> list[str] | None:
        """级联失效时序记录  [v10-ready]

        失效指定记录并通过依赖图级联传播到所有下游记录。

        Args:
            record_id: 待失效记录ID
            reason: 失效原因

        Returns:
            list[str]: 所有受影响的记录ID列表
        """
        if not self._invalidator:
            return None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import asyncio as _asyncio
                return _asyncio.run_coroutine_threadsafe(
                    self._invalidator.invalidate(record_id, reason), loop
                ).result(timeout=30)
            else:
                return asyncio.run(self._invalidator.invalidate(record_id, reason))
        except Exception as e:
            logger.warning(f"级联失效失败: {e}")
            return None

    def run_dual_process_consolidation(
        self, since: datetime | None = None, batch_size: int = 50
    ) -> dict | None:
        """执行双过程固结 (L3 Episodic → L4 Semantic)  [v10-ready]

        DeepSeek驱动的System1(快)/System2(慢)双过程知识提炼。

        Returns:
            dict: ConsolidationReport
        """
        if not self._dual_consolidator:
            return None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import asyncio as _asyncio
                report = _asyncio.run_coroutine_threadsafe(
                    self._dual_consolidator.consolidate(since, batch_size), loop
                ).result(timeout=300)
            else:
                report = asyncio.run(
                    self._dual_consolidator.consolidate(since, batch_size)
                )
            return report.to_dict() if hasattr(report, "to_dict") else report
        except Exception as e:
            logger.warning(f"双过程固结失败: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════
    # 状态与诊断
    # ═══════════════════════════════════════════════════════════════════

    def get_full_status(self) -> CherryClawMemoryStats:
        """获取全量记忆系统状态  [v10-ready]

        Returns:
            CherryClawMemoryStats: 完整统计信息
        """
        if not self._started or self._engine is None:
            return CherryClawMemoryStats()

        with self._lock:
            layer_info = {}
            try:
                layer_info = self._engine.get_layer_capacity_info()
            except Exception:
                pass

            health = {}
            try:
                health = self._engine._get_engine_health()
            except Exception:
                pass

            stats = self._engine._stats

            return CherryClawMemoryStats(
                total_entries=stats.get("total_entries", 0),
                total_accesses=stats.get("total_accesses", 0),
                total_consolidations=stats.get("total_consolidations", 0),
                total_archivals=stats.get("total_archivals", 0),
                total_rejected=stats.get("total_rejected", 0),
                total_downgraded=stats.get("total_downgraded", 0),
                total_conflicts=stats.get("total_conflicts", 0),
                total_recall_calls=stats.get("total_recall_calls", 0),
                total_recall_hits=stats.get("total_recall_hits", 0),
                layers=layer_info,
                uptime_seconds=time.time() - self._start_time,
                engine_health=health,
            )

    def get_consolidation_candidates(
        self, layer: str = "", threshold: float = 0.5
    ) -> list[dict]:
        """获取晋升候选列表"""
        if not self._started or self._engine is None:
            return []
        return self._engine.get_consolidation_candidates(layer, threshold)

    def health_check(self) -> dict[str, bool]:
        """健康检查"""
        return {
            "started": self._started,
            "engine_ok": self._engine is not None,
            "llm_enabled": self._enable_llm,
            "quality_gate_enabled": self._enable_quality_gate,
            "dual_process_enabled": self._dual_consolidator is not None,
            "cascade_invalidation_enabled": self._invalidator is not None,
            "protocol_mode": self._protocol_mode,
            "data_path": str(self._data_path) if self._data_path else None,
        }

    def get_layer_summary(self) -> dict:
        """获取六层简要统计"""
        if not self._started or self._engine is None:
            return {}
        summary = {}
        layers_order = ["sensory", "working", "short_term", "episodic", "semantic", "meta"]
        for layer_name in layers_order:
            if layer_name in self._engine._layers:
                entries = self._engine._layers[layer_name]
                size = self._engine._layer_sizes.get(layer_name, 0)
                summary[layer_name] = {
                    "count": len(entries),
                    "size_bytes": size,
                    "size_mb": round(size / (1024 * 1024), 2),
                }
        return summary

    # ═══════════════════════════════════════════════════════════════════
    # 内部辅助
    # ═══════════════════════════════════════════════════════════════════

    def _route_layer(
        self, metadata: dict[str, Any], default: str = "working"
    ) -> str:
        """根据metadata中的content_type自动路由到合适层级"""
        content_type = metadata.get("content_type", "").lower()
        if content_type in self.CONTENT_ROUTING:
            return self.CONTENT_ROUTING[content_type]

        source = metadata.get("source", "").lower()
        if source in ("trae_capture", "conversation", "chat"):
            return "sensory"
        if source in ("decision", "audit", "governance"):
            return "episodic"

        return default

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def engine(self):
        return self._engine

    @property
    def data_path(self) -> Path | None:
        return self._data_path
