# -*- coding: utf-8-sig -*-
"""DeepSeek LLM策略插件 — DeepSeekLLMStrategy  [v10-ready]

将 core/llm_bridge.py 的 LLM 桥接能力提取为可插拔的 ILLMStrategy 实现。
本策略是 v9.1 单进程下唯一的本地 LLM 实现，包装 DeepSeekClient +
MemoryDecisionEngine，提供统一、降级友好、线程安全的同步 LLM 调用接口。

实现的 Protocol: core.shared.protocols.ILLMStrategy
    - classify(content, context)        内容分类
    - extract_knowledge(content)        知识提取
    - generate_summary(content, max_len) 生成摘要
    - expand_query(query)               查询扩展

设计原则 (与原 LLMBridge 一致):
    - 同步封装: engine 是同步的，内部决策引擎已做 async->sync 封装
    - 降级友好: DeepSeek 不可用 (无 api_key / 包缺失 / 异常) 时所有方法
      返回合理空结果而非抛异常
    - 零阻塞感知: 底层调用异常统一吞掉并回退，超时由 DeepSeekClient 保护
    - 线程安全: 使用 threading.RLock 保护共享统计状态

分布式切换:
    单进程  -> DeepSeekLLMStrategy (本文件)
    分布式  -> RemoteLLMStrategy (core/llm/remote_stub.py, 灵境多模型网关)

架构定位: core/llm/ LLM策略子包 — 本地默认策略
版本: 1.0.0
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Optional

# LLM统计计数器持久化文件 (P0-1: 重启不丢失累计值)
# core/llm/ -> ../../ = 天机v9.1 根目录 -> data/.memory/
LLM_STATS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", ".memory", "llm_stats_counters.json"
)

# 需持久化的累计计数器键 (start_time/last_call_time 为会话级, 不持久化)
_PERSIST_KEYS = (
    "total_calls",
    "successful_calls",
    "failed_calls",
    "fallback_calls",
    "summarize_ops",
    "expand_ops",
    "token_input",
    "token_output",
    "total_tokens",
)

# DeepSeek 外部依赖 — 包裹 try/except 以支持不可用时的降级运行
try:
    from llm_integration.client import DeepSeekClient, DeepSeekConfig
    from llm_integration.decision_engine import MemoryDecisionEngine

    _DEEPSEEK_AVAILABLE = True
except Exception:  # pragma: no cover - 依赖缺失时的降级分支
    DeepSeekClient = None  # type: ignore[assignment,misc]
    DeepSeekConfig = None  # type: ignore[assignment,misc]
    MemoryDecisionEngine = None  # type: ignore[assignment,misc]
    _DEEPSEEK_AVAILABLE = False

from core.shared.plugin_interface import PluginInfo

from .classification import ClassificationEngine
from .knowledge_extraction import KnowledgeExtractionEngine


class DeepSeekLLMStrategy:
    """DeepSeek LLM 策略 (本地默认实现)。  [v10-ready]

    实现 ILLMStrategy 全部 4 个方法，并额外暴露原 LLMBridge 使用的
    LLM 原语 (classify_content/auto_tag/assess_value/decide_storage/
    summarize 等)，供兼容层瘦身委托。
    """

    def __init__(
        self,
        config: Optional[Any] = None,
        recorder: Optional[Any] = None,
        learning_engine: Optional[Any] = None,
    ):
        """初始化 DeepSeek LLM 策略。

        Args:
            config: 可选 DeepSeekConfig；为 None 时从环境变量加载。
            recorder: 可选行为记录器 (透传给决策引擎)。
            learning_engine: 可选学习引擎 (透传给决策引擎)。
        """
        self._lock = threading.RLock()
        self._config: Optional[Any] = None
        self._client: Optional[Any] = None
        self._engine: Optional[Any] = None
        self._ready = False
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "fallback_calls": 0,
            "summarize_ops": 0,
            "expand_ops": 0,
            "token_input": 0,
            "token_output": 0,
            "total_tokens": 0,
            "last_call_time": 0.0,
            "start_time": time.time(),
        }
        # P0-1: 持久化恢复 — total_calls 等累计值重启不丢失
        self._persist_every = 5
        self._dirty_count = 0
        # token 基线 (= 历史累计), 当前进程 token = 基线 + client会话token
        self._token_baseline = {"input": 0, "output": 0, "total": 0}
        self._load_persisted_stats()

        self._init(config)

        # 能力子引擎 (engine 为 None 时自动进入降级模式)
        self._classification = ClassificationEngine(self._engine)
        self._knowledge = KnowledgeExtractionEngine(self._engine)

    def _load_persisted_stats(self) -> None:
        """从JSON恢复关键计数器, 避免重启丢失 (P0-1)。"""
        try:
            if not os.path.exists(LLM_STATS_FILE):
                return
            with open(LLM_STATS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k in _PERSIST_KEYS:
                v = saved.get(k)
                if isinstance(v, (int, float)):
                    self._stats[k] = v
            # token 字段作为基线, 后续叠加本进程 client 会话用量
            self._token_baseline = {
                "input": self._stats.get("token_input", 0),
                "output": self._stats.get("token_output", 0),
                "total": self._stats.get("total_tokens", 0),
            }
        except Exception:
            pass

    def _persist_stats(self) -> None:
        """将关键计数器写入JSON持久化 (P0-1)。"""
        try:
            os.makedirs(os.path.dirname(LLM_STATS_FILE), exist_ok=True)
            with self._lock:
                data = {
                    k: self._stats[k]
                    for k in _PERSIST_KEYS
                    if isinstance(self._stats.get(k), (int, float))
                }
            data["_updated_at"] = time.time()
            with open(LLM_STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _mark_dirty(self) -> None:
        """标记统计已变更, 每 N 次落盘一次以减少IO (P0-1)。"""
        self._dirty_count += 1
        if self._dirty_count >= self._persist_every:
            self._dirty_count = 0
            self._persist_stats()

    def _sync_token_stats(self) -> None:
        """从底层 DeepSeekClient 同步本会话 token 用量 (基线+会话, 真实计数)。"""
        session = {"input": 0, "output": 0, "total": 0}
        try:
            client_tokens = getattr(self._client, "token_stats", None)
            if isinstance(client_tokens, dict):
                session = client_tokens
        except Exception:
            pass
        with self._lock:
            self._stats["token_input"] = self._token_baseline["input"] + int(
                session.get("input", 0)
            )
            self._stats["token_output"] = self._token_baseline["output"] + int(
                session.get("output", 0)
            )
            self._stats["total_tokens"] = (
                self._stats["token_input"] + self._stats["token_output"]
            )

    def _init(self, config: Optional[Any]) -> None:
        """初始化底层 DeepSeek 客户端与决策引擎 (降级友好)。"""
        if not _DEEPSEEK_AVAILABLE:
            return
        try:
            self._config = config or DeepSeekConfig.from_env()
            if not getattr(self._config, "api_key", ""):
                return
            self._client = DeepSeekClient(self._config)
            self._engine = MemoryDecisionEngine(
                self._client,
                recorder=self._recorder,
                learning_engine=self._learning_engine,
            )
            self._ready = True
        except Exception:
            self._client = None
            self._engine = None
            self._ready = False

    @property
    def is_ready(self) -> bool:
        """DeepSeek 是否就绪可用。  [v10-ready]"""
        return self._ready

    def _safe_call(self, fn, *args, **kwargs) -> Any:
        """带统计的安全调用包装 — 异常时回退 None。  [v10-ready]"""
        with self._lock:
            self._stats["total_calls"] += 1
            self._stats["last_call_time"] = time.time()
        try:
            result = fn(*args, **kwargs)
            with self._lock:
                self._stats["successful_calls"] += 1
            self._mark_dirty()
            return result
        except Exception:
            with self._lock:
                self._stats["failed_calls"] += 1
                self._stats["fallback_calls"] += 1
            self._mark_dirty()
            return None

    # ------------------------------------------------------------------
    # ILLMStrategy 接口实现 (4 个方法)
    # ------------------------------------------------------------------

    def classify(self, content: str, context: Optional[dict] = None) -> dict[str, Any]:
        """内容分类。  [v10-ready]

        Args:
            content: 待分类内容文本。
            context: 内容上下文字典。

        Returns:
            分类结果字典；降级时返回安全默认值。
        """
        return self._classification.classify(content, context)

    def extract_knowledge(self, content: str) -> list[dict[str, Any]]:
        """知识提取。  [v10-ready]

        Args:
            content: 待提取内容文本。

        Returns:
            知识三元组字典列表；降级时返回空列表。
        """
        return self._knowledge.extract_knowledge(content)

    def generate_summary(self, content: str, max_len: int = 200) -> str:
        """生成摘要。  [v10-ready]

        Args:
            content: 待摘要内容文本。
            max_len: 摘要最大长度。

        Returns:
            摘要文本；降级时返回内容截断。
        """
        with self._lock:
            self._stats["summarize_ops"] += 1
        if not self._ready or self._engine is None:
            return content[:max_len]
        result = self._safe_call(self._engine.summarize, content, max_len)
        return result if isinstance(result, str) else content[:max_len]

    def expand_query(self, query: str) -> list[str]:
        """查询扩展。  [v10-ready]

        Args:
            query: 原始查询文本。

        Returns:
            扩展查询列表 (含原始查询)；降级时返回 [query]。
        """
        with self._lock:
            self._stats["expand_ops"] += 1
        if not self._ready or self._engine is None:
            return [query]
        result = self._safe_call(self._engine.expand_query, query)
        return result if isinstance(result, list) else [query]

    # ------------------------------------------------------------------
    # LLM 原语 (供兼容层 LLMBridge 委托)
    # ------------------------------------------------------------------

    def classify_content(
        self, content: str, context: Optional[dict] = None
    ) -> Optional[Any]:
        """判定记忆层级 — 返回 ClassificationResult。  [v10-ready]"""
        return self._classification.classify_content(content, context)

    def auto_tag(self, content: str) -> list[str]:
        """自动生成标签。  [v10-ready]"""
        return self._classification.auto_tag(content)

    def assess_value(self, content: str) -> float:
        """评估记忆价值 0.0-1.0。  [v10-ready]"""
        return self._classification.assess_value(content)

    def decide_storage(
        self, content: str, context: Optional[dict] = None
    ) -> Optional[Any]:
        """综合存储策略决策 — 返回 StorageDecision。  [v10-ready]"""
        # [FIX-COUNTER-AUDIT] decide_storage内部调用引擎层summarize(当content>200字符)
        # (见llm_integration/decision_engine.py:420)，但不会触发generate_summary计数器。
        # 修复: 当content>200时同步bump summarize_ops，准确反映摘要操作实际发生次数。
        if len(content) > 200:
            with self._lock:
                self._stats["summarize_ops"] += 1
        return self._classification.decide_storage(content, context)

    def summarize(self, content: str, max_length: int = 200) -> str:
        """生成摘要 (generate_summary 别名, 兼容原 LLMBridge)。  [v10-ready]"""
        return self.generate_summary(content, max_length)

    # ------------------------------------------------------------------
    # 健康/统计
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """获取策略健康状态。  [v10-ready]"""
        with self._lock:
            return {
                "status": "ready" if self._ready else "not_ready",
                "version": "1.0.0",
                "is_ready": self._ready,
                "deepseek_available": _DEEPSEEK_AVAILABLE,
                "total_calls": self._stats["total_calls"],
                "successful_calls": self._stats["successful_calls"],
                "failed_calls": self._stats["failed_calls"],
                "fallback_calls": self._stats["fallback_calls"],
            }

    def get_stats(self) -> dict[str, Any]:
        """获取策略统计。  [v10-ready]"""
        self._sync_token_stats()
        with self._lock:
            base = {
                "version": "1.0.0",
                "status": "ready" if self._ready else "not_ready",
                "is_ready": self._ready,
                **self._stats,
            }
        base["classification"] = self._classification.get_stats()
        base["knowledge"] = self._knowledge.get_stats()
        # 读取时落盘一次, 保证最新累计值持久化
        self._persist_stats()
        return base


# ============================================================================
# 插件注册元信息 (PluginManager 发现)
# ============================================================================

PLUGIN_INFO = PluginInfo(
    name="deepseek_llm",
    version="1.0.0",
    description="DeepSeek LLM策略",
    category="llm",
    protocols=["ILLMStrategy"],
)
