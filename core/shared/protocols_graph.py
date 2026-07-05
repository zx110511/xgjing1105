# -*- coding: utf-8-sig -*-
"""天机v10.0.1 共享内核Protocol图谱域+资产域接口  [v10-ready]

定义6个Protocol接口：
图谱域 (3个):
- IGraphEngine: 图谱引擎接口
- IGraphQuery: 图谱查询接口
- ITripleExtractor: 三元组提取接口

资产域 (3个):
- IAssetRegistry: 资产注册表接口
- IAssetBinding: 资产绑定接口
- IAssetSnapshot: 资产快照接口

架构定位: core/shared/ Ω基点层 — 图谱+资产聚阵契约
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable


# ============================================================================
# 图谱域 (3个) — IGraphEngine / IGraphQuery / ITripleExtractor
# ============================================================================


@runtime_checkable
class IGraphEngine(Protocol):
    """图谱引擎接口  [v10-ready]

    本地实现: NetworkXGraphEngine (进程内内存图, 单进程默认)
    远程实现: Neo4jGraphEngine (独立图数据库服务)

    切换方式: 提供节点/边增删查与从记忆批量同步图结构，
    分布式模式下图操作下推至远程图数据库。
    """

    def add_node(
        self, node_id: str, node_type: str, properties: dict[str, Any]
    ) -> bool:
        """添加节点。

        Args:
            node_id: 节点唯一标识。
            node_type: 节点类型。
            properties: 节点属性字典。

        Returns:
            添加是否成功。
        """
        ...

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """添加边。

        Args:
            source_id: 起点节点标识。
            target_id: 终点节点标识。
            relation: 关系类型。
            properties: 边属性字典。

        Returns:
            添加是否成功。
        """
        ...

    def query(
        self, pattern: dict[str, Any], *, limit: int = 50
    ) -> list[dict[str, Any]]:
        """按模式查询图。

        Args:
            pattern: 查询模式字典 (节点/关系约束)。
            limit: 返回结果上限。

        Returns:
            命中的子图/路径字典列表。
        """
        ...

    def sync_from_memories(self, entries: list[dict[str, Any]]) -> int:
        """从记忆条目批量同步图结构。

        Args:
            entries: 记忆条目字典列表。

        Returns:
            同步生成/更新的节点数量。
        """
        ...


@runtime_checkable
class IGraphQuery(Protocol):
    """图谱查询接口  [v10-ready]

    本地实现: LocalGraphQuery (进程内图遍历算法)
    远程实现: RemoteGraphQuery (灵境 Cypher/Gremlin 查询服务)

    切换方式: 提供邻居/最短路径/子图提取能力，
    分布式模式下查询语句下推至远程图引擎执行。
    """

    def query_neighbors(
        self,
        node_id: str,
        *,
        depth: int = 1,
        relation_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询邻居节点。

        Args:
            node_id: 中心节点标识。
            depth: 遍历深度。
            relation_filter: 可选关系类型过滤。

        Returns:
            邻居节点字典列表。
        """
        ...

    def shortest_path(self, source_id: str, target_id: str) -> list[str]:
        """计算最短路径。

        Args:
            source_id: 起点节点标识。
            target_id: 终点节点标识。

        Returns:
            路径上的节点标识有序列表 (不可达时为空)。
        """
        ...

    def subgraph(self, node_ids: Sequence[str]) -> dict[str, Any]:
        """提取子图。

        Args:
            node_ids: 子图节点标识序列。

        Returns:
            包含 nodes/edges 的子图字典。
        """
        ...


@runtime_checkable
class ITripleExtractor(Protocol):
    """三元组提取接口  [v10-ready]

    本地实现: LocalTripleExtractor (规则/轻量 NLP 抽取)
    远程实现: RemoteTripleExtractor (灵境 LLM 抽取服务)

    切换方式: 从文本抽取 (主谓宾) 三元组，
    分布式模式下抽取交由远程大模型完成。
    """

    def extract(self, content: str) -> list[tuple[str, str, str]]:
        """从单段文本抽取三元组。

        Args:
            content: 输入文本。

        Returns:
            (主语, 谓语, 宾语) 三元组列表。
        """
        ...

    def batch_extract(
        self, contents: Sequence[str]
    ) -> list[list[tuple[str, str, str]]]:
        """批量抽取三元组。

        Args:
            contents: 文本序列。

        Returns:
            与输入一一对应的三元组列表。
        """
        ...


# ============================================================================
# 资产域 (3个) — IAssetRegistry / IAssetBinding / IAssetSnapshot
# ============================================================================


@runtime_checkable
class IAssetRegistry(Protocol):
    """资产注册表接口  [v10-ready]

    本地实现: LocalAssetRegistry (SQLite 资产表, 单进程默认)
    远程实现: RemoteAssetRegistry (灵境集中式资产银行服务)

    切换方式: 维护 L-Asset 知识资产的注册与检索，
    分布式模式下资产由远程资产银行统一托管。
    """

    def register(
        self,
        memory_id: str,
        content: str,
        content_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """注册一个知识资产。

        Args:
            memory_id: 关联的记忆条目标识。
            content: 资产内容。
            content_type: 内容类型。
            metadata: 可选元数据。

        Returns:
            生成的 asset_id。
        """
        ...

    def get(self, asset_id: str) -> dict[str, Any] | None:
        """读取资产。

        Args:
            asset_id: 资产唯一标识。

        Returns:
            资产字典；不存在时返回 None。
        """
        ...

    def list(
        self, *, content_type: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """列出资产。

        Args:
            content_type: 可选按内容类型过滤。
            limit: 返回数量上限。

        Returns:
            资产字典列表。
        """
        ...

    def verify_binding(self, asset_id: str) -> bool:
        """校验资产三重绑定一致性。

        Args:
            asset_id: 资产唯一标识。

        Returns:
            memory_id↔asset_id↔content_hash 绑定是否一致。
        """
        ...


@runtime_checkable
class IAssetBinding(Protocol):
    """资产绑定接口  [v10-ready]

    本地实现: LocalAssetBinding (进程内绑定表维护)
    远程实现: RemoteAssetBinding (灵境绑定关系服务)

    切换方式: 管理记忆与资产间的绑定关系，
    分布式模式下绑定关系由远程服务一致性维护。
    """

    def bind(self, memory_id: str, asset_id: str) -> bool:
        """建立记忆与资产的绑定。

        Args:
            memory_id: 记忆条目标识。
            asset_id: 资产标识。

        Returns:
            绑定是否成功。
        """
        ...

    def unbind(self, memory_id: str, asset_id: str) -> bool:
        """解除记忆与资产的绑定。

        Args:
            memory_id: 记忆条目标识。
            asset_id: 资产标识。

        Returns:
            解绑是否成功。
        """
        ...

    def get_binding(self, memory_id: str) -> dict[str, Any] | None:
        """查询某记忆的绑定信息。

        Args:
            memory_id: 记忆条目标识。

        Returns:
            绑定关系字典；无绑定时返回 None。
        """
        ...


@runtime_checkable
class IAssetSnapshot(Protocol):
    """资产快照接口  [v10-ready]

    本地实现: LocalAssetSnapshot (进程内版本快照)
    远程实现: RemoteAssetSnapshot (灵境快照存储服务)

    切换方式: 提供资产快照创建/恢复/差异能力，
    分布式模式下快照持久化至远程对象存储。
    """

    def create_snapshot(self, asset_id: str) -> str:
        """为资产创建快照。

        Args:
            asset_id: 资产标识。

        Returns:
            生成的快照标识 snapshot_id。
        """
        ...

    def restore(self, snapshot_id: str) -> bool:
        """从快照恢复资产。

        Args:
            snapshot_id: 快照标识。

        Returns:
            恢复是否成功。
        """
        ...

    def diff(self, snapshot_id_a: str, snapshot_id_b: str) -> dict[str, Any]:
        """比较两个快照差异。

        Args:
            snapshot_id_a: 快照 A 标识。
            snapshot_id_b: 快照 B 标识。

        Returns:
            差异描述字典。
        """
        ...


__all__ = [
    # 图谱域
    "IGraphEngine",
    "IGraphQuery",
    "ITripleExtractor",
    # 资产域
    "IAssetRegistry",
    "IAssetBinding",
    "IAssetSnapshot",
]
