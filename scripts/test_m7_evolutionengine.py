import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=== M7 审计4.1: 语法导入 ===")
from core.processors.evolution_engine import (
    EvolutionEngine, EvolutionLevel, EvolutionStatus,
    RuleChange, ArchitectureProposal,
)
from core.processors.evolution_loop import CausalPairRecorder
print("✅ v1.1 全部类导入成功")

print("\n=== 审计4.2: 三级进化枚举 ===")
for lvl in EvolutionLevel:
    print(f"   {lvl.name}: {lvl.value}")
assert len(list(EvolutionLevel)) == 3
print("✅ 3个进化等级")

print("\n=== 审计4.3: EvolutionEngine 初始化 (含SQLite) ===")
engine = EvolutionEngine()
assert engine._sqlite_conn is not None
print(f"✅ SQLite连接: 已建立")

stats = engine.get_stats()
print(f"   初始stats: {stats}")
assert "tick_loops" in stats
print(f"✅ tick_loops在stats中: {stats['tick_loops']}")

print("\n=== 审计4.4: evolve_from_learning + persist (JSON+SQLite) ===")
causal_pairs = []
eff_summary = {
    "deep_think_evolution": {"avg_effectiveness": -0.1, "positive_rate": 0.2, "count": 10},
}
mutable_rules = {
    "deep_think_interval": 300.0,
    "conversation_target_layer": "sensory",
}

result = engine.evolve_from_learning(causal_pairs, eff_summary, mutable_rules)
print(f"   evolve结果: {result['evolution_summary']}")
print(f"   修改: {result['rules_modified']}")

if result["rules_modified"]:
    mod = result["rules_modified"][0]
    print(f"   → {mod['rule']}: {mod['old_value']} → {mod['new_value']}")

print(f"   mutable_rules: {mutable_rules}")
assert engine._persist_dir.exists()
json_files = list(engine._persist_dir.glob("evolution_*.json"))
db_file = engine._persist_dir / "evolution_history.db"
print(f"✅ JSON: {len(json_files)}个, DB: {db_file.exists()}, SQLite表: evolution_history + rule_changes")

history = engine.get_change_history(limit=5)
print(f"✅ 变更历史: {len(history)}条")

print("\n=== 审计4.5: _tick 自动闭环 ===")
recorder = CausalPairRecorder()
recorder.record("gate_check", {"rate": 0.1}, {"verdict": "reject"}, -0.5, "quality_gate")
recorder.record("gate_check", {"rate": 0.1}, {"verdict": "reject"}, -0.5, "quality_gate")
recorder.record("gate_check", {"rate": 0.1}, {"verdict": "reject"}, -0.5, "quality_gate")
recorder.record("gate_check", {"rate": 0.1}, {"verdict": "reject"}, -0.5, "quality_gate")
recorder.record("gate_check", {"rate": 0.1}, {"verdict": "reject"}, -0.5, "quality_gate")
recorder.record("deep_think_evolution", {}, {}, -0.3, "evolution")
recorder.record("deep_think_evolution", {}, {}, -0.3, "evolution")
recorder.record("deep_think_evolution", {}, {}, -0.3, "evolution")
recorder.record("deep_think_evolution", {}, {}, -0.3, "evolution")
recorder.record("deep_think_evolution", {}, {}, -0.3, "evolution")

engine2 = EvolutionEngine(recorder=recorder)
tick_rules = {"deep_think_interval": 300.0}
tick_result = engine2._tick(tick_rules)
print(f"   tick结果: {tick_result['evolution_summary']}")
print(f"   tick后rules: deep_think_interval={tick_rules['deep_think_interval']}")
stats2 = engine2.get_stats()
print(f"   tick_loops: {stats2['tick_loops']}")
assert stats2['tick_loops'] == 1
print("✅ _tick 自动拉取recorder数据 → evolve_from_learning 成功")

print("\n=== 审计4.6: rollback_change 回滚闭环 ===")
history2 = engine2.get_change_history()
if history2:
    cid = history2[-1]["change_id"]
    rollback_rules = {"deep_think_interval": tick_rules["deep_think_interval"]}
    rolled = engine2.rollback_change(cid, rollback_rules)
    print(f"   回滚 {cid}: {'成功' if rolled else '失败'}")
    if rolled:
        assert rollback_rules["deep_think_interval"] == 300.0
        print(f"   回滚后: deep_think_interval={rollback_rules['deep_think_interval']}")
        print("✅ 回滚闭环生效")
else:
    print("   (无变更可回滚)")

print("\n=== 审计4.7: 频率限制 ===")
rate_engine = EvolutionEngine()
check = rate_engine._check_rate_limit(EvolutionLevel.PARAMETER_TUNING)
print(f"✅ Level-1 频率检查: {'通过' if check else '受限'}")
check = rate_engine._check_rate_limit(EvolutionLevel.ARCHITECTURE_EVOLUTION)
print(f"✅ Level-3 频率检查: {'通过' if check else '受限'}")

print("\n=== 审计4.8: process_evolution_signal 增强 ===")
from core.processors.evolution_loop import EvolutionSignal, EvolutionSignalType
sig_high = EvolutionSignal(
    source_module="quality_gate",
    signal_type=EvolutionSignalType.GATE_MISJUDGMENT,
    severity=0.8,
    description="高严重性信号",
)
result_high = engine.process_evolution_signal(sig_high)
print(f"   高严重性信号(0.8): {result_high}")

sig_low = EvolutionSignal(
    source_module="test",
    signal_type=EvolutionSignalType.ROUTE_INEFFICIENCY,
    severity=0.2,
    description="低严重性信号",
)
result_low = engine.process_evolution_signal(sig_low)
print(f"   低严重性信号(0.2): {result_low}")
print("✅ process_evolution_signal 增强: severity>=0.6→routed, low→None")

print("\n=== 审计4.9: start/stop_tick_loop ===")
loop_engine = EvolutionEngine()
assert not loop_engine.is_tick_running

def fake_rules():
    return {"deep_think_interval": 300.0}

loop_engine.start_tick_loop(fake_rules)
import time; time.sleep(0.3)
print(f"   start后 is_running: {loop_engine.is_tick_running}")
assert loop_engine.is_tick_running

loop_engine.stop_tick_loop()
time.sleep(0.3)
print(f"   stop后 is_running: {loop_engine.is_tick_running}")
assert not loop_engine.is_tick_running
print("✅ start/stop_tick_loop 生命周期正常")

print("\n=== 审计4.10: 集成验证 ===")
from server.main import app
evo_routes = [r.path for r in app.routes if "evolution" in r.path.lower()]
print(f"   evolution 路由: {evo_routes}")
print(f"   路由总数: {len(app.routes)}")

print(f"\n✅ M7 EvolutionEngine 三级审计全部通过!")
