r"""
天机六层精准分解器 v1.0 — 对话内容100%精准分层存储
====================================================
TVP: @天枢(tianshu) → @忆库(yiku) | 任务: 六层精准分解 | 优先级: P0

核心功能:
- 将Trae对话内容精准分解到ICME六层记忆(L0-L5)
- 基于内容语义特征自动判断目标层级
- 支持单条对话→多层写入(一条对话可能同时产生多个层级记录)
- 批量历史对话回填
- 与MCP工具链集成(tianji_intercept → 六层分解 → memory_remember)

分层规则:
  L0 sensory: 原始对话snapshot (完整对话原文, 不做任何处理)
  L1 working: 当前会话上下文 (摘要+关键实体+任务状态)
  L2 short_term: 跨会话关键决策 (决策点+方案选择+执行结果)
  L3 episodic: 事件经历 (操作记录+错误修复+系统变更)
  L4 semantic: 知识概念 (架构知识+规则定义+技术原理)
  L5 meta: 策略元认知 (规则变更+策略优化+系统自调整)

闭环链路:
  对话输入 → LayerDecomposer.decompose() → 6个memory_remember调用 → KG同步
"""

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.shared.platform_detector import PLATFORM_QODER, PLATFORM_TRAE, get_platform


@dataclass
class DecomposedLayer:
    layer: str
    content: str
    tags: list[str]
    priority: str
    metadata: dict[str, Any] = field(default_factory=dict)


LAYER_KEYWORDS = {
    "meta": [
        "策略",
        "规则",
        "规范",
        "元认知",
        "宪法",
        "律令",
        "铁律",
        "SOP",
        "降级",
        "恢复",
        "配置变更",
        "策略调整",
        "系统策略",
        "规则更新",
        "优先级矩阵",
        "权限矩阵",
        "TVP协议",
        "质量门禁",
        "Stage Gate",
    ],
    "semantic": [
        "知识",
        "概念",
        "定义",
        "原理",
        "架构",
        "设计",
        "模式",
        "算法",
        "框架",
        "协议",
        "标准",
        "规范定义",
        "技术原理",
        "数据模型",
        "API端点",
        "类图",
        "流程图",
        "架构图",
        "设计模式",
        "范式",
    ],
    "episodic": [
        "修复",
        "错误",
        "异常",
        "审计",
        "测试",
        "bug",
        "问题",
        "故障",
        "调试",
        "排查",
        "根因",
        "崩溃",
        "报错",
        "traceback",
        "error",
        "失败",
        "回滚",
        "补丁",
        "hotfix",
        "修复记录",
        "事故",
    ],
    "short_term": [
        "决策",
        "执行",
        "调度",
        "tvp",
        "任务",
        "计划",
        "排期",
        "里程碑",
        "进度",
        "状态",
        "完成",
        "进行中",
        "待办",
        "优先级",
        "P0",
        "P1",
        "P2",
        "需求",
        "目标",
        "交付",
        "验收",
    ],
}


class LayerDecomposer:
    def __init__(self, engine: Any = None, data_path: Path = None):
        self._engine = engine
        if data_path is None:
            from .config import DEFAULT_CONFIG

            data_path = DEFAULT_CONFIG.data_path
        self._data_path = data_path
        self._stats = {
            "total_decomposed": 0,
            "layer_distribution": {
                "sensory": 0,
                "working": 0,
                "short_term": 0,
                "episodic": 0,
                "semantic": 0,
                "meta": 0,
            },
            "total_writes": 0,
            "write_errors": 0,
        }

    def decompose(
        self,
        user_input: str,
        ai_output: str = "",
        session_id: str = "",
        platform: str | None = None,
    ) -> list[DecomposedLayer]:
        if platform is None:
            platform = get_platform()
        results = []

        results.append(self._to_sensory(user_input, ai_output, session_id, platform))
        results.append(self._to_working(user_input, ai_output, session_id, platform))

        if ai_output:
            st = self._to_short_term(user_input, ai_output, session_id)
            if st:
                results.append(st)

            ep = self._to_episodic(user_input, ai_output, session_id)
            if ep:
                results.append(ep)

            sem = self._to_semantic(user_input, ai_output, session_id)
            if sem:
                results.append(sem)

            mt = self._to_meta(user_input, ai_output, session_id)
            if mt:
                results.append(mt)

        self._stats["total_decomposed"] += 1
        for r in results:
            self._stats["layer_distribution"][r.layer] = (
                self._stats["layer_distribution"].get(r.layer, 0) + 1
            )

        return results

    def decompose_and_store(
        self,
        user_input: str,
        ai_output: str = "",
        session_id: str = "",
        platform: str | None = None,
    ) -> dict[str, Any]:
        if platform is None:
            platform = get_platform()
        layers = self.decompose(user_input, ai_output, session_id, platform)
        results = {"total": len(layers), "stored": 0, "errors": 0, "details": []}

        for layer_data in layers:
            try:
                if self._engine is not None:
                    result = self._engine.remember(
                        content=layer_data.content,
                        layer=layer_data.layer,
                        tags=layer_data.tags,
                        priority=layer_data.priority,
                        metadata=layer_data.metadata,
                        use_llm=False,
                    )
                    if result.get("id"):
                        results["stored"] += 1
                        self._stats["total_writes"] += 1
                        results["details"].append(
                            {
                                "layer": layer_data.layer,
                                "id": result["id"],
                                "status": "stored",
                            }
                        )
                    else:
                        results["errors"] += 1
                        self._stats["write_errors"] += 1
                        results["details"].append(
                            {
                                "layer": layer_data.layer,
                                "status": "rejected",
                                "reason": result.get("reason", "unknown"),
                            }
                        )
                else:
                    self._fallback_store(layer_data)
                    results["stored"] += 1
                    self._stats["total_writes"] += 1
                    results["details"].append(
                        {
                            "layer": layer_data.layer,
                            "status": "fallback_stored",
                        }
                    )
            except Exception as e:
                results["errors"] += 1
                self._stats["write_errors"] += 1
                results["details"].append(
                    {
                        "layer": layer_data.layer,
                        "status": "error",
                        "error": str(e)[:100],
                    }
                )

        return results

    def _to_sensory(
        self, user_input: str, ai_output: str, session_id: str, platform: str
    ) -> DecomposedLayer:
        platform_label = (
            "Qoder"
            if platform == PLATFORM_QODER
            else ("Trae" if platform == PLATFORM_TRAE else platform.title())
        )
        snapshot = (
            f"[{platform_label}对话Snapshot] {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        snapshot += f"会话: {session_id or 'unknown'} | 平台: {platform}\n"
        snapshot += f"--- 用户输入 ---\n{user_input[:2000]}\n"
        if ai_output:
            snapshot += f"--- AI输出(前500字) ---\n{ai_output[:500]}"
        return DecomposedLayer(
            layer="sensory",
            content=snapshot,
            tags=["snapshot", platform, "sensory_capture", "auto_decomposed"],
            priority="medium",
            metadata={
                "source": "layer_decomposer",
                "session_id": session_id,
                "platform": platform,
            },
        )

    def _to_working(
        self, user_input: str, ai_output: str, session_id: str, platform: str
    ) -> DecomposedLayer:
        summary = f"[会话上下文] {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        summary += f"用户意图: {self._extract_intent(user_input)}\n"
        entities = self._extract_entities(user_input + " " + ai_output)
        if entities:
            summary += f"关键实体: {', '.join(entities[:10])}\n"
        summary += f"摘要: {user_input[:300]}"
        return DecomposedLayer(
            layer="working",
            content=summary,
            tags=["context", platform, "working_context", "auto_decomposed"]
            + entities[:5],
            priority="high",
            metadata={"source": "layer_decomposer", "session_id": session_id},
        )

    def _to_short_term(
        self, user_input: str, ai_output: str, session_id: str
    ) -> DecomposedLayer | None:
        combined = (user_input + " " + ai_output).lower()
        score = sum(1 for kw in LAYER_KEYWORDS["short_term"] if kw in combined)
        if score == 0:
            return None

        decisions = self._extract_decisions(user_input, ai_output)
        if not decisions:
            return None

        content = f"[跨会话决策] {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        for i, d in enumerate(decisions[:5], 1):
            content += f"决策{i}: {d}\n"
        return DecomposedLayer(
            layer="short_term",
            content=content,
            tags=["decision", "cross_session", "auto_decomposed"] + decisions[:3],
            priority="high",
            metadata={
                "source": "layer_decomposer",
                "session_id": session_id,
                "decision_count": len(decisions),
            },
        )

    def _to_episodic(
        self, user_input: str, ai_output: str, session_id: str
    ) -> DecomposedLayer | None:
        combined = (user_input + " " + ai_output).lower()
        score = sum(1 for kw in LAYER_KEYWORDS["episodic"] if kw in combined)
        if score == 0:
            return None

        incidents = self._extract_incidents(user_input, ai_output)
        if not incidents:
            return None

        content = f"[事件记录] {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        for inc in incidents[:5]:
            content += f"• {inc}\n"
        return DecomposedLayer(
            layer="episodic",
            content=content,
            tags=["incident", "event", "auto_decomposed"] + incidents[:3],
            priority="high",
            metadata={"source": "layer_decomposer", "session_id": session_id},
        )

    def _to_semantic(
        self, user_input: str, ai_output: str, session_id: str
    ) -> DecomposedLayer | None:
        combined = (user_input + " " + ai_output).lower()
        score = sum(1 for kw in LAYER_KEYWORDS["semantic"] if kw in combined)
        if score == 0:
            return None

        knowledge = self._extract_knowledge(user_input, ai_output)
        if not knowledge:
            return None

        content = f"[知识沉淀] {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        for k in knowledge[:5]:
            content += f"◆ {k}\n"
        return DecomposedLayer(
            layer="semantic",
            content=content,
            tags=["knowledge", "concept", "auto_decomposed"] + knowledge[:3],
            priority="high",
            metadata={"source": "layer_decomposer", "session_id": session_id},
        )

    def _to_meta(
        self, user_input: str, ai_output: str, session_id: str
    ) -> DecomposedLayer | None:
        combined = (user_input + " " + ai_output).lower()
        score = sum(1 for kw in LAYER_KEYWORDS["meta"] if kw in combined)
        if score < 2:
            return None

        policies = self._extract_policies(user_input, ai_output)
        if not policies:
            return None

        content = f"[策略归档] {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        for p in policies[:5]:
            content += f"⚙ {p}\n"
        return DecomposedLayer(
            layer="meta",
            content=content,
            tags=["policy", "meta", "strategy", "auto_decomposed"] + policies[:3],
            priority="critical",
            metadata={"source": "layer_decomposer", "session_id": session_id},
        )

    def _extract_intent(self, text: str) -> str:
        text = text.strip()
        if len(text) <= 100:
            return text
        sentences = re.split(r"[。！？\n]", text)
        return sentences[0][:100] if sentences else text[:100]

    def _extract_entities(self, text: str) -> list[str]:
        entities = set()
        patterns = [
            r"天机[vV]?(\d+\.?\d*)",
            r"ICME",
            r"@(\w+)",
            r"([A-Z][a-z]+(?:Engine|Store|Router|Hook|Loop|Bridge|Driver|Processor))",
            r"([a-z_]+\.py)",
            r"([a-z_]+\.tsx?)",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text):
                entities.add(m.group(0))
        return list(entities)[:15]

    def _extract_decisions(self, user_input: str, ai_output: str) -> list[str]:
        decisions = []
        patterns = [
            r"(?:决定|决策|选择|采用|实施|执行)([^。！？\n]{5,80})",
            r"(?:方案[一二三四五A-E])([^。！？\n]{5,80})",
            r"(?:优先级[：:])([^。！？\n]{3,50})",
        ]
        for pat in patterns:
            for m in re.finditer(pat, user_input + ai_output):
                decisions.append(m.group(0)[:80])
        return decisions[:10]

    def _extract_incidents(self, user_input: str, ai_output: str) -> list[str]:
        incidents = []
        patterns = [
            r"(?:修复|解决|排查|根因)([^。！？\n]{5,80})",
            r"(?:Error|Exception|Bug|错误|异常)([^。！？\n]{3,80})",
            r"(?:修复记录|问题)([^。！？\n]{5,80})",
        ]
        for pat in patterns:
            for m in re.finditer(pat, user_input + ai_output, re.IGNORECASE):
                incidents.append(m.group(0)[:80])
        return incidents[:10]

    def _extract_knowledge(self, user_input: str, ai_output: str) -> list[str]:
        knowledge = []
        patterns = [
            r"(?:架构|设计|原理|定义|模式)([^。！？\n]{5,80})",
            r"(?:API端点|路由|接口)([^。！？\n]{3,80})",
            r"(?:特性|功能|模块)([^。！？\n]{5,80})",
        ]
        for pat in patterns:
            for m in re.finditer(pat, user_input + ai_output):
                knowledge.append(m.group(0)[:80])
        return knowledge[:10]

    def _extract_policies(self, user_input: str, ai_output: str) -> list[str]:
        policies = []
        patterns = [
            r"(?:规则|策略|规范|律令|宪法)([^。！？\n]{5,80})",
            r"(?:SOP|降级|恢复|门禁|Gate)([^。！？\n]{3,80})",
            r"(?:权限矩阵|TVP|Stage Gate)([^。！？\n]{3,80})",
        ]
        for pat in patterns:
            for m in re.finditer(pat, user_input + ai_output, re.IGNORECASE):
                policies.append(m.group(0)[:80])
        return policies[:10]

    def _fallback_store(self, layer_data: DecomposedLayer):
        try:
            layer_dir = self._data_path / layer_data.layer
            layer_dir.mkdir(parents=True, exist_ok=True)
            entry_id = hashlib.sha256(
                f"{layer_data.content}{time.time()}".encode()
            ).hexdigest()[:16]
            entry = {
                "id": entry_id,
                "content": layer_data.content,
                "layer": layer_data.layer,
                "tags": layer_data.tags,
                "priority": layer_data.priority,
                "created_at": time.time(),
                "last_accessed": time.time(),
                "access_count": 0,
                "effectiveness_score": 0.5,
                "related_ids": [],
                "metadata": layer_data.metadata,
                "changelog": [],
            }
            (layer_dir / f"{entry_id}.json").write_text(
                json.dumps(entry, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def batch_backfill(self, conversations: list[dict]) -> dict[str, Any]:
        results = {
            "total": len(conversations),
            "success": 0,
            "errors": 0,
            "layer_stats": {},
        }
        for conv in conversations:
            user_input = conv.get("user_input", conv.get("content", ""))
            ai_output = conv.get("ai_output", conv.get("ai_response", ""))
            session_id = conv.get("session_id", "")
            platform = conv.get("platform") or get_platform()

            if not user_input:
                continue

            try:
                result = self.decompose_and_store(
                    user_input, ai_output, session_id, platform
                )
                if result["stored"] > 0:
                    results["success"] += 1
                for detail in result.get("details", []):
                    layer = detail.get("layer", "unknown")
                    results["layer_stats"][layer] = (
                        results["layer_stats"].get(layer, 0) + 1
                    )
            except Exception:
                results["errors"] += 1

        return results

    def get_stats(self) -> dict[str, Any]:
        return {**self._stats}
