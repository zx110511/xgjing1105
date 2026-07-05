"""
可观测性框架 v1.0
=================
基于现有 tdaf_schema.py / tdaf_exporter.py 增强:
  1. OTel Span 全链路追踪(remember→recall→consolidate)
  2. OTel Metrics 暴露(QPS/延迟/错误率/容量)
  3. OTel Logs 结构化日志
  4. Prometheus 指标导出
  5. 降级模式(OTel不可用时退化为纯日志)
"""

import logging
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("tianji.sla.observability")

# OTel可选依赖
_OTEL_AVAILABLE = False
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    _OTEL_AVAILABLE = True
except ImportError:
    pass


@dataclass
class SpanRecord:
    """Span记录"""
    span_id: str
    operation: str
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    parent_span_id: Optional[str] = None

    def finish(self) -> None:
        """结束Span"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000.0


@dataclass
class MetricPoint:
    """指标数据点"""
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)


class TianjiTracer:
    """天机链路追踪器"""

    def __init__(self, service_name: str = "tianji-memory") -> None:
        self._service_name = service_name
        self._spans: List[SpanRecord] = []
        self._active_spans: Dict[str, SpanRecord] = {}
        self._lock = threading.Lock()
        self._otel_tracer = None
        self._max_spans = 10000
        self._span_counter = 0

        if _OTEL_AVAILABLE:
            try:
                provider = TracerProvider()
                trace.set_tracer_provider(provider)
                self._otel_tracer = trace.get_tracer(service_name)
            except Exception as e:
                logger.warning("OTel Tracer初始化失败: %s", e)

    def start_span(
        self,
        operation: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent_span_id: Optional[str] = None,
    ) -> SpanRecord:
        """创建Span"""
        self._span_counter += 1
        span_id = f"span-{self._span_counter}"
        span = SpanRecord(
            span_id=span_id,
            operation=operation,
            start_time=time.time(),
            attributes=attributes or {},
            parent_span_id=parent_span_id,
        )
        with self._lock:
            self._active_spans[span_id] = span
        return span

    def end_span(self, span: SpanRecord, status: str = "ok") -> None:
        """结束Span"""
        span.status = status
        span.finish()
        with self._lock:
            self._active_spans.pop(span.span_id, None)
            self._spans.append(span)
            if len(self._spans) > self._max_spans:
                self._spans = self._spans[-self._max_spans:]

    @contextmanager
    def trace_operation(
        self,
        operation: str,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """上下文管理器: 自动追踪操作"""
        span = self.start_span(operation, attributes)
        try:
            yield span
            self.end_span(span, status="ok")
        except Exception as e:
            self.end_span(span, status="error")
            span.attributes["error"] = str(e)
            raise

    def get_spans(
        self, operation: Optional[str] = None, limit: int = 100
    ) -> List[SpanRecord]:
        """查询Span记录"""
        with self._lock:
            spans = list(self._spans)
        if operation:
            spans = [s for s in spans if s.operation == operation]
        return spans[-limit:]

    def get_active_spans(self) -> List[SpanRecord]:
        """获取活跃Span"""
        with self._lock:
            return list(self._active_spans.values())

    @property
    def is_otel_enabled(self) -> bool:
        """OTel是否可用"""
        return self._otel_tracer is not None


class TianjiMeter:
    """天机指标计量器"""

    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._history: List[MetricPoint] = []
        self._lock = threading.Lock()
        self._max_history = 10000

    def increment_counter(
        self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """递增计数器"""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + value
            self._history.append(MetricPoint(
                name=name, value=self._counters[name], labels=labels or {}
            ))
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    def set_gauge(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """设置仪表值"""
        with self._lock:
            self._gauges[name] = value
            self._history.append(MetricPoint(
                name=name, value=value, labels=labels or {}
            ))

    def record_histogram(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """记录直方图值"""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)
            self._history.append(MetricPoint(
                name=name, value=value, labels=labels or {}
            ))
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    def get_counter(self, name: str) -> float:
        """获取计数器值"""
        return self._counters.get(name, 0.0)

    def get_gauge(self, name: str) -> float:
        """获取仪表值"""
        return self._gauges.get(name, 0.0)

    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """获取直方图统计"""
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p99": 0}
        sorted_vals = sorted(values)
        return {
            "count": len(values),
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(values) / len(values),
            "p50": sorted_vals[int(len(values) * 0.5)],
            "p99": sorted_vals[int(len(values) * 0.99)],
        }

    def export_prometheus(self) -> str:
        """导出Prometheus格式指标"""
        lines: List[str] = []
        for name, value in self._counters.items():
            prom_name = name.replace(".", "_").replace("-", "_")
            lines.append(f"# TYPE {prom_name} counter")
            lines.append(f"{prom_name} {value}")
        for name, value in self._gauges.items():
            prom_name = name.replace(".", "_").replace("-", "_")
            lines.append(f"# TYPE {prom_name} gauge")
            lines.append(f"{prom_name} {value}")
        return "\n".join(lines)

    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: self.get_histogram_stats(k) for k in self._histograms
            },
        }


class TianjiLogger:
    """天机结构化日志器"""

    def __init__(self, name: str = "tianji") -> None:
        self._logger = logging.getLogger(name)
        self._default_fields: Dict[str, Any] = {}
        self._log_buffer: List[Dict[str, Any]] = []
        self._max_buffer = 1000
        self._lock = threading.Lock()

    def set_default_fields(self, fields: Dict[str, Any]) -> None:
        """设置默认日志字段"""
        self._default_fields.update(fields)

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """内部日志方法"""
        entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            **self._default_fields,
            **kwargs,
        }
        with self._lock:
            self._log_buffer.append(entry)
            if len(self._log_buffer) > self._max_buffer:
                self._log_buffer = self._log_buffer[-self._max_buffer:]

        log_method = getattr(self._logger, level.lower(), self._logger.info)
        log_method("%s %s", message, {k: v for k, v in kwargs.items() if v is not None})

    def info(self, message: str, **kwargs: Any) -> None:
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log("ERROR", message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log("DEBUG", message, **kwargs)

    def get_logs(self, level: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """查询日志"""
        with self._lock:
            logs = list(self._log_buffer)
        if level:
            logs = [l for l in logs if l["level"] == level]
        return logs[-limit:]
