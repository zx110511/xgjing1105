r"""

并行调度器 (Agent Dispatcher) — [v10-ready]

=====================================================

天机Agent编排子包·职责4: Agent选择与并行调度



职责边界:

  - ParallelDispatcher — 并行任务精准Agent分配

  - Agent选择/分配/调度决策



依赖: registry (AGENT_CAPABILITY_MATRIX, PipelineStage),

      tracker (ToolCallTracker)



位置: 天机/core/orchestration/dispatcher.py

"""



from __future__ import annotations



import uuid

from collections.abc import Callable



from .registry import AGENT_CAPABILITY_MATRIX, PipelineStage

from .tracker import ToolCallTracker



# ═══════════════════════════════════════════════════════════════

# ParallelDispatcher — 并行任务精准Agent分配 — [v10-ready]

# ═══════════════════════════════════════════════════════════════





class ParallelDispatcher:

    """

    并行调度器 — 多个并行任务各自分配Agent



    示例:

      "并行分析架构、安全、性能" →

        @jingwei(经纬) 分析架构 → 3次工具调用

        @zhenshan(镇山) 安全扫描 → 5次工具调用

        @zhuiguang(追光) 性能剖析 → 4次工具调用

    """



    def __init__(self, tracker: ToolCallTracker, event_bus=None, max_workers: int = 5):

        self.tracker = tracker

        self.event_bus = event_bus

        self.max_workers = max_workers

        self._output_handler: Callable | None = None



    def set_output_handler(self, handler: Callable[[str], None]):

        self._output_handler = handler



    def dispatch(self, parallel_tasks: list[dict]) -> list[dict]:

        """并行分发任务到各自的Agent



        parallel_tasks: [

            {"agent_id":"jingwei", "goal":"分析架构", "context":"..."},

            {"agent_id":"zhenshan","goal":"安全扫描", "context":"..."},

            {"agent_id":"zhuiguang","goal":"性能剖析","context":"..."},

        ]

        """

        if len(parallel_tasks) > 1 and self._output_handler:

            agents_str = " + ".join(

                f"@{AGENT_CAPABILITY_MATRIX.get(t['agent_id'], {}).get('name', t['agent_id'])}"

                for t in parallel_tasks

            )

            self._output_handler(

                f"[TVP] 🎯 并行调度: {len(parallel_tasks)}路并行 → {agents_str}"

            )



        results = []

        for i, task in enumerate(parallel_tasks):

            agent_id = task.get("agent_id", "tianshu")

            info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})

            task_id = f"parallel-{uuid.uuid4().hex[:6]}"



            self.tracker.set_context(

                agent_id=agent_id,

                stage=PipelineStage.EXECUTE,

                task_id=task_id,

            )



            if self._output_handler:

                self._output_handler(

                    f"[TVP] ├─ 路{i + 1}: {info.get('emoji', '🤖')}@"

                    f"{info.get('name', agent_id)} → {task.get('goal', '')[:50]}"

                )



            results.append(

                {

                    "task_id": task_id,

                    "agent_id": agent_id,

                    "agent_name": info.get("name", agent_id),

                    "agent_emoji": info.get("emoji", "🤖"),

                    "goal": task.get("goal", ""),

                    "tools_allowed": info.get("tools", []),

                }

            )



        if self._output_handler and len(parallel_tasks) > 1:

            self._output_handler("[TVP] └─ 并行任务已分发，等待结果聚合")



        return results





# 向后兼容/任务约定别名: AgentDispatcher

AgentDispatcher = ParallelDispatcher

