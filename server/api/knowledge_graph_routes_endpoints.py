# -*- coding: utf-8-sig -*-
"""knowledge_graph_routes_endpoints.py — KG API端点定义 (SSS拆分修复)

SSS-PhaseB拆分后，路由端点函数丢失，本文件补回全部API端点。
依赖: knowledge_graph_routes_helpers.py (helpers + _get_conn)
"""

import sqlite3
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .knowledge_graph_routes_helpers import (
    _get_conn,
    _cache_get,
    _cache_set,
    _calc_power_law_r2,
    _calc_avg_path_length,
)


router = APIRouter()


# ==================== 数据模型 ====================

class KGNode(BaseModel):
    id: str
    label: str
    type: str
    frequency: int = 0
    properties: Dict[str, Any] = {}


class KGEdge(BaseModel):
    source: str
    target: str
    relation: str
    weight: float = 1.0


class TopologyResponse(BaseModel):
    """对齐前端 KGTopology 接口 (kg-types.ts)"""
    nodes: List[KGNode]
    edges: List[KGEdge]
    meta: Dict[str, Any] = Field(default_factory=dict)
    communities: List[Dict[str, Any]] = Field(default_factory=list)


class MetricsResponse(BaseModel):
    total_nodes: int
    total_edges: int
    avg_degree: float
    max_degree: int
    density: float
    power_law_r2: float
    avg_path_length: float
    top_hubs: List[Dict[str, Any]]
    type_distribution: Dict[str, int]
    relation_distribution: Dict[str, int]


class SSSAuditResponse(BaseModel):
    total_nodes: int
    total_edges: int
    power_law_r2: float
    density: float
    avg_path_length: float
    score: float
    grade: str
    issues: List[str]
    recommendations: List[str]


class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索关键词")
    limit: int = Field(20, ge=1, le=200)


class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total: int


# ==================== API 端点 ====================

@router.get("/topology", response_model=TopologyResponse)
async def get_topology(
    mode: str = Query("sample", description="采样模式: sample/full"),
    sample_rate: float = Query(0.3, ge=0.01, le=1.0),
    max_nodes: int = Query(500, ge=10, le=5000),
):
    """获取知识图谱拓扑数据 (含自动采样)"""
    cache_key = f"topology:{mode}:{sample_rate}:{max_nodes}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        conn = _get_conn()
    except HTTPException:
        return TopologyResponse(nodes=[], edges=[], meta={"error": "database_unavailable"}, communities=[])

    try:
        # 获取节点
        if mode == "sample":
            cur = conn.execute(
                "SELECT entity_name, entity_type, frequency, properties "
                "FROM knowledge_graph ORDER BY frequency DESC LIMIT ?",
                (max_nodes,),
            )
        else:
            cur = conn.execute(
                "SELECT entity_name, entity_type, frequency, properties FROM knowledge_graph"
            )

        nodes_raw = cur.fetchall()
        node_names = set()
        nodes: List[KGNode] = []
        for row in nodes_raw:
            name = row["entity_name"]
            node_names.add(name)
            props = {}
            try:
                if row["properties"]:
                    props = __import__("json").loads(row["properties"])
            except Exception:
                pass
            nodes.append(KGNode(
                id=name,
                label=name,
                type=row["entity_type"] or "entity",
                frequency=row["frequency"] or 0,
                properties=props,
            ))

        # 获取边 (仅连接已加载节点的边)
        if node_names:
            placeholders = ",".join("?" * min(len(node_names), 900))
            limited_names = list(node_names)[:900]
            cur = conn.execute(
                f"SELECT source, target, relation, weight FROM knowledge_edges "
                f"WHERE source IN ({placeholders}) AND target IN ({placeholders})",
                (*limited_names, *limited_names),
            )
            edges = [
                KGEdge(
                    source=row["source"],
                    target=row["target"],
                    relation=row["relation"] or "related",
                    weight=row["weight"] or 1.0,
                )
                for row in cur.fetchall()
            ]
        else:
            edges = []

        # [FIX-AUDIT] 对齐前端KGTopology.meta字段名 (kg-types.ts)
        meta = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "returned_nodes": len(nodes),
            "returned_edges": len(edges),
            "mode": mode,
            "sample_rate": sample_rate,
        }

        # [FIX-AUDIT] 计算communities (按type分组)
        type_counter = Counter(n.type for n in nodes)
        communities = [
            {"type": t, "count": c, "sample_ids": [n.id for n in nodes if n.type == t][:5]}
            for t, c in type_counter.most_common(20)
        ]

        result = TopologyResponse(nodes=nodes, edges=edges, meta=meta, communities=communities)
        _cache_set(cache_key, result)
        return result
    finally:
        conn.close()


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """获取知识图谱指标"""
    cached = _cache_get("metrics")
    if cached:
        return cached

    try:
        conn = _get_conn()
    except HTTPException:
        return MetricsResponse(
            total_nodes=0, total_edges=0, avg_degree=0, max_degree=0,
            density=0, power_law_r2=0, avg_path_length=0,
            top_hubs=[], type_distribution={}, relation_distribution={},
        )

    try:
        # 节点/边总数
        total_nodes = conn.execute("SELECT COUNT(*) FROM knowledge_graph").fetchone()[0]
        total_edges = conn.execute("SELECT COUNT(*) FROM knowledge_edges").fetchone()[0]

        # 度分布
        degree_map: Dict[str, int] = defaultdict(int)
        cur = conn.execute("SELECT source FROM knowledge_edges")
        for row in cur:
            degree_map[row["source"]] += 1
        cur = conn.execute("SELECT target FROM knowledge_edges")
        for row in cur:
            degree_map[row["target"]] += 1

        degrees = list(degree_map.values())
        avg_degree = sum(degrees) / len(degrees) if degrees else 0
        max_degree = max(degrees) if degrees else 0

        # 密度
        density = (2 * total_edges) / (total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0

        # 幂律R²
        power_law_r2 = _calc_power_law_r2(degrees) if degrees else 0

        # 平均路径长度 (采样)
        adj: Dict[str, set] = defaultdict(set)
        cur = conn.execute("SELECT source, target FROM knowledge_edges LIMIT 5000")
        for row in cur:
            adj[row["source"]].add(row["target"])
            adj[row["target"]].add(row["source"])
        nodes_list = list(adj.keys())[:20]
        avg_path_length = _calc_avg_path_length(nodes_list, adj) if nodes_list else 0

        # Top hubs
        top_hubs = sorted(degree_map.items(), key=lambda x: x[1], reverse=True)[:10]
        top_hubs_list = [{"node": n, "degree": d} for n, d in top_hubs]

        # 类型分布
        cur = conn.execute(
            "SELECT entity_type, COUNT(*) as cnt FROM knowledge_graph GROUP BY entity_type ORDER BY cnt DESC"
        )
        type_dist = {row["entity_type"]: row["cnt"] for row in cur.fetchall()}

        # 关系分布
        cur = conn.execute(
            "SELECT relation, COUNT(*) as cnt FROM knowledge_edges GROUP BY relation ORDER BY cnt DESC LIMIT 20"
        )
        relation_dist = {row["relation"]: row["cnt"] for row in cur.fetchall()}

        result = MetricsResponse(
            total_nodes=total_nodes,
            total_edges=total_edges,
            avg_degree=round(avg_degree, 2),
            max_degree=max_degree,
            density=round(density, 6),
            power_law_r2=power_law_r2,
            avg_path_length=round(avg_path_length, 2),
            top_hubs=top_hubs_list,
            type_distribution=type_dist,
            relation_distribution=relation_dist,
        )
        _cache_set("metrics", result)
        return result
    finally:
        conn.close()


@router.get("/sss-audit", response_model=SSSAuditResponse)
async def sss_audit():
    """SSS审计 — 知识图谱质量评估"""
    cached = _cache_get("sss_audit")
    if cached:
        return cached

    try:
        conn = _get_conn()
    except HTTPException:
        return SSSAuditResponse(
            total_nodes=0, total_edges=0, power_law_r2=0, density=0,
            avg_path_length=0, score=0, grade="F",
            issues=["数据库不可用"], recommendations=["检查数据库连接"],
        )

    try:
        total_nodes = conn.execute("SELECT COUNT(*) FROM knowledge_graph").fetchone()[0]
        total_edges = conn.execute("SELECT COUNT(*) FROM knowledge_edges").fetchone()[0]

        degree_map: Dict[str, int] = defaultdict(int)
        cur = conn.execute("SELECT source FROM knowledge_edges")
        for row in cur:
            degree_map[row["source"]] += 1
        cur = conn.execute("SELECT target FROM knowledge_edges")
        for row in cur:
            degree_map[row["target"]] += 1

        degrees = list(degree_map.values())
        power_law_r2 = _calc_power_law_r2(degrees) if degrees else 0
        density = (2 * total_edges) / (total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0

        adj: Dict[str, set] = defaultdict(set)
        cur = conn.execute("SELECT source, target FROM knowledge_edges LIMIT 5000")
        for row in cur:
            adj[row["source"]].add(row["target"])
            adj[row["target"]].add(row["source"])
        nodes_list = list(adj.keys())[:20]
        avg_path_length = _calc_avg_path_length(nodes_list, adj) if nodes_list else 0

        # 评分
        score = 0.0
        issues: List[str] = []
        recommendations: List[str] = []

        if total_nodes > 100:
            score += 20
        else:
            issues.append(f"节点数不足 ({total_nodes} < 100)")
            recommendations.append("增加知识抽取频率")

        if total_edges > 1000:
            score += 20
        else:
            issues.append(f"边数不足 ({total_edges} < 1000)")
            recommendations.append("加强实体关系挖掘")

        if power_law_r2 > 0.5:
            score += 25
        elif power_law_r2 > 0.3:
            score += 15
            issues.append(f"幂律分布R²偏低 ({power_law_r2:.3f})")
            recommendations.append("优化Hub节点识别")
        else:
            issues.append(f"幂律分布R²过低 ({power_law_r2:.3f})")
            recommendations.append("重新评估图谱结构")

        if density > 0.001:
            score += 15
        else:
            issues.append(f"密度过低 ({density:.6f})")
            recommendations.append("增加实体间连接")

        if avg_path_length > 0:
            score += 10
        if total_nodes > 0 and total_edges > 0:
            score += 10

        grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D" if score >= 40 else "F"

        result = SSSAuditResponse(
            total_nodes=total_nodes,
            total_edges=total_edges,
            power_law_r2=power_law_r2,
            density=round(density, 6),
            avg_path_length=round(avg_path_length, 2),
            score=round(score, 1),
            grade=grade,
            issues=issues,
            recommendations=recommendations,
        )
        _cache_set("sss_audit", result)
        return result
    finally:
        conn.close()


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """搜索知识图谱实体"""
    try:
        conn = _get_conn()
    except HTTPException:
        return SearchResponse(results=[], total=0)

    try:
        cur = conn.execute(
            "SELECT entity_name, entity_type, frequency, properties "
            "FROM knowledge_graph WHERE entity_name LIKE ? "
            "ORDER BY frequency DESC LIMIT ?",
            (f"%{req.query}%", req.limit),
        )
        results = []
        for row in cur.fetchall():
            props = {}
            try:
                if row["properties"]:
                    props = __import__("json").loads(row["properties"])
            except Exception:
                pass
            results.append({
                "id": row["entity_name"],
                "label": row["entity_name"],
                "type": row["entity_type"],
                "frequency": row["frequency"],
                "properties": props,
            })
        return SearchResponse(results=results, total=len(results))
    finally:
        conn.close()


@router.get("/stats")
async def get_stats():
    """获取知识图谱统计信息 (轻量级)"""
    try:
        conn = _get_conn()
    except HTTPException:
        return {"total_nodes": 0, "total_edges": 0}

    try:
        total_nodes = conn.execute("SELECT COUNT(*) FROM knowledge_graph").fetchone()[0]
        total_edges = conn.execute("SELECT COUNT(*) FROM knowledge_edges").fetchone()[0]
        return {"total_nodes": total_nodes, "total_edges": total_edges}
    finally:
        conn.close()


# [FIX-AUDIT] 补充前端config定义但缺失的节点CRUD端点
class NodeListResponse(BaseModel):
    total: int
    nodes: List[KGNode]


class NodeDetailResponse(BaseModel):
    node: KGNode
    edges: List[KGEdge] = []
    connected_nodes: List[KGNode] = []


@router.get("/nodes", response_model=NodeListResponse)
async def list_nodes(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    """获取节点列表 (对齐前端 api.config.ts nodes)"""
    try:
        conn = _get_conn()
    except HTTPException:
        return NodeListResponse(total=0, nodes=[])

    try:
        total = conn.execute("SELECT COUNT(*) FROM knowledge_graph").fetchone()[0]
        cur = conn.execute(
            "SELECT entity_name, entity_type, frequency, properties "
            "FROM knowledge_graph ORDER BY frequency DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        nodes = []
        for row in cur.fetchall():
            props = {}
            try:
                if row["properties"]:
                    props = __import__("json").loads(row["properties"])
            except Exception:
                pass
            nodes.append(KGNode(
                id=row["entity_name"],
                label=row["entity_name"],
                type=row["entity_type"] or "entity",
                frequency=row["frequency"] or 0,
                properties=props,
            ))
        return NodeListResponse(total=total, nodes=nodes)
    finally:
        conn.close()


@router.get("/nodes/{node_id}", response_model=NodeDetailResponse)
async def get_node_detail(node_id: str):
    """获取节点详情 (对齐前端 api.config.ts nodeDetail)"""
    try:
        conn = _get_conn()
    except HTTPException:
        raise HTTPException(status_code=503, detail="database_unavailable")

    try:
        cur = conn.execute(
            "SELECT entity_name, entity_type, frequency, properties "
            "FROM knowledge_graph WHERE entity_name = ?",
            (node_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

        props = {}
        try:
            if row["properties"]:
                props = __import__("json").loads(row["properties"])
        except Exception:
            pass

        node = KGNode(
            id=row["entity_name"],
            label=row["entity_name"],
            type=row["entity_type"] or "entity",
            frequency=row["frequency"] or 0,
            properties=props,
        )

        # 获取关联边
        cur2 = conn.execute(
            "SELECT source, target, relation, weight FROM knowledge_edges "
            "WHERE source = ? OR target = ? LIMIT 100",
            (node_id, node_id),
        )
        edges = [
            KGEdge(source=r["source"], target=r["target"],
                   relation=r["relation"] or "related", weight=r["weight"] or 1.0)
            for r in cur2.fetchall()
        ]

        # 获取关联节点ID
        connected_ids = set()
        for e in edges:
            connected_ids.add(e.source)
            connected_ids.add(e.target)
        connected_ids.discard(node_id)

        return NodeDetailResponse(node=node, edges=edges, connected_nodes=[])
    finally:
        conn.close()
