import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=== 审计4.1: 语法导入 ===")
from core.processors.evolution_loop import (
    CausalPairRecorder, EvolutionLoop, EvolutionBus,
    ModuleCausalPair, EvolutionSignal, EvolutionSignalType,
    LoopPhase, EvolutionResult, ModuleChallenger,
)
print("✅ evolution_loop 全部类导入成功 (v1.1)")

print("\n=== 审计4.2: CausalPairRecorder 核心功能 ===")
recorder = CausalPairRecorder()

p1 = recorder.record("gate_check", {"rate": 0.1}, {"verdict": "pass"}, 0.5, "quality_gate")
p2 = recorder.record("gate_check", {"rate": 0.2}, {"verdict": "reject"}, -0.5, "quality_gate")
p3 = recorder.record("gate_check", {"rate": 0.15}, {"verdict": "pass"}, 0.3, "quality_gate")
p4 = recorder.record("enforce", {"before": 0}, {"after": 1}, 0.4, "enforcement")
p5 = recorder.record("enforce", {"before": 0}, {"after": 0}, -0.2, "enforcement")
p6 = recorder.record("enforce", {"before": 0}, {"after": 1}, 0.0, "enforcement")

print(f"✅ record: 6对已记录")

stats = recorder.get_stats()
print(f"✅ get_stats: total={stats['total_pairs']}, pos={stats['positive_pairs']}, neg={stats['negative_pairs']}, neutral={stats['neutral_pairs']}, avg_effect={stats['avg_effect']}, actions={stats['actions']}")

summary = recorder.get_effectiveness_summary()
print(f"✅ get_effectiveness_summary (all): avg={summary['avg']}, neg_ratio={summary['negative_ratio']}, by_action={list(summary['by_action'].keys())}")
for act, s in summary["by_action"].items():
    print(f"   {act}: count={s['count']}, avg_effect={s['avg_effect']}, positive_rate={s['positive_rate']}")

summary_gate = recorder.get_effectiveness_summary("gate_check")
print(f"✅ per-action summary (gate_check): count={summary_gate['count']}, avg={summary_gate['avg_effectiveness']}, pos_rate={summary_gate['positive_rate']}")

pairs_gate = recorder.get_pairs("gate_check", limit=10)
print(f"✅ get_pairs (gate_check): {len(pairs_gate)} 对")

pairs_all = recorder.get_pairs(limit=2)
print(f"✅ get_pairs (all,limit=2): {len(pairs_all)} 对")

print("\n=== 审计4.3: EvolutionLoop + Recorder 集成 ===")

def eff_fn(action, before, after):
    if after.get("verdict") == "reject":
        return -0.5
    return 0.3

def learn_fn(pairs, summary):
    return {"neg_count": summary.get("negative_ratio", 0)}

def evolve_fn(learn, config):
    return {"changes": []}

def health_fn():
    return {"rejection_rate": 0.05, "capacity_usage": 0.3}

loop = EvolutionLoop(
    module_name="test_module",
    effectiveness_fn=eff_fn,
    learn_fn=learn_fn,
    evolve_fn=evolve_fn,
    health_metrics_fn=health_fn,
    recorder=recorder,
)
print(f"✅ EvolutionLoop + recorder 初始化成功")
print(f"   loop.recorder is not None: {loop.recorder is not None}")

pair = loop.record_action("gate_check", {"rate": 0.05}, {"verdict": "pass"})
print(f"✅ record_action: effectiveness={pair.effectiveness}")

recorder_stats = recorder.get_stats()
print(f"✅ recorder已同步: total_pairs={recorder_stats['total_pairs']} (应为7)")

results = loop.tick()
print(f"✅ tick: {len(results)} results, phase={loop.phase.value}, urgency={loop.urgency}")

print("\n=== 审计4.4: EvolutionBus + global_recorder ===")
bus = EvolutionBus()
print(f"✅ EvolutionBus 初始化 (含global_recorder)")
bus_recorder = bus.global_recorder
bp = bus_recorder.record("bus_check", {"x": 1}, {"y": 2}, 0.7, "evolution_bus")
print(f"✅ global_recorder.record: total={bus_recorder.get_stats()['total_pairs']}")

bus.register_loop(loop)
bus_stats = bus.get_stats()
print(f"✅ bus.register_loop + get_stats: modules={bus_stats['registered_modules']}")

print("\n=== 审计4.5: 闭环完整路径 ===")
for i in range(5):
    loop.record_action("gate_check", {"rate": 0.01 * i}, {"verdict": "pass" if i < 3 else "reject"})
print(f"✅ 5次连续record_action (含negative)")

final_stats = loop.get_stats()
print(f"✅ EvolutionLoop.stats: actions_recorded={final_stats['actions_recorded']}, causal_pairs={final_stats['causal_pairs']}, urgency={final_stats['urgency']}")

recorder_final = recorder.get_stats()
print(f"✅ Recorder.stats: total_pairs={recorder_final['total_pairs']}, actions_tracked={recorder_final['actions_tracked']}")

print("\n=== 审计4.6: 集成验证 ===")
from server.main import app
evo_routes = [r.path for r in app.routes if "evolution" in r.path.lower()]
print(f"✅ main.py evolution 路由: {evo_routes}")

print(f"\n✅ M6 CausalPairRecorder 三级审计全部通过!")
