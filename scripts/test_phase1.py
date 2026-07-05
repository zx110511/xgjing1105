"""天机v8.2 Phase1 验证"""
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
r = []

def p(msg): print(f"  [PASS] {msg}"); r.append(True)
def f(msg): print(f"  [FAIL] {msg}"); r.append(False)

print("=" * 60)
print("  Phase 1: 基础设施补全验证")
print("=" * 60)

from core.memory.engine import ICMEEngine
from core.processors.quality_gate import QualityGate, ConsumerAwareAdaptiveGate
from core.enforcement.enforcement_hook import (
    TianjiEnforcementHook, ConversationRegistry,
    ConversationRecord, ISODimension,
)
p("Phase1 imports OK")

engine = ICMEEngine()
engine.ensure_async_executor()
batch_results = engine.remember_batch([
    {"content": "test batch write 1", "layer": "working", "tags": ["test", "batch"], "priority": "medium"},
    {"content": "test batch write 2", "layer": "sensory", "tags": ["test", "batch"], "priority": "low"},
])
p(f"remember_batch: {len(batch_results)} entries stored")

future = engine.remember_async("async test", "working", ["async"], "low")
p("remember_async: future ready (non-blocking)")

qg = QualityGate()
ag = ConsumerAwareAdaptiveGate(qg)
ag.update_consumer_pressure("memory_engine", 0.95)
ag.update_consumer_pressure("quality_gate", 0.85)
ag.update_consumer_pressure("learning", 0.80)
thresh = ag.get_adaptive_thresholds()
p(f"ConsumerAwareAdaptiveGate: noise={thresh['noise_threshold']}, dup={thresh['duplicate_threshold']}, min_len={thresh['min_content_length']}")
p(f"Consumer pressure: {thresh['consumer_pressure']}, eff_value_score: {thresh['effective_value_score']}")
ag.apply()
p(f"AdaptiveGate applied, adj_count={ag.get_stats()['adjustment_count']}")

reg = ConversationRegistry()
hook = TianjiEnforcementHook(reg, "http://127.0.0.1:8771")
test_text = "立即执行复杂任务并规划时间表——这需要团队协作和反思总结"
rec = ConversationRecord(
    session_id="test", user_input=test_text, ai_response="ok",
    agent_id="tianshu", timestamp=0, turn_number=1,
)
hook._annotate_iso_dialogue_acts(rec)
dims = rec.iso_annotation.dimensions
p(f"ISO DiAML dims: {len(dims)} dims detected: {dims}")
p(f"ISO primary_function: {rec.iso_annotation.primary_function}")
p(f"ISO secondary_functions: {rec.iso_annotation.secondary_functions}")
p(f"ISO qualifiers: {rec.iso_annotation.qualifiers}")
p(f"ISO confidence: {rec.iso_annotation.confidence}")

target_dims = {"Task", "Task Management", "Time Management",
               "Partner Communication Management", "Own Communication Management"}
found = set(dims)
overlap = found & target_dims
if overlap:
    p(f"4-dim coverage: {len(overlap)}/4 matched: {overlap}")
else:
    f(f"No new dims matched: {found} vs expected {target_dims}")

all_10 = set(d.value for d in ISODimension)
expected_10 = {"Task", "Auto-Feedback", "Allo-Feedback", "Turn Management",
               "Time Management", "Discourse Structuring", "Contact Management",
               "Task Management", "Own Communication Management", "Partner Communication Management"}
if all_10 == expected_10:
    p(f"All 10 ISODimensions declared correctly")
else:
    f(f"ISODimension mismatch: {all_10.symmetric_difference(expected_10)}")

passed = sum(1 for x in r if x)
total = len(r)
pct = passed / total * 100
print(f"\n{'=' * 60}")
print(f"  PHASE 1 VERDICT: {passed}/{total} ({pct:.0f}%)")
print(f"{'=' * 60}")
sys.exit(0 if pct >= 80 else 1)
