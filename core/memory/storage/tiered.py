"""
[v10-ready] 热冷分层存储引擎 — core.storage.tiered

灵境道谱溯源: D1-2【Δ阈值煞】· 道一·记忆体道 · 四地煞之芯之术
  - 从 core/hybrid_engine.py 拆分而来 (P1-03)
  - 职责: MemoryTier / TierConfig / TIER_DEFAULTS / TieredStorageEngine
  - 阈值管理 + 降级保护 + 容量监控 + 分层迁移

设计哲学:
  Hot  — L0感官/L1工作 → 高频访问, 内存缓存, 实时读写
  Warm — L2短期/L3事件 → 中频访问, SQLite存储, 批量迁移
  Cold — L4语义/L5元知 → 低频访问, JSON归档, 压缩存储
"""

import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class MemoryTier(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


@dataclass
class TierConfig:
    tier: MemoryTier
    layers: list[str]
    max_size_mb: float
    access_threshold_promote: int
    access_threshold_demote: int
    recency_days_hot: float
    in_memory_cache: bool


TIER_DEFAULTS = {
    MemoryTier.HOT: TierConfig(
        tier=MemoryTier.HOT,
        layers=["sensory", "working"],
        max_size_mb=50.0,
        access_threshold_promote=10,
        access_threshold_demote=5,
        recency_days_hot=1.0,
        in_memory_cache=True,
    ),
    MemoryTier.WARM: TierConfig(
        tier=MemoryTier.WARM,
        layers=["short_term", "episodic"],
        max_size_mb=200.0,
        access_threshold_promote=30,
        access_threshold_demote=2,
        recency_days_hot=7.0,
        in_memory_cache=False,
    ),
    MemoryTier.COLD: TierConfig(
        tier=MemoryTier.COLD,
        layers=["semantic", "meta"],
        max_size_mb=500.0,
        access_threshold_promote=50,
        access_threshold_demote=0,
        recency_days_hot=30.0,
        in_memory_cache=False,
    ),
}


class TieredStorageEngine:
    """
    [v10-ready] 热冷分层存储引擎 v1.0

    设计哲学:
      Hot  — L0感官/L1工作 → 高频访问, 内存缓存, 实时读写
      Warm — L2短期/L3事件 → 中频访问, SQLite存储, 批量迁移
      Cold — L4语义/L5元知 → 低频访问, JSON归档, 压缩存储

    晋升/降级规则:
      晋升: access_count ≥ promote_threshold → 向上迁移一层
      降级: access_count < demote_threshold AND days_since_access > recency → 向下迁移一层
    """

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            # [FIX-tiered-001] 修正幽灵导入路径 + 处理DEFAULT_CONFIG可能是dict的情况
            from core.shared.config import ICMEConfig as _ICMEConfig
            _cfg = getattr(_ICMEConfig, 'DEFAULT_CONFIG', None)
            if isinstance(_cfg, dict):
                data_dir = _cfg.get('data_path', str(Path.cwd() / "data"))
            elif hasattr(_cfg, 'data_path'):
                data_dir = _cfg.data_path
            else:
                data_dir = str(Path.cwd() / "data")
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._tiers: dict[MemoryTier, TierConfig] = dict(TIER_DEFAULTS)
        self._entry_tiers: dict[str, MemoryTier] = {}
        self._hot_cache: dict[str, dict] = {}
        self._migration_log: list[dict[str, Any]] = []
        self._lock = threading.RLock()

        self._tier_dirs = {}
        for tier in MemoryTier:
            tp = self._data_dir / tier.value
            tp.mkdir(parents=True, exist_ok=True)
            self._tier_dirs[tier] = tp

    def classify_entry(self, entry_id: str, entry_data: dict) -> MemoryTier:
        layer = entry_data.get("layer", "working")
        priority = entry_data.get("priority", "medium")
        access_count = entry_data.get("access_count", 0)
        value_score = entry_data.get("value_score", 0.5)

        if layer in self._tiers[MemoryTier.HOT].layers:
            return MemoryTier.HOT
        if layer in self._tiers[MemoryTier.WARM].layers:
            return MemoryTier.WARM
        if layer in self._tiers[MemoryTier.COLD].layers:
            return MemoryTier.COLD

        if priority in ("critical", "high") and access_count >= 5:
            return MemoryTier.HOT
        if priority == "low" or (access_count == 0 and value_score < 0.4):
            return MemoryTier.COLD
        return MemoryTier.WARM

    def promote(self, entry_id: str, entry_data: dict) -> MemoryTier | None:
        with self._lock:
            current = self._entry_tiers.get(
                entry_id, self.classify_entry(entry_id, entry_data)
            )
            tiers_order = [MemoryTier.COLD, MemoryTier.WARM, MemoryTier.HOT]
            try:
                idx = tiers_order.index(current)
                if idx < len(tiers_order) - 1:
                    new_tier = tiers_order[idx + 1]
                    self._entry_tiers[entry_id] = new_tier
                    self._migration_log.append(
                        {
                            "entry_id": entry_id,
                            "from_tier": current.value,
                            "to_tier": new_tier.value,
                            "reason": "promote",
                            "timestamp": time.time(),
                        }
                    )
                    if new_tier == MemoryTier.HOT:
                        self._hot_cache[entry_id] = entry_data
                    return new_tier
            except ValueError:
                pass
            return None

    def demote(self, entry_id: str, entry_data: dict) -> MemoryTier | None:
        with self._lock:
            current = self._entry_tiers.get(
                entry_id, self.classify_entry(entry_id, entry_data)
            )
            tiers_order = [MemoryTier.COLD, MemoryTier.WARM, MemoryTier.HOT]
            try:
                idx = tiers_order.index(current)
                if idx > 0:
                    new_tier = tiers_order[idx - 1]
                    self._entry_tiers[entry_id] = new_tier
                    self._migration_log.append(
                        {
                            "entry_id": entry_id,
                            "from_tier": current.value,
                            "to_tier": new_tier.value,
                            "reason": "demote",
                            "timestamp": time.time(),
                        }
                    )
                    if current == MemoryTier.HOT:
                        self._hot_cache.pop(entry_id, None)
                    return new_tier
            except ValueError:
                pass
            return None

    def auto_rebalance(self, entries: dict[str, dict]) -> dict[str, int]:
        stats = {"promoted": 0, "demoted": 0, "unchanged": 0}
        now = time.time()

        for eid, data in entries.items():
            access_count = data.get("access_count", 0)
            last_accessed = data.get("last_accessed", now)
            current = self._entry_tiers.get(eid, self.classify_entry(eid, data))
            cfg = self._tiers[current]

            days_since = (now - last_accessed) / 86400.0

            if access_count >= cfg.access_threshold_promote:
                result = self.promote(eid, data)
                if result:
                    stats["promoted"] += 1
                else:
                    stats["unchanged"] += 1
            elif (
                access_count < cfg.access_threshold_demote
                and days_since > cfg.recency_days_hot
            ):
                result = self.demote(eid, data)
                if result:
                    stats["demoted"] += 1
                else:
                    stats["unchanged"] += 1
            else:
                stats["unchanged"] += 1

        return stats

    def get_tier(self, entry_id: str) -> MemoryTier:
        return self._entry_tiers.get(entry_id, MemoryTier.WARM)

    def get_tier_stats(self) -> dict[str, Any]:
        with self._lock:
            counts = {t.value: 0 for t in MemoryTier}
            for tid, tier in self._entry_tiers.items():
                counts[tier.value] += 1

            return {
                "tier_counts": counts,
                "hot_cache_size": len(self._hot_cache),
                "total_classified": len(self._entry_tiers),
                "migrations": len(self._migration_log),
                "recent_migrations": self._migration_log[-10:]
                if self._migration_log
                else [],
            }

    def get_hot_entries(self) -> list[str]:
        with self._lock:
            return list(self._hot_cache.keys())

    def get_tier_dir(self, tier: MemoryTier) -> Path:
        return self._tier_dirs[tier]

    def clear_migration_log(self):
        with self._lock:
            self._migration_log.clear()
