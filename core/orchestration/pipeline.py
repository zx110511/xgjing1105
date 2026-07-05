r"""

管道编排器 (Pipeline Orchestrator) — [v10-ready]

=====================================================

天机Agent编排子包·职责3: 管道编排



职责边界:

  - StageResult 阶段结果数据结构

  - AgentPipeline — 长链任务多Agent阶段切换、结果聚合

  - 标准流水线模板 STANDARD_PIPELINES



依赖: registry (AGENT_CAPABILITY_MATRIX, PipelineStage),

      tracker (ToolCallTracker, ToolCallRecord)



位置: 天机/core/orchestration/pipeline.py

"""



from __future__ import annotations



import uuid

from collections.abc import Callable

from dataclasses import dataclass



from .registry import AGENT_CAPABILITY_MATRIX, PipelineStage

from .tracker import ToolCallRecord, ToolCallTracker



# ═══════════════════════════════════════════════════════════════

# 数据结构

# ═══════════════════════════════════════════════════════════════





@dataclass

class StageResult:

    stage: PipelineStage

    agent_id: str

    agent_name: str

    agent_emoji: str

    status: str

    summary: str

    tool_calls: list[ToolCallRecord]

    duration_s: float

    next_stage: PipelineStage | None = None



    def to_tvp(self) -> str:

        return (

            f"[TVP] {'✅' if self.status == 'completed' else '❌'} "

            f"{self.agent_emoji}@{self.agent_name} 完成阶段[{self.stage.value}] "

            f"({len(self.tool_calls)}次工具调用, {self.duration_s:.1f}s)"

        )





# ═══════════════════════════════════════════════════════════════

# AgentPipeline — 长链任务多Agent阶段切换 — [v10-ready]

# ═══════════════════════════════════════════════════════════════





class AgentPipeline:

    """

    Agent流水线 — 长链任务的精准适配与灵活切换



    典型长链示例:

      "开发一个新功能" →

        S0: @dongcha(洞察) 分析需求 → 提取意图+关键词

        S1: @jingwei(经纬) 架构设计 → 模块划分+技术选型

        S2: @miaobi(妙笔) 编码实现 → 实际编码

        S3: @mingjing(明镜) 代码审校 → 质量检查

        S4: @tiewei(铁卫)  测试验证 → SG门禁

        S5: @gongzao(工造) 部署上线 → CI/CD

        S6: @shiguan(史官) 版本归档 → 变更记录



    每个阶段:

      - 自动切换到对应的Agent

      - 所有工具调用标注Agent

      - TVP透明声明每次切换

    """



    # 标准流水线模板

    STANDARD_PIPELINES = {

        "development": [

            (PipelineStage.ANALYZE, "dongcha", "需求分析与意图识别"),

            (PipelineStage.PLAN, "jingwei", "架构设计"),

            (PipelineStage.EXECUTE, "miaobi", "编码实现"),

            (PipelineStage.REVIEW, "mingjing", "代码审校"),

            (PipelineStage.VERIFY, "tiewei", "测试验证"),

            (PipelineStage.DEPLOY, "gongzao", "部署上线"),

        ],

        "content_creation": [

            (PipelineStage.ANALYZE, "dongcha", "需求分析"),

            (PipelineStage.PLAN, "wenzong", "创作规划"),

            (PipelineStage.EXECUTE, "miaobi", "内容创作"),

            (PipelineStage.REVIEW, "mingjing", "内容审校"),

            (PipelineStage.FORMAT, "jinshu", "格式化导出"),

            (PipelineStage.ARCHIVE, "shiguan", "版本归档"),

        ],

        "system_diagnosis": [

            (PipelineStage.ANALYZE, "qianli", "系统健康检查"),

            (PipelineStage.EXECUTE, "tiansuan", "性能数据分析"),

            (PipelineStage.REVIEW, "zhuiguang", "瓶颈定位"),

            (PipelineStage.PLAN, "jingwei", "优化方案设计"),

        ],

        "security_audit": [

            (PipelineStage.ANALYZE, "zhenshan", "安全扫描"),

            (PipelineStage.REVIEW, "luling", "合规检查"),

            (PipelineStage.PLAN, "jingwei", "修复方案"),

            (PipelineStage.EXECUTE, "gongzao", "执行修复"),

            (PipelineStage.VERIFY, "tiewei", "验证修复"),

        ],

        "system_audit": [

            (PipelineStage.ANALYZE, "jianheng", "5维全量审计扫描"),

            (PipelineStage.EXECUTE, "jianheng", "审计引擎执行"),

            (PipelineStage.REVIEW, "mingjing", "审计报告审校"),

            (PipelineStage.PLAN, "jingwei", "修复方案设计"),

            (PipelineStage.VERIFY, "tiewei", "修复验证"),

        ],

    }



    def __init__(

        self,

        tracker: ToolCallTracker,

        event_bus=None,

        pipeline_type: str = "development",

    ):

        self.tracker = tracker

        self.event_bus = event_bus

        self.pipeline_type = pipeline_type

        self.stages = self.STANDARD_PIPELINES.get(

            pipeline_type, self.STANDARD_PIPELINES["development"]

        )

        self._results: list[StageResult] = []

        self._current_stage_index = 0

        self._pipeline_id = f"ppl-{uuid.uuid4().hex[:8]}"

        self._output_handler: Callable | None = None



    def set_output_handler(self, handler: Callable[[str], None]):

        self._output_handler = handler

        self.tracker.set_output_handler(handler)



    def get_stage_count(self) -> int:

        return len(self.stages)



    def get_current_stage(self) -> tuple[PipelineStage, str, str] | None:

        if self._current_stage_index < len(self.stages):

            return self.stages[self._current_stage_index]

        return None



    def switch_to_stage(

        self, stage_index: int, task_goal: str, task_context: str = ""

    ) -> dict:

        """切换到指定阶段 → 声明Agent切换 + 更新Tracker上下文"""

        if stage_index >= len(self.stages):

            return {"error": "Stage index out of range"}



        stage, agent_id, description = self.stages[stage_index]

        info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})

        self._current_stage_index = stage_index



        self.tracker.set_context(

            agent_id=agent_id,

            stage=stage,

            task_id=f"{self._pipeline_id}-stage{stage_index}",

        )



        if stage_index > 0 and self._output_handler:

            prev_stage, prev_agent, _ = self.stages[stage_index - 1]

            prev_info = AGENT_CAPABILITY_MATRIX.get(prev_agent, {})

            switch_msg = (

                f"[TVP] 🎯 阶段切换: "

                f"{prev_info.get('emoji', '')}@{prev_info.get('name', prev_agent)} → "

                f"{info.get('emoji', '')}@{info.get('name', agent_id)} "

                f"[{stage.value}] {description}"

            )

            self._output_handler(switch_msg)

            if self.event_bus:

                try:

                    from core.shared.deepseek_driver import EventType, TianjiEvent



                    self.event_bus.publish(

                        TianjiEvent(

                            event_type=EventType.AGENT_SWITCH,

                            source="agent_pipeline",

                            payload={

                                "from_agent": prev_agent,

                                "to_agent": agent_id,

                                "stage": stage.value,

                                "description": description,

                                "pipeline_id": self._pipeline_id,

                            },

                        )

                    )

                except Exception:

                    pass



        return {

            "pipeline_id": self._pipeline_id,

            "stage_index": stage_index,

            "stage": stage.value,

            "agent_id": agent_id,

            "agent_name": info.get("name", agent_id),

            "agent_emoji": info.get("emoji", "🤖"),

            "description": description,

            "task_goal": task_goal,

            "tools_allowed": info.get("tools", []),

            "total_stages": len(self.stages),

            "next_stage": self.stages[stage_index + 1]

            if stage_index + 1 < len(self.stages)

            else None,

        }



    def record_stage_result(

        self, status: str, summary: str, duration_s: float

    ) -> StageResult:

        """记录阶段执行结果"""

        stage, agent_id, _ = self.stages[self._current_stage_index]

        info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})

        stage_calls = self.tracker.get_calls_by_stage(stage)



        result = StageResult(

            stage=stage,

            agent_id=agent_id,

            agent_name=info.get("name", agent_id),

            agent_emoji=info.get("emoji", "🤖"),

            status=status,

            summary=summary,

            tool_calls=stage_calls,

            duration_s=duration_s,

            next_stage=(

                self.stages[self._current_stage_index + 1][0]

                if self._current_stage_index + 1 < len(self.stages)

                else None

            ),

        )

        self._results.append(result)



        if self._output_handler:

            self._output_handler(result.to_tvp())



        return result



    def is_complete(self) -> bool:

        return self._current_stage_index >= len(self.stages) - 1



    def get_pipeline_summary(self) -> dict:

        total_calls = sum(len(r.tool_calls) for r in self._results)

        total_duration = sum(r.duration_s for r in self._results)

        return {

            "pipeline_id": self._pipeline_id,

            "pipeline_type": self.pipeline_type,

            "total_stages": len(self.stages),

            "completed_stages": len(self._results),

            "stage_results": [

                {

                    "stage": r.stage.value,

                    "agent": f"{r.agent_emoji} {r.agent_name}",

                    "status": r.status,

                    "tool_calls": len(r.tool_calls),

                    "duration_s": r.duration_s,

                }

                for r in self._results

            ],

            "total_tool_calls": total_calls,

            "total_duration_s": total_duration,

        }





# 向后兼容/任务约定别名: PipelineOrchestrator

PipelineOrchestrator = AgentPipeline

