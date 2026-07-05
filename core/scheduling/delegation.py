r"""
天机调度 - DeepSeek 委派决策器 (Delegation Decider) [v10-ready]
================================================================
DeepSeek 驾驶委派决策 — 判断是否需要委派、如何委派 (策略/并发度/模型选择)。

决策三级链路:
  1. _quick_rules     — 快速规则 (简单任务直执行 / 并行关键词 / 高复杂度)
  2. _deepseek_decision — DeepSeek 大模型决策 (decision_engine 就绪时)
  3. _fallback_decision — 降级决策 (大模型不可用时的保底)

从 core/intelligent_scheduler.py 拆分而来 (原 DeepSeekDelegationDecider)。
"""

import logging
from typing import Optional, List

from core.scheduling import DelegationStrategy, SubAgentTask, DelegationDecision

logger = logging.getLogger("tianji.scheduler")


class DelegationDecider:
    """DeepSeek驾驶委派决策 — 判断是否需要委派、如何委派"""

    def __init__(self, decision_engine=None):
        self.decision_engine = decision_engine
        self._stats = {"decisions_made": 0, "delegations": 0, "direct": 0}

    def decide(self, task_description: str, available_agents: List[str],
               task_complexity: str = "medium") -> DelegationDecision:
        """DeepSeek决定委派策略"""

        self._stats["decisions_made"] += 1

        quick_rules = self._quick_rules(task_description, available_agents, task_complexity)
        if quick_rules:
            self._stats["delegations" if quick_rules.strategy != DelegationStrategy.DIRECT else "direct"] += 1
            return quick_rules

        if self.decision_engine and self.decision_engine.is_ready:
            return self._deepseek_decision(task_description, available_agents, task_complexity)

        return self._fallback_decision(task_description, available_agents, task_complexity)

    def _quick_rules(self, desc: str, agents: List[str], complexity: str) -> Optional[DelegationDecision]:
        if len(desc) < 200 and complexity == "low":
            self._stats["direct"] += 1
            return DelegationDecision(
                strategy=DelegationStrategy.DIRECT,
                sub_tasks=[],
                max_concurrency=1,
                use_cheaper_model=False,
                reason="简单任务无需委派",
                confidence=0.95,
            )

        parallel_keywords = ["并行", "同时", "多个", "批量", "分别", "各自"]
        if any(kw in desc for kw in parallel_keywords) and len(agents) >= 3:
            sub_goals = [s.strip() for s in desc.replace("并行", "|").replace("同时", "|").split("|") if s.strip()]
            if len(sub_goals) >= 2:
                self._stats["delegations"] += 1
                sub_tasks = [
                    SubAgentTask(
                        task_id="", goal=sg[:100], context=desc[:500],
                        toolsets=agents[:3],
                    )
                    for sg in sub_goals[:5]
                ]
                return DelegationDecision(
                    strategy=DelegationStrategy.PARALLEL_BATCH,
                    sub_tasks=sub_tasks,
                    max_concurrency=min(3, len(sub_tasks)),
                    use_cheaper_model=len(sub_tasks) >= 3,
                    reason=f"检测到并行关键词，拆分为{len(sub_tasks)}个子任务",
                    confidence=0.85,
                )

        if complexity in ("high", "very_high") and len(agents) >= 2:
            self._stats["delegations"] += 1
            sub_tasks = [
                SubAgentTask(
                    task_id="", goal=f"分析维度: {agent}",
                    context=desc[:500],
                    toolsets=[agent],
                )
                for agent in agents[:3]
            ]
            return DelegationDecision(
                strategy=DelegationStrategy.PARALLEL_BATCH,
                sub_tasks=sub_tasks,
                max_concurrency=min(3, len(sub_tasks)),
                use_cheaper_model=True,
                reason=f"高复杂度任务，委派{len(sub_tasks)}个子代理并行分析",
                confidence=0.80,
            )

        return None

    def _deepseek_decision(self, desc: str, agents: List[str], complexity: str) -> DelegationDecision:
        prompt = f"""分析以下任务，决定是否需要子代理委派:

任务: {desc[:1000]}
可用Agent: {', '.join(agents[:8])}
复杂度: {complexity}

判断规则:
- DIRECT: 简单任务/单一Agent即可完成
- SINGLE_SUBAGENT: 需要隔离上下文执行的任务
- PARALLEL_BATCH: 可拆分为多个独立子任务并行执行
- HIERARCHICAL: 大型复杂项目需要层级管理

返回JSON:
{{"strategy": "parallel_batch", "sub_goals": ["目标1", "目标2"], "max_concurrency": 3, "use_cheaper_model": true, "reason": "可并行化", "confidence": 0.85}}"""

        try:
            result = self.decision_engine.client.chat_sync(prompt, expect_json=True)
            strategy_map = {
                "direct": DelegationStrategy.DIRECT,
                "single_subagent": DelegationStrategy.SINGLE_SUBAGENT,
                "parallel_batch": DelegationStrategy.PARALLEL_BATCH,
                "hierarchical": DelegationStrategy.HIERARCHICAL,
            }
            strategy = strategy_map.get(
                result.get("strategy", "direct"), DelegationStrategy.DIRECT
            )
            sub_goals = result.get("sub_goals", [desc[:100]])
            sub_tasks = [
                SubAgentTask(
                    task_id="", goal=sg[:100], context=desc[:500],
                    toolsets=agents[:3],
                )
                for sg in sub_goals[:5]
            ]
            self._stats["delegations" if strategy != DelegationStrategy.DIRECT else "direct"] += 1
            return DelegationDecision(
                strategy=strategy,
                sub_tasks=sub_tasks,
                max_concurrency=result.get("max_concurrency", 3),
                use_cheaper_model=result.get("use_cheaper_model", False),
                reason=result.get("reason", "DeepSeek决策"),
                confidence=result.get("confidence", 0.8),
            )
        except Exception as e:
            logger.error(f"DeepSeek delegation decision failed: {e}")
            return self._fallback_decision(desc, agents, complexity)

    def _fallback_decision(self, desc: str, agents: List[str], complexity: str) -> DelegationDecision:
        if complexity in ("high", "very_high"):
            sub_tasks = [
                SubAgentTask(task_id="", goal=f"子任务{i+1}: {desc[:80]}",
                             context=desc[:500], toolsets=agents[:2])
                for i in range(min(3, len(agents)))
            ]
            return DelegationDecision(
                strategy=DelegationStrategy.PARALLEL_BATCH,
                sub_tasks=sub_tasks,
                max_concurrency=2,
                use_cheaper_model=False,
                reason="降级决策: 高复杂度默认并行",
                confidence=0.5,
            )
        return DelegationDecision(
            strategy=DelegationStrategy.DIRECT,
            sub_tasks=[],
            max_concurrency=1,
            use_cheaper_model=False,
            reason="降级决策: 默认直接执行",
            confidence=0.5,
        )

    def get_stats(self) -> dict:
        return self._stats


# 兼容别名: 原 Hermes 命名
DeepSeekDelegationDecider = DelegationDecider
