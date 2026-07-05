"""D4: 计费模型测试"""
import pytest

from core.sla.billing import (
    BillingEngine,
    BillingCycle,
    FREE_TIER,
    BASIC_TIER,
    PRO_TIER,
    PricingTier,
    UsageMeter,
)


class TestPricingTier:
    def test_free_tier(self):
        assert FREE_TIER.price == 0.0
        assert FREE_TIER.max_entries == 1000

    def test_basic_tier(self):
        assert BASIC_TIER.price == 99.0
        assert BASIC_TIER.max_entries == 50000

    def test_pro_tier(self):
        assert PRO_TIER.price == 499.0

    def test_to_dict(self):
        d = BASIC_TIER.to_dict()
        assert d["name"] == "基础版"
        assert "price" in d


class TestUsageMeter:
    def test_record_api_call(self):
        m = UsageMeter(tenant_id="t1")
        m.record_api_call()
        m.record_api_call()
        assert m.current_api_calls == 2

    def test_record_entry(self):
        m = UsageMeter(tenant_id="t1")
        m.record_entry()
        assert m.current_entries == 1

    def test_usage_percentage(self):
        m = UsageMeter(tenant_id="t1", tier=BASIC_TIER)
        m.current_entries = 25000
        pct = m.usage_percentage()
        assert pct["entries"] == 50.0

    def test_check_warning(self):
        m = UsageMeter(tenant_id="t1", tier=BASIC_TIER)
        m.current_entries = 45000  # 90% of 50000
        warnings = m.check_warning(threshold=80.0)
        assert len(warnings) >= 1

    def test_no_warning(self):
        m = UsageMeter(tenant_id="t1", tier=BASIC_TIER)
        m.current_entries = 100
        warnings = m.check_warning()
        assert len(warnings) == 0

    def test_reset_period(self):
        m = UsageMeter(tenant_id="t1")
        m.current_entries = 50
        m.current_api_calls = 100
        record = m.reset_period()
        assert record.entries_used == 50
        assert m.current_entries == 0


class TestBillingEngine:
    def test_register_tenant(self):
        engine = BillingEngine()
        meter = engine.register_tenant("t1", "basic")
        assert meter.tier.tier_id == "basic"

    def test_register_default_free(self):
        engine = BillingEngine()
        meter = engine.register_tenant("t1")
        assert meter.tier.tier_id == "free"

    def test_upgrade_tier(self):
        engine = BillingEngine()
        engine.register_tenant("t1", "free")
        assert engine.upgrade_tier("t1", "basic") is True
        assert engine.get_meter("t1").tier.tier_id == "basic"

    def test_upgrade_nonexistent(self):
        engine = BillingEngine()
        assert engine.upgrade_tier("t1", "basic") is False

    def test_calculate_overage(self):
        engine = BillingEngine()
        m = engine.register_tenant("t1", "basic")
        m.current_entries = 55000
        overage = engine.calculate_overage(m)
        assert overage > 0

    def test_no_overage(self):
        engine = BillingEngine()
        m = engine.register_tenant("t1", "basic")
        m.current_entries = 100
        assert engine.calculate_overage(m) == 0.0

    def test_generate_bill(self):
        engine = BillingEngine()
        m = engine.register_tenant("t1", "basic")
        m.current_entries = 100
        bill = engine.generate_bill("t1")
        assert bill.base_price == 99.0
        assert bill.total == 99.0

    def test_generate_bill_with_overage(self):
        engine = BillingEngine()
        m = engine.register_tenant("t1", "basic")
        m.current_entries = 55000
        m.current_api_calls = 600000
        bill = engine.generate_bill("t1")
        assert bill.overage_charges > 0
        assert bill.total > bill.base_price

    def test_generate_bill_nonexistent(self):
        engine = BillingEngine()
        assert engine.generate_bill("nonexistent") is None

    def test_get_bills(self):
        engine = BillingEngine()
        engine.register_tenant("t1", "basic")
        engine.generate_bill("t1")
        assert len(engine.get_bills("t1")) == 1

    def test_check_warnings(self):
        engine = BillingEngine()
        m = engine.register_tenant("t1", "basic")
        m.current_entries = 45000
        warnings = engine.check_warnings("t1", threshold=80.0)
        assert len(warnings) >= 1

    def test_audit_log(self):
        engine = BillingEngine()
        engine.register_tenant("t1", "basic")
        engine.upgrade_tier("t1", "pro")
        log = engine.get_audit_log("t1")
        assert len(log) == 2
        assert log[0]["action"] == "register"
        assert log[1]["action"] == "upgrade"

    def test_available_tiers(self):
        engine = BillingEngine()
        tiers = engine.available_tiers
        assert "free" in tiers
        assert "basic" in tiers
        assert "pro" in tiers
