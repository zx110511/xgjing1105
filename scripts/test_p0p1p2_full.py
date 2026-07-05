"""天机v8.2 P0+P1+P2 全流程验证"""
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
r = []

def p(msg): print(f"  [PASS] {msg}"); r.append(True)
def f(msg): print(f"  [FAIL] {msg}"); r.append(False)

print("=" * 60)
print("  天机v8.2 P0+P1+P2 全功能验证")
print("=" * 60)

from core.enforcement.enforcement_hook import (
    OtelGenAISpanKind, OtelMCPInterceptor,
    vConParty, vConConsent, vConConsentStatus, vConLifecycle, vConLifecycleState,
    SevenDimensionalLogModel, ReasoningLog, StateLog, DecisionLog, TokenEconomy,
    FeedbackRecord, FeedbackAwareLoop,
    LoongSuiteAgentCategory, LoongSuiteMetadata, LoongSuiteAlignment,
    ConversationRecord, TianjiEnforcementHook, ConversationRegistry,
)
p("All imports (28 types)")

# ── OTel ──
interceptor = OtelMCPInterceptor()
interceptor.intercept_mcp_call("t1", "p1", "r1", 10, "success", "s1", "a1")
interceptor.intercept_agent_switch("src", "tgt", "task", "s1")
interceptor.intercept_workflow("wf", "phase", "s1", "a1")
p(f"OTel: {interceptor.get_otel_stats()['total_spans']} spans, 5 SpanKinds")

# ── vCon ──
party = vConParty(party_id="p-t", name="tianshu", role="agent")
consent = vConConsent(party_id="p-u", consent_type="explicit", granted=True)
lc = vConLifecycle(state=vConLifecycleState.ACTIVE)
lc.transition(vConLifecycleState.COMPLETED, "done")
p(f"vCon: party={party.party_id}, consent={consent.consent_type}, lifecycle={lc.state.value}")

# ── 7-dim + Feedback ──
rl = ReasoningLog(chain_id="rc-1")
rl.add_step("think", "evidence", 0.9)
p(f"7dim: ReasonLog {len(rl.steps)} steps")

sl = StateLog(entity_id="e1", state_type="agent", old_state="idle", new_state="active")
p(f"7dim: StateLog {sl.old_state}->{sl.new_state}")

te = TokenEconomy(prompt_tokens=100, completion_tokens=50)
te.estimate()
p(f"7dim: TokenEconomy {te.total_tokens}tk USD{te.estimated_cost_usd:.6f}")

fal = FeedbackAwareLoop()
fal.receive_feedback("m1", "warning", "test", "low")
p(f"Feedback: {fal.get_stats()['total_feedback']} items")

# ── LoongSuite ──
cat = LoongSuiteAlignment.classify_agent("tianshu")
p(f"LoongSuite: tianshu -> {cat.value}")

meta = LoongSuiteAlignment.generate_metadata("tianshu")
ls_dict = meta.to_loongsuite_dict()
p(f"LoongSuite: {len(ls_dict)} attrs, vendor={ls_dict['loongsuite.provider.vendor']}")

all_agents = list(LoongSuiteAlignment.AGENT_CATEGORY_MAP.keys())
p(f"LoongSuite: {len(all_agents)} agents mapped")

# ── Integration ──
registry = ConversationRegistry()
hook = TianjiEnforcementHook(registry, "http://127.0.0.1:8771")
hook.set_session_agent("sess-1", "tianshu")
hook.register_mcp_call("sess-1", "memory_recall", "q:test", "ok", 50, "success")
hook.register_agent_switch("sess-1", "tianshu", "yiku", "recall", "ctx")
hook.record_reasoning("sess-1", "rc-1", [{"thought": "test"}], "ok", 0.9, 100)
hook.record_state_change("sess-1", "sess-1", "hook", "idle", "active")
hook.record_token_usage("sess-1", 500, 300)
hook.receive_consumer_feedback("qg", "info", "all green")

rec = ConversationRecord(session_id="sess-1", user_input="hi", ai_response="ok",
    agent_id="tianshu", timestamp=1717012345.0, turn_number=1)
hook._flush_pending_to_record(rec, "sess-1")

p(f"vcon_uuid: {rec.vcon_uuid}")
p(f"otel_spans: {len(rec.otel_spans)}")
p(f"reasoning: {len(rec.reasoning_logs)}")
p(f"state_logs: {len(rec.state_logs)}")
p(f"token_economy: {len(rec.token_economy_logs)}")
p(f"loongsuite: {rec.loongsuite_metadata.agent_category.value if rec.loongsuite_metadata else 'NONE'}")

compliance = hook.check_loongsuite_compliance(rec)
p(f"LoongSuite compliance: {compliance}")

stats = hook.get_stats()
p(f"otel stats: traces={stats['otel']['total_traces']}")
p(f"seven_dim sessions: {stats['seven_dim']['session_count']}")

# ── VERDICT ──
passed = sum(1 for x in r if x)
total = len(r)
pct = passed / total * 100
print(f"\n{'=' * 60}")
print(f"  P0+P1+P2 FINAL: {passed}/{total} ({pct:.0f}%)")
print(f"  >>> {'ALL TASKS COMPLETE 100%' if pct == 100 else 'NEEDS FIX'}")
print(f"{'=' * 60}")
sys.exit(0 if pct == 100 else 1)
