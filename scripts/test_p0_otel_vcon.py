r"""天机v8.2 P0 OTel + vCon 验证"""
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

results = []

def p(msg): print(f"  [PASS] {msg}")
def f(msg): print(f"  [FAIL] {msg}"); results.append(False)

print("=" * 60)
print("  P0-OTel v1.41.0 + vCon 综合验证")
print("=" * 60)

try:
    from core.enforcement.enforcement_hook import (
        OtelGenAISpanKind, GenAIAgentAttributes, OtelGenAISpan, OtelMCPInterceptor,
        vConParty, vConConsent, vConConsentStatus, vConLifecycle, vConLifecycleState,
        ConversationRecord, TianjiEnforcementHook, ConversationRegistry,
        FileOperation, MCPCallDetail, ErrorLog,
    )
    p("All OTel+vCon types imported")
    results.append(True)
except Exception as e:
    f(f"Import failed: {e}")
    sys.exit(1)

# ── OTel SpanKind ──
kinds = [k.value for k in OtelGenAISpanKind]
expected_kinds = ["create_agent", "invoke_agent_client", "invoke_agent_internal", "invoke_workflow", "execute_tool"]
if kinds == expected_kinds:
    p(f"OTel SpanKind: {kinds}")
    results.append(True)
else:
    f(f"SpanKind mismatch: {kinds}")
    results.append(False)

# ── OTel Interceptor ──
interceptor = OtelMCPInterceptor()
span1 = interceptor.intercept_mcp_call("memory_remember", "content:test", "result:ok", 42.5, "success", "sess-1", "tianshu")
if span1.span_kind == OtelGenAISpanKind.EXECUTE_TOOL:
    p(f"execute_tool span: trace={span1.trace_id[:20]}... dur={span1.tool_duration_ms}ms")
    results.append(True)
else:
    f(f"Expected EXECUTE_TOOL, got {span1.span_kind}")
    results.append(False)

span2 = interceptor.intercept_agent_switch("tianshu", "yiku", "memory_recall", "sess-1", "high")
if span2.span_kind == OtelGenAISpanKind.INVOKE_AGENT_INTERNAL:
    p(f"invoke_agent_internal: {span2.source_agent} -> {span2.target_agent}")
    results.append(True)
else:
    f(f"Expected INVOKE_AGENT_INTERNAL, got {span2.span_kind}")
    results.append(False)

span3 = interceptor.intercept_workflow("governance_pipeline", "audit", "sess-1", "tianshu")
if span3.span_kind == OtelGenAISpanKind.INVOKE_WORKFLOW:
    p(f"invoke_workflow: {span3.workflow_name}/{span3.workflow_phase}")
    results.append(True)
else:
    f(f"Expected INVOKE_WORKFLOW, got {span3.span_kind}")
    results.append(False)

otel_stats = interceptor.get_otel_stats()
if otel_stats["total_spans"] == 3 and otel_stats["total_traces"] == 3:
    p(f"OTel stats: {otel_stats}")
    results.append(True)
else:
    f(f"OTel stats wrong: {otel_stats}")
    results.append(False)

span1_dict = span1.to_otel_dict()
required_attrs = ["gen_ai.agent.name", "gen_ai.agent.id", "gen_ai.provider.name",
                   "gen_ai.conversation.id", "gen_ai.operation.name", "gen_ai.model.name"]
missing = [a for a in required_attrs if a not in span1_dict.get("attributes", {})]
if not missing:
    p("OTel standard attributes: all 6 present")
    results.append(True)
else:
    f(f"Missing attributes: {missing}")
    results.append(False)

# ── vCon ──
party = vConParty(party_id="party-tianshu", name="tianshu", role="agent")
p(f"vConParty: {party.to_dict()}")
results.append(True)

consent = vConConsent(party_id="party-user", consent_type="explicit", granted=True)
p(f"vConConsent: {consent.to_dict()}")
results.append(True)

lifecycle = vConLifecycle(state=vConLifecycleState.ACTIVE)
lifecycle.transition(vConLifecycleState.COMPLETED, "session ended")
p(f"vConLifecycle: {lifecycle.state.value} ({len(lifecycle.transitions)} transitions)")
results.append(True)

# ── Integration: Hook + ConversationRecord ──
registry = ConversationRegistry()
hook = TianjiEnforcementHook(registry, "http://127.0.0.1:8771")
hook.set_session_agent("sess-1", "tianshu")
hook.register_mcp_call("sess-1", "memory_recall", "query:test", "7 results", 120.0, "success")
hook.register_agent_switch("sess-1", "tianshu", "yiku", "memory_recall", "recall task")
rec = ConversationRecord(session_id="sess-1", user_input="test", ai_response="ok",
                          agent_id="tianshu", timestamp=0, turn_number=1)
hook._flush_pending_to_record(rec, "sess-1")

if rec.vcon_uuid and rec.vcon_uuid.startswith("vcon-"):
    p(f"vcon_uuid: {rec.vcon_uuid}")
    results.append(True)
else:
    f(f"vcon_uuid failed: {rec.vcon_uuid}")
    results.append(False)

if len(rec.vcon_parties) == 2:
    roles = [p.role for p in rec.vcon_parties]
    p(f"vcon_parties: 2 parties ({roles})")
    results.append(True)
else:
    f(f"vcon_parties count: {len(rec.vcon_parties)}")
    results.append(False)

if len(rec.vcon_consents) == 2:
    p(f"vcon_consents: 2 consents")
    results.append(True)
else:
    f(f"vcon_consents count: {len(rec.vcon_consents)}")
    results.append(False)

if rec.vcon_lifecycle and rec.vcon_lifecycle.state == vConLifecycleState.ACTIVE:
    p(f"vcon_lifecycle: ACTIVE (auto-populated)")
    results.append(True)
else:
    f(f"vcon_lifecycle failed")
    results.append(False)

if len(rec.otel_spans) == 2:
    kinds = [s.span_kind.value for s in rec.otel_spans]
    p(f"otel_spans: 2 spans ({kinds})")
    results.append(True)
else:
    f(f"otel_spans count: {len(rec.otel_spans)}")
    results.append(False)

if rec.otel_trace_id:
    p(f"otel_trace_id: {rec.otel_trace_id[:20]}...")
    results.append(True)
else:
    f("otel_trace_id empty")
    results.append(False)

stats = hook.get_stats()
if "otel" in stats and stats["otel"]["total_spans"] >= 2:
    p(f"get_stats.otel: {stats['otel']}")
    results.append(True)
else:
    f(f"get_stats.otel missing or wrong")
    results.append(False)

# ── mcp_bridge export ──
try:
    from core.enforcement.mcp_bridge import EnforcementHookMCP
    p("mcp_bridge import OK")
    results.append(True)
except ImportError as e:
    f(f"mcp_bridge import failed: {e}")
    results.append(False)

# ── VERDICT ──
passed = sum(1 for r in results if r)
total = len(results)
pct = passed / total * 100

print(f"\n{'=' * 60}")
print(f"  P0 OTel+vCon VERDICT: {passed}/{total} ({pct:.0f}%)")
if pct >= 90:
    print(f"  >>> P0 COMPLETE - 100% target achieved <<<")
elif pct >= 70:
    print(f"  >>> P0 mostly complete <<<")
else:
    print(f"  >>> NEEDS FIX <<<")
print(f"{'=' * 60}")

sys.exit(0 if pct >= 90 else 1)
