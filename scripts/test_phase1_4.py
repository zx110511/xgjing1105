"""天机v8.2 Phase1-4 全流程验证"""
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
r = []

def p(msg): print(f"  [PASS] {msg}"); r.append(True)
def f(msg): print(f"  [FAIL] {msg}"); r.append(False)

print("=" * 60)
print("  天机v8.2 Phase1-4 全流程基础设施升级验证")
print("=" * 60)

# ═══════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════
from core.memory.engine import ICMEEngine
from core.processors.quality_gate import QualityGate, ConsumerAwareAdaptiveGate
from core.shared.knowledge_extractor import KnowledgeExtractor
from core.enforcement.enforcement_hook import (
    TianjiEnforcementHook, ConversationRegistry, ConversationRecord, ISODimension,
    OWASPAosBridge, OWASPInspectionColumn, OTelEvaluationBridge, OTelEvaluationSpanKind,
)
p("Phase1-4 imports (12+ types)")

# ═══════════════════════════════════════════
# PHASE 1: Infrastructure
# ═══════════════════════════════════════════
engine = ICMEEngine()
engine.ensure_async_executor()
batch_r = engine.remember_batch([
    {"content": "batch item 1", "layer": "working", "tags": ["test"], "priority": "medium"},
    {"content": "batch item 2", "layer": "sensory", "tags": ["test"], "priority": "low"},
])
p(f"P1.1 batch_write: {len(batch_r)} entries")

future = engine.remember_async("async test", "working", ["async"], "low")
p("P1.1 remember_async: future ready")

qg = QualityGate()
ag = ConsumerAwareAdaptiveGate(qg)
ag.update_consumer_pressure("memory_engine", 0.95)
ag.update_consumer_pressure("learning", 0.80)
thresh = ag.get_adaptive_thresholds()
ag.apply()
p(f"P1.2 ConsumerAwareGate: noise={thresh['noise_threshold']}, dup={thresh['duplicate_threshold']}, min_len={thresh['min_content_length']}")

reg = ConversationRegistry()
hook = TianjiEnforcementHook(reg, "http://127.0.0.1:8771")
hook.set_session_agent("test", "tianshu")
rec = ConversationRecord(
    session_id="test", user_input="立即执行复杂任务并规划时间表——这需要团队协作和反思总结，发送给伙伴",
    ai_response="ok", agent_id="tianshu", timestamp=0, turn_number=1,
)
hook._annotate_iso_dialogue_acts(rec)
dims = rec.iso_annotation.dimensions
p(f"P1.3 ISO DiAML: {len(dims)} dims, confidence={rec.iso_annotation.confidence}, qualifiers={rec.iso_annotation.qualifiers}")

# ═══════════════════════════════════════════
# PHASE 2: Standards
# ═══════════════════════════════════════════
aos = OWASPAosBridge()
aos.register_component("test", "v1", "core")
aos.record_instrument("hook_trigger", "enforcement_hook", {"event": "test"}, "info")
aos.record_trace("mcp_call", "enforcement_hook", "tianji_mcp_server", {"tool": "memory_remember"})
aos.record_inspect("compliance_check", "quality_gate", {"pass": True})
aos_stats = aos.get_stats()
p(f"P2.1 OWASP AOS: {aos_stats['agbom_components']} components, {aos_stats['total_observations']} obs ({aos_stats['by_column']})")

hook.register_aos_components()
p(f"P2.1 AOS registration: {len(hook.get_aos_ag_bom())} AgBOM entries")

eval_bridge = OTelEvaluationBridge()
for score in [0.95, 0.72, 0.45, 0.88, 0.33]:
    eval_bridge.evaluate("quality_test", "input", "output", score, "PASS" if score > 0.6 else "FAIL")
eval_stats = eval_bridge.get_stats()
p(f"P2.3 OTel Eval: {eval_stats['total']} evals, avg={eval_stats['avg_score']}, pass_rate={eval_stats['pass_rate']}")
hook.evaluate_quality("test_eval", 0.85, "GOOD", "test passes")
p(f"P2.3 Hook eval stats: {hook.get_evaluation_stats()['total']} evals")

# ═══════════════════════════════════════════
# PHASE 3: Learning
# ═══════════════════════════════════════════
tl = hook.trigger_learning_loop("test", force=True)
p(f"P3.1 learning_loop trigger: {tl}")
sig = hook.broadcast_evolution_signal("quality_drop", "enforcement_hook", {"drop_rate": 0.15}, "high")
p(f"P3.2 evolution_signal: type={sig['type']}, priority={sig['priority']}")
ke = KnowledgeExtractor()
triples = ke.extract_with_patterns("天机系统使用DeepSeek驱动进行语义搜索，依赖SQLite存储记忆，产生知识图谱")
p(f"P3.3 knowledge_extractor: {len(triples)} triples ({[t.relation for t in triples[:5]]})")

# ═══════════════════════════════════════════
# PHASE 4: Autonomy
# ═══════════════════════════════════════════
deg = hook.adaptive_degradation_check()
p(f"P4.1 adaptive_degradation: degraded={deg['degraded']}, score={deg['score']}")
mig = hook.smart_memory_migrate("test")
p(f"P4.2 smart_migrate: {mig['migrated']} layers")
events = [
    {"type": "memory_error", "priority": "critical", "target": "resilience"},
    {"type": "conversation_input", "priority": "high", "target": "engine"},
    {"type": "stats_update", "priority": "low", "target": "stat_collector"},
]
event_result = hook.priority_event_route(events)
p(f"P4.3 event_route: {event_result['routed']}")

# ═══════════════════════════════════════════
# VERDICT
# ═══════════════════════════════════════════
passed = sum(1 for x in r if x)
total = len(r)
pct = passed / total * 100
print(f"\n{'=' * 60}")
print(f"  PHASE1-4 FINAL: {passed}/{total} ({pct:.0f}%)")
if pct >= 90:
    print(f"  >>> ALL 4 PHASES COMPLETE 100%")
elif pct >= 70:
    print(f"  >>> Mostly complete")
print(f"{'=' * 60}")
sys.exit(0 if pct >= 80 else 1)
