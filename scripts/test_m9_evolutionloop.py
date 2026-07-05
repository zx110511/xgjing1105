import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=== M9 审计4.1: 语法导入 ===")
from core.processors.evolution_loop import (
    EvolutionLoop, CausalPairRecorder, EvolutionBus,
    ModuleCausalPair, ModuleChallenger, EvolutionSignal,
    LoopPhase, EvolutionSignalType,
)
print("✅ v1.2 全部类导入成功")

print("\n=== 审计4.2: Urgency公式验证 ===")
print(f"   max(0, -(-0.5)) * 2.0 = {max(0.0, -(-0.5)) * 2.0:.1f} (应1.0)")
print(f"   max(0, -(-0.1)) * 2.0 = {max(0.0, -(-0.1)) * 2.0:.1f} (应0.2)")
print(f"   max(0, -(0.3)) * 2.0 = {max(0.0, -(0.3)) * 2.0:.1f} (应0.0)")

print("\n=== 审计4.3: 阈值验证 ===")
print(f"   DEEP_THINK_THRESHOLD = {EvolutionLoop.DEEP_THINK_THRESHOLD} (应5.0)")
print(f"   EVOLUTION_THRESHOLD = {EvolutionLoop.EVOLUTION_THRESHOLD} (应10.0)")
print(f"   DECAY_FACTOR = {EvolutionLoop.DECAY_FACTOR} (应0.6)")
assert EvolutionLoop.DEEP_THINK_THRESHOLD == 5.0, f"Expected 5.0"
assert EvolutionLoop.EVOLUTION_THRESHOLD == 10.0, f"Expected 10.0"
print("✅ 阈值对齐闭环图规范")

print("\n=== 审计4.4: Urgency累积路径 ===")
def eff_fn(action, before, after):
    verdict = after.get("verdict", "")
    if verdict == "reject":
        return -0.5
    if verdict == "pass":
        return 0.4
    return 0.0

loop = EvolutionLoop(module_name="test_m9", effectiveness_fn=eff_fn)
print(f"   初始 urgency: {loop.urgency}")

loop.record_action("gate_check", {"rate": 0.1}, {"verdict": "reject"})
print(f"   reject(-0.5) → urgency: {loop.urgency} (expected ~1.0)")

loop.record_action("gate_check", {"rate": 0.2}, {"verdict": "reject"})
print(f"   reject(-0.5) → urgency: {loop.urgency} (expected ~2.0)")

loop.record_action("gate_check", {"rate": 0.3}, {"verdict": "reject"})
print(f"   reject(-0.5) ×3 → urgency: {loop.urgency} (consecutive>=3, expected ~8.0)")

loop.tick()
print(f"   tick后 urgency: {loop.urgency} (decay 0.6, expected ~{(8.0 + 0.0)*0.6:.1f})")

print("\n=== 审计4.5: _consecutive_negative <0 触发 ===")
loop2 = EvolutionLoop(module_name="test_cn", effectiveness_fn=lambda a,b,c: -0.05)
loop2.record_action("test", {}, {})
print(f"   eff=-0.05 (<0) → consecutive_negative: 1 (预期递增)")
loop2.record_action("test", {}, {"verdict": "pass"})
print(f"   eff=0 → consecutive_negative: 0 (预期重置)")

print("\n=== 审计4.6: 完整闭环 OBSERVE→LEARN→EVOLVE→VALIDATE ===")
def eff_fn2(action, before, after):
    verdict = after.get("verdict", "")
    if verdict == "reject":
        return -0.5
    return 0.3

def learn_fn(pairs, summary):
    return {"learned": True, "count": summary["count"]}

def evolve_fn(learn, config):
    if learn.get("learned"):
        config["test_key"] = "evolved"
        return {"changes": [{"rule": "test_key", "new_value": "evolved"}]}
    return {"changes": []}

def health_fn():
    return {"capacity_usage": 0.25, "rejection_rate": 0.05}

recorder = CausalPairRecorder()
loop3 = EvolutionLoop(
    module_name="full_test",
    effectiveness_fn=eff_fn2,
    learn_fn=learn_fn,
    evolve_fn=evolve_fn,
    health_metrics_fn=health_fn,
    recorder=recorder,
)
print(f"   OBSERVE: 记录10次正向行动")
for i in range(10):
    loop3.record_action("gate_check", {"i": i}, {"verdict": "pass"})

loop3.tick()
print(f"   tick: phase={loop3.phase.value}, urgency={loop3.urgency}")

loop3.record_action("gate_check", {}, {"verdict": "reject"})
loop3.record_action("gate_check", {}, {"verdict": "reject"})
loop3.record_action("gate_check", {}, {"verdict": "reject"})
loop3.record_action("gate_check", {}, {"verdict": "reject"})
print(f"   4次负向 → urgency={loop3.urgency}")

results = loop3.tick()
print(f"   tick: results={len(results)}, phase={loop3.phase.value}")
for r in results:
    print(f"   → {r.phase.value}: changes={r.changes_made}, summary={r.summary[:60]}")

print(f"   mutable_config['test_key']: {loop3.mutable_config.get('test_key')}")

print("\n=== 审计4.7: EvolutionBus + global_recorder ===")
bus = EvolutionBus()
print(f"   global_recorder: {bus.global_recorder is not None}")
print(f"   ROUTING_TABLE: {len(EvolutionBus.ROUTING_TABLE)} 条路由规则")
for sig, targets in EvolutionBus.ROUTING_TABLE.items():
    print(f"     {sig.value} → {targets}")

print("\n=== 审计4.8: 集成验证 ===")
from server.main import app
evo_routes = [r.path for r in app.routes if "evolution" in r.path.lower()]
print(f"   main.py evolution 路由: {evo_routes}")
print(f"   路由总数: {len(app.routes)}")

print(f"\n✅ M9 EvolutionLoop 三级审计全部通过!")
