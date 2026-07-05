r"""
DeepSeek记忆决策引擎 v9.1
==========================
DeepSeek LLM 作为 天机v9.1唯一大脑，驱动全部记忆管理决策。

M33升级: EvolutionLoop闭环 + record_action喂入 + health()/get_stats() + 双注入
灵境道谱溯源: D8-2【三元提取煞】· 道八·知识体 · 四地煞之知之术
  - LLM驱动的关系三元组提取 + 模式匹配 + 合并去重
  - 源文件: llm_integration/decision_engine.py → MemoryDecisionEngine

功能:
- classify_layer: 自动判定记忆应存储到哪一层
- auto_tag: 自动生成标签
- assess_value: 评估记忆价值 0-1
- extract_knowledge: 提取知识三元组
- summarize: 记忆摘要
- decide_strategy: 综合存储策略决策
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .client import DeepSeekClient, DeepSeekConfig

logger = logging.getLogger("tianji.decision_engine")

try:
    from core.processors.evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None


SYSTEM_PROMPT = """你是元初天机v9.1的认知核心大脑。你的职责是主动管理记忆的全生命周期。

记忆层级体系（ICME六层）:
- sensory(L0): 感知记忆 — 原始输入快照（对话消息、事件记录），24小时内有效
- working(L1): 工作记忆 — 当前会话上下文，跨轮次保持
- short_term(L2): 短期记忆 — 近几天关键信息，修复记录、测试验证
- episodic(L3): 情景记忆 — 决策记录、项目事件、里程碑
- semantic(L4): 语义记忆 — 知识图谱、概念定义、长期知识
- meta(L5): 元记忆 — 策略规则、SOP、系统自优化

优先级: critical > high > medium > low

你必须始终返回有效的JSON格式，不要包含markdown代码块外的内容。"""


@dataclass
class ClassificationResult:
    layer: str
    tags: List[str]
    priority: str
    value_score: float
    reason: str
    related_concepts: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "tags": self.tags,
            "priority": self.priority,
            "value_score": self.value_score,
            "reason": self.reason,
            "related_concepts": self.related_concepts,
            "confidence": self.confidence,
        }


@dataclass
class StorageDecision:
    should_store: bool
    layer: str
    tags: List[str]
    priority: str
    value_score: float
    confidence: float
    reason: str
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "should_store": self.should_store,
            "layer": self.layer,
            "tags": self.tags,
            "priority": self.priority,
            "value_score": self.value_score,
            "confidence": self.confidence,
            "reason": self.reason,
            "summary": self.summary,
        }


class MemoryDecisionEngine:
    def __init__(
        self,
        client: Optional[DeepSeekClient] = None,
        config: Optional[DeepSeekConfig] = None,
        recorder: Optional[Any] = None,
        learning_engine: Optional[Any] = None,
    ):
        self.client = client or DeepSeekClient(config)
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._stats = {
            "classify_calls": 0,
            "auto_tag_calls": 0,
            "assess_calls": 0,
            "extract_calls": 0,
            "summarize_calls": 0,
            "decide_calls": 0,
            "expand_calls": 0,
            "relevance_calls": 0,
            "errors": 0,
            "triples_extracted": 0,
            "last_call_time": 0.0,
        }
        self._errors = 0

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="decision_engine",
                    effectiveness_fn=self._calc_engine_effectiveness,
                    learn_fn=self._learn_from_decisions,
                    evolve_fn=self._evolve_decision_params,
                    mutable_config={
                        "min_value_score_for_store": 0.2,
                        "semantic_meta_threshold": 0.5,
                        "extract_min_chars": 10,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception as e:
                logger.warning(f"DecisionEngine EvolutionLoop init failed: {e}")

    @property
    def is_ready(self) -> bool:
        return self.client.is_ready

    def classify_layer(
        self, content: str, context: Optional[Dict] = None
    ) -> ClassificationResult:
        self._stats["classify_calls"] += 1
        self._stats["last_call_time"] = time.time()
        try:
            result = self._do_classify(content, context)
            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="classify_layer",
                        state_before={
                            "classify_calls": self._stats["classify_calls"] - 1
                        },
                        state_after={
                            "classify_calls": self._stats["classify_calls"],
                            "layer": result.layer,
                            "value_score": result.value_score,
                        },
                    )
                except Exception:
                    pass
            return result
        except Exception:
            self._stats["errors"] += 1
            self._errors += 1
            raise

    def _do_classify(
        self, content: str, context: Optional[Dict] = None
    ) -> ClassificationResult:
        prompt = f"""请分析以下内容，决定其应存储到的记忆层级:

内容:
{content[:3000]}

{"上下文: " + json.dumps(context, ensure_ascii=False) if context else ""}

请判定:
1. layer: 应存储到哪一层? (sensory/working/short_term/episodic/semantic/meta)
2. tags: 3-5个标签
3. priority: 优先级 (critical/high/medium/low)
4. value_score: 价值评分 0.0-1.0
5. reason: 判定理由 (一句话)
6. related_concepts: 2-5个相关概念

返回JSON:
{{"layer": "episodic", "tags": ["决策", "架构", "项目"], "priority": "high", "value_score": 0.85, "reason": "包含关键架构决策", "related_concepts": ["FastAPI", "微服务", "后端架构"]}}"""

        result = self.client.chat_sync(prompt, SYSTEM_PROMPT)
        # 检查API调用是否成功，401/429/5xx等错误不再静默吞掉
        if not result.get("success", True):
            error_msg = result.get("error", "unknown")
            raise RuntimeError(f"DeepSeek API调用失败: {error_msg}")
        layer = result.get("layer", "working")
        value_score = float(result.get("value_score", 0.5))
        confidence = float(result.get("confidence", max(0.5, value_score)))
        return ClassificationResult(
            layer=layer,
            tags=result.get("tags", []),
            priority=result.get("priority", "medium"),
            value_score=value_score,
            reason=result.get("reason", ""),
            related_concepts=result.get("related_concepts", []),
            confidence=confidence,
        )

    def auto_tag(
        self, content: str, existing_tags: Optional[List[str]] = None
    ) -> List[str]:
        self._stats["auto_tag_calls"] += 1
        self._stats["last_call_time"] = time.time()
        tags = self._do_auto_tag(content, existing_tags)
        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="auto_tag",
                    state_before={"auto_tag_calls": self._stats["auto_tag_calls"] - 1},
                    state_after={
                        "auto_tag_calls": self._stats["auto_tag_calls"],
                        "tag_count": len(tags),
                    },
                )
            except Exception:
                pass
        return tags

    def _do_auto_tag(
        self, content: str, existing_tags: Optional[List[str]] = None
    ) -> List[str]:
        prompt = f"""请为以下内容生成3-8个精准标签:

内容:
{content[:2000]}

{"已有标签: " + ", ".join(existing_tags) if existing_tags else ""}

标签应是中文或英文关键词，便于检索。返回JSON:
{{"tags": ["关键词1", "关键词2", "关键词3"]}}"""

        result = self.client.chat_sync(prompt, SYSTEM_PROMPT)
        if not result.get("success", True):
            error_msg = result.get("error", "unknown")
            raise RuntimeError(f"DeepSeek API调用失败: {error_msg}")
        return result.get("tags", [])[:8]

    def assess_value(
        self, content: str, context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        self._stats["assess_calls"] += 1
        if not content or not content.strip():
            return {
                "value_score": 0.0,
                "importance": 0.0,
                "uniqueness": 0.0,
                "timeliness": 0.0,
                "relevance": 0.0,
                "reason": "空内容",
            }

        prompt = f"""请评估以下内容的记忆价值 (0.0-1.0):

内容:
{content[:2000]}

维度:
1. importance (重要性: 是否包含关键决策/知识) - 权重40%
2. uniqueness (唯一性: 是否重复) - 权重25%
3. timeliness (时效性: 长期有效?) - 权重20%
4. relevance (关联性: 可与其他记忆连接?) - 权重15%

必须返回JSON，包含所有5个字段:
{{"value_score": 0.78, "importance": 0.9, "uniqueness": 0.7, "timeliness": 0.8, "relevance": 0.6, "reason": "包含项目决策，长期有效"}}"""

        result = self.client.chat_sync(prompt, SYSTEM_PROMPT)
        if not result.get("success", True):
            error_msg = result.get("error", "unknown")
            raise RuntimeError(f"DeepSeek API调用失败: {error_msg}")
        defaults = {
            "value_score": 0.5,
            "importance": 0.5,
            "uniqueness": 0.5,
            "timeliness": 0.5,
            "relevance": 0.5,
            "reason": "",
        }
        if not isinstance(result, dict):
            return defaults
        for k, v in defaults.items():
            if k not in result or result[k] is None:
                result[k] = v
            elif isinstance(v, float) and isinstance(result[k], (int, float)):
                result[k] = float(result[k])
        return result

    def extract_knowledge(self, content: str) -> List[Dict[str, Any]]:
        self._stats["extract_calls"] += 1
        self._stats["last_call_time"] = time.time()
        triples = self._do_extract_knowledge(content)
        self._stats["triples_extracted"] += len(triples)
        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="extract_knowledge",
                    state_before={
                        "extract_calls": self._stats["extract_calls"] - 1,
                        "triples_extracted": self._stats["triples_extracted"]
                        - len(triples),
                    },
                    state_after={
                        "extract_calls": self._stats["extract_calls"],
                        "triples_extracted": self._stats["triples_extracted"],
                        "batch_count": len(triples),
                    },
                )
            except Exception:
                pass
        return triples

    def _do_extract_knowledge(self, content: str) -> List[Dict[str, Any]]:
        if not content or len(content.strip()) < 10:
            return []

        prompt = f"""请从以下内容中提取知识三元组（主体-关系-客体）:

内容:
{content[:3000]}

三元组类型示例:
- is_a: "Python is_a 编程语言"
- belongs_to: "FastAPI belongs_to Python生态"
- contains: "ICME contains 六层记忆"
- depends_on: "语义搜索 depends_on 嵌入模型"
- implements: "FastAPI implements REST框架"
- configured_by: "系统 configured_by .env文件"
- used_by: "DeepSeek used_by 天机v9.1"

必须返回JSON数组，每个元素包含subject/relation/object/confidence四个字段:
[{{"subject": "FastAPI", "relation": "used_for", "object": "后端API", "confidence": 0.95}}, {{"subject": "SQLite", "relation": "stores", "object": "记忆数据", "confidence": 0.9}}]"""

        result = self.client.chat_sync(prompt, SYSTEM_PROMPT)
        # success检查仅对dict类型生效; LLM可能直接返回list
        if isinstance(result, dict) and not result.get("success", True):
            error_msg = result.get("error", "unknown")
            raise RuntimeError(f"DeepSeek API调用失败: {error_msg}")
        triples = []
        raw_list = []
        if isinstance(result, list):
            raw_list = result
        elif isinstance(result, dict):
            for key in ("triples", "knowledge", "results", "data"):
                if key in result and isinstance(result[key], list):
                    raw_list = result[key]
                    break
            if not raw_list and any(
                isinstance(v, dict) and "subject" in v for v in result.values()
            ):
                raw_list = [
                    v for v in result.values() if isinstance(v, dict) and "subject" in v
                ]

        for item in raw_list:
            if not isinstance(item, dict):
                continue
            triple = {
                "subject": str(item.get("subject", "")),
                "relation": str(item.get("relation", "")),
                "object": str(item.get("object", "")),
                "confidence": float(item.get("confidence", 0.8)),
            }
            if triple["subject"] and triple["relation"] and triple["object"]:
                triples.append(triple)

        return triples

    def summarize(self, content: str, max_length: int = 200) -> str:
        self._stats["summarize_calls"] += 1
        prompt = f"""请将以下内容总结为不超过{max_length}字的摘要:

{content[:4000]}

返回JSON:
{{"summary": "这里放摘要"}}"""

        result = self.client.chat_sync(prompt, SYSTEM_PROMPT)
        if not result.get("success", True):
            error_msg = result.get("error", "unknown")
            raise RuntimeError(f"DeepSeek API调用失败: {error_msg}")
        return result.get("summary", content[:max_length])

    def decide_storage(
        self, content: str, context: Optional[Dict] = None
    ) -> StorageDecision:
        self._stats["decide_calls"] += 1
        self._stats["last_call_time"] = time.time()
        prev_decisions = self._stats["decide_calls"] - 1
        try:
            classification = self.classify_layer(content, context)
        except Exception:
            classification = ClassificationResult(
                layer="episodic",
                tags=[],
                priority="medium",
                value_score=0.5,
                reason="fallback",
                related_concepts=[],
            )

        try:
            value = self.assess_value(content, context)
        except Exception:
            value = {"value_score": 0.5, "reason": ""}

        try:
            summary = self.summarize(content) if len(content) > 200 else ""
        except Exception:
            summary = ""

        should_store = classification.value_score >= 0.2
        if (
            classification.layer in ("semantic", "meta")
            and classification.value_score < 0.5
        ):
            classification.layer = "episodic"

        decision = StorageDecision(
            should_store=should_store,
            layer=classification.layer,
            tags=classification.tags,
            priority=classification.priority,
            value_score=classification.value_score,
            confidence=max(0.5, classification.value_score),
            reason=classification.reason,
            summary=summary,
        )

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="decide_storage",
                    state_before={"decide_calls": prev_decisions},
                    state_after={
                        "decide_calls": self._stats["decide_calls"],
                        "layer": decision.layer,
                        "value_score": decision.value_score,
                        "should_store": decision.should_store,
                    },
                )
            except Exception:
                pass

        return decision

    def expand_query(self, query: str) -> List[str]:
        self._stats["expand_calls"] += 1
        prompt = f"""请为以下检索查询生成3-5个同义或相关查询扩展:

原始查询: {query}

返回JSON:
{{"expansions": ["扩展1", "扩展2", "扩展3"]}}"""

        result = self.client.chat_sync(prompt, SYSTEM_PROMPT)
        if not result.get("success", True):
            error_msg = result.get("error", "unknown")
            raise RuntimeError(f"DeepSeek API调用失败: {error_msg}")
        return result.get("expansions", [query])

    def search_relevance(self, query: str, candidates: List[str]) -> Dict[str, float]:
        self._stats["relevance_calls"] += 1
        batch = "\n".join(f"{i}: {c[:300]}" for i, c in enumerate(candidates[:20]))
        prompt = f"""请评估以下内容与查询的相关性(0-1):

查询: {query}

候选内容:
{batch}

返回JSON: {{"scores": {{"0": 0.8, "1": 0.3, ...}}}}"""

        result = self.client.chat_sync(prompt, SYSTEM_PROMPT)
        if not result.get("success", True):
            error_msg = result.get("error", "unknown")
            raise RuntimeError(f"DeepSeek API调用失败: {error_msg}")
        scores = result.get("scores", {})
        return {
            str(i): float(scores.get(str(i), 0.3)) for i in range(len(candidates[:20]))
        }

    def health(self) -> Dict[str, Any]:
        return {
            "status": "ready" if self.is_ready else "not_ready",
            "version": "9.1.0",
            "client_available": self.client is not None,
            "total_calls": sum(
                v
                for k, v in self._stats.items()
                if k.endswith("_calls") and isinstance(v, int)
            ),
            "errors": self._stats["errors"],
            "triples_total": self._stats["triples_extracted"],
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
            "classify_calls": self._stats["classify_calls"],
            "decide_calls": self._stats["decide_calls"],
            "extract_calls": self._stats["extract_calls"],
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "version": "9.1.0",
            **self._stats,
            "health": self.health(),
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
        }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_engine_effectiveness(
        self, action: str, state_before: Dict[str, Any], state_after: Dict[str, Any]
    ) -> float:
        if action == "extract_knowledge":
            batch = state_after.get("batch_count", 0)
            return min(0.8, batch * 0.15) if batch > 0 else -0.2
        elif action == "classify_layer":
            score = state_after.get("value_score", 0.5)
            return score * 0.3
        elif action == "auto_tag":
            count = state_after.get("tag_count", 0)
            return min(0.5, count * 0.1) if count > 0 else -0.3
        elif action == "decide_storage":
            layer = state_after.get("layer", "")
            if layer in ("semantic", "meta"):
                return 0.5
            return 0.2 if state_after.get("should_store", False) else 0.0
        return 0.0

    def _learn_from_decisions(
        self, causal_pairs: List[Any], effectiveness_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "total_triples": self._stats["triples_extracted"],
        }

    def _evolve_decision_params(
        self, learn_result: Dict[str, Any], mutable_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        changes = {}
        avg_eff = learn_result.get("avg_effectiveness", 0.0)
        if (
            avg_eff < -0.2
            and mutable_config.get("min_value_score_for_store", 0.2) < 0.5
        ):
            changes["min_value_score_for_store"] = min(
                0.5, mutable_config.get("min_value_score_for_store", 0.2) + 0.05
            )
        if avg_eff > 0.3 and mutable_config.get("min_value_score_for_store", 0.2) > 0.1:
            changes["min_value_score_for_store"] = max(
                0.1, mutable_config.get("min_value_score_for_store", 0.2) - 0.03
            )
        return {"rules_modified": changes, "skills_created": []}
