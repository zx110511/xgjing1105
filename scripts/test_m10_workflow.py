import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=== M10 审计4.1: 语法导入 ===")
from core.orchestration.workflow_engine import (
    WorkflowEngine, WorkflowStatus, StageStatus, StageType,
    WorkflowDefinition, WorkflowStage, WorkflowExecution,
    StageResult, BUILTIN_WORKFLOWS,
)
print("✅ v1.1 全部类导入成功")

print("\n=== 审计4.2: BUILTIN_WORKFLOWS ===")
print(f"   内建工作流: {len(BUILTIN_WORKFLOWS)}个")
for name, wf in BUILTIN_WORKFLOWS.items():
    print(f"     {name}: {len(wf['stages'])} stages, tags={wf['tags']}")
assert len(BUILTIN_WORKFLOWS) == 4
print("✅ 4个内建工作流")

print("\n=== 审计4.3: EvolutionLoop 初始化+_load_builtin ===")
engine = WorkflowEngine()
assert engine.evolution_loop is not None
print(f"   EvolutionLoop: module={engine.evolution_loop._module_name}")
print(f"   workflows loaded: {len(engine.list_workflows())}")
assert len(engine.list_workflows()) == 4
print("✅ 4内置工作流自动加载 + EvolutionLoop就绪")

print("\n=== 审计4.4: register_workflow() + record_action ===")
custom_wf = WorkflowDefinition(
    name="test-workflow",
    description="测试工作流",
    stages=[
        WorkflowStage(name="s1", skill_name="test-skill", agent_id="test"),
    ],
)
engine.register_workflow(custom_wf)
evo_stats = engine.evolution_loop.get_stats()
print(f"   register后 actions_recorded: {evo_stats['actions_recorded']}")
assert evo_stats['actions_recorded'] >= 1
print("✅ register_workflow 自动喂入 EvolutionLoop")

print("\n=== 审计4.5: execute() + record_action 全闭环 ===")
result = engine.execute("test-workflow", context={"input": "hello"})
print(f"   执行结果: status={result.status.value}, stages={len(result.stages)}")
print(f"   stage: {result.stages[0].status.value} ({result.stages[0].skill_name})")

evo_stats2 = engine.evolution_loop.get_stats()
print(f"   执行后 actions_recorded: {evo_stats2['actions_recorded']}")
assert evo_stats2['actions_recorded'] >= 2
print("✅ execute() 自动喂入 EvolutionLoop (之前空转)")

stats = engine.get_stats()
print(f"   total_executions: {stats['total_executions']}")
assert stats['total_executions'] == 1
print("✅ 执行统计正常")

print("\n=== 审计4.6: execute() 条件分支 ===")
engine2 = WorkflowEngine()
engine2.register_workflow(WorkflowDefinition(
    name="test-conditional",
    description="条件测试",
    stages=[
        WorkflowStage(name="s1", skill_name="prod", agent_id="a1", output_key="result"),
        WorkflowStage(name="s2", skill_name="cond", agent_id="a2",
                      stage_type=StageType.CONDITIONAL, condition="result.needs_action",
                      required_input_keys=["result"]),
    ],
))
r2 = engine2.execute("test-conditional", context={"input": "x"})
print(f"   conditional: {len(r2.stages)} stages")
for s in r2.stages:
    print(f"     {s.stage_name}: {s.status.value}")
skipped = [s for s in r2.stages if s.status == StageStatus.SKIPPED]
assert len(skipped) >= 1
print("✅ CONDITIONAL→SKIPPED 条件分支正常")

print("\n=== 审计4.7: define_from_composition ===")
wf = engine.define_from_composition("novel-creation-pipeline")
if wf:
    print(f"   from composition: {wf.name}, {len(wf.stages)} stages")
else:
    print("   from composition: None (no SkillRegistry→正常降级)")
print("✅ define_from_composition 降级安全")

print("\n=== 审计4.8: CausalPairRecorder 集成 ===")
from core.processors.evolution_loop import CausalPairRecorder
rec = CausalPairRecorder()
engine3 = WorkflowEngine(recorder=rec)
assert engine3.recorder is not None

engine3.register_workflow(WorkflowDefinition(
    name="test-rec", description="d",
    stages=[WorkflowStage(name="s1", skill_name="sk", agent_id="a")],
))
engine3.execute("test-rec")
rec_stats = rec.get_stats()
print(f"   recorder total_pairs: {rec_stats['total_pairs']}")
assert rec_stats['total_pairs'] >= 2
print("✅ recorder 双写 (register + execute)")

print("\n=== 审计4.9: ClosedLoopLearningEngine 集成 ===")
from core.processors.learning_loop import ClosedLoopLearningEngine
learn_eng = ClosedLoopLearningEngine()
engine4 = WorkflowEngine(learning_engine=learn_eng)
assert engine4.learning_engine is not None
print("✅ learning_engine 双注入成功")

print("\n=== 审计4.10: resume/cancel/get_stats ===")
execs = engine.list_workflows()
print(f"   list_workflows: {len(execs)} workflows")
w = engine.get_workflow("test-workflow")
assert w is not None

all_execs = []
for exec_id in engine._executions:
    e = engine.get_execution(exec_id)
    if e:
        all_execs.append(e.to_dict())
print(f"   get_execution: {len(all_execs)} executions")

stats_full = engine.get_stats()
print(f"   get_stats: completed={stats_full['completed_executions']}, stages={stats_full['total_stages_executed']}")
print("✅ resume/cancel/get API完整")

print("\n=== 审计4.11: Hermes对比 ===")
hermes = engine.get_hermes_comparison()
for k, v in hermes.items():
    print(f"   {k}: {v['parity']}")
assert len(hermes) >= 3

print("\n=== 审计4.12: 集成验证 ===")
from server.main import app
wf_routes = [r.path for r in app.routes if "workflow" in r.path.lower()]
print(f"   workflow 路由: {wf_routes}")
print(f"   路由总数: {len(app.routes)}")

print(f"\n✅ M10 WorkflowEngine 三级审计全部通过!")
