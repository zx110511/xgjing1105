"""D3: 可观测性测试"""
import time

import pytest

from core.sla.observability import (
    TianjiTracer,
    TianjiMeter,
    TianjiLogger,
    SpanRecord,
    MetricPoint,
)


class TestTianjiTracer:
    def test_start_end_span(self):
        tracer = TianjiTracer()
        span = tracer.start_span("remember")
        assert span.operation == "remember"
        assert span.status == "ok"
        tracer.end_span(span)
        assert span.duration_ms >= 0

    def test_trace_operation_context(self):
        tracer = TianjiTracer()
        with tracer.trace_operation("recall", {"layer": "working"}) as span:
            assert span.operation == "recall"
        spans = tracer.get_spans()
        assert len(spans) == 1
        assert spans[0].status == "ok"

    def test_trace_operation_error(self):
        tracer = TianjiTracer()
        with pytest.raises(ValueError):
            with tracer.trace_operation("fail"):
                raise ValueError("boom")
        spans = tracer.get_spans()
        assert spans[0].status == "error"

    def test_get_spans_filter(self):
        tracer = TianjiTracer()
        tracer.end_span(tracer.start_span("remember"))
        tracer.end_span(tracer.start_span("recall"))
        assert len(tracer.get_spans(operation="remember")) == 1

    def test_active_spans(self):
        tracer = TianjiTracer()
        span = tracer.start_span("active")
        active = tracer.get_active_spans()
        assert len(active) == 1
        tracer.end_span(span)
        assert len(tracer.get_active_spans()) == 0

    def test_span_history_limit(self):
        tracer = TianjiTracer()
        tracer._max_spans = 5
        for i in range(10):
            tracer.end_span(tracer.start_span(f"op-{i}"))
        assert len(tracer.get_spans()) == 5


class TestTianjiMeter:
    def test_counter(self):
        meter = TianjiMeter()
        meter.increment_counter("requests", 3)
        assert meter.get_counter("requests") == 3.0

    def test_gauge(self):
        meter = TianjiMeter()
        meter.set_gauge("cpu", 75.5)
        assert meter.get_gauge("cpu") == 75.5

    def test_histogram_stats(self):
        meter = TianjiMeter()
        for v in [10, 20, 30, 40, 50]:
            meter.record_histogram("latency", v)
        stats = meter.get_histogram_stats("latency")
        assert stats["count"] == 5
        assert stats["min"] == 10
        assert stats["max"] == 50
        assert stats["avg"] == 30

    def test_empty_histogram(self):
        meter = TianjiMeter()
        stats = meter.get_histogram_stats("nonexistent")
        assert stats["count"] == 0

    def test_prometheus_export(self):
        meter = TianjiMeter()
        meter.increment_counter("api_calls", 10)
        meter.set_gauge("memory_mb", 256)
        output = meter.export_prometheus()
        assert "api_calls" in output
        assert "memory_mb" in output

    def test_get_all_metrics(self):
        meter = TianjiMeter()
        meter.increment_counter("c1")
        meter.set_gauge("g1", 1.0)
        all_m = meter.get_all_metrics()
        assert "counters" in all_m
        assert "gauges" in all_m
        assert "histograms" in all_m


class TestTianjiLogger:
    def test_info_log(self):
        tlog = TianjiLogger()
        tlog.info("hello", key="value")
        logs = tlog.get_logs()
        assert len(logs) == 1
        assert logs[0]["level"] == "INFO"
        assert logs[0]["message"] == "hello"

    def test_warning_log(self):
        tlog = TianjiLogger()
        tlog.warning("warn")
        logs = tlog.get_logs(level="WARNING")
        assert len(logs) == 1

    def test_default_fields(self):
        tlog = TianjiLogger()
        tlog.set_default_fields({"service": "tianji"})
        tlog.info("test")
        logs = tlog.get_logs()
        assert logs[0]["service"] == "tianji"

    def test_log_buffer_limit(self):
        tlog = TianjiLogger()
        tlog._max_buffer = 5
        for i in range(10):
            tlog.info(f"msg-{i}")
        assert len(tlog.get_logs()) == 5
