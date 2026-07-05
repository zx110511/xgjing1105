r"""
天机全链路可观测性引擎 (Tianji Observability) v1.0
==================================================
借鉴 OpenTelemetry + Prometheus 的可观测性标准，
为天机v9.1调度引擎提供分布式追踪、指标暴露、结构化日志能力。

核心能力:
  1. Span追踪 — pipeline→stage→task→tool_call 四级嵌套
  2. Metrics暴露 — Prometheus格式指标 (计数器/直方图/仪表)
  3. 结构化日志 — JSON格式 + Trace ID关联
  4. 调度延迟分析 — P50/P90/P99延迟统计
  5. 错误率监控 — 按pipeline/stage维度聚合

参考架构:
  - OpenTelemetry: Span + Resource + Attributes
  - Prometheus: Counter/Gauge/Histogram + /metrics 端点
  - Logfire: 结构化日志 + Trace上下文传播

位置: 天机/core/observability.py
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("tianji.observability")


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


class SpanKind(str, Enum):
    PIPELINE = "pipeline"
    STAGE = "stage"
    TASK = "task"
    TOOL_CALL = "tool_call"
    WORKFLOW = "workflow"
    WORKFLOW_STEP = "workflow_step"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


@dataclass
class Span:
    """OpenTelemetry-compatible Span"""

    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    name: str = ""
    kind: SpanKind = SpanKind.TASK
    status: SpanStatus = SpanStatus.UNSET
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration_ms: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    error: str | None = None

    def add_event(self, name: str, attributes: dict = None):
        self.events.append(
            {
                "name": name,
                "timestamp": time.time(),
                "attributes": attributes or {},
            }
        )

    def set_status(self, status: SpanStatus, error: str = None):
        self.status = status
        if error:
            self.error = error

    def finish(self):
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind.value,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 2),
            "attributes": self.attributes,
            "events": self.events,
            "error": self.error,
        }


@dataclass
class Trace:
    """一次完整的追踪链"""

    trace_id: str
    root_span: Span | None = None
    spans: dict[str, Span] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════
# Metrics 指标收集器
# ═══════════════════════════════════════════════════════════════


class MetricsCollector:
    """
    Prometheus-compatible 指标收集器

    内置指标:
      - tianji_pipelines_total: 流水线执行总数 (counter)
      - tianji_nodes_total: 节点执行总数 (counter, by status)
      - tianji_pipeline_duration_ms: 流水线执行延迟 (histogram)
      - tianji_active_pipelines: 活跃流水线数 (gauge)
      - tianji_errors_total: 错误总数 (counter, by pipeline)
      - tianji_agent_utilization: Agent利用率 (gauge, by agent)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._labels: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # 内置计数器
        self._counters["tianji_pipelines_total"] = 0
        self._counters["tianji_nodes_total"] = 0
        self._counters["tianji_nodes_completed"] = 0
        self._counters["tianji_nodes_failed"] = 0
        self._counters["tianji_errors_total"] = 0
        self._counters["tianji_workflows_total"] = 0

        # 延迟分桶 (ms)
        self._latency_buckets = [
            10,
            50,
            100,
            250,
            500,
            1000,
            2500,
            5000,
            10000,
            30000,
            60000,
        ]
        self._latency_histogram: dict[str, dict[int, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        self._start_time = time.time()

    def increment(self, name: str, value: int = 1, labels: dict[str, str] = None):
        with self._lock:
            self._counters[name] += value
            if labels:
                label_key = json.dumps(labels, sort_keys=True)
                self._labels[name][label_key] += value

    def set_gauge(self, name: str, value: float, labels: dict = None):
        with self._lock:
            if labels:
                key = f"{name}:{json.dumps(labels, sort_keys=True)}"
                self._gauges[key] = value
            else:
                self._gauges[name] = value

    def observe_latency(self, name: str, duration_ms: float):
        with self._lock:
            self._histograms[name].append(duration_ms)
            # 分桶统计
            for bound in self._latency_buckets:
                if duration_ms <= bound:
                    self._latency_histogram[name][bound] += 1

            # 只保留最近1000个样本
            if len(self._histograms[name]) > 1000:
                self._histograms[name] = self._histograms[name][-1000:]

    def get_p50(self, name: str) -> float:
        samples = sorted(self._histograms.get(name, []))
        if not samples:
            return 0.0
        idx = int(len(samples) * 0.5)
        return samples[min(idx, len(samples) - 1)]

    def get_p90(self, name: str) -> float:
        samples = sorted(self._histograms.get(name, []))
        if not samples:
            return 0.0
        idx = int(len(samples) * 0.9)
        return samples[min(idx, len(samples) - 1)]

    def get_p99(self, name: str) -> float:
        samples = sorted(self._histograms.get(name, []))
        if not samples:
            return 0.0
        idx = int(len(samples) * 0.99)
        return samples[min(idx, len(samples) - 1)]

    def to_prometheus(self) -> str:
        """导出为Prometheus文本格式"""
        lines = []
        with self._lock:
            # Counters
            for name, value in self._counters.items():
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {value}")
                for label_key, label_value in self._labels.get(name, {}).items():
                    lines.append(f"{name}{{{label_key}}} {label_value}")

            # Gauges
            for key, value in self._gauges.items():
                name = key.split(":")[0]
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{key} {value}")

            # Histograms
            for name, samples in self._histograms.items():
                lines.append(f"# TYPE {name} histogram")
                lines.append(f"# HELP {name} Latency histogram")
                for bound in self._latency_buckets:
                    count = self._latency_histogram.get(name, {}).get(bound, 0)
                    lines.append(f'{name}_bucket{{le="{bound}"}} {count}')
                lines.append(f'{name}_bucket{{le="+Inf"}} {len(samples)}')
                if samples:
                    lines.append(f"{name}_sum {sum(samples)}")
                    lines.append(f"{name}_count {len(samples)}")

            lines.append("# TYPE tianji_uptime_seconds gauge")
            lines.append(f"tianji_uptime_seconds {time.time() - self._start_time}")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        """返回结构化统计"""
        return {
            "counters": dict(self._counters),
            "gauges": {k: v for k, v in self._gauges.items() if ":" not in k},
            "latency_p50": {
                k: self.get_p50(k) for k in list(self._histograms.keys())[:10]
            },
            "latency_p90": {
                k: self.get_p90(k) for k in list(self._histograms.keys())[:10]
            },
            "latency_p99": {
                k: self.get_p99(k) for k in list(self._histograms.keys())[:10]
            },
            "uptime_s": time.time() - self._start_time,
        }


# ═══════════════════════════════════════════════════════════════
# 追踪提供者
# ═══════════════════════════════════════════════════════════════


class TracerProvider:
    """
    OpenTelemetry-compatible Tracer

    使用:
      tracer = TracerProvider()
      with tracer.start_span("security_audit", SpanKind.PIPELINE) as span:
          span.add_event("started", {"target": "tianji"})
          # ... do work ...
          span.set_status(SpanStatus.OK)
    """

    def __init__(self, max_traces: int = 100):
        self.max_traces = max_traces
        self._traces: dict[str, Trace] = {}
        self._lock = threading.Lock()
        self.metrics = MetricsCollector()
        self._current_span: dict[int, Span] = {}  # thread_id → current span

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.TASK,
        attributes: dict = None,
        parent_span: Span = None,
    ) -> Span:
        """创建新Span"""
        span_id = f"span-{uuid.uuid4().hex[:12]}"

        if parent_span:
            trace_id = parent_span.trace_id
            parent_span_id = parent_span.span_id
        else:
            trace_id = f"trace-{uuid.uuid4().hex[:16]}"
            parent_span_id = None

        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            attributes=attributes or {},
        )

        # 注册到trace
        with self._lock:
            if trace_id not in self._traces:
                self._traces[trace_id] = Trace(trace_id=trace_id)
            trace = self._traces[trace_id]
            trace.spans[span_id] = span
            if parent_span is None and trace.root_span is None:
                trace.root_span = span

            # 清理旧trace
            if len(self._traces) > self.max_traces:
                oldest = min(
                    self._traces.keys(),
                    key=lambda tid: self._traces[tid].created_at,
                )
                del self._traces[oldest]

        # 设置为当前span
        tid = threading.get_ident()
        self._current_span[tid] = span

        return span

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.TASK,
        attributes: dict = None,
        parent: Span = None,
    ):
        """上下文管理器 — 自动start/finish"""
        sp = self.start_span(name, kind, attributes, parent)
        try:
            yield sp
            sp.set_status(SpanStatus.OK)
        except Exception as e:
            sp.set_status(SpanStatus.ERROR, str(e))
            self.metrics.increment("tianji_errors_total", 1, {"span": name})
            raise
        finally:
            sp.finish()
            # 记录延迟
            self.metrics.observe_latency(
                f"tianji_{kind.value}_duration_ms", sp.duration_ms
            )

    def get_current_span(self) -> Span | None:
        """获取当前线程的活跃Span"""
        return self._current_span.get(threading.get_ident())

    def get_trace(self, trace_id: str) -> Trace | None:
        with self._lock:
            return self._traces.get(trace_id)

    def list_traces(self, limit: int = 50) -> list[dict]:
        with self._lock:
            sorted_traces = sorted(
                self._traces.values(),
                key=lambda t: t.created_at,
                reverse=True,
            )[:limit]
            return [
                {
                    "trace_id": t.trace_id,
                    "span_count": len(t.spans),
                    "root_span": t.root_span.to_dict() if t.root_span else None,
                    "created_at": t.created_at,
                }
                for t in sorted_traces
            ]

    def get_stats(self) -> dict:
        return {
            "active_traces": len(self._traces),
            "total_spans": sum(len(t.spans) for t in self._traces.values()),
            "metrics": self.metrics.get_stats(),
        }


# ═══════════════════════════════════════════════════════════════
# 结构化日志 (JSON + Trace ID)
# ═══════════════════════════════════════════════════════════════


class StructuredLogger:
    """JSON格式结构化日志 — 自动关联Trace ID"""

    def __init__(self, tracer: TracerProvider = None):
        self.tracer = tracer

    def _get_trace_context(self) -> dict:
        span = self.tracer.get_current_span() if self.tracer else None
        if span:
            return {
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "span_name": span.name,
                "span_kind": span.kind.value,
            }
        return {}

    def log(self, level: str, message: str, **extra):
        record = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            **self._get_trace_context(),
            **extra,
        }
        log_fn = getattr(logger, level.lower(), logger.info)
        log_fn(json.dumps(record, ensure_ascii=False))

    def info(self, message: str, **extra):
        self.log("INFO", message, **extra)

    def warning(self, message: str, **extra):
        self.log("WARNING", message, **extra)

    def error(self, message: str, **extra):
        self.log("ERROR", message, **extra)

    def debug(self, message: str, **extra):
        self.log("DEBUG", message, **extra)


# ═══════════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════════

_tracer: TracerProvider | None = None
_metrics: MetricsCollector | None = None
_structured_logger: StructuredLogger | None = None
_obs_lock = threading.RLock()


def get_tracer(max_traces: int = 100) -> TracerProvider:
    global _tracer
    with _obs_lock:
        if _tracer is None:
            _tracer = TracerProvider(max_traces=max_traces)
        return _tracer


def get_metrics() -> MetricsCollector:
    global _metrics
    with _obs_lock:
        if _metrics is None:
            _metrics = get_tracer().metrics
        return _metrics


def get_structured_logger() -> StructuredLogger:
    global _structured_logger
    with _obs_lock:
        if _structured_logger is None:
            _structured_logger = StructuredLogger(get_tracer())
        return _structured_logger


# ═══════════════════════════════════════════════════════════════
# 便捷装饰器 — 自动追踪函数调用
# ═══════════════════════════════════════════════════════════════


def traced(name: str = None, kind: SpanKind = SpanKind.TASK):
    """装饰器: 自动为函数创建Span追踪"""

    def decorator(func):
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            span_name = name or func.__name__
            with tracer.span(span_name, kind) as span:
                span.add_event(
                    "call",
                    {"args_count": len(args), "kwargs_keys": list(kwargs.keys())},
                )
                result = func(*args, **kwargs)
                span.add_event("return", {"success": True})
                return result

        return wrapper

    return decorator
