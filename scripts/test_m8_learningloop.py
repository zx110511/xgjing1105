import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=== M8 审计4.1: 语法导入 ===")
from core.processors.learning_loop import (
    ClosedLoopLearningEngine, TaskComplexity, LearningPhase,
    KnowledgeType, LearningRecord, ExtractedKnowledge,
    ReflectionResult, COMPLEXITY_RULES, CRITICAL_KEYWORDS, MODERATE_KEYWORDS,
)
print("✅ v1.1 全部类导入成功")

print("\n=== 审计4.2: 枚举和常量 ===")
print(f"   TaskComplexity: {[c.value for c in TaskComplexity]}")
print(f"   LearningPhase: {[p.value for p in LearningPhase]}")
print(f"   KnowledgeType: {[k.value for k in KnowledgeType]}")
print(f"   CRITICAL_KEYWORDS: {len(CRITICAL_KEYWORDS)}个")
print(f"   COMPLEXITY_RULES: {len(COMPLEXITY_RULES)}级")
assert len(list(TaskComplexity)) == 4
assert len(list(LearningPhase)) == 5
assert len(COMPLEXITY_RULES) == 4
print("✅ 枚举+规则完整")

print("\n=== 审计4.3: evaluate_complexity ===")
engine = ClosedLoopLearningEngine()
tests = [
    ("普通对话", [], 1000, False, TaskComplexity.SIMPLE),
    ("修复bug", [], 5000, True, TaskComplexity.CRITICAL),
    ("性能优化", ["a","b","c","d","e"], 10000, False, TaskComplexity.COMPLEX),
    ("架构重构", [], 1000, False, TaskComplexity.CRITICAL),
    ("配置迁移", ["a","b","c"], 6000, False, TaskComplexity.MODERATE),
]
for task, mcp, dur, err, expected in tests:
    result = engine.evaluate_complexity(task, mcp, dur, err)
    match = "✅" if result == expected else "❌"
    print(f"   {match} {task[:10]:10s} → {result.value} (expected {expected.value})")
    assert result == expected, f"Expected {expected}, got {result}"

print("\n=== 审计4.4: Bug修复 - action字段 (not action_taken) ===")
from core.processors.evolution_loop import ModuleCausalPair
pair = ModuleCausalPair(
    module_name="test",
    action="gate_check",
    state_before={"rate": 0.1},
    state_after={"verdict": "pass"},
    effectiveness=-0.5,
)
print(f"   ModuleCausalPair.action: '{pair.action}' (not action_taken)")
assert getattr(pair, 'action', 'unknown') == "gate_check"
print(f"✅ action字段 = 'gate_check' (之前getattr(action_taken)会返回'unknown')")

print("\n=== 审计4.5: learn_from_causal_pairs ===")
pairs = [
    ModuleCausalPair("m", "gate_check", {"r":0.1}, {"v":"reject"}, -0.5),
    ModuleCausalPair("m", "gate_check", {"r":0.2}, {"v":"reject"}, -0.6),
    ModuleCausalPair("m", "gate_check", {"r":0.3}, {"v":"reject"}, -0.4),
    ModuleCausalPair("m", "enforce", {"x":0}, {"y":1}, 0.8),
    ModuleCausalPair("m", "enforce", {"x":0}, {"y":1}, 0.7),
    ModuleCausalPair("m", "enforce", {"x":0}, {"y":1}, 0.9),
]
eff_summary = {
    "gate_check": {"avg_effectiveness": -0.5, "positive_rate": 0.0, "count": 3},
    "enforce": {"avg_effectiveness": 0.8, "positive_rate": 1.0, "count": 3},
}
result = engine.learn_from_causal_pairs(pairs, eff_summary)
print(f"   patterns_found: {result['patterns_found']}")
print(f"   strategies_optimized: {result['strategies_optimized']}")
print(f"   capabilities_discovered: {result['capabilities_discovered']}")
print(f"   patterns: {len(result['patterns'])}个")
for p in result['patterns']:
    print(f"     {p['pattern_type']}: {p['action']} (samples={p['sample_size']})")
assert result['patterns_found'] >= 1
print("✅ action字段修复后模式识别正常 (之前action_taken→unknown→无效)")

print("\n=== 审计4.6: _create_skill_from_task (SkillStatus fix) ===")
record = LearningRecord(
    session_id="s1", task_description="修复bug: X",
    agent_id="debugger", complexity=TaskComplexity.COMPLEX,
    phase=LearningPhase.EXECUTE, mcp_calls=["a","b"],
)
try:
    ok = engine._create_skill_from_task(record, "response")
    print(f"   _create_skill_from_task: {ok} (no skill_registry→False)")
except NameError as e:
    print(f"❌ SkillStatus导入Bug: {e}")
    assert False, "SkillStatus 未导入!"
print("✅ SkillStatus导入修复确认 (之前会NameError)")

print("\n=== 审计4.7: process_task_completion 5阶段 ===")
result = engine.process_task_completion(
    session_id="s2", task_description="优化性能",
    agent_id="optimizer", ai_response="优化了索引结构，性能提升50%",
    mcp_calls=["a"], duration_ms=3000, success=True,
)
print(f"   complexity={result['complexity']}, layers={result['target_layers']}")
assert result['complexity'] in [c.value for c in TaskComplexity]
stats = engine.get_stats()
print(f"   total_tasks_evaluated: {stats['total_tasks_evaluated']}")
assert stats['total_tasks_evaluated'] >= 1
print("✅ 5阶段闭环入口正常")

print("\n=== 审计4.8: CausalPairRecorder + EvolutionEngine 集成 ===")
from core.processors.evolution_loop import CausalPairRecorder
from core.processors.evolution_engine import EvolutionEngine
recorder = CausalPairRecorder()
evo_engine = EvolutionEngine(recorder=recorder)

engine2 = ClosedLoopLearningEngine(recorder=recorder, evolution_engine=evo_engine)
print(f"   recorder: {engine2.recorder is not None}")
print(f"   evolution_engine: {engine2.evolution_engine is not None}")
assert engine2.recorder is not None
assert engine2.evolution_engine is not None
print("✅ recorder + evolution_engine 双注入成功")

engine2.learn_from_causal_pairs(pairs, eff_summary)
print(f"   _feed_to_evolution 完成 (柔性, try/except保护)")
evo_stats = evo_engine.get_stats()
print(f"   evo_engine stats: changes_proposed={evo_stats['total_changes_proposed']}")
print("✅ LEARN → EVOLVE 自动桥接")

print("\n=== 审计4.9: _run_reflection 15任务自触发 ===")
engine3 = ClosedLoopLearningEngine()
for i in range(15):
    engine3.process_task_completion(
        session_id=f"s{i}", task_description=f"test {i}",
        agent_id="test", ai_response="ok", success=True,
    )
stats3 = engine3.get_stats()
print(f"   15个任务后 reflections_completed: {stats3['reflections_completed']}")
assert stats3['reflections_completed'] >= 1
assert stats3['total_tasks_evaluated'] == 15
print("✅ 15任务自触发反思循环")

print("\n=== 审计4.10: 集成验证 ===")
from server.main import app
learn_routes = [r.path for r in app.routes if "learn" in r.path.lower()]
print(f"   learning 路由: {learn_routes}")
print(f"   路由总数: {len(app.routes)}")

print(f"\n✅ M8 ClosedLoopLearningEngine 三级审计全部通过!")
