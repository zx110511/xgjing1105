"""D3+D4 快速验证"""
# D3: 可观测性
from core.sla.observability import TianjiTracer, TianjiMeter, TianjiLogger

tracer = TianjiTracer()
with tracer.trace_operation("remember", {"layer": "working"}) as span:
    pass
spans = tracer.get_spans()
print(f"D3 Tracer: {len(spans)} spans, duration={spans[0].duration_ms:.1f}ms")

meter = TianjiMeter()
meter.increment_counter("api.calls", 5)
meter.set_gauge("memory.usage", 42.5)
meter.record_histogram("latency", 12.3)
meter.record_histogram("latency", 45.6)
stats = meter.get_histogram_stats("latency")
print(f"D3 Meter: counters={meter.get_counter('api.calls')}, p99={stats['p99']}")
print(f"D3 Prometheus: {len(meter.export_prometheus().splitlines())} lines")

tlog = TianjiLogger()
tlog.info("test message", tenant="t1")
print(f"D3 Logger: {len(tlog.get_logs())} logs")

# D4: 计费
from core.sla.billing import BillingEngine, FREE_TIER, BASIC_TIER
engine = BillingEngine()
m = engine.register_tenant("t1", "basic")
m.current_entries = 55000
m.current_api_calls = 600000
overage = engine.calculate_overage(m)
print(f"D4 Overage: {overage}")
bill = engine.generate_bill("t1")
print(f"D4 Bill: base={bill.base_price}, overage={bill.overage_charges}, total={bill.total}")
print(f"D4 Warnings: {engine.check_warnings('t1')}")
print(f"D4 Audit: {len(engine.get_audit_log())} entries")
print("D3+D4 ALL OK")
