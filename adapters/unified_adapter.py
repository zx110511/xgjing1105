"""
统一记忆适配器 - 集成自unified-memory-bridge
双写保障 + 智能路由 + 并行查询

修复v3.1: 直接注入ICME引擎，不再通过HTTP调用基类
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

from .base import PlatformAdapter, MemorySDKConfig

try:
    from core.shared.router import LayerRouter, TargetSystem
except ImportError:
    from ..core.router import LayerRouter, TargetSystem


@dataclass
class UnifiedMemory:
    id: str
    content: str
    layer: str
    source: str
    tags: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass
class StoreResult:
    entry_id: str
    layer: str
    target_system: str
    status: str


@dataclass
class RecallResult:
    results: List[UnifiedMemory]
    total: int
    sources: Dict[str, int]
    query_time_ms: float


class UnifiedMemoryAdapter(PlatformAdapter):
    def __init__(
        self,
        config: MemorySDKConfig = None,
        engine: Any = None,
        external_client: Optional[Any] = None,
    ):
        super().__init__(config)
        self.engine = engine
        self.external_client = external_client
        self.router = LayerRouter(
            health_check_fn=self._external_health_check if external_client else None,
            health_check_interval=30.0,
        )
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._stats = {
            "total_stores": 0,
            "total_recalls": 0,
            "icme_calls": 0,
            "external_calls": 0,
            "start_time": time.time(),
        }

    def _external_health_check(self) -> bool:
        if self.external_client and hasattr(self.external_client, "health_check"):
            try:
                return bool(self.external_client.health_check())
            except Exception:
                return False
        return False

    def remember(
        self,
        content: str,
        layer: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority: str = "medium",
    ) -> StoreResult:
        target = self.router.route(content, layer, tags)
        entry_id = ""
        status = "unknown"
        resolved_layer = layer or "working"

        if target == TargetSystem.BOTH:
            icme_id = ""
            external_id = ""
            icme_ok = False
            external_ok = False

            try:
                if self.engine:
                    result = self.engine.remember(content, resolved_layer, tags, priority)
                    icme_id = result.get("id", "") if isinstance(result, dict) else result
                else:
                    icme_id = self._store_to_server(content, resolved_layer, tags, priority)
                icme_ok = bool(icme_id)
            except Exception:
                pass

            try:
                external_id = self._store_to_external(content, layer, tags)
                external_ok = bool(external_id)
            except Exception:
                pass

            self._stats["icme_calls"] += 1
            self._stats["external_calls"] += 1
            self._stats["total_stores"] += 1

            entry_id = icme_id or external_id or ""
            if icme_ok and external_ok:
                status = "stored_in_both"
            elif icme_ok:
                status = "stored_in_icme_external_failed"
                self.router.update_external_health(False)
            elif external_ok:
                status = "stored_in_external_icme_failed"
            else:
                status = "both_failed"

        elif target == TargetSystem.EXTERNAL:
            entry_id = self._store_to_external(content, layer, tags)
            self._stats["external_calls"] += 1
            status = "stored_in_external"
        else:
            if self.engine:
                result = self.engine.remember(content, resolved_layer, tags, priority)
                entry_id = result.get("id", "") if isinstance(result, dict) else result
            else:
                entry_id = self._store_to_server(content, resolved_layer, tags, priority)
            self._stats["icme_calls"] += 1
            status = "stored_in_icme"

        self._stats["total_stores"] += 1 if target != TargetSystem.BOTH else 0

        return StoreResult(
            entry_id=entry_id, layer=resolved_layer, target_system=target.value, status=status
        )

    def recall(
        self, query: str, layers: Optional[List[str]] = None, limit: int = 10
    ) -> RecallResult:
        start_time = time.time()
        routing = self.router.split_query(query, layers)

        external_results = []
        icme_results = []

        futures = []
        if routing["external_layers"]:
            futures.append(
                (
                    "external",
                    self._executor.submit(
                        self._external_recall, query, routing["external_layers"], limit
                    ),
                )
            )
        if routing["icme_layers"]:
            futures.append(
                (
                    "icme",
                    self._executor.submit(
                        self._icme_recall, query, routing["icme_layers"], limit
                    ),
                )
            )

        for source_name, f in futures:
            try:
                result = f.result(timeout=10)
                if result is not None and isinstance(result, list):
                    for mem in result:
                        if isinstance(mem, UnifiedMemory):
                            if source_name == "external":
                                external_results.append(mem)
                            else:
                                icme_results.append(mem)
            except Exception as e:
                print(f"[UnifiedAdapter] {source_name} recall worker error: {e}")

        unified_results = []
        sources = {"external": 0, "icme": 0}
        seen_ids = set()

        for mem in external_results + icme_results:
            if mem.id not in seen_ids:
                seen_ids.add(mem.id)
                unified_results.append(mem)
                sources[mem.source] = sources.get(mem.source, 0) + 1

        unified_results.sort(key=lambda x: x.relevance_score, reverse=True)
        unified_results = unified_results[:limit]

        self._stats["total_recalls"] += 1

        return RecallResult(
            results=unified_results,
            total=len(unified_results),
            sources=sources,
            query_time_ms=(time.time() - start_time) * 1000,
        )

    def _store_to_server(self, content: str, layer: str, tags: List[str], priority: str) -> str:
        result = super().remember(content, layer, tags, priority)
        if result and isinstance(result, dict):
            return result.get("id", "")
        return ""

    def _store_to_external(self, content: str, layer: Optional[str], tags: List[str]) -> str:
        if self.external_client and hasattr(self.external_client, "store"):
            return self.external_client.store(content, layer, tags)
        return ""

    def _icme_recall(self, query: str, layers: List[str], limit: int) -> List[UnifiedMemory]:
        try:
            if self.engine:
                entries = self.engine.recall(query=query, layers=layers, limit=limit)
            else:
                entries = self._recall_from_server(query, layers, limit)
        except Exception as e:
            print(f"[UnifiedAdapter] icme recall failed: {e}")
            return []
        result = []
        for m in entries:
            if isinstance(m, dict):
                score = m.get("value_score", m.get("relevance_score", 0.8))
                result.append(
                    UnifiedMemory(
                        id=f"icme-{m.get('id', '')}",
                        content=m.get("content", ""),
                        layer=m.get("layer", "working"),
                        source="icme",
                        tags=m.get("tags", []),
                        relevance_score=score,
                        created_at=m.get("created_at", time.time()),
                    )
                )
            elif hasattr(m, "to_dict"):
                d = m.to_dict()
                result.append(
                    UnifiedMemory(
                        id=f"icme-{d.get('id', '')}",
                        content=d.get("content", ""),
                        layer=d.get("layer", "working"),
                        source="icme",
                        tags=d.get("tags", []),
                        relevance_score=d.get("value_score", 0.8),
                        created_at=d.get("created_at", time.time()),
                    )
                )
        return result

    def _recall_from_server(self, query: str, layers: List[str], limit: int) -> List[Dict]:
        result = super().recall(query, limit=limit)
        if isinstance(result, list):
            return result
        return []

    def _external_recall(self, query: str, layers: List[str], limit: int) -> List[UnifiedMemory]:
        if not self.external_client or not hasattr(self.external_client, "recall"):
            return []
        try:
            memories = self.external_client.recall(query, layers=layers, limit=limit)
        except Exception as e:
            print(f"[UnifiedAdapter] external recall failed: {e}")
            return []
        result = []
        for m in memories:
            result.append(
                UnifiedMemory(
                    id=f"external-{m.get('id', '')}",
                    content=m.get("content", ""),
                    layer=m.get("layer", "working"),
                    source="external",
                    tags=m.get("tags", []),
                    relevance_score=m.get("relevance_score", 0.8),
                    created_at=m.get("created_at", time.time()),
                )
            )
        return result

    def get_stats(self) -> Dict[str, Any]:
        external_healthy = self._external_health_check()

        return {
            "adapter": self._stats,
            "external": {"healthy": external_healthy},
            "router": self.router.get_stats(),
            "uptime_seconds": time.time() - self._stats["start_time"],
        }

    def health_check(self) -> Dict[str, bool]:
        external_ok = self._external_health_check()
        return {"external": external_ok, "icme": True, "overall": external_ok or True}

    def close(self):
        if self._executor:
            self._executor.shutdown(wait=False)
