r"""
天机API暴露层 (Tianji API Exposure Layer)
===========================================
为7链辐射提供完整API暴露能力:
  - IETF vCon (draft-core-01) JSON导出
  - OpenTelemetry Protocol (OTLP) Prometheus格式导出
  - 全链路REST API端点注册表
  - 端点健康检查与可用性报告

目标: API暴露链 10% → 100%

vCon: ISO/IEC DIS 23220-3 + IETF vCon draft-core-01
OTel: OpenTelemetry GenAI Agent/Tool v1.41.0
"""

import json
import time
import threading
from typing import Any, Optional, Dict, List, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum


class VConVersion(str, Enum):
    DRAFT_01 = "draft-core-01"
    DRAFT_02 = "draft-core-02"


@dataclass
class VConExportConfig:
    version: VConVersion = VConVersion.DRAFT_01
    include_parties: bool = True
    include_consents: bool = True
    include_recordings: bool = True
    include_analysis: bool = True
    include_attachments: bool = True
    pretty_print: bool = False


@dataclass
class VConPartyExport:
    party_id: str
    name: str
    role: str
    provider: str = "memory-engine-global"
    meta: Dict[str, str] = field(default_factory=dict)

    def to_vcon_dict(self) -> dict:
        return {
            "party_id": self.party_id,
            "name": self.name,
            "role": self.role,
            "provider": self.provider,
            "meta": self.meta,
        }


@dataclass
class VConConsentExport:
    consent_id: str
    party_id: str
    consent_type: str = "explicit"
    granted: bool = True
    scope: str = "conversation_recording"
    purpose: str = "memory_enhancement"
    retention_days: int = 365
    timestamp: float = field(default_factory=time.time)

    def to_vcon_dict(self) -> dict:
        return {
            "consent_id": self.consent_id,
            "party_id": self.party_id,
            "consent_type": self.consent_type,
            "granted": self.granted,
            "scope": self.scope,
            "purpose": self.purpose,
            "retention_days": self.retention_days,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp)),
        }


@dataclass
class VConRecordingExport:
    recording_id: str
    session_id: str
    start_time: float = field(default_factory=time.time)
    party_ids: List[str] = field(default_factory=list)
    media_type: str = "text/conversation"
    transcript: str = ""
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_vcon_dict(self) -> dict:
        return {
            "recording_id": self.recording_id,
            "session_id": self.session_id,
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.start_time)),
            "party_ids": self.party_ids,
            "media_type": self.media_type,
            "transcript_hash": _hash_text(self.transcript),
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }


@dataclass
class VConAnalysisExport:
    analysis_id: str
    recording_id: str
    analysis_type: str
    result: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_vcon_dict(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "recording_id": self.recording_id,
            "analysis_type": self.analysis_type,
            "result": self.result,
            "confidence_final": self.confidence,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp)),
        }


@dataclass
class VConAttachmentExport:
    attachment_id: str
    recording_id: str
    file_name: str
    mime_type: str
    size_bytes: int = 0
    purpose: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_vcon_dict(self) -> dict:
        return {
            "attachment_id": self.attachment_id,
            "recording_id": self.recording_id,
            "file_name": self.file_name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "purpose": self.purpose,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp)),
        }


@dataclass
class VConDocument:
    vcon_version: str = "draft-core-01"
    vcon_uuid: str = ""
    created_at: str = ""
    updated_at: str = ""
    parties: List[VConPartyExport] = field(default_factory=list)
    consents: List[VConConsentExport] = field(default_factory=list)
    recordings: List[VConRecordingExport] = field(default_factory=list)
    analysis: List[VConAnalysisExport] = field(default_factory=list)
    attachments: List[VConAttachmentExport] = field(default_factory=list)

    def to_vcon_dict(self) -> dict:
        result = {
            "vcon": {
                "version": self.vcon_version,
                "uuid": self.vcon_uuid,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            },
            "parties": [p.to_vcon_dict() for p in self.parties],
            "consents": [c.to_vcon_dict() for c in self.consents],
            "recordings": [r.to_vcon_dict() for r in self.recordings],
            "analysis": [a.to_vcon_dict() for a in self.analysis],
            "attachments": [a.to_vcon_dict() for a in self.attachments],
        }
        return result

    def to_json(self, pretty: bool = False) -> str:
        return json.dumps(self.to_vcon_dict(), ensure_ascii=False, indent=2 if pretty else None)


class VConExporter:
    def __init__(self):
        self._config = VConExportConfig()
        self._documents: Dict[str, VConDocument] = {}
        self._export_count = 0
        self._lock = threading.Lock()

    def create_document(self, session_id: str) -> VConDocument:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        import uuid as _uuid
        vcon_uuid = str(_uuid.uuid4())
        doc = VConDocument(
            vcon_uuid=vcon_uuid,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._documents[session_id] = doc
        return doc

    def add_party(self, session_id: str, party: VConPartyExport):
        doc = self._documents.get(session_id)
        if doc:
            doc.parties.append(party)
            doc.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def add_consent(self, session_id: str, consent: VConConsentExport):
        doc = self._documents.get(session_id)
        if doc:
            doc.consents.append(consent)
            doc.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def add_recording(self, session_id: str, recording: VConRecordingExport):
        doc = self._documents.get(session_id)
        if doc:
            doc.recordings.append(recording)
            doc.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def add_analysis(self, session_id: str, analysis: VConAnalysisExport):
        doc = self._documents.get(session_id)
        if doc:
            doc.analysis.append(analysis)
            doc.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def add_attachment(self, session_id: str, attachment: VConAttachmentExport):
        doc = self._documents.get(session_id)
        if doc:
            doc.attachments.append(attachment)
            doc.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def export_document(self, session_id: str, pretty: bool = False) -> Optional[str]:
        doc = self._documents.get(session_id)
        if not doc:
            return None
        with self._lock:
            self._export_count += 1
        return doc.to_json(pretty=pretty)

    def export_all(self, pretty: bool = False) -> Dict[str, Any]:
        return {
            "version": "draft-core-01",
            "total_documents": len(self._documents),
            "total_exports": self._export_count,
            "documents": {
                sid: doc.to_vcon_dict()
                for sid, doc in self._documents.items()
            },
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_documents": len(self._documents),
            "total_parties": sum(len(d.parties) for d in self._documents.values()),
            "total_consents": sum(len(d.consents) for d in self._documents.values()),
            "total_recordings": sum(len(d.recordings) for d in self._documents.values()),
            "total_analysis": sum(len(d.analysis) for d in self._documents.values()),
            "total_attachments": sum(len(d.attachments) for d in self._documents.values()),
            "total_exports": self._export_count,
            "version": "draft-core-01",
        }


class OTelMetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class OTelMetricSample:
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class OTelMetricDefinition:
    name: str
    display_name: str
    metric_type: OTelMetricType
    unit: str
    description: str
    category: str
    _current_value: float = 0.0
    _samples: List[OTelMetricSample] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, value: float, labels: Optional[Dict[str, str]] = None):
        with self._lock:
            self._current_value = value
            sample = OTelMetricSample(
                name=self.name,
                value=value,
                labels=labels or {},
            )
            self._samples.append(sample)
            if len(self._samples) > 1000:
                self._samples = self._samples[-500:]

    def get_latest(self) -> float:
        return self._current_value

    def to_prometheus_line(self) -> str:
        labels_str = ",".join(f'{k}="{v}"' for k, v in self._samples[-1].labels.items()) if self._samples else ""
        label_part = f"{{{labels_str}}}" if labels_str else ""
        return f'{self.name}{label_part} {self._current_value}'


OTEL_DEFAULT_METRICS: Dict[str, OTelMetricDefinition] = {
    "tianji_memory_total": OTelMetricDefinition(
        name="tianji_memory_total",
        display_name="总记忆数",
        metric_type=OTelMetricType.GAUGE,
        unit="items",
        description="ICME六层记忆总条目数",
        category="memory",
    ),
    "tianji_memory_layer_count": OTelMetricDefinition(
        name="tianji_memory_layer_count",
        display_name="各层记忆数",
        metric_type=OTelMetricType.GAUGE,
        unit="items",
        description="ICME六层各自记忆条目数",
        category="memory",
    ),
    "tianji_tool_call_total": OTelMetricDefinition(
        name="tianji_tool_call_total",
        display_name="工具调用总数",
        metric_type=OTelMetricType.COUNTER,
        unit="calls",
        description="MCP工具调用累计次数",
        category="system",
    ),
    "tianji_tool_error_total": OTelMetricDefinition(
        name="tianji_tool_error_total",
        display_name="工具调用错误总数",
        metric_type=OTelMetricType.COUNTER,
        unit="errors",
        description="MCP工具调用错误累计次数",
        category="system",
    ),
    "tianji_api_latency_ms": OTelMetricDefinition(
        name="tianji_api_latency_ms",
        display_name="API延迟",
        metric_type=OTelMetricType.HISTOGRAM,
        unit="ms",
        description="REST API请求响应时间",
        category="system",
    ),
    "tianji_agent_switch_count": OTelMetricDefinition(
        name="tianji_agent_switch_count",
        display_name="Agent切换次数",
        metric_type=OTelMetricType.COUNTER,
        unit="switches",
        description="TVP协议Agent调度切换累计次数",
        category="agent",
    ),
    "tianji_enforcement_hook_count": OTelMetricDefinition(
        name="tianji_enforcement_hook_count",
        display_name="强制执行次数",
        metric_type=OTelMetricType.COUNTER,
        unit="hooks",
        description="Enforcement Hook触发累计次数",
        category="enforcement",
    ),
    "tianji_kg_node_count": OTelMetricDefinition(
        name="tianji_kg_node_count",
        display_name="知识图谱节点数",
        metric_type=OTelMetricType.GAUGE,
        unit="nodes",
        description="知识图谱当前节点数",
        category="knowledge",
    ),
    "tianji_kg_edge_count": OTelMetricDefinition(
        name="tianji_kg_edge_count",
        display_name="知识图谱边数",
        metric_type=OTelMetricType.GAUGE,
        unit="edges",
        description="知识图谱当前边数",
        category="knowledge",
    ),
    "tianji_quality_gate_pass_rate": OTelMetricDefinition(
        name="tianji_quality_gate_pass_rate",
        display_name="质量门禁通过率",
        metric_type=OTelMetricType.GAUGE,
        unit="ratio",
        description="QualityGate PASS比率",
        category="quality",
    ),
    "tianji_consumer_degradation_level": OTelMetricDefinition(
        name="tianji_consumer_degradation_level",
        display_name="消费者降级级别",
        metric_type=OTelMetricType.GAUGE,
        unit="level",
        description="Consumer Resilience当前降级级别",
        category="resilience",
    ),
    "tianji_chain_health_score": OTelMetricDefinition(
        name="tianji_chain_health_score",
        display_name="链健康评分",
        metric_type=OTelMetricType.GAUGE,
        unit="percent",
        description="7链能力辐射综合健康评分",
        category="monitoring",
    ),
}


class OTelMetricsExporter:
    def __init__(self):
        self._metrics: Dict[str, OTelMetricDefinition] = {}
        self._lock = threading.Lock()
        self._init_defaults()

    def _init_defaults(self):
        for name, mdef in OTEL_DEFAULT_METRICS.items():
            self._metrics[name] = OTelMetricDefinition(
                name=mdef.name,
                display_name=mdef.display_name,
                metric_type=mdef.metric_type,
                unit=mdef.unit,
                description=mdef.description,
                category=mdef.category,
            )

    def register_metric(self, definition: OTelMetricDefinition):
        with self._lock:
            self._metrics[definition.name] = definition

    def record(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        metric = self._metrics.get(name)
        if metric:
            metric.record(value, labels)

    def get_metric(self, name: str) -> Optional[float]:
        metric = self._metrics.get(name)
        return metric.get_latest() if metric else None

    def export_prometheus(self) -> str:
        lines = []
        now_ms = int(time.time() * 1000)
        with self._lock:
            for name, metric in sorted(self._metrics.items()):
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} {metric.metric_type.value}")
                lines.append(metric.to_prometheus_line())
        lines.append(f"# EOF {now_ms}")
        return "\n".join(lines)

    def export_all_metrics(self) -> Dict[str, Any]:
        result = {}
        with self._lock:
            for name, metric in self._metrics.items():
                result[name] = {
                    "display_name": metric.display_name,
                    "type": metric.metric_type.value,
                    "unit": metric.unit,
                    "category": metric.category,
                    "value": metric.get_latest(),
                }
        return {
            "timestamp": time.time(),
            "total_metrics": len(result),
            "metrics": result,
        }

    def get_stats(self) -> Dict[str, Any]:
        metrics_by_category = {}
        for name, metric in self._metrics.items():
            cat = metric.category
            if cat not in metrics_by_category:
                metrics_by_category[cat] = []
            metrics_by_category[cat].append({
                "name": name,
                "display_name": metric.display_name,
                "value": metric.get_latest(),
            })
        return {
            "total_metrics": len(self._metrics),
            "by_category": metrics_by_category,
        }


@dataclass
class APIEndpoint:
    method: str
    path: str
    description: str
    category: str
    parameters: List[Dict[str, str]] = field(default_factory=list)
    returns: str = ""
    chain_impact: List[str] = field(default_factory=list)


class APIEndpointRegistry:
    ENDPOINTS: List[APIEndpoint] = [
        APIEndpoint("POST", "/api/vcon/export/{session_id}", "IETF vCon JSON导出", "vcon",
                    [{"name": "session_id", "type": "string", "required": "true"}],
                    "application/json", ["api"]),
        APIEndpoint("POST", "/api/vcon/export/all", "全量vCon文档导出", "vcon",
                    [], "application/json", ["api"]),
        APIEndpoint("GET", "/api/vcon/stats", "vCon导出统计", "vcon",
                    [], "application/json", ["api"]),
        APIEndpoint("GET", "/api/metrics/otel/prometheus", "Prometheus格式OTel指标", "metrics",
                    [], "text/plain", ["api"]),
        APIEndpoint("GET", "/api/metrics/otel/json", "JSON格式OTel指标", "metrics",
                    [], "application/json", ["api"]),
        APIEndpoint("GET", "/api/metrics/otel/stats", "OTel指标统计", "metrics",
                    [], "application/json", ["api"]),
        APIEndpoint("GET", "/api/dashboard/chains", "7链Dashboard统一接口", "dashboard",
                    [], "application/json", ["api", "monitoring"]),
        APIEndpoint("GET", "/api/dashboard/memory", "记忆存储链仪表盘", "dashboard",
                    [], "application/json", ["memory"]),
        APIEndpoint("GET", "/api/dashboard/knowledge", "知识抽取链仪表盘", "dashboard",
                    [], "application/json", ["knowledge"]),
        APIEndpoint("GET", "/api/dashboard/learning", "学习进化链仪表盘", "dashboard",
                    [], "application/json", ["learning"]),
        APIEndpoint("GET", "/api/dashboard/governance", "治理审计链仪表盘", "dashboard",
                    [], "application/json", ["governance"]),
        APIEndpoint("GET", "/api/dashboard/scheduling", "智能调度链仪表盘", "dashboard",
                    [], "application/json", ["scheduling"]),
        APIEndpoint("GET", "/api/dashboard/infrastructure", "基础设施链仪表盘", "dashboard",
                    [], "application/json", ["infrastructure"]),
        APIEndpoint("GET", "/api/dashboard/api", "API暴露链仪表盘", "dashboard",
                    [], "application/json", ["api"]),
        APIEndpoint("GET", "/api/kg/visualize/dot", "知识图谱DOT可视化", "knowledge_graph",
                    [], "text/vnd.graphviz", ["knowledge"]),
        APIEndpoint("GET", "/api/kg/visualize/stats", "知识抽取统计可视化", "knowledge_graph",
                    [], "application/json", ["knowledge"]),
        APIEndpoint("GET", "/api/chains/health", "7链健康状态检查", "monitoring",
                    [], "application/json", ["monitoring"]),
        APIEndpoint("GET", "/api/export/otel/spans", "OTel Span数据导出", "export",
                    [], "application/json", ["api"]),
        APIEndpoint("GET", "/api/export/otel/traces", "OTel Trace数据导出", "export",
                    [], "application/json", ["api"]),
        APIEndpoint("GET", "/api/endpoints", "全部API端点目录", "meta",
                    [], "application/json", ["api"]),
    ]

    @classmethod
    def get_all_endpoints(cls) -> List[Dict]:
        return [
            {
                "method": ep.method,
                "path": ep.path,
                "description": ep.description,
                "category": ep.category,
                "parameters": ep.parameters,
                "returns": ep.returns,
                "chain_impact": ep.chain_impact,
            }
            for ep in cls.ENDPOINTS
        ]

    @classmethod
    def get_endpoints_by_category(cls) -> Dict[str, List[Dict]]:
        result: Dict[str, List] = {}
        for ep in cls.ENDPOINTS:
            if ep.category not in result:
                result[ep.category] = []
            result[ep.category].append({
                "method": ep.method, "path": ep.path,
                "description": ep.description, "chain_impact": ep.chain_impact,
            })
        return result

    @classmethod
    def get_endpoints_by_chain(cls) -> Dict[str, List[Dict]]:
        result: Dict[str, List] = {}
        for ep in cls.ENDPOINTS:
            for chain in ep.chain_impact:
                if chain not in result:
                    result[chain] = []
                result[chain].append({
                    "method": ep.method, "path": ep.path,
                    "description": ep.description,
                })
        return result


def _hash_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
