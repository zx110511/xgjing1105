r"""
P13-P14 7链Dashboard+API暴露链 集成测试
============================================
验证:
  P13: API暴露链 vCon+OTel+REST API 30项
  P14: 7链Dashboard+可视化 24项

总计: 54项检查
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

passed = 0
failed = 0
checks = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed, checks
    checks += 1
    if condition:
        passed += 1
        print(f"  [PASS] [{checks:02d}] {name}")
    else:
        failed += 1
        print(f"  [FAIL] [{checks:02d}] {name} — {detail}")


def banner(text: str):
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


banner("P13-P14 Integration Test: API Exposure + 7-Chain Dashboard")

banner("P13.1 — VConExporter 数据模型")
try:
    from core.orchestration.api_exposure import (
        VConPartyExport, VConConsentExport, VConRecordingExport,
        VConAnalysisExport, VConAttachmentExport, VConDocument,
        VConExporter, VConExportConfig, VConVersion,
        OTelMetricsExporter, OTelMetricDefinition, OTelMetricType,
        APIEndpointRegistry, APIEndpoint,
    )

    party = VConPartyExport(party_id="agent-001", name="天枢", role="agent")
    d = party.to_vcon_dict()
    check("VConPartyExport创建", party.party_id == "agent-001")
    check("VConPartyExport role", d["role"] == "agent")
    check("VConPartyExport provider", d["provider"] == "memory-engine-global")

    consent = VConConsentExport(consent_id="c-001", party_id="agent-001")
    cd = consent.to_vcon_dict()
    check("VConConsentExport consent_id", cd["consent_id"] == "c-001")
    check("VConConsentExport type", cd["consent_type"] == "explicit")
    check("VConConsentExport granted", cd["granted"] is True)
    check("VConConsentExport retention", cd["retention_days"] == 365)

    recording = VConRecordingExport(recording_id="r-001", session_id="sess-123",
                                     transcript="test conversation")
    rd = recording.to_vcon_dict()
    check("VConRecordingExport recording_id", rd["recording_id"] == "r-001")
    check("VConRecordingExport session_id", rd["session_id"] == "sess-123")
    check("VConRecordingExport has transcript_hash", "transcript_hash" in rd)

    analysis = VConAnalysisExport(analysis_id="a-001", recording_id="r-001",
                                   analysis_type="sentiment", confidence=0.92)
    ad = analysis.to_vcon_dict()
    check("VConAnalysisExport confidence", ad["confidence_final"] == 0.92)
    check("VConAnalysisExport type", ad["analysis_type"] == "sentiment")

    attachment = VConAttachmentExport(attachment_id="att-001", recording_id="r-001",
                                       file_name="screenshot.png", mime_type="image/png",
                                       size_bytes=102400)
    atd = attachment.to_vcon_dict()
    check("VConAttachmentExport mime_type", atd["mime_type"] == "image/png")
    check("VConAttachmentExport size_bytes", atd["size_bytes"] == 102400)

    doc = VConDocument(vcon_uuid="test-uuid", created_at="2026-05-30T00:00:00Z")
    doc.parties.append(party)
    doc.consents.append(consent)
    doc.recordings.append(recording)
    doc.analysis.append(analysis)
    doc.attachments.append(attachment)
    json_str = doc.to_json(pretty=True)
    d2 = json.loads(json_str)
    check("VConDocument JSON序列化", len(d2["parties"]) == 1)
    check("VConDocument JSON vcon version", d2["vcon"]["version"] == "draft-core-01")
    check("VConDocument JSON uuid", d2["vcon"]["uuid"] == "test-uuid")

except Exception as e:
    check(f"P13.1异常", False, str(e))

banner("P13.2 — VConExporter 会话管理")
try:
    exporter = VConExporter()
    doc = exporter.create_document("session-p13")
    check("VConExporter create_document", doc is not None)

    exporter.add_party("session-p13", VConPartyExport("p1", "天枢", "agent"))
    exporter.add_party("session-p13", VConPartyExport("p2", "用户", "user"))
    exporter.add_consent("session-p13", VConConsentExport("c1", "p2"))
    exporter.add_recording("session-p13", VConRecordingExport("r1", "session-p13"))
    exporter.add_analysis("session-p13", VConAnalysisExport("a1", "r1", "kg_extraction"))
    exporter.add_attachment("session-p13", VConAttachmentExport("att1", "r1", "log.json", "application/json"))

    exported = exporter.export_document("session-p13", pretty=True)
    check("VConExporter export_document", exported is not None and len(exported) > 100)

    stats = exporter.get_stats()
    check("VConExporter get_stats total_documents", stats["total_documents"] == 1)
    check("VConExporter get_stats total_parties", stats["total_parties"] == 2)
    check("VConExporter get_stats total_consents", stats["total_consents"] == 1)
    check("VConExporter get_stats version", stats["version"] == "draft-core-01")

    exported_all = exporter.export_all()
    check("VConExporter export_all", exported_all["total_documents"] == 1)

except Exception as e:
    check(f"P13.2异常", False, str(e))

banner("P13.3 — OTelMetricsExporter Prometheus格式")
try:
    otel = OTelMetricsExporter()

    otel.record("tianji_memory_total", 1500.0)
    otel.record("tianji_tool_call_total", 423.0)
    otel.record("tianji_kg_node_count", 256.0, {"domain": "code"})
    otel.record("tianji_api_latency_ms", 12.5, {"endpoint": "/api/vcon/export"})
    otel.record("tianji_chain_health_score", 87.5)

    prometheus_output = otel.export_prometheus()
    check("OTel Prometheus格式输出", len(prometheus_output) > 0)
    check("OTel Prometheus包含HELP", "# HELP" in prometheus_output)
    check("OTel Prometheus包含TYPE", "# TYPE" in prometheus_output)
    check("OTel Prometheus包含EOF", "# EOF" in prometheus_output)
    check("OTel Prometheus包含指标值", "tianji_memory_total" in prometheus_output)

    all_metrics = otel.export_all_metrics()
    check("OTel export_all_metrics count", all_metrics["total_metrics"] >= 5)
    check("OTel export_all_metrics timestamp", "timestamp" in all_metrics)

    otel_stats = otel.get_stats()
    check("OTel get_stats by_category", "memory" in otel_stats["by_category"])
    check("OTel get_stats total", otel_stats["total_metrics"] >= 5)

except Exception as e:
    check(f"P13.3异常", False, str(e))

banner("P13.4 — APIEndpointRegistry 端点注册表")
try:
    endpoints = APIEndpointRegistry.get_all_endpoints()
    check("APIEndpointRegistry 端点>=20", len(endpoints) >= 20)

    has_vcon = any("vcon" in ep["path"] for ep in endpoints)
    check("APIEndpointRegistry 包含vCon端点", has_vcon)

    has_metrics = any("metrics/otel" in ep["path"] for ep in endpoints)
    check("APIEndpointRegistry 包含OTel端点", has_metrics)

    has_dashboard = any("dashboard" in ep["path"] for ep in endpoints)
    check("APIEndpointRegistry 包含Dashboard端点", has_dashboard)

    has_endpoints_meta = any(ep["path"] == "/api/endpoints" for ep in endpoints)
    check("APIEndpointRegistry 自描述端点", has_endpoints_meta)

    by_cat = APIEndpointRegistry.get_endpoints_by_category()
    check("APIEndpointRegistry by_category vcon", "vcon" in by_cat)
    check("APIEndpointRegistry by_category metrics", "metrics" in by_cat)
    check("APIEndpointRegistry by_category dashboard", "dashboard" in by_cat)

    by_chain = APIEndpointRegistry.get_endpoints_by_chain()
    check("APIEndpointRegistry by_chain api", "api" in by_chain)
    check("APIEndpointRegistry by_chain knowledge", "knowledge" in by_chain)

except Exception as e:
    check(f"P13.4异常", False, str(e))

banner("P14.1 — ChainHealthMonitor 7链健康监控")
try:
    from core.shared.chain_dashboard import (
        ChainHealthMonitor, ChainDashboardBuilder,
        KnowledgeGraphDOTExporter, ExtractionStatsDashboard,
        get_chain_scores, get_chain_gaps, get_chain_summary,
        CHAIN_DEFINITIONS,
    )

    check("CHAIN_DEFINITIONS 含8链", len(CHAIN_DEFINITIONS) == 8)
    check("CHAIN_DEFINITIONS memory", "memory" in CHAIN_DEFINITIONS)
    check("CHAIN_DEFINITIONS api", "api" in CHAIN_DEFINITIONS)
    check("CHAIN_DEFINITIONS knowledge", "knowledge" in CHAIN_DEFINITIONS)
    check("CHAIN_DEFINITIONS learning", "learning" in CHAIN_DEFINITIONS)
    check("CHAIN_DEFINITIONS governance", "governance" in CHAIN_DEFINITIONS)
    check("CHAIN_DEFINITIONS scheduling", "scheduling" in CHAIN_DEFINITIONS)
    check("CHAIN_DEFINITIONS infrastructure", "infrastructure" in CHAIN_DEFINITIONS)

    monitor = ChainHealthMonitor()
    health = monitor.get_current_health()
    check("ChainHealthMonitor chains>=8", health["chain_count"] >= 8)
    check("ChainHealthMonitor average_score>0", health["average_score"] > 0)
    check("ChainHealthMonitor status_breakdown", "optimal" in health["status_breakdown"])

    coverage = monitor.compute_coverage()
    check("ChainHealthMonitor compute_coverage", coverage["total_chains"] >= 8)

except Exception as e:
    check(f"P14.1异常", False, str(e))

banner("P14.2 — ChainDashboardBuilder 统一Dashboard")
try:
    builder = ChainDashboardBuilder()
    full = builder.build_full_dashboard()
    check("Dashboard build_full_dashboard", "health" in full)
    check("Dashboard build_full_dashboard chains", "chain_definitions" in full)

    mem_dash = builder.build_memory_dashboard()
    check("MemoryDashboard layers==6", len(mem_dash["layers"]) == 6)
    check("MemoryDashboard operations batch", mem_dash["operations"]["batch_write"] == "enabled")

    kg_dash = builder.build_knowledge_dashboard()
    check("KnowledgeDashboard 11 relations", len(kg_dash["relation_patterns"]) == 11)
    check("KnowledgeDashboard 3 passes", len(kg_dash["extraction_pipeline"]) == 4)

    learn_dash = builder.build_learning_dashboard()
    check("LearningDashboard 8 categories", len(learn_dash["knowledge_categories"]) == 8)

    gov_dash = builder.build_governance_dashboard()
    check("GovernanceDashboard quality_gate", gov_dash["quality_gate"]["type"] == "ConsumerAwareAdaptiveGate")
    check("GovernanceDashboard 9 consumers", len(gov_dash["agbom"]["registered"]) == 9)

    sched_dash = builder.build_scheduling_dashboard()
    check("SchedulingDashboard 4 span types", len(sched_dash["agent_spans"]) == 4)
    check("SchedulingDashboard 3 cycles", len(sched_dash["three_cycle_orchestrator"]) == 3)

    infra_dash = builder.build_infrastructure_dashboard()
    check("InfraDashboard resilience", infra_dash["resilience"]["circuit_breakers"] is not None)
    check("InfraDashboard capacity consumers", len(infra_dash["capacity"]["consumer_weights"]) == 9)

except Exception as e:
    check(f"P14.2异常", False, str(e))

banner("P14.3 — KnowledgeGraphDOTExporter DOT可视化")
try:
    dot_exporter = KnowledgeGraphDOTExporter()

    test_nodes = [
        {"id": "tianji", "type": "agent", "label": "天机"},
        {"id": "enforcement", "type": "module", "label": "EnforcementHook"},
        {"id": "km", "type": "concept", "label": "KnowledgeModel"},
    ]
    test_edges = [
        {"source": "tianji", "target": "enforcement", "relation": "USES", "weight": 1.0},
        {"source": "enforcement", "target": "km", "relation": "PRODUCES", "weight": 1.0},
    ]
    dot1 = dot_exporter.export_nodes_edges(test_nodes, test_edges)
    check("DOT export digraph header", dot1.startswith("digraph"))
    check("DOT export all nodes", "tianji" in dot1 and "enforcement" in dot1 and "km" in dot1)
    check("DOT export rankdir TB", "rankdir=TB" in dot1)
    check("DOT export edges", "->" in dot1)

    dot_stats = dot_exporter.get_stats()
    check("DOT stats total_exports>0", dot_stats["total_exports"] > 0)

except Exception as e:
    check(f"P14.3异常", False, str(e))

banner("P14.4 — ExtractionStatsDashboard 抽取统计")
try:
    stats_dash = ExtractionStatsDashboard()
    stats_dash.record_extraction("pattern", 45)
    stats_dash.record_extraction("entity_kw", 30)
    stats_dash.record_extraction("llm", 15)
    stats_dash.record_extraction("fusion", 10)

    dash_data = stats_dash.get_dashboard()
    check("ExtractionStats total_extractions", dash_data["total_extractions"] == 100)
    check("ExtractionStats by_method pattern", dash_data["by_method"]["pattern"] == 45)
    check("ExtractionStats by_method llm", dash_data["by_method"]["llm"] == 15)
    check("ExtractionStats method_percentages", "pattern" in dash_data["method_percentages"])
    check("ExtractionStats pipeline 4 stages", len(dash_data["pipeline_stages"]) == 4)

except Exception as e:
    check(f"P14.4异常", False, str(e))

banner("P14.5 — 辅助函数")
try:
    scores = get_chain_scores()
    check("get_chain_scores 8 chains", len(scores) == 8)

    gaps = get_chain_gaps()
    check("get_chain_gaps 8 chains", len(gaps) == 8)

    summary = get_chain_summary()
    check("get_chain_summary total_chains", summary["total_chains"] == 8)
    check("get_chain_summary average_score", summary["average_score"] > 0)

except Exception as e:
    check(f"P14.5异常", False, str(e))

banner(f"Results: {passed}/{checks} passed, {failed}/{checks} failed")
print(f"  Pass rate: {passed/checks*100:.1f}%")
print(f"  {'*** ALL PASSED ***' if failed == 0 else '* WARNING: failures exist *'}")

sys.exit(0 if failed == 0 else 1)