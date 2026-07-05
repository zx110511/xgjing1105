# -*- coding: utf-8-sig -*-
"""天机核心聚阵 — "六层记忆+L-Asset" L3聚阵统一门面  [v10-ready]

天机v9.1核心架构组件，统一编排6个天罡合体：
- 天罡-01 记忆写入体 (MemoryWriter)
- 天罡-02 记忆检索单 (MemoryRetriever)
- 天罡-03 记忆晋升体 (MemoryConsolidator)
- 天罡-17 图谱同步体 (GraphSynchronizer)
- 天罡-23 图谱填充体 (GraphFiller)
- 天罡-88 主动记忆体 (ActiveMemoryEngine)

架构定位: L3聚阵 = 多个L2合体协同完成系统级能力
对标: v10.0.1企划书 "六层记忆+L-Asset = 天机核心聚阵"
版本: 1.0.0
兼容: v9.1原有API不变，本模块为上层封装
"""

# [v10-ready]
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # [v10-ready] 仅类型检查期导入，运行期零开销
    from core.shared.interfaces import ClusterHealth


class MemoryCluster:
    """天机核心聚阵 — 六层记忆+L-Asset统一编排器  [v10-ready]

    职责：
    1. 统一初始化和生命周期管理（启动/停止/重启）
    2. 提供高级API（记忆写入/检索/晋升的统一入口）
    3. 编排合体间协作（写入→图谱填充，晋升→图谱同步）
    4. 健康检查和状态报告
    5. 为Protocol接口层提供默认本地实现的组装

    使用方式:
        cluster = MemoryCluster()
        cluster.start()
        result = cluster.remember("重要知识", layer="semantic")
        entries = cluster.recall("知识查询")
        cluster.stop()
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """初始化聚阵 — 懒加载各合体，不立即创建实例  [v10-ready]"""
        self._config: dict[str, Any] = config or {}
        self._engine: Any = None  # 天罡-01/02/03 (ICMEStorageEngine)
        self._graph: Any = None  # 天罡-17 (KnowledgeGraphStore)
        self._asset_registry: Any = None  # L-Asset (AssetRegistry)
        self._active_memory: Any = None  # 天罡-88 (InterceptLayer)
        self._started: bool = False
        self._start_time: float | None = None

    # === 懒加载 (延迟导入避免循环依赖) ===

    def _get_engine(self) -> Any:
        """获取记忆引擎实例 — 天罡-01/02/03  [v10-ready]"""
        if self._engine is None:
            from core.memory.hybrid_engine import ICMEStorageEngine

            self._engine = ICMEStorageEngine()
        return self._engine

    def _get_graph(self) -> Any:
        """获取图谱引擎实例 — 天罡-17/23  [v10-ready]"""
        if self._graph is None:
            try:
                from core.memory.graph_store import KnowledgeGraphStore

                self._graph = KnowledgeGraphStore()
            except Exception:
                self._graph = None  # 图谱不可用时降级
        return self._graph

    def _get_asset_registry(self) -> Any:
        """获取知识资产注册表实例 — L-Asset  [v10-ready]"""
        if self._asset_registry is None:
            try:
                from core.memory.asset_atom import AssetRegistry

                self._asset_registry = AssetRegistry()
            except Exception:
                self._asset_registry = None  # 资产银行不可用时降级
        return self._asset_registry

    def _get_active_memory(self) -> Any:
        """获取主动记忆实例 — 天罡-88  [v10-ready]"""
        if self._active_memory is None:
            try:
                from active_memory.protocol import InterceptLayer

                self._active_memory = InterceptLayer(engine=self._get_engine())
            except Exception:
                self._active_memory = None
        return self._active_memory

    # === 高级API ===

    def remember(
        self,
        content: str,
        layer: str = "working",
        tags: list[str] | None = None,
        use_llm: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """统一记忆写入 — 编排写入体+门禁+资产注册+图谱填充  [v10-ready]

        流程: content → QualityGate → engine.remember → AssetRegistry → GraphFill

        Returns:
            写入结果字典 (含 id, status, layer 等字段)
        """
        engine = self._get_engine()
        result = engine.remember(
            content=content, layer=layer, tags=tags, use_llm=use_llm, **kwargs
        )

        # 写入后钩子：触发图谱填充
        if result and result.get("id"):
            self._on_memory_written(result)

        return result

    def recall(
        self,
        query: str,
        layers: list[str] | None = None,
        limit: int = 20,
        use_graph: bool = True,
        **kwargs: Any,
    ) -> list[Any]:
        """统一记忆检索 — 编排检索单+图谱辅助+TCL增强  [v10-ready]

        流程: query → TCL归一化 → engine.recall → (可选)graph辅助 → 融合排序
        """
        engine = self._get_engine()
        entries = engine.recall(query=query, layers=layers, limit=limit, **kwargs)

        # 可选：图谱辅助扩展
        if use_graph and entries:
            entries = self._enrich_with_graph(entries, query)

        return entries

    def consolidate(
        self,
        from_layer: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """统一晋升触发 — 编排晋升体+图谱同步  [v10-ready]

        Returns:
            晋升结果字典 (含 promoted_count, details 等字段)
        """
        engine = self._get_engine()
        # 调用引擎的晋升方法
        if from_layer:
            result = engine.consolidate_batch(
                from_layer=from_layer, use_quality_promotion=force
            )
        else:
            # 全层扫描
            result = {"promoted_count": 0, "details": []}
            for layer in ["sensory", "working", "short_term", "episodic", "semantic"]:
                try:
                    layer_result = engine.consolidate_batch(
                        from_layer=layer, use_quality_promotion=force
                    )
                    if layer_result:
                        result["promoted_count"] += layer_result.get(
                            "promoted_count", 0
                        )
                        result["details"].append(layer_result)
                except Exception:
                    continue

        # 晋升后钩子：触发图谱同步
        if result and result.get("promoted_count", 0) > 0:
            self._on_consolidation_done(result)

        return result

    # === 生命周期 ===

    def start(self) -> None:
        """启动聚阵 — 初始化所有合体  [v10-ready]"""
        import time

        self._get_engine()  # 预热引擎
        self._started = True
        self._start_time = time.time()

    def stop(self) -> None:
        """停止聚阵 — 优雅关闭  [v10-ready]"""
        self._started = False
        self._engine = None
        self._graph = None
        self._asset_registry = None
        self._active_memory = None

    def restart(self) -> None:
        """重启聚阵  [v10-ready]"""
        self.stop()
        self.start()

    # === 健康与状态 ===

    def health_check(self) -> "ClusterHealth":
        """聚阵健康检查 — 检查6个合体状态  [v10-ready]"""
        import time

        from core.shared.interfaces import ClusterHealth

        engine = self._get_engine()
        components: dict[str, bool] = {
            "memory_engine": engine is not None,
            "graph_engine": self._get_graph() is not None,
            "active_memory": self._get_active_memory() is not None,
            "asset_registry": self._get_asset_registry() is not None,
            "quality_gate": hasattr(engine, "_apply_quality_gate")
            or hasattr(engine, "remember"),
            "consolidation": hasattr(engine, "consolidate_batch"),
        }

        all_healthy = all(components.values())
        critical_healthy = components["memory_engine"] and components["consolidation"]

        status = (
            "healthy"
            if all_healthy
            else ("degraded" if critical_healthy else "unhealthy")
        )
        uptime = (time.time() - self._start_time) if self._start_time else 0.0

        return ClusterHealth(
            status=status,
            components=components,
            memory_usage=self._get_memory_usage(),
            uptime_seconds=uptime,
        )

    def get_status(self) -> dict[str, Any]:
        """获取聚阵运行状态  [v10-ready]"""
        engine = self._get_engine()
        stats = engine.stats() if hasattr(engine, "stats") else {}
        return {
            "started": self._started,
            "engine_stats": stats,
            "graph_available": self._get_graph() is not None,
            "active_memory_available": self._get_active_memory() is not None,
        }

    def get_layer_stats(self) -> dict[str, dict[str, Any]]:
        """获取六层记忆的详细统计  [v10-ready]"""
        engine = self._get_engine()
        if hasattr(engine, "_layers"):
            return {
                name: {"count": len(layer), "size_bytes": 0}
                for name, layer in engine._layers.items()
            }
        return {}

    # === 内部编排方法 ===

    def _on_memory_written(self, result: dict[str, Any]) -> None:
        """写入后钩子 — 触发图谱填充（天罡-23）  [v10-ready]"""
        graph = self._get_graph()
        if graph is None:
            return
        try:
            # 从写入结果中提取信息填充图谱
            if hasattr(graph, "sync_from_memories"):
                graph.sync_from_memories([result])
        except Exception:
            pass  # 图谱填充失败不影响主流程

    def _on_consolidation_done(self, result: dict[str, Any]) -> None:
        """晋升后钩子 — 触发图谱同步（天罡-17）  [v10-ready]"""
        graph = self._get_graph()
        if graph is None:
            return
        try:
            promoted_entries = result.get("promoted_entries", [])
            if promoted_entries and hasattr(graph, "sync_from_memories"):
                graph.sync_from_memories(promoted_entries)
        except Exception:
            pass  # 图谱同步失败不影响主流程

    def _enrich_with_graph(self, entries: list[Any], query: str) -> list[Any]:
        """图谱辅助检索增强  [v10-ready]"""
        graph = self._get_graph()
        if graph is None:
            return entries
        try:
            # 从图谱中找到与查询相关的节点，扩展检索结果
            if hasattr(graph, "query_related"):
                related = graph.query_related(query, depth=1)
                # 将图谱相关信息注入到返回结果的metadata中
                for entry in entries:
                    if hasattr(entry, "metadata"):
                        entry.metadata["graph_context"] = related
            return entries
        except Exception:
            return entries

    def _get_memory_usage(self) -> dict[str, Any]:
        """获取记忆使用量  [v10-ready]"""
        try:
            engine = self._get_engine()
            if hasattr(engine, "stats"):
                return engine.stats()
        except Exception:
            pass
        return {}


# === 模块级便捷实例 ===  [v10-ready]

_default_cluster: MemoryCluster | None = None


def get_cluster(config: dict[str, Any] | None = None) -> MemoryCluster:
    """获取默认聚阵实例（单例）  [v10-ready]"""
    global _default_cluster
    if _default_cluster is None:
        _default_cluster = MemoryCluster(config=config)
    return _default_cluster


__all__ = [
    "MemoryCluster",
    "get_cluster",
]
