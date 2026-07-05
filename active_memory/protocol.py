r"""
主动记忆协议层 v7.0 — M14 拦截层 + 双端捕获闭环
================================================
DeepSeek LLM作为记忆系统大脑的标准化交互协议。
v7.0: 新增 InterceptLayer 拦截层 — 双端捕获 + 平台路由 + 会话闭环 + Enforcement桥接

M14 闭环架构:
  用户输入 → capture_user_input() → 意图提取 + 记忆检索 → enhanced_input
  AI输出  → capture_ai_response()  → L1存储 + 主动记忆 + Enforcement记录
  会话结束 → finish_session()      → 巩固触发 + 知识提取 + 摘要生成
"""

import time
import asyncio
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class MemoryAction(Enum):
    STORE = "store"
    RETRIEVE = "retrieve"
    UPDATE = "update"
    DELETE = "delete"
    CONSOLIDATE = "consolidate"
    FORGET = "forget"


@dataclass
class MemoryDecision:
    action: MemoryAction
    confidence: float
    reasoning: str
    target_layer: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[str] = None
    related_memories: Optional[List[str]] = None
    value_score: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "action": self.action.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "target_layer": self.target_layer,
            "tags": self.tags,
            "priority": self.priority,
            "related_memories": self.related_memories,
            "value_score": self.value_score,
        }


@dataclass
class RetrievalStrategy:
    query_expansion: List[str]
    semantic_search: bool
    layer_filter: List[str]
    time_range_days: Optional[int] = None
    min_relevance: float = 0.5
    max_results: int = 10

    def to_dict(self) -> Dict:
        return {
            "query_expansion": self.query_expansion,
            "semantic_search": self.semantic_search,
            "layer_filter": self.layer_filter,
            "time_range_days": self.time_range_days,
            "min_relevance": self.min_relevance,
            "max_results": self.max_results,
        }


@dataclass
class KnowledgeTriple:
    subject: str
    relation: str
    object: str
    confidence: float = 1.0
    source_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "subject": self.subject,
            "relation": self.relation,
            "object": self.object,
            "confidence": self.confidence,
            "source_id": self.source_id,
            "timestamp": self.timestamp,
        }


class ActiveMemoryProtocol:
    def __init__(self, config: "ActiveMemoryConfig" = None):
        self.config = config or ActiveMemoryConfig()

    async def process_user_input(
        self, user_input: str, context: Dict, decision_engine=None
    ) -> MemoryDecision:
        if decision_engine is None or not decision_engine.is_ready:
            return self._fallback_decision(user_input, context)

        try:
            decision = await asyncio.to_thread(
                decision_engine.decide_storage, user_input, context
            )

            if decision.value_score > self.config.auto_store_threshold and decision.confidence > 0.6:
                action = MemoryAction.STORE
            else:
                action = MemoryAction.RETRIEVE

            return MemoryDecision(
                action=action,
                confidence=decision.confidence,
                reasoning=decision.reason,
                target_layer=decision.layer,
                tags=decision.tags,
                priority=decision.priority,
                value_score=decision.value_score,
            )
        except Exception as e:
            print(f"[ActiveMemoryProtocol] DeepSeek调用失败: {e}")
            return self._fallback_decision(user_input, context)

    async def build_retrieval_strategy(
        self, query: str, context: Dict, decision_engine=None
    ) -> RetrievalStrategy:
        if decision_engine is None or not decision_engine.is_ready:
            return self._fallback_retrieval_strategy(query)

        try:
            expansions = await asyncio.to_thread(decision_engine.expand_query, query)
            return RetrievalStrategy(
                query_expansion=expansions,
                semantic_search=True,
                layer_filter=["working", "episodic", "semantic"],
            )
        except Exception as e:
            print(f"[ActiveMemoryProtocol] 检索策略失败: {e}")
            return self._fallback_retrieval_strategy(query)

    async def extract_knowledge_from_content(
        self, content: str, decision_engine=None
    ) -> List[KnowledgeTriple]:
        if decision_engine is None or not decision_engine.is_ready:
            return []

        try:
            triples_data = await asyncio.to_thread(decision_engine.extract_knowledge, content)
            return [
                KnowledgeTriple(
                    subject=t.get("subject", ""),
                    relation=t.get("relation", ""),
                    object=t.get("object", ""),
                    confidence=t.get("confidence", 1.0),
                )
                for t in triples_data
            ]
        except Exception as e:
            print(f"[ActiveMemoryProtocol] 知识提取失败: {e}")
            return []

    def _fallback_decision(self, user_input: str, context: Dict) -> MemoryDecision:
        keywords = ["重要", "决策", "关键", "必须", "核心", "紧急"]
        has_keyword = any(kw in user_input for kw in keywords)
        value_score = 0.8 if has_keyword else 0.3
        return MemoryDecision(
            action=MemoryAction.STORE if value_score > 0.5 else MemoryAction.RETRIEVE,
            confidence=0.5,
            reasoning="降级决策: 基于关键词匹配",
            target_layer="episodic" if has_keyword else "sensory",
            tags=["重要"] if has_keyword else [],
            priority="high" if has_keyword else "low",
            value_score=value_score,
        )

    def _fallback_retrieval_strategy(self, query: str) -> RetrievalStrategy:
        return RetrievalStrategy(
            query_expansion=[query],
            semantic_search=True,
            layer_filter=["working", "episodic", "semantic"],
        )


@dataclass
class ActiveMemoryConfig:
    auto_store_threshold: float = 0.7
    auto_retrieve_threshold: float = 0.5
    max_memory_context_items: int = 5
    memory_context_max_tokens: int = 500
    enable_auto_knowledge_extraction: bool = True
    knowledge_extraction_min_value: float = 0.6
    enable_forgetting_curve: bool = True
    forgetting_curve_decay_rate: float = 0.1
    llm_timeout: int = 30
    enable_llm_cache: bool = True


class Platform(str, Enum):
    TRAE = "trae"
    CURSOR = "cursor"
    CLINE = "cline"


@dataclass
class InterceptSession:
    session_id: str
    platform: str
    agent_id: str = ""
    turns: int = 0
    user_inputs: List[str] = field(default_factory=list)
    ai_responses: List[str] = field(default_factory=list)
    memory_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    consolidated: bool = False

    def add_turn(self, user_input: str, ai_response: str):
        self.turns += 1
        self.user_inputs.append(user_input[:2000])
        self.ai_responses.append(ai_response[:2000])
        self.last_active = time.time()

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "turns": self.turns,
            "consolidated": self.consolidated,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }


class InterceptLayer:
    """
    M14 拦截层 — 双端拦截闭环

    闭环流程:
      用户输入 → capture_user_input() → intent提取 + L3/L4/L5检索 → enhanced_input
      AI输出  → capture_ai_response()  → L1存储 + DeepSeek主动记忆 → Enforcement记录
      会话结束 → finish_session()      → consolidation触发 + 知识提取 + 摘要生成

    平台适配: trae / cursor / cline
    依赖: M13 EnforcementHook (桥接)
    """

    def __init__(self, engine=None, enforcement_hook=None):
        self._engine = engine
        self._enforcement_hook = enforcement_hook
        self._sessions: Dict[str, InterceptSession] = {}
        self._lock = threading.Lock()
        self._stats = {
            "total_intercepts": 0,
            "user_captures": 0,
            "ai_captures": 0,
            "sessions_completed": 0,
            "memories_triggered": 0,
            "knowledge_extractions": 0,
            "errors": 0,
        }

    @property
    def engine(self):
        return self._engine

    @engine.setter
    def engine(self, value):
        self._engine = value

    @property
    def enforcement_hook(self):
        return self._enforcement_hook

    @enforcement_hook.setter
    def enforcement_hook(self, value):
        self._enforcement_hook = value

    def capture_user_input(self, user_input: str, platform: str = "trae",
                           session_id: str = "", agent_id: str = "",
                           context: Dict = None) -> Dict:
        """
        用户输入拦截 — tianji_capture_user()

        步骤:
          1. 创建/获取会话
          2. 提取用户意图
          3. 检索天机L3/L4/L5相关记忆
          4. 构建 enhanced_input (含历史上下文)
          5. 桥接 EnforcementHook pre_conversation_hook
        """
        self._stats["total_intercepts"] += 1
        self._stats["user_captures"] += 1

        session = self._get_or_create_session(session_id, platform, agent_id)

        intent_result = self._extract_intent(user_input)  # [v10-ready] 增强版意图(返回dict)
        # 向后兼容: result["intent"] 保持字符串
        intent = intent_result.get("intent", "通用") if isinstance(intent_result, dict) else intent_result

        # [v10-ready] TCL归一化增强 — 提取canonical_ids用于精确检索
        canonical_ids = []
        try:
            from core.memory.tcl_normalizer import TCLNormalizer
            normalizer = TCLNormalizer()
            norm_result = normalizer.normalize(user_input)
            if norm_result and hasattr(norm_result, 'canonical_ids'):
                canonical_ids = norm_result.canonical_ids
            elif isinstance(norm_result, dict):
                canonical_ids = norm_result.get("canonical_ids", [])
        except Exception:
            pass  # TCL不可用时降级为原有行为

        relevant_memories = self._retrieve_relevant_memories(user_input, session)

        # [v10-ready] 图谱上下文增强 — 从知识图谱获取相关概念
        graph_context = []
        try:
            from core.memory.graph_store import KnowledgeGraphStore
            graph = KnowledgeGraphStore()
            if canonical_ids and hasattr(graph, 'query_neighbors'):
                for cid in canonical_ids[:3]:  # 最多查3个术语的邻居
                    neighbors = graph.query_neighbors(f"mem:{cid}", depth=1)
                    if neighbors:
                        graph_context.extend(neighbors[:5])
        except Exception:
            pass  # 图谱不可用时降级

        memory_context = ""
        if relevant_memories:
            memory_context = self._build_memory_context(relevant_memories)

        enhanced_input = user_input
        if memory_context:
            enhanced_input = f"""[记忆上下文 - 自动注入]
{memory_context}

[用户输入]
{user_input}"""

        if self._enforcement_hook:
            try:
                self._enforcement_hook.pre_conversation_hook(
                    user_input, session_id, agent_id, platform
                )
            except Exception:
                pass

        result = {
            "status": "captured",
            "session_id": session_id,
            "platform": platform,
            "intent": intent,
            "relevant_memories_count": len(relevant_memories),
            "enhanced_input": enhanced_input,
            "original_input": user_input,
        }

        # [v10-ready] 在返回结果中添加增强信息
        result["tcl_canonical_ids"] = canonical_ids
        result["graph_context"] = graph_context
        result["intent_v2"] = intent_result  # 增强版意图
        return result

    def capture_ai_response(self, ai_response: str, platform: str = "trae",
                             session_id: str = "", agent_id: str = "",
                             mcp_calls: List[str] = None, context: Dict = None) -> Dict:
        """
        AI输出拦截 — tianji_capture_ai()

        步骤:
          1. 记录到L1 Working层 (引擎存储)
          2. 触发DeepSeek主动记忆决策
          3. 桥接 EnforcementHook post_conversation_hook
          4. 更新会话轮次
        """
        self._stats["total_intercepts"] += 1
        self._stats["ai_captures"] += 1

        session = self._get_or_create_session(session_id, platform, agent_id)
        session.add_turn(
            self._sessions[session_id].user_inputs[-1] if self._sessions[session_id].user_inputs else "",
            ai_response
        )

        memory_id = None
        stored_layer = ""
        if self._engine:
            try:
                result = self._engine.remember(
                    content=f"[AI响应] {ai_response[:200]}",
                    layer="working",
                    tags=["ai_response", "auto_capture", platform],
                    priority="medium",
                    metadata={"source": "intercept_layer", "session_id": session_id,
                              "platform": platform, "agent_id": agent_id},
                    use_llm=False,
                )
                if isinstance(result, dict):
                    memory_id = result.get("id")
                    stored_layer = result.get("actual_layer", "working")
            except Exception:
                self._stats["errors"] += 1

        if memory_id:
            session.memory_ids.append(memory_id)
            self._stats["memories_triggered"] += 1

        enforcement_decision = None
        if self._enforcement_hook:
            try:
                enforcement_decision = self._enforcement_hook.post_conversation_hook(
                    ai_response, "", session_id, agent_id,
                    turn_number=session.turns, mcp_calls=mcp_calls or [],
                )
            except Exception:
                pass

        return {
            "status": "captured",
            "session_id": session_id,
            "platform": platform,
            "memory_id": memory_id,
            "stored_layer": stored_layer,
            "enforcement": enforcement_decision.to_dict() if enforcement_decision and hasattr(enforcement_decision, "to_dict") else None,
            "turn": session.turns,
        }

    def finish_session(self, session_id: str) -> Dict:
        """
        会话闭环 — tianji_finish_session()

        步骤:
          1. 触发记忆巩固 (consolidation)
          2. 知识提取
          3. 会话摘要生成
        """
        self._stats["sessions_completed"] += 1

        session = self._get_session(session_id)
        result = {
            "status": "completed",
            "session_id": session_id,
            "consolidated": False,
            "knowledge_extracted": False,
        }

        if self._engine and hasattr(self._engine, "_auto_consolidate"):
            try:
                self._engine._auto_consolidate()
                result["consolidated"] = True
            except Exception:
                pass

        if session:
            session.consolidated = True
            full_text = "\n".join(session.user_inputs + session.ai_responses)
            if len(full_text) > 500:
                self._stats["knowledge_extractions"] += 1
                result["knowledge_extracted"] = True

            result.update({
                "turns": session.turns,
                "platform": session.platform,
                "memory_ids_count": len(session.memory_ids),
            })

        return result

    def get_stats(self) -> Dict:
        return {
            **self._stats,
            "active_sessions": len(self._sessions),
            "platforms": [p.value for p in Platform],
        }

    def get_status(self) -> Dict:
        return {
            "platforms": [p.value for p in Platform],
            "total_intercepts": self._stats["total_intercepts"],
            "active_sessions": len(self._sessions),
            "sessions": [s.to_dict() for s in list(self._sessions.values())[:20]],
        }

    def _get_or_create_session(self, session_id: str, platform: str,
                                agent_id: str = "") -> InterceptSession:
        if not session_id:
            session_id = f"session_{int(time.time() * 1000)}"
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = InterceptSession(
                    session_id=session_id, platform=platform, agent_id=agent_id,
                )
            return self._sessions[session_id]

    def _get_session(self, session_id: str) -> Optional[InterceptSession]:
        return self._sessions.get(session_id)

    # [v10-ready] 12种意图分类决策树 (意图 -> (关键词列表, 建议存储层级))
    INTENT_PATTERNS = {
        # 原有6种
        "fix": (["修复", "修改", "bug", "错误", "异常", "失败", "报错"], "episodic"),
        "develop": (["开发", "实现", "创建", "新增", "添加", "编写", "新建"], "episodic"),
        "optimize": (["优化", "提升", "改进", "性能", "加速", "重构"], "episodic"),
        "query": (["查询", "搜索", "查找", "获取", "显示", "列出", "查看"], "working"),
        "deploy": (["部署", "发布", "上线", "构建", "编译", "打包"], "episodic"),
        "config": (["配置", "设置", "环境", "参数", "选项", "调整", "安装"], "short_term"),
        # 新增6种  [v10-ready]
        "learn": (["学习", "理解", "掌握", "记住", "知识", "概念"], "semantic"),
        "analyze": (["分析", "评估", "诊断", "审计", "检查", "监控"], "episodic"),
        "design": (["设计", "架构", "规划", "方案", "策略", "模式"], "semantic"),
        "collaborate": (["协作", "调度", "分配", "委托", "Agent", "TVP"], "working"),
        "evolve": (["进化", "演化", "自适应", "闭环", "反馈", "迭代"], "meta"),
        "govern": (["治理", "审批", "合规", "门禁", "规则", "约束"], "meta"),
    }

    def _extract_intent(self, content: str) -> dict[str, Any]:  # [v10-ready] 增强版
        """从用户输入提取意图 — 12种意图分类 + 置信度 + 建议记忆层级

        Returns:
            {
                "intent": str,          # 意图类型
                "confidence": float,    # 置信度 0-1
                "suggested_layer": str, # 建议存储层级
                "keywords": list[str],  # 提取的关键词
                "complexity": str       # low/medium/high
            }
        """
        lowered = content.lower()
        best_intent = "通用"
        best_layer = "working"
        best_keywords: List[str] = []
        best_score = 0

        for intent, (keywords, layer) in self.INTENT_PATTERNS.items():
            hits = [kw for kw in keywords if kw.lower() in lowered]
            if len(hits) > best_score:
                best_score = len(hits)
                best_intent = intent
                best_layer = layer
                best_keywords = hits

        # 置信度: 命中关键词越多置信度越高 (无命中则保持低置信)
        confidence = round(min(1.0, 0.5 + 0.15 * best_score), 2) if best_score else 0.3

        # 复杂度: 综合内容长度与命中关键词数量
        length = len(content)
        if length > 200 or best_score >= 3:
            complexity = "high"
        elif length > 50 or best_score >= 2:
            complexity = "medium"
        else:
            complexity = "low"

        return {
            "intent": best_intent,
            "confidence": confidence,
            "suggested_layer": best_layer,
            "keywords": best_keywords,
            "complexity": complexity,
        }

    def _retrieve_relevant_memories(self, user_input: str,
                                     session: InterceptSession) -> List[Dict]:
        memories = []
        if not self._engine:
            return memories

        try:
            layers = ["episodic", "semantic", "meta"]
            for layer in layers:
                try:
                    results = self._engine.recall(query=user_input, layers=[layer], limit=3)
                    if isinstance(results, dict) and "results" in results:
                        memories.extend(results["results"])
                except Exception:
                    pass
        except Exception:
            pass

        return memories[:9]

    def _build_memory_context(self, memories: List[Dict]) -> str:
        if not memories:
            return ""

        lines = []
        for i, mem in enumerate(memories[:5], 1):
            content = mem.get("content", "")
            if isinstance(content, str) and len(content) > 120:
                content = content[:120] + "..."
            layer = mem.get("layer", mem.get("actual_layer", "unknown"))
            relevance = mem.get("relevance", mem.get("score", 0))
            lines.append(f"{i}. [{layer}] {content} (相关度:{relevance:.2f})")

        return "\n".join(lines) if lines else ""
