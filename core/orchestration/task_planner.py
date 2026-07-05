r"""
天机LLM任务规划器 (Tianji Task Planner) v1.0
============================================
借鉴 LangGraph Supervisor + AutoGen Task Decomposition + ReAcTree 的分层规划思想，
将自然语言任务描述拆解为DAG流水线。

核心能力:
  1. 任务拆解 — 自然语言→子任务列表+依赖关系
  2. DAG生成 — 子任务+依赖→DAGPipeline (自动分配Agent)
  3. 复杂度评估 — 自动判断任务复杂度 (low/medium/high/very_high)
  4. 并行度检测 — 识别可并行的独立子任务
  5. Agent推荐 — 基于能力矩阵推荐最优Agent
  6. 策略推荐 — 推荐调度策略 (串行/并行/DAG)

参考架构:
  - LangGraph Supervisor: LLM Supervisor→Worker routing
  - ReAcTree: 动态树展开的分层任务规划
  - AutoGen: 多Agent对话驱动任务分解

位置: 天机/core/task_planner.py
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from core.orchestration.dag_scheduler import (
    DAGBuilder,
    DAGPipeline,
)

logger = logging.getLogger("tianji.task_planner")


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════


class TaskComplexity(str, Enum):
    LOW = "low"  # 单一Agent即可完成
    MEDIUM = "medium"  # 2-3个Agent串行
    HIGH = "high"  # 3-5个Agent, 有并行分支
    VERY_HIGH = "very_high"  # 5+ Agents, 复杂DAG


class ExecutionStrategy(str, Enum):
    SINGLE_AGENT = "single_agent"  # 单一Agent
    SERIAL_CHAIN = "serial_chain"  # 串行链
    PARALLEL_BATCH = "parallel_batch"  # 并行批量
    DAG_PIPELINE = "dag_pipeline"  # 完整DAG


@dataclass
class SubTask:
    """子任务"""

    index: int
    goal: str
    context: str = ""
    agent_id: str = ""  # 推荐的Agent ID
    agent_name: str = ""  # Agent名称
    agent_emoji: str = "🤖"
    depends_on: list[int] = field(default_factory=list)  # 依赖的子任务索引
    can_parallel: bool = False  # 是否可与其他任务并行
    tools_needed: list[str] = field(default_factory=list)
    estimated_duration_s: int = 60  # 预估耗时(秒)
    priority: str = "medium"


@dataclass
class TaskPlan:
    """任务规划结果"""

    original_task: str
    complexity: TaskComplexity
    strategy: ExecutionStrategy
    sub_tasks: list[SubTask]
    reasoning: str  # 规划推理过程
    confidence: float  # 置信度 0-1
    suggested_agents: list[str]  # 建议的Agent列表
    warnings: list[str] = field(default_factory=list)
    plan_id: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "original_task": self.original_task[:200],
            "complexity": self.complexity.value,
            "strategy": self.strategy.value,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "suggested_agents": self.suggested_agents,
            "warnings": self.warnings,
            "sub_tasks": [
                {
                    "index": st.index,
                    "goal": st.goal,
                    "agent_id": st.agent_id,
                    "agent_name": st.agent_name,
                    "agent_emoji": st.agent_emoji,
                    "depends_on": st.depends_on,
                    "can_parallel": st.can_parallel,
                    "estimated_duration_s": st.estimated_duration_s,
                }
                for st in self.sub_tasks
            ],
        }


# ═══════════════════════════════════════════════════════════════
# Agent能力知识库 (单源 — 与 agent_orchestrator 保持一致)
# ═══════════════════════════════════════════════════════════════

AGENT_DESCRIPTIONS = {
    "dongcha": "需求分析/意图感知/上下文提取 — 擅长理解用户需求和提取关键信息",
    "jingwei": "架构设计/技术选型/系统规划 — 擅长设计系统架构和技术方案",
    "miaobi": "代码实现/内容创作/生成 — 擅长编码和创造性工作",
    "mingjing": "代码审校/质量评估/一致性检查 — 擅长发现问题和评估质量",
    "tiewei": "测试验证/门禁检查/安全测试 — 擅长质量保障和测试",
    "gongzao": "部署上线/CI/CD/环境管理 — 擅长部署和运维自动化",
    "shiguan": "版本管理/变更归档/历史追踪 — 擅长版本控制和归档",
    "tianshu": "全局调度/任务分发/编排决策 — 擅长协调多个Agent协作",
    "wenzong": "项目管理/内容审核/进度追踪 — 擅长项目管理和审核",
    "tiansuan": "数据分析/统计/可视化/模式识别 — 擅长数据处理和分析",
    "kuangshi": "语料导入/数据清洗/批量处理 — 擅长数据处理和导入",
    "qianli": "系统监控/性能采集/智能告警 — 擅长系统监控和运维",
    "zhenshan": "安全扫描/漏洞检测/合规检查 — 擅长安全审计",
    "zhuiguang": "性能剖析/瓶颈分析/资源优化 — 擅长性能优化",
    "yiku": "记忆管理/语义检索/知识图谱 — 擅长记忆存储和检索",
    "luling": "规则匹配/合规检查/冲突检测 — 擅长规则执行",
    "baiqiao": "技能调用/工作流编排/MCP工具 — 擅长工具调度",
    "jinshu": "格式导出/成品美化/模板应用 — 擅长格式化输出",
    "jianheng": "5维系统审计/功能完整性检查/稳定性审计/性能基准/安全合规/数据准确性 — 擅长全维度系统审计",
    "lianli": "实体抽取/关系识别/图谱构建/多跳推理 — 擅长知识图谱",
    "huasheng": "自我检查/递归改进/规则演化/架构升级 — 擅长系统进化",
    "lingxi": "对话完整性/意图连续性/异常检测 — 擅长会话监控",
    "wanxiang": "图像理解/表格解析/多模态融合 — 擅长多模态处理",
}

AGENT_KEYWORDS = {
    "dongcha": ["分析", "理解", "感知", "意图", "需求", "调研", "探索"],
    "jingwei": ["架构", "设计", "系统", "结构", "方案", "规划", "重构"],
    "miaobi": ["写", "创建", "生成", "代码", "实现", "开发", "构建", "编码"],
    "mingjing": ["审查", "审核", "检查", "审校", "评估", "review"],
    "tiewei": ["测试", "验证", "门禁", "test", "验证", "通过"],
    "gongzao": ["部署", "发布", "上线", "CI/CD", "构建", "打包"],
    "shiguan": ["版本", "归档", "历史", "记录", "追踪"],
    "tianshu": ["调度", "分发", "协调", "编排", "指挥"],
    "tiansuan": ["数据", "统计", "分析报告", "可视化", "趋势"],
    "zhenshan": ["安全", "漏洞", "扫描", "防护", "security"],
    "jianheng": ["审计", "检查", "诊断", "合规", "基准", "audit", "diagnose", "check"],
    "zhuiguang": ["性能", "优化", "瓶颈", "加速", "profile"],
    "yiku": ["记忆", "回忆", "存储", "检索", "搜索", "知识"],
    "qianli": ["监控", "运维", "健康", "告警", "deploy"],
}


# ═══════════════════════════════════════════════════════════════
# 任务规划器
# ═══════════════════════════════════════════════════════════════


class TaskPlanner:
    """
    LLM驱动的任务规划器 — 将自然语言任务拆解为DAG流水线

    两种规划模式:
      1. LLM模式: DeepSeek深度推理 → 高质量拆解
      2. 规则模式: 关键词+模板快速匹配 → 即时响应 (降级)
    """

    VERSION = "1.0.0-Planner"

    def __init__(self, decision_engine=None, event_bus=None):
        self.decision_engine = decision_engine
        self.event_bus = event_bus
        self._stats = {
            "plans_created": 0,
            "llm_plans": 0,
            "rule_plans": 0,
            "avg_confidence": 0.0,
        }

    def plan(
        self,
        task_description: str,
        context: str = "",
        available_agents: list[str] = None,
        prefer_llm: bool = True,
    ) -> TaskPlan:
        """
        规划任务

        Args:
            task_description: 自然语言任务描述
            context: 额外上下文
            available_agents: 可用Agent列表
            prefer_llm: 是否优先使用LLM

        Returns:
            TaskPlan
        """
        self._stats["plans_created"] += 1

        # 优先使用LLM
        if prefer_llm and self.decision_engine and self.decision_engine.is_ready:
            try:
                plan = self._llm_plan(task_description, context, available_agents)
                self._stats["llm_plans"] += 1
                return plan
            except Exception as e:
                logger.warning(f"[Planner] LLM planning failed, fallback to rules: {e}")

        # 降级到规则模式
        plan = self._rule_plan(task_description, context, available_agents)
        self._stats["rule_plans"] += 1
        return plan

    def _llm_plan(
        self, task: str, context: str, available_agents: list[str] = None
    ) -> TaskPlan:
        """DeepSeek驱动的智能任务拆解"""
        agents_desc = "\n".join(
            f"  - {aid}: {desc}"
            for aid, desc in AGENT_DESCRIPTIONS.items()
            if available_agents is None or aid in available_agents
        )

        prompt = f"""你是一个任务规划专家。请将以下任务拆解为子任务，并为每个子任务推荐最合适的Agent。

## 可用Agent
{agents_desc}

## 任务
{task}

## 上下文
{context or "无"}

## 要求
1. 将任务拆解为2-8个子任务
2. 标注子任务间的依赖关系 (depends_on: [前置子任务索引])
3. 标注哪些子任务可以并行执行
4. 为每个子任务推荐最合适的Agent
5. 评估整体任务复杂度和推荐执行策略

## 输出JSON格式:
```json
{{
  "complexity": "low|medium|high|very_high",
  "strategy": "single_agent|serial_chain|parallel_batch|dag_pipeline",
  "reasoning": "规划理由(中文, 2-3句话)",
  "confidence": 0.85,
  "suggested_agents": ["agent_id1", "agent_id2"],
  "warnings": ["警告信息"],
  "sub_tasks": [
    {{
      "index": 0,
      "goal": "子任务目标",
      "agent_id": "dongcha",
      "depends_on": [],
      "can_parallel": false,
      "estimated_duration_s": 60
    }}
  ]
}}
```

只返回JSON，不要包含其他内容。"""

        try:
            result = self.decision_engine.client.chat_sync(prompt, expect_json=True)

            # 解析结果
            complexity = TaskComplexity(result.get("complexity", "medium"))
            strategy = ExecutionStrategy(result.get("strategy", "serial_chain"))
            sub_tasks_data = result.get("sub_tasks", [])

            sub_tasks = []
            for st_data in sub_tasks_data:
                agent_id = st_data.get("agent_id", "tianshu")
                from core.orchestration.agent_orchestrator import AGENT_CAPABILITY_MATRIX

                agent_info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})
                sub_tasks.append(
                    SubTask(
                        index=st_data.get("index", len(sub_tasks)),
                        goal=st_data.get("goal", f"子任务{len(sub_tasks) + 1}"),
                        context=context,
                        agent_id=agent_id,
                        agent_name=agent_info.get("name", agent_id),
                        agent_emoji=agent_info.get("emoji", "🤖"),
                        depends_on=st_data.get("depends_on", []),
                        can_parallel=st_data.get("can_parallel", False),
                        estimated_duration_s=st_data.get("estimated_duration_s", 60),
                    )
                )

            import uuid

            plan = TaskPlan(
                original_task=task,
                complexity=complexity,
                strategy=strategy,
                sub_tasks=sub_tasks,
                reasoning=result.get("reasoning", ""),
                confidence=result.get("confidence", 0.8),
                suggested_agents=result.get("suggested_agents", []),
                warnings=result.get("warnings", []),
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            )
            self._update_stats(plan)
            return plan

        except Exception as e:
            logger.error(f"[Planner] LLM planning error: {e}")
            raise

    def _rule_plan(
        self, task: str, context: str, available_agents: list[str] = None
    ) -> TaskPlan:
        """基于规则的快速任务拆解 (降级模式)"""
        import uuid

        task_lower = task.lower()

        # 复杂度评估
        word_count = len(task)
        has_parallel_keywords = any(
            kw in task_lower for kw in ["并行", "同时", "多个", "批量", "分别", "各自"]
        )
        has_multi_stage = any(
            kw in task_lower for kw in ["开发", "构建", "重构", "架构", "系统"]
        )

        if has_parallel_keywords and word_count > 10:
            complexity = TaskComplexity.HIGH
            strategy = ExecutionStrategy.PARALLEL_BATCH
        elif has_multi_stage and word_count > 15:
            complexity = TaskComplexity.HIGH
            strategy = ExecutionStrategy.DAG_PIPELINE
        elif word_count > 20:
            complexity = TaskComplexity.MEDIUM
            strategy = ExecutionStrategy.SERIAL_CHAIN
        else:
            complexity = TaskComplexity.LOW
            strategy = ExecutionStrategy.SINGLE_AGENT

        # Agent匹配
        agent_scores: dict[str, int] = {}
        for agent_id, keywords in AGENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                agent_scores[agent_id] = score

        # 按分数排序
        sorted_agents = sorted(agent_scores.items(), key=lambda x: -x[1])

        # 构建子任务
        sub_tasks = []
        from core.orchestration.agent_orchestrator import AGENT_CAPABILITY_MATRIX

        if strategy == ExecutionStrategy.SINGLE_AGENT:
            # 单一Agent: 选择最高分Agent
            agent_id = sorted_agents[0][0] if sorted_agents else "tianshu"
            info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})
            sub_tasks.append(
                SubTask(
                    index=0,
                    goal=task[:100],
                    agent_id=agent_id,
                    agent_name=info.get("name", agent_id),
                    agent_emoji=info.get("emoji", "🤖"),
                )
            )

        elif strategy == ExecutionStrategy.DAG_PIPELINE:
            # 标准开发流水线
            pipeline_steps = [
                ("dongcha", f"需求分析: {task[:60]}"),
                ("jingwei", f"架构设计: {task[:60]}"),
                ("miaobi", f"编码实现: {task[:60]}"),
                ("mingjing", f"代码审校: {task[:60]}"),
                ("tiewei", f"测试验证: {task[:60]}"),
            ]
            for i, (aid, goal) in enumerate(pipeline_steps):
                info = AGENT_CAPABILITY_MATRIX.get(aid, {})
                sub_tasks.append(
                    SubTask(
                        index=i,
                        goal=goal,
                        agent_id=aid,
                        agent_name=info.get("name", aid),
                        agent_emoji=info.get("emoji", "🤖"),
                        depends_on=[i - 1] if i > 0 else [],
                    )
                )

        elif strategy == ExecutionStrategy.PARALLEL_BATCH:
            # 并行任务: 分配不同Agent给不同维度
            dimensions = self._extract_dimensions(task)
            for i, dim in enumerate(dimensions):
                agent_id = sorted_agents[i][0] if i < len(sorted_agents) else "tianshu"
                info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})
                sub_tasks.append(
                    SubTask(
                        index=i,
                        goal=dim,
                        agent_id=agent_id,
                        agent_name=info.get("name", agent_id),
                        agent_emoji=info.get("emoji", "🤖"),
                        can_parallel=True,
                    )
                )

        else:
            # 串行链: 使用top-2 Agent
            for i in range(min(2, len(sorted_agents))):
                agent_id = sorted_agents[i][0]
                info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})
                sub_tasks.append(
                    SubTask(
                        index=i,
                        goal=f"{info.get('name', agent_id)}执行: {task[:60]}"
                        if i > 0
                        else f"分析: {task[:60]}",
                        agent_id=agent_id,
                        agent_name=info.get("name", agent_id),
                        agent_emoji=info.get("emoji", "🤖"),
                        depends_on=[i - 1] if i > 0 else [],
                    )
                )

        plan = TaskPlan(
            original_task=task,
            complexity=complexity,
            strategy=strategy,
            sub_tasks=sub_tasks,
            reasoning=f"规则匹配: 关键词分析 → {complexity.value}复杂度 → {strategy.value}策略",
            confidence=0.6,
            suggested_agents=[a[0] for a in sorted_agents[:5]],
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
        )
        self._update_stats(plan)
        return plan

    def _extract_dimensions(self, task: str) -> list[str]:
        """从任务描述中提取分析维度"""
        task_lower = task.lower()
        dimensions = []

        dimension_map = {
            "安全": "安全性分析",
            "性能": "性能分析",
            "架构": "架构分析",
            "代码": "代码质量分析",
            "数据": "数据分析",
            "部署": "部署方案分析",
            "测试": "测试策略分析",
            "设计": "设计方案分析",
            "文档": "文档分析",
        }

        for key, dim in dimension_map.items():
            if key in task_lower or key in task:
                dimensions.append(dim)

        if not dimensions:
            dimensions = [
                f"综合维度{i + 1}: {task[:40]}"
                for i in range(min(3, len(task) // 30 + 1))
            ]

        return dimensions[:5]

    def _update_stats(self, plan: TaskPlan):
        n = self._stats["plans_created"]
        self._stats["avg_confidence"] = (
            self._stats["avg_confidence"] * (n - 1) + plan.confidence
        ) / n

    def plan_to_dag(self, plan: TaskPlan, event_bus=None) -> DAGPipeline:
        """将TaskPlan转换为DAGPipeline"""
        builder = DAGBuilder(f"Plan: {plan.original_task[:40]}")

        node_ids: dict[int, str] = {}

        for st in plan.sub_tasks:
            builder.node(
                st.agent_id,
                st.goal,
                st.context,
                priority=st.priority,
                timeout_s=st.estimated_duration_s,
            )
            node_ids[st.index] = builder._last_node_id

        # 添加依赖边
        for st in plan.sub_tasks:
            for dep_idx in st.depends_on:
                if dep_idx in node_ids:
                    builder.pipeline.add_edge(node_ids[dep_idx], node_ids[st.index])

        return builder.build(event_bus)

    def get_stats(self) -> dict:
        return {"version": self.VERSION, **self._stats}


# ═══════════════════════════════════════════════════════════════
# 快速工厂函数
# ═══════════════════════════════════════════════════════════════


def quick_plan(task: str, decision_engine=None) -> TaskPlan:
    """快速规划 (单次调用便捷接口)"""
    planner = TaskPlanner(decision_engine)
    return planner.plan(task)


def quick_dag(task: str, decision_engine=None, event_bus=None) -> DAGPipeline:
    """快速生成DAG (单次调用)"""
    planner = TaskPlanner(decision_engine)
    plan = planner.plan(task)
    return planner.plan_to_dag(plan, event_bus)


# ═══════════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════════

_task_planner: TaskPlanner | None = None
_planner_lock = __import__("threading").Lock()


def get_task_planner(decision_engine=None, event_bus=None) -> TaskPlanner:
    global _task_planner
    with _planner_lock:
        if _task_planner is None:
            _task_planner = TaskPlanner(decision_engine, event_bus)
        return _task_planner
