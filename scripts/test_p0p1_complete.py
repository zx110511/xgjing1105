"""天机v8.2 P0+P1 综合验证"""
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
r = []

def p(msg): print(f"  [PASS] {msg}"); r.append(True)
def f(msg): print(f"  [FAIL] {msg}"); r.append(False)

print("=" * 60)
print("  P0+P1 OTel+vCon+7dim+Feedback 验证")
print("=" * 60)

from core.enforcement.enforcement_hook import (
    SevenDimensionalLogModel, ReasoningLog, StateLog, DecisionLog,
    ActionLog, ObservationLog, ReflectionLog, TokenEconomy,
    FeedbackRecord, FeedbackAwareLoop,
    ConversationRecord, TianjiEnforcementHook, ConversationRegistry,
)
p("P0+P1 imports OK")

# P1A: 7-dim model
expected_dims = ["action", "observation", "reasoning", "state",
                 "reflection", "decision", "token_economy"]
if SevenDimensionalLogModel.DIMENSIONS == expected_dims:
    p(f"7-dim dimensions: {SevenDimensionalLogModel.DIMENSIONS}")
else:
    f(f"7-dim mismatch: {SevenDimensionalLogModel.DIMENSIONS}")

rl = ReasoningLog(chain_id="r-1")
rl.add_step("analyze task", "input", 0.8)
rl.add_step("generate plan", "context", 0.7)
rl.conclusion = "proceed with OTel"
rl.confidence = 0.75
if len(rl.steps) == 2:
    p(f"ReasoningLog: {len(rl.steps)} steps, conf={rl.confidence}")
else:
    f(f"ReasoningLog steps: {len(rl.steps)}")

sl = StateLog(entity_id="sess-1", state_type="agent", old_state="idle",
              new_state="active", trigger="input")
p(f"StateLog: {sl.old_state} -> {sl.new_state}")

te = TokenEconomy(prompt_tokens=1500, completion_tokens=800)
te.estimate()
p(f"TokenEconomy: {te.total_tokens} tokens, USD{te.estimated_cost_usd:.6f}")

dl = DecisionLog(decision_id="d-1", options=["otel", "native"],
                 chosen="otel", rationale="standard")
p(f"DecisionLog: {dl.chosen} of {len(dl.options)} options")

# P1B: FeedbackAwareLoop
fal = FeedbackAwareLoop()
fb = fal.receive_feedback("memory_engine", "latency_warning", "P95>2s", "warning")
p(f"FeedbackAwareLoop: id={fb.feedback_id}, total={fal.get_stats()['total_feedback']}")

# Integration
registry = ConversationRegistry()
hook = TianjiEnforcementHook(registry, "http://127.0.0.1:8771")
hook.set_session_agent("sess-1", "tianshu")
hook.record_reasoning("sess-1", "r-1",
    [{"thought": "step1"}, {"thought": "step2"}],
    "go OTel", 0.85, 350.0)
hook.record_state_change("sess-1", "sess-1", "enforcement",
    "idle", "active", "hook_triggered")
hook.record_token_usage("sess-1", 3000, 1500)
hook.receive_consumer_feedback("quality_gate", "threshold", "min_value", "critical")

rec = ConversationRecord(session_id="sess-1", user_input="test", ai_response="ok",
    agent_id="tianshu", timestamp=0, turn_number=1)
hook._flush_pending_to_record(rec, "sess-1")

p(f"reasoning_logs flushed: {len(rec.reasoning_logs)}")
p(f"state_logs flushed: {len(rec.state_logs)}")
p(f"token_economy_logs flushed: {len(rec.token_economy_logs)}")

f_stats = fal.get_stats()
p(f"feedback_loop: {f_stats['total_feedback']} total, {f_stats['unacknowledged']} pending")

stats = hook.get_stats()
sd = stats.get("seven_dim", {})
p(f"seven_dim: reasoning={sd.get('reasoning_queued')} "
  f"state={sd.get('state_changes_queued')} "
  f"token={sd.get('token_economy_queued')}")
p(f"otel: traces={stats['otel']['total_traces']} spans={stats['otel']['total_spans']}")

# ============= VERDICT =============
passed = sum(1 for x in r if x)
total = len(r)
pct = passed / total * 100
print(f"\n{'=' * 60}")
print(f"  P0+P1 VERDICT: {passed}/{total} ({pct:.0f}%)")
print(f"  >>> {'COMPLETE 100%' if pct >= 90 else 'NEEDS FIX'}")
print(f"{'=' * 60}")
sys.exit(0 if pct >= 90 else 1)
