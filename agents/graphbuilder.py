r"""
天机GraphBuilder Agent - 知识图谱构建师 v1.0
========================================================
L2层Agent，负责知识图谱构建和维护

角色: 知识图谱构建师
层级: L2
核心能力:
  - 实体抽取
  - 关系识别
  - 图谱构建
  - 图谱查询
  - 多跳推理

架构位置: 天机/agents/graphbuilder.py
依赖: core/graph_store, core/knowledge_extractor

灵境道谱溯源: D2-1【图谱构建煞】· 道二·知枢体道 · 四地煞之知之术
"""

import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.orchestration.agent_serializer import AgentSerializable
from core.memory.graph_store import TianjiGraphStore, KnowledgeNode, KnowledgeEdge, KnowledgeTriple
from core.shared.knowledge_extractor import KnowledgeExtractor, tianji_extract_knowledge_enhanced

logger = logging.getLogger(__name__)


class GraphBuilderAgent(AgentSerializable):
    """
    GraphBuilder Agent - 知识图谱构建师

    TVP声明:
      [TVP] Agent: @graphbuilder | 层级: L2 | 角色: 知识图谱构建师
      [TVP] 可调用: @yiku (记忆检索), @evolver (进化协作)
      [TVP] 协作模式: C-层级 (主控→子协调→工作者)
    """

    AGENT_ID = "lianli"
    AGENT_NAME = "连理"
    LAYER = "L2"
    ROLE = "知识图谱构建师"
    EMOJI = "🕸️"

    CAPABILITIES = [
        "实体抽取",
        "关系识别",
        "图谱构建",
        "图谱查询",
        "多跳推理",
        "路径查找"
    ]

    TOOLS = [
        "tianji_extract_knowledge",
        "memory_build_graph",
        "memory_query_graph",
        "memory_recall"
    ]

    MCP_SERVER = "memory-engine-global"

    def __init__(self, amim=None, graph_store: Optional[TianjiGraphStore] = None):
        self.amim = amim
        self.graph_store = graph_store or TianjiGraphStore()
        self.extractor = KnowledgeExtractor()

        self._build_count = 0
        self._query_count = 0
        self._last_build_time = 0.0

        logger.info(f"[TVP] Agent初始化: @{self.AGENT_ID} ({self.ROLE})")

    def build_from_text(
        self,
        text: str,
        source: str = "unknown",
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        从文本构建图谱

        Args:
            text: 输入文本
            source: 来源标识
            use_llm: 是否使用LLM增强

        Returns:
            构建结果统计
        """
        start_time = time.time()

        extraction = self.extractor.extract(text, use_llm=use_llm)

        nodes_added = 0
        edges_added = 0

        for triple in extraction.triples:
            try:
                node_ids = self.graph_store.add_triple(triple)
                nodes_added += 2
                edges_added += 1
            except Exception as e:
                logger.warning(f"三元组添加失败: {e}")

        self._build_count += 1
        self._last_build_time = time.time() - start_time

        return {
            "status": "success",
            "nodes_added": nodes_added,
            "edges_added": edges_added,
            "triples_count": len(extraction.triples),
            "entities_count": len(extraction.entities),
            "confidence_avg": extraction.confidence_avg,
            "build_time": self._last_build_time,
            "source": source
        }

    def _query_memories_direct(self, layer: str, limit: int) -> List[Dict[str, Any]]:
        """[FIX-D1] 直接查询 .memory DB 替代 AMIM调用

        当AMIM未配置时，直接读取memories表获取记忆数据。
        """
        import sqlite3
        import json as _json

        db_paths = [
            Path(__file__).resolve().parent.parent / "data" / ".memory" / "icme.db",
            Path(__file__).resolve().parent.parent / "data" / "icme.db",
        ]

        for db_path in db_paths:
            if db_path.exists():
                try:
                    conn = sqlite3.connect(str(db_path))
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT * FROM memories WHERE layer=? AND archived=0 "
                        "ORDER BY created_at DESC LIMIT ?",
                        (layer, limit),
                    )
                    rows = cur.fetchall()
                    results = []
                    for row in rows:
                        d = dict(row)
                        # 解析JSON字段
                        for json_field in ("tags", "metadata", "related_ids", "changelog", "content_segmented"):
                            if d.get(json_field) and isinstance(d[json_field], str):
                                try:
                                    d[json_field] = _json.loads(d[json_field])
                                except (_json.JSONDecodeError, TypeError):
                                    pass
                        results.append(d)
                    conn.close()
                    logger.info(
                        f"[GraphBuilder] 直接DB查询: layer={layer} "
                        f"retrieved {len(results)} memories from {db_path}"
                    )
                    return results
                except Exception as e:
                    logger.warning(f"[GraphBuilder] 直接DB查询失败 ({db_path}): {e}")
                    continue

        logger.error("[GraphBuilder] 所有DB路径均不可用")
        return []

    def build_from_memory(
        self,
        layer: str = "episodic",
        limit: int = 100,
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """
        从记忆层构建图谱

        Args:
            layer: 记忆层
            limit: 最大记忆数
            batch_size: 批处理大小

        Returns:
            构建结果统计
        """
        # [FIX-D1] AMIM未配置时使用直接数据库查询fallback
        use_direct_db = not self.amim
        if use_direct_db:
            logger.info("[GraphBuilder] AMIM未配置, 使用直接数据库查询fallback")
            memory_list = self._query_memories_direct(layer, limit)
            if not memory_list:
                return {"status": "error", "message": "AMIM未配置且直接数据库查询失败"}
        else:
            start_time = time.time()
            try:
                memories = self.amim.call_tool(
                    "memory_recall",
                    {"layer": layer, "limit": limit}
                )

                if not memories or "results" not in memories:
                    return {"status": "error", "message": "记忆检索失败"}

                memory_list = memories["results"]

        start_time = time.time()

        try:
            total_nodes = 0
            total_edges = 0
            total_triples = 0

            for i in range(0, len(memory_list), batch_size):
                batch = memory_list[i:i+batch_size]

                for mem in batch:
                    content = mem.get("content", "")
                    if len(content) > 20:
                        result = self.build_from_text(
                            content,
                            source=f"memory:{mem.get('id', 'unknown')}",
                            use_llm=False
                        )
                        total_nodes += result.get("nodes_added", 0)
                        total_edges += result.get("edges_added", 0)
                        total_triples += result.get("triples_count", 0)

            self._build_count += 1

            return {
                "status": "success",
                "memories_processed": len(memory_list),
                "nodes_added": total_nodes,
                "edges_added": total_edges,
                "triples_count": total_triples,
                "build_time": time.time() - start_time,
                "layer": layer
            }
        except Exception as e:
            logger.error(f"从记忆构建图谱失败: {e}")
            return {"status": "error", "message": str(e)}

    def query_graph(
        self,
        query: str,
        hops: int = 2,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        图谱查询

        Args:
            query: 查询文本
            hops: 多跳深度
            top_k: 返回结果数

        Returns:
            查询结果
        """
        start_time = time.time()

        extraction = self.extractor.extract(query, use_llm=False)

        results = []
        seen_nodes = set()

        for entity in extraction.entities[:5]:
            node = self.graph_store.query_by_content(entity)

            if node and node.id not in seen_nodes:
                seen_nodes.add(node.id)

                related = self.graph_store.multi_hop(node.id, hops=hops)

                for item in related:
                    node_id = item.get("node_id", "")
                    if node_id not in seen_nodes:
                        seen_nodes.add(node_id)
                        results.append({
                            "node_id": node_id,
                            "content": item.get("node_data", {}).get("content", ""),
                            "relation": item.get("relation", ""),
                            "depth": item.get("depth", 1),
                            "confidence": item.get("confidence", 0.5)
                        })

        results.sort(key=lambda x: x["confidence"], reverse=True)
        results = results[:top_k]

        self._query_count += 1

        return {
            "status": "success",
            "query": query,
            "results": results,
            "total": len(results),
            "query_time": time.time() - start_time
        }

    def find_path(
        self,
        source: str,
        target: str,
        max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        查找路径

        Args:
            source: 起始实体
            target: 目标实体
            max_depth: 最大深度

        Returns:
            路径结果
        """
        source_node = self.graph_store.query_by_content(source)
        target_node = self.graph_store.query_by_content(target)

        if not source_node or not target_node:
            return {
                "status": "not_found",
                "message": "起始或目标节点不存在"
            }

        path = self.graph_store.find_path(source_node.id, target_node.id, max_depth)

        return {
            "status": "success",
            "source": source,
            "target": target,
            "path": path,
            "path_length": len(path)
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        graph_stats = self.graph_store.get_stats()

        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            "layer": self.LAYER,
            "build_count": self._build_count,
            "query_count": self._query_count,
            "last_build_time": self._last_build_time,
            "graph_stats": graph_stats
        }

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            stats = self.graph_store.get_stats()

            return {
                "status": "healthy",
                "agent_id": self.AGENT_ID,
                "node_count": stats.get("node_count", 0),
                "edge_count": stats.get("edge_count", 0),
                "engine": stats.get("engine", "unknown")
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "agent_id": self.AGENT_ID,
                "error": str(e)
            }
