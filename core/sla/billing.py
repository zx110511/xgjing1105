"""
计费框架 v1.0
==============
功能:
  1. 使用量计量(记忆条目/QPS/API调用/存储)
  2. 计费规则引擎(阶梯定价/包年/免费额度)
  3. 账单生成(日/月)
  4. 使用量预警(接近配额80%)
  5. 审计日志(所有计费操作可追溯)
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tianji.sla.billing")


class BillingCycle(str, Enum):
    """计费周期"""
    DAILY = "daily"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class PricingModel(str, Enum):
    """定价模型"""
    FREE = "free"
    TIERED = "tiered"
    FLAT = "flat"
    USAGE_BASED = "usage_based"


@dataclass
class PricingTier:
    """定价套餐"""
    name: str
    tier_id: str
    price: float = 0.0
    cycle: BillingCycle = BillingCycle.MONTHLY
    max_entries: int = 1000
    max_qps: int = 10
    max_api_calls: int = 10000
    max_storage_mb: float = 10.0
    model: PricingModel = PricingModel.TIERED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tier_id": self.tier_id,
            "price": self.price,
            "cycle": self.cycle.value,
            "max_entries": self.max_entries,
            "max_qps": self.max_qps,
            "max_api_calls": self.max_api_calls,
            "max_storage_mb": self.max_storage_mb,
        }


# 预定义套餐
FREE_TIER = PricingTier(
    name="免费版", tier_id="free", price=0.0,
    max_entries=1000, max_qps=10, max_api_calls=10000,
    max_storage_mb=10.0, model=PricingModel.FREE,
)

BASIC_TIER = PricingTier(
    name="基础版", tier_id="basic", price=99.0,
    max_entries=50000, max_qps=50, max_api_calls=500000,
    max_storage_mb=100.0,
)

PRO_TIER = PricingTier(
    name="专业版", tier_id="pro", price=499.0,
    max_entries=500000, max_qps=200, max_api_calls=5000000,
    max_storage_mb=1000.0,
)

ENTERPRISE_TIER = PricingTier(
    name="企业版", tier_id="enterprise", price=0.0,
    max_entries=0, max_qps=0, max_api_calls=0,
    max_storage_mb=0.0, model=PricingModel.FLAT,
)


@dataclass
class UsageRecord:
    """使用量记录"""
    tenant_id: str
    timestamp: float = field(default_factory=time.time)
    entries_used: int = 0
    api_calls: int = 0
    storage_mb: float = 0.0
    qps_peak: float = 0.0


@dataclass
class UsageMeter:
    """使用量计量器"""
    tenant_id: str
    tier: PricingTier = field(default_factory=lambda: FREE_TIER)
    current_entries: int = 0
    current_api_calls: int = 0
    current_storage_mb: float = 0.0
    current_qps: float = 0.0
    period_start: float = field(default_factory=time.time)

    def record_api_call(self) -> None:
        """记录API调用"""
        self.current_api_calls += 1

    def record_entry(self) -> None:
        """记录条目写入"""
        self.current_entries += 1

    def set_storage(self, mb: float) -> None:
        """设置存储使用量"""
        self.current_storage_mb = mb

    def set_qps(self, qps: float) -> None:
        """设置当前QPS"""
        self.current_qps = qps

    def usage_percentage(self) -> Dict[str, float]:
        """计算使用率百分比"""
        tier = self.tier
        return {
            "entries": (self.current_entries / tier.max_entries * 100) if tier.max_entries > 0 else 0.0,
            "api_calls": (self.current_api_calls / tier.max_api_calls * 100) if tier.max_api_calls > 0 else 0.0,
            "storage": (self.current_storage_mb / tier.max_storage_mb * 100) if tier.max_storage_mb > 0 else 0.0,
        }

    def check_warning(self, threshold: float = 80.0) -> List[str]:
        """检查使用率预警"""
        warnings: List[str] = []
        pct = self.usage_percentage()
        for dim, value in pct.items():
            if value >= threshold:
                warnings.append(f"{dim} 使用率 {value:.1f}% 超过预警阈值 {threshold}%")
        return warnings

    def reset_period(self) -> UsageRecord:
        """重置计费周期，返回使用记录"""
        record = UsageRecord(
            tenant_id=self.tenant_id,
            entries_used=self.current_entries,
            api_calls=self.current_api_calls,
            storage_mb=self.current_storage_mb,
            qps_peak=self.current_qps,
        )
        self.current_entries = 0
        self.current_api_calls = 0
        self.period_start = time.time()
        return record


@dataclass
class Bill:
    """账单"""
    bill_id: str
    tenant_id: str
    tier: PricingTier
    period_start: float
    period_end: float
    base_price: float = 0.0
    overage_charges: float = 0.0
    total: float = 0.0
    usage: Optional[UsageRecord] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bill_id": self.bill_id,
            "tenant_id": self.tenant_id,
            "tier": self.tier.name,
            "base_price": self.base_price,
            "overage_charges": self.overage_charges,
            "total": self.total,
        }


class BillingEngine:
    """计费引擎"""

    OVERAGE_RATE_PER_1K_ENTRIES = 2.0
    OVERAGE_RATE_PER_1K_API = 0.5
    OVERAGE_RATE_PER_MB = 0.1

    def __init__(self) -> None:
        self._meters: Dict[str, UsageMeter] = {}
        self._bills: List[Bill] = []
        self._audit_log: List[Dict[str, Any]] = []
        self._tiers: Dict[str, PricingTier] = {
            "free": FREE_TIER,
            "basic": BASIC_TIER,
            "pro": PRO_TIER,
            "enterprise": ENTERPRISE_TIER,
        }

    def register_tenant(
        self, tenant_id: str, tier_id: str = "free"
    ) -> UsageMeter:
        """注册租户到计费系统"""
        tier = self._tiers.get(tier_id, FREE_TIER)
        meter = UsageMeter(tenant_id=tenant_id, tier=tier)
        self._meters[tenant_id] = meter
        self._audit("register", tenant_id, {"tier": tier_id})
        return meter

    def get_meter(self, tenant_id: str) -> Optional[UsageMeter]:
        """获取租户计量器"""
        return self._meters.get(tenant_id)

    def upgrade_tier(self, tenant_id: str, new_tier_id: str) -> bool:
        """升级套餐"""
        meter = self._meters.get(tenant_id)
        new_tier = self._tiers.get(new_tier_id)
        if meter is None or new_tier is None:
            return False
        old_tier = meter.tier
        meter.tier = new_tier
        self._audit("upgrade", tenant_id, {
            "from": old_tier.tier_id, "to": new_tier_id
        })
        return True

    def downgrade_tier(self, tenant_id: str, new_tier_id: str) -> bool:
        """降级套餐"""
        return self.upgrade_tier(tenant_id, new_tier_id)

    def calculate_overage(self, meter: UsageMeter) -> float:
        """计算超额费用"""
        tier = meter.tier
        overage = 0.0

        if tier.max_entries > 0 and meter.current_entries > tier.max_entries:
            excess = meter.current_entries - tier.max_entries
            overage += (excess / 1000) * self.OVERAGE_RATE_PER_1K_ENTRIES

        if tier.max_api_calls > 0 and meter.current_api_calls > tier.max_api_calls:
            excess = meter.current_api_calls - tier.max_api_calls
            overage += (excess / 1000) * self.OVERAGE_RATE_PER_1K_API

        if tier.max_storage_mb > 0 and meter.current_storage_mb > tier.max_storage_mb:
            excess = meter.current_storage_mb - tier.max_storage_mb
            overage += excess * self.OVERAGE_RATE_PER_MB

        return round(overage, 2)

    def generate_bill(self, tenant_id: str) -> Optional[Bill]:
        """生成账单"""
        meter = self._meters.get(tenant_id)
        if meter is None:
            return None

        overage = self.calculate_overage(meter)
        base = meter.tier.price
        total = base + overage

        bill = Bill(
            bill_id=f"bill-{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id,
            tier=meter.tier,
            period_start=meter.period_start,
            period_end=time.time(),
            base_price=base,
            overage_charges=overage,
            total=total,
            usage=meter.reset_period(),
        )
        self._bills.append(bill)
        self._audit("bill", tenant_id, {"total": total})
        return bill

    def get_bills(self, tenant_id: Optional[str] = None) -> List[Bill]:
        """获取账单列表"""
        if tenant_id:
            return [b for b in self._bills if b.tenant_id == tenant_id]
        return list(self._bills)

    def check_warnings(self, tenant_id: str, threshold: float = 80.0) -> List[str]:
        """检查使用率预警"""
        meter = self._meters.get(tenant_id)
        if meter is None:
            return []
        return meter.check_warning(threshold)

    def get_audit_log(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取审计日志"""
        if tenant_id:
            return [l for l in self._audit_log if l["tenant_id"] == tenant_id]
        return list(self._audit_log)

    def _audit(
        self, action: str, tenant_id: str, details: Dict[str, Any]
    ) -> None:
        """记录审计日志"""
        self._audit_log.append({
            "timestamp": time.time(),
            "action": action,
            "tenant_id": tenant_id,
            **details,
        })

    @property
    def available_tiers(self) -> Dict[str, PricingTier]:
        """获取可用套餐"""
        return dict(self._tiers)
