r"""
天机知识图谱存储引擎 (Tianji Knowledge Graph Store) v1.0
========================================================
GraphRAG双引擎架构 - 知识图谱+向量检索混合存储

设计哲学:
  向量检索作为入口点，快速定位相关记忆
  图谱扩展提供多跳推理能力
  融合排序平衡准确率和延迟

架构位置: 天机/core/graph_store.py
依赖: networkx, neo4j-driver (可选)

灵境道谱溯源: D2-3【知识图谱煞】· 道二·知枢体道 · 四地煞之知之术
"""

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX = False
    nx = None

try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeNode:
    """知识节点"""

    id: str
    type: str  # entity, concept, event
    content: str
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "embedding": self.embedding[:10] if self.embedding else [],
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
        }


@dataclass
class KnowledgeEdge:
    """知识边 (关系)"""

    id: str
    source_id: str
    target_id: str
    relation: str  # is_a, has_part, causes, relates_to, uses, belongs_to
    weight: float = 1.0
    evidence: str = ""
    confidence: float = 0.8
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "weight": self.weight,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


@dataclass
class KnowledgeTriple:
    """知识三元组 (主体, 关系, 客体)"""

    subject: str
    relation: str
    object: str
    confidence: float = 0.8
    evidence: str = ""

    def to_tuple(self) -> tuple[str, str, str]:
        return (self.subject, self.relation, self.object)


class TianjiGraphStore:
    """天机知识图谱存储引擎"""

    RELATION_TYPES = {
        "is_a": "是一个",
        "has_part": "包含",
        "causes": "导致",
        "relates_to": "相关",
        "uses": "使用",
        "belongs_to": "属于",
        "located_in": "位于",
        "created_by": "创建者",
        "modified_by": "修改者",
    }

    def __init__(
        self,
        storage_path: str = "data/.memory/knowledge_graph",
        use_neo4j: bool = False,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.use_neo4j = use_neo4j and NEO4J_AVAILABLE
        self.neo4j_driver = None

        if self.use_neo4j:
            try:
                self.neo4j_driver = GraphDatabase.driver(
                    neo4j_uri, auth=(neo4j_user, neo4j_password)
                )
                logger.info(f"Neo4j连接成功: {neo4j_uri}")
            except Exception as e:
                logger.warning(f"Neo4j连接失败，回退到NetworkX: {e}")
                self.use_neo4j = False

        if not self.use_neo4j:
            if not NETWORKX_AVAILABLE:
                raise ImportError("NetworkX未安装，请执行: pip install networkx")
            self.graph = nx.MultiDiGraph()
            self._load_graph()

        self._lock = threading.RLock()
        self._node_index: dict[str, str] = {}
        self._edge_index: dict[str, str] = {}

        logger.info(
            f"天机图谱存储初始化完成 (引擎: {'Neo4j' if self.use_neo4j else 'NetworkX'})"
        )

    def initialize(self) -> dict[str, Any]:
        """初始化图谱存储"""
        with self._lock:
            if self.use_neo4j:
                with self.neo4j_driver.session() as session:
                    session.run(
                        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE"
                    )
                    session.run(
                        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Concept) REQUIRE n.id IS UNIQUE"
                    )
                    session.run(
                        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Event) REQUIRE n.id IS UNIQUE"
                    )
            else:
                self.graph.clear()
                self._save_graph()

            return {
                "status": "initialized",
                "engine": "Neo4j" if self.use_neo4j else "NetworkX",
                "storage_path": str(self.storage_path),
            }

    def _load_graph(self):
        """加载图谱 (NetworkX)"""
        graph_file = self.storage_path / "knowledge_graph.json"
        if graph_file.exists():
            try:
                with open(graph_file, encoding="utf-8") as f:
                    data = json.load(f)

                for node_data in data.get("nodes", []):
                    self.graph.add_node(
                        node_data["id"],
                        **{k: v for k, v in node_data.items() if k != "id"},
                    )

                for edge_data in data.get("edges", []):
                    self.graph.add_edge(
                        edge_data["source"],
                        edge_data["target"],
                        key=edge_data.get("id", edge_data["relation"]),
                        **edge_data,
                    )

                logger.info(
                    f"图谱加载完成: {self.graph.number_of_nodes()} 节点, {self.graph.number_of_edges()} 边"
                )
            except Exception as e:
                logger.error(f"图谱加载失败: {e}")

    def _save_graph(self):
        """保存图谱 (NetworkX)"""
        graph_file = self.storage_path / "knowledge_graph.json"

        nodes = []
        for node_id, node_data in self.graph.nodes(data=True):
            nodes.append({"id": node_id, **node_data})

        edges = []
        for u, v, key, edge_data in self.graph.edges(data=True, keys=True):
            edges.append({"source": u, "target": v, "id": key, **edge_data})

        with open(graph_file, "w", encoding="utf-8") as f:
            json.dump(
                {"nodes": nodes, "edges": edges, "updated_at": time.time()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _generate_id(self, content: str) -> str:
        """生成唯一ID"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:16]

    def add_node(self, node: KnowledgeNode) -> str:
        """添加节点"""
        with self._lock:
            if not node.id:
                node.id = self._generate_id(node.content)

            if self.use_neo4j:
                with self.neo4j_driver.session() as session:
                    session.run(
                        f"MERGE (n:{node.type} {{id: $id}}) "
                        "SET n.content = $content, n.created_at = $created_at, "
                        "n.updated_at = $updated_at, n.access_count = $access_count",
                        id=node.id,
                        content=node.content,
                        created_at=node.created_at,
                        updated_at=node.updated_at,
                        access_count=node.access_count,
                    )
            else:
                self.graph.add_node(
                    node.id,
                    type=node.type,
                    content=node.content,
                    embedding=node.embedding,
                    metadata=node.metadata,
                    created_at=node.created_at,
                    updated_at=node.updated_at,
                    access_count=node.access_count,
                )
                self._save_graph()

            self._node_index[node.content] = node.id
            logger.debug(f"节点添加成功: {node.id} ({node.type})")
            return node.id

    def add_edge(self, edge: KnowledgeEdge) -> str:
        """添加边 (关系)"""
        with self._lock:
            if not edge.id:
                edge.id = self._generate_id(
                    f"{edge.source_id}:{edge.relation}:{edge.target_id}"
                )

            if self.use_neo4j:
                with self.neo4j_driver.session() as session:
                    session.run(
                        "MATCH (s {id: $source_id}), (t {id: $target_id}) "
                        f"MERGE (s)-[r:{edge.relation.upper()}]->(t) "
                        "SET r.weight = $weight, r.confidence = $confidence, "
                        "r.evidence = $evidence, r.created_at = $created_at",
                        source_id=edge.source_id,
                        target_id=edge.target_id,
                        weight=edge.weight,
                        confidence=edge.confidence,
                        evidence=edge.evidence,
                        created_at=edge.created_at,
                    )
            else:
                self.graph.add_edge(
                    edge.source_id,
                    edge.target_id,
                    key=edge.id,
                    relation=edge.relation,
                    weight=edge.weight,
                    confidence=edge.confidence,
                    evidence=edge.evidence,
                    created_at=edge.created_at,
                )
                self._save_graph()

            logger.debug(
                f"边添加成功: {edge.source_id} -[{edge.relation}]-> {edge.target_id}"
            )
            return edge.id

    def add_triple(self, triple: KnowledgeTriple) -> tuple[str, str]:
        """添加知识三元组"""
        subject_id = self._generate_id(triple.subject)
        object_id = self._generate_id(triple.object)

        subject_node = KnowledgeNode(
            id=subject_id, type="entity", content=triple.subject
        )
        object_node = KnowledgeNode(id=object_id, type="entity", content=triple.object)

        self.add_node(subject_node)
        self.add_node(object_node)

        edge = KnowledgeEdge(
            source_id=subject_id,
            target_id=object_id,
            relation=triple.relation,
            confidence=triple.confidence,
            evidence=triple.evidence,
        )
        edge_id = self.add_edge(edge)

        return (subject_id, edge_id)

    def multi_hop(
        self, node_id: str, hops: int = 2, relation_filter: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """多跳查询"""
        with self._lock:
            results = []

            if self.use_neo4j:
                with self.neo4j_driver.session() as session:
                    query = f"""
                    MATCH path = (start {{id: $node_id}})-[r*1..{hops}]-(end)
                    RETURN end, r, length(path) as depth
                    ORDER BY depth
                    """
                    records = session.run(query, node_id=node_id)
                    for record in records:
                        results.append(
                            {
                                "node": dict(record["end"]),
                                "relations": [dict(r) for r in record["r"]],
                                "depth": record["depth"],
                            }
                        )
            else:
                if node_id not in self.graph:
                    return []

                visited = {node_id}
                current_level = {node_id}

                for hop in range(1, hops + 1):
                    next_level = set()
                    for current_node in current_level:
                        for neighbor in self.graph.neighbors(current_node):
                            if neighbor not in visited:
                                edge_data = self.graph.get_edge_data(
                                    current_node, neighbor
                                )
                                if edge_data:
                                    for key, data in edge_data.items():
                                        if (
                                            relation_filter is None
                                            or data.get("relation") in relation_filter
                                        ):
                                            next_level.add(neighbor)
                                            results.append(
                                                {
                                                    "node_id": neighbor,
                                                    "node_data": dict(
                                                        self.graph.nodes[neighbor]
                                                    ),
                                                    "relation": data.get("relation"),
                                                    "depth": hop,
                                                    "confidence": data.get(
                                                        "confidence", 0.8
                                                    ),
                                                }
                                            )

                    visited.update(next_level)
                    current_level = next_level

            return results

    def find_path(
        self, source_id: str, target_id: str, max_depth: int = 5
    ) -> list[dict[str, Any]]:
        """查找两个节点之间的路径"""
        with self._lock:
            if self.use_neo4j:
                with self.neo4j_driver.session() as session:
                    query = f"""
                    MATCH path = shortestPath((start {{id: $source_id}})-[*1..{max_depth}]-(end {{id: $target_id}}))
                    RETURN path
                    """
                    record = session.run(
                        query, source_id=source_id, target_id=target_id
                    ).single()
                    if record:
                        return [{"path": str(record["path"])}]
                    return []
            else:
                try:
                    path = nx.shortest_path(self.graph, source_id, target_id)
                    path_data = []
                    for i in range(len(path) - 1):
                        edge_data = self.graph.get_edge_data(path[i], path[i + 1])
                        if edge_data:
                            for key, data in edge_data.items():
                                path_data.append(
                                    {
                                        "from": path[i],
                                        "to": path[i + 1],
                                        "relation": data.get("relation"),
                                        "confidence": data.get("confidence", 0.8),
                                    }
                                )
                    return path_data
                except nx.NetworkXNoPath:
                    return []

    def query_by_content(self, content: str) -> KnowledgeNode | None:
        """通过内容查询节点"""
        node_id = self._node_index.get(content)
        if not node_id:
            node_id = self._generate_id(content)

        with self._lock:
            if self.use_neo4j:
                with self.neo4j_driver.session() as session:
                    record = session.run(
                        "MATCH (n {id: $node_id}) RETURN n", node_id=node_id
                    ).single()
                    if record:
                        node_data = dict(record["n"])
                        return KnowledgeNode(
                            id=node_data["id"],
                            type=node_data.get("type", "entity"),
                            content=node_data["content"],
                            created_at=node_data.get("created_at", time.time()),
                            updated_at=node_data.get("updated_at", time.time()),
                        )
                return None
            else:
                if node_id in self.graph:
                    node_data = self.graph.nodes[node_id]
                    return KnowledgeNode(
                        id=node_id,
                        type=node_data.get("type", "entity"),
                        content=node_data.get("content", ""),
                        created_at=node_data.get("created_at", time.time()),
                        updated_at=node_data.get("updated_at", time.time()),
                    )
                return None

    def get_stats(self) -> dict[str, Any]:
        """获取图谱统计信息"""
        with self._lock:
            if self.use_neo4j:
                with self.neo4j_driver.session() as session:
                    node_count = session.run(
                        "MATCH (n) RETURN count(n) as count"
                    ).single()["count"]
                    edge_count = session.run(
                        "MATCH ()-[r]->() RETURN count(r) as count"
                    ).single()["count"]
                    return {
                        "engine": "Neo4j",
                        "node_count": node_count,
                        "edge_count": edge_count,
                    }
            else:
                return {
                    "engine": "NetworkX",
                    "node_count": self.graph.number_of_nodes(),
                    "edge_count": self.graph.number_of_edges(),
                    "is_connected": nx.is_weakly_connected(self.graph)
                    if self.graph.number_of_nodes() > 0
                    else True,
                    "density": nx.density(self.graph)
                    if self.graph.number_of_nodes() > 0
                    else 0,
                }

    def close(self):
        """关闭连接"""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("Neo4j连接已关闭")

    # ===== 天罡-17 图谱同步体接口 =====  [v10-ready]

    def sync_from_memories(self, entries: list) -> int:
        """从晋升的记忆条目同步到知识图谱 (天罡-17 图谱同步体)  [v10-ready]

        在记忆晋升到L3(episodic)/L4(semantic)时调用，
        从条目内容中提取知识节点和关系边，更新图谱。

        Args:
            entries: 已晋升的记忆条目列表
                     每个entry至少包含: content, tags, metadata (可选tcl_canonical_ids)

        Returns:
            成功同步的条目数

        注意: 失败时返回0，不抛异常（降级模式）
        """
        synced_count = 0
        for entry in entries:
            try:
                content = (
                    entry.get("content", "")
                    if isinstance(entry, dict)
                    else getattr(entry, "content", "")
                )
                tags = (
                    entry.get("tags", [])
                    if isinstance(entry, dict)
                    else getattr(entry, "tags", [])
                )
                metadata = (
                    entry.get("metadata", {})
                    if isinstance(entry, dict)
                    else getattr(entry, "metadata", {})
                )

                if not content:
                    continue

                # 1. 从TCL canonical_ids获取已归一化的术语节点
                canonical_ids = (
                    metadata.get("tcl_canonical_ids", [])
                    if isinstance(metadata, dict)
                    else []
                )

                # 2. 从tags中提取概念节点
                tag_nodes = []
                for tag in (tags or []):
                    if tag and len(str(tag)) > 1:
                        tag_nodes.append(str(tag))

                # 3. 创建/更新节点
                all_nodes = list(
                    set([str(c) for c in (canonical_ids or [])] + tag_nodes)
                )
                for node_label in all_nodes[:10]:  # 限制单条最多10个节点
                    node_id = f"mem:{node_label}"
                    self._ensure_node(node_id, node_label, node_type="concept")

                # 4. 在同一条目的节点间建立 relates_to 边
                for i, n1 in enumerate(all_nodes[:10]):
                    for n2 in all_nodes[i + 1:10]:
                        self._ensure_edge(f"mem:{n1}", f"mem:{n2}", "relates_to")

                synced_count += 1
            except Exception:
                continue  # 单条失败不影响整体

        return synced_count

    def _ensure_node(self, node_id: str, label: str, node_type: str = "concept") -> None:
        """确保节点存在（幂等）  [v10-ready]

        适配本类真实API：add_node(node: KnowledgeNode)。
        """
        try:
            node = KnowledgeNode(id=node_id, type=node_type, content=label)
            self.add_node(node)
        except Exception:
            pass

    def _ensure_edge(self, source_id: str, target_id: str, relation: str) -> None:
        """确保边存在（幂等）  [v10-ready]

        适配本类真实API：add_edge(edge: KnowledgeEdge)。
        """
        try:
            edge = KnowledgeEdge(
                id="",
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                weight=1.0,
            )
            self.add_edge(edge)
        except Exception:
            pass


# [v10-ready] 兼容别名：天罡-17 图谱同步体统一以 KnowledgeGraphStore 暴露
KnowledgeGraphStore = TianjiGraphStore
