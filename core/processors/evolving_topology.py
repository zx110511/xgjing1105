r"""
天机自进化Agent拓扑引擎 (Tianji Evolving Topology) v1.0
========================================================
借鉴 GPTSwarm 的Agent图拓扑 + 强化学习优化 + ReSo自组织，
为天机v9.1提供Agent协作图的自动进化能力。

核心能力:
  1. AgentGraph — Agent协作图数据模型 (节点=Agent, 边=协作关系)
  2. 成功率追踪 — 追踪每条边的协作成功率
  3. 边权重自适应 — 根据历史成功率调整边权重
  4. 低效边自动断开 — 连续失败>3次的边标记为断开
  5. 新路由规则发现 — 发现高效的新协作路径
  6. 三层进化循环 — L1参数调优(秒级) / L2规则增补(分钟级) / L3拓扑演化(小时级)

参考架构:
  - GPTSwarm: Agent图 + 强化学习边权重优化 (MIT)
  - ReSo: Reward-driven Self-organizing MAS (ACL 2025)
  - 天机EvolutionLoop: 三级自修改 (参数→规则→架构)

位置: 天机/core/evolving_topology.py
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("tianji.evolving_topology")


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


class EdgeStatus(str, Enum):
    ACTIVE = "active"  # 正常协作
    DEGRADED = "degraded"  # 降级 (成功率下降)
    DISCONNECTED = "disconnected"  # 已断开
    NEW = "new"  # 新发现的路由


class EvolutionLevel(str, Enum):
    L1_PARAMETER = "L1_parameter"  # 参数调优 (秒级)
    L2_RULE = "L2_rule"  # 规则增补 (分钟级)
    L3_TOPOLOGY = "L3_topology"  # 拓扑演化 (小时级)


@dataclass
class AgentNode:
    """Agent协作图中的节点"""

    agent_id: str
    name: str = ""
    emoji: str = "🤖"
    # 运行时统计
    total_tasks: int = 0
    successful_tasks: int = 0
    avg_duration_ms: float = 0.0
    utilization: float = 0.0  # 利用率 0-1
    # 自适应参数
    optimal_concurrency: int = 2
    optimal_timeout_ms: int = 60000
    optimal_retries: int = 2
    # 历史
    last_active: float = 0.0
    evolution_generation: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 1.0
        return self.successful_tasks / self.total_tasks

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "success_rate": round(self.success_rate, 3),
            "total_tasks": self.total_tasks,
            "utilization": round(self.utilization, 3),
            "optimal_concurrency": self.optimal_concurrency,
        }


@dataclass
class TopologyEdge:
    """Agent协作图中的边"""

    edge_id: str
    source_id: str
    target_id: str
    status: EdgeStatus = EdgeStatus.ACTIVE
    # 权重 (0-1)
    weight: float = 0.5
    # 成功率追踪
    collaboration_count: int = 0
    successful_collaborations: int = 0
    consecutive_failures: int = 0
    # 延迟统计
    avg_latency_ms: float = 0.0
    # 历史
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    disconnected_at: float | None = None
    # 进化信息
    evolution_generation: int = 0
    reward_signal: float = 0.0  # 强化学习奖励信号

    @property
    def success_rate(self) -> float:
        if self.collaboration_count == 0:
            return 0.5
        return self.successful_collaborations / self.collaboration_count

    def record_collaboration(self, success: bool, latency_ms: float = 0):
        """记录一次协作结果"""
        self.collaboration_count += 1
        self.last_used = time.time()
        if success:
            self.successful_collaborations += 1
            self.consecutive_failures = 0
            # 奖励: 成功 → 增加权重
            self.reward_signal += 0.1
        else:
            self.consecutive_failures += 1
            # 惩罚: 失败 → 降低权重
            self.reward_signal -= 0.3

        # 更新延迟
        if latency_ms > 0:
            alpha = 0.3  # EMA平滑因子
            self.avg_latency_ms = (
                alpha * latency_ms + (1 - alpha) * self.avg_latency_ms
                if self.avg_latency_ms > 0
                else latency_ms
            )

        # 更新权重 (基于成功率 + 延迟 + reward信号)
        sr_weight = self.success_rate * 0.6
        latency_weight = max(0, 1.0 - self.avg_latency_ms / 300000) * 0.2
        reward_weight = (0.5 + self.reward_signal * 0.1) * 0.2
        self.weight = max(0.0, min(1.0, sr_weight + latency_weight + reward_weight))

        # 自动断开检测
        if self.consecutive_failures >= 3 and self.status == EdgeStatus.ACTIVE:
            self.status = EdgeStatus.DEGRADED
            logger.warning(
                f"[EvoTopo] ⚠️ Edge {self.edge_id} degraded: "
                f"{self.consecutive_failures} consecutive failures"
            )
        if self.consecutive_failures >= 5:
            self.status = EdgeStatus.DISCONNECTED
            self.disconnected_at = time.time()
            logger.warning(
                f"[EvoTopo] ❌ Edge {self.edge_id} disconnected: "
                f"{self.consecutive_failures} consecutive failures"
            )

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "source": self.source_id,
            "target": self.target_id,
            "status": self.status.value,
            "weight": round(self.weight, 3),
            "success_rate": round(self.success_rate, 3),
            "collaboration_count": self.collaboration_count,
            "consecutive_failures": self.consecutive_failures,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
        }


@dataclass
class AgentTopology:
    """完整的Agent协作拓扑图"""

    topology_id: str
    nodes: dict[str, AgentNode] = field(default_factory=dict)
    edges: dict[str, TopologyEdge] = field(default_factory=dict)
    evolution_generation: int = 0
    created_at: float = field(default_factory=time.time)
    last_evolved_at: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: AgentNode):
        self.nodes[node.agent_id] = node

    def add_edge(
        self, source_id: str, target_id: str, weight: float = 0.5
    ) -> TopologyEdge:
        edge_id = f"edge-{source_id}-{target_id}"
        if edge_id in self.edges:
            return self.edges[edge_id]
        edge = TopologyEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            weight=weight,
            evolution_generation=self.evolution_generation,
        )
        self.edges[edge_id] = edge
        return edge

    def get_active_edges(self) -> list[TopologyEdge]:
        return [
            e
            for e in self.edges.values()
            if e.status in (EdgeStatus.ACTIVE, EdgeStatus.NEW)
        ]

    def get_best_routes(self, source: str, top_k: int = 3) -> list[TopologyEdge]:
        """获取从source出发的最优路由"""
        candidates = [
            e
            for e in self.edges.values()
            if e.source_id == source and e.status == EdgeStatus.ACTIVE
        ]
        candidates.sort(key=lambda e: e.weight, reverse=True)
        return candidates[:top_k]

    def to_dict(self) -> dict:
        return {
            "topology_id": self.topology_id,
            "evolution_generation": self.evolution_generation,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "metrics": self.metrics,
        }


# ═══════════════════════════════════════════════════════════════
# 进化引擎
# ═══════════════════════════════════════════════════════════════


class TopologyEvolutionEngine:
    """
    拓扑进化引擎 — 驱动Agent协作图的自动进化

    三层进化循环:
      L1 参数调优: 调整超时/重试/并发数 (秒级)
      L2 规则增补: 发现新路由规则，写入策略库 (分钟级)
      L3 拓扑演化: 调整Agent协作图结构 (小时级)
    """

    VERSION = "1.0.0-EvoTopo"

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(
                os.environ.get("AI_MEMORY_ROOT", os.getcwd()),
                "data",
                "evolving_topology.db",
            )
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._topology: AgentTopology | None = None
        self._init_db()
        self._build_default_topology()

        # 进化统计
        self._evolution_stats = {
            "L1_evolutions": 0,
            "L2_evolutions": 0,
            "L3_evolutions": 0,
            "edges_disconnected": 0,
            "new_routes_discovered": 0,
            "parameters_optimized": 0,
        }

        # 进化定时器
        self._last_l1_evolve = time.time()
        self._last_l2_evolve = time.time()
        self._last_l3_evolve = time.time()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topology_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    topology_json TEXT,
                    evolution_generation INTEGER,
                    created_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS collaboration_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_agent TEXT,
                    target_agent TEXT,
                    task_goal TEXT,
                    success INTEGER,
                    latency_ms REAL,
                    timestamp REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS routing_rules (
                    rule_id TEXT PRIMARY KEY,
                    source_agent TEXT,
                    target_agent TEXT,
                    condition TEXT,
                    priority REAL,
                    discovered_at REAL,
                    usage_count INTEGER DEFAULT 0
                )
            """)

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _build_default_topology(self):
        """构建默认Agent协作拓扑 (基于S0-S6工业化流水线)"""
        topology = AgentTopology(topology_id="tianji-v9-default")

        from core.orchestration.agent_orchestrator import AGENT_CAPABILITY_MATRIX

        # 添加所有Agent节点
        for agent_id, info in AGENT_CAPABILITY_MATRIX.items():
            topology.add_node(
                AgentNode(
                    agent_id=agent_id,
                    name=info.get("name", agent_id),
                    emoji=info.get("emoji", "🤖"),
                )
            )

        # 标准S0-S6流水线边
        pipeline_edges = [
            ("dongcha", "jingwei", 0.9),  # S0→S1
            ("jingwei", "miaobi", 0.85),  # S1→S2
            ("miaobi", "mingjing", 0.9),  # S2→S3
            ("mingjing", "tiewei", 0.85),  # S3→S4
            ("tiewei", "gongzao", 0.8),  # S4→S5
            ("gongzao", "shiguan", 0.75),  # S5→S6
        ]
        for src, tgt, w in pipeline_edges:
            topology.add_edge(src, tgt, w)

        # 交叉协作边
        cross_edges = [
            ("tianshu", "dongcha", 0.7),
            ("tianshu", "tiansuan", 0.6),
            ("tianshu", "zhenshan", 0.5),
            ("tianshu", "zhuiguang", 0.5),
            ("mingjing", "miaobi", 0.6),  # 审校反馈
            ("yiku", "tianshu", 0.8),
            ("yiku", "dongcha", 0.6),
        ]
        for src, tgt, w in cross_edges:
            topology.add_edge(src, tgt, w)

        self._topology = topology

    def get_topology(self) -> AgentTopology:
        return self._topology

    def record_collaboration(
        self,
        source_agent: str,
        target_agent: str,
        task_goal: str,
        success: bool,
        latency_ms: float = 0,
    ):
        """记录一次Agent协作"""
        if not self._topology:
            return

        edge_id = f"edge-{source_agent}-{target_agent}"
        edge = self._topology.edges.get(edge_id)

        if not edge:
            # 新边: 自动发现路由
            edge = self._topology.add_edge(source_agent, target_agent, 0.3)
            edge.status = EdgeStatus.NEW
            self._evolution_stats["new_routes_discovered"] += 1
            logger.info(
                f"[EvoTopo] 🔗 New route discovered: {source_agent}→{target_agent}"
            )

        edge.record_collaboration(success, latency_ms)

        # 更新源节点统计
        node = self._topology.nodes.get(source_agent)
        if node:
            node.total_tasks += 1
            if success:
                node.successful_tasks += 1
            node.last_active = time.time()

        # 持久化记录
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO collaboration_history (source_agent, target_agent, task_goal, success, latency_ms, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    source_agent,
                    target_agent,
                    task_goal,
                    int(success),
                    latency_ms,
                    time.time(),
                ),
            )

    def record_node_task(self, agent_id: str, success: bool, duration_ms: float = 0):
        """记录单个Agent的任务执行"""
        if not self._topology:
            return
        node = self._topology.nodes.get(agent_id)
        if node:
            node.total_tasks += 1
            if success:
                node.successful_tasks += 1
            if duration_ms > 0:
                alpha = 0.3
                node.avg_duration_ms = (
                    alpha * duration_ms + (1 - alpha) * node.avg_duration_ms
                    if node.avg_duration_ms > 0
                    else duration_ms
                )
            node.last_active = time.time()

    # ═══════════════════════════════════════════════════════════
    # L1: 参数调优 (秒级)
    # ═══════════════════════════════════════════════════════════

    def evolve_l1_parameters(self) -> dict:
        """
        L1进化: 调整每个Agent的最优参数

        基于: 历史成功率 + 平均延迟 + 利用率
        调整: concurrency / timeout / retries
        """
        if not self._topology:
            return {"level": "L1", "changes": 0}

        changes = []
        for agent_id, node in self._topology.nodes.items():
            if node.total_tasks < 5:
                continue

            # 根据成功率调整重试次数
            if node.success_rate < 0.7 and node.optimal_retries < 4:
                old = node.optimal_retries
                node.optimal_retries += 1
                changes.append(
                    {
                        "agent": agent_id,
                        "param": "retries",
                        "old": old,
                        "new": node.optimal_retries,
                    }
                )

            # 根据延迟调整超时
            if node.avg_duration_ms > 0:
                optimal_timeout = int(node.avg_duration_ms * 2.5)
                if abs(optimal_timeout - node.optimal_timeout_ms) > 10000:
                    old = node.optimal_timeout_ms
                    node.optimal_timeout_ms = optimal_timeout
                    changes.append(
                        {
                            "agent": agent_id,
                            "param": "timeout_ms",
                            "old": old,
                            "new": node.optimal_timeout_ms,
                        }
                    )

            # 根据利用率调整并发
            if node.utilization > 0.8 and node.optimal_concurrency < 6:
                old = node.optimal_concurrency
                node.optimal_concurrency += 1
                changes.append(
                    {
                        "agent": agent_id,
                        "param": "concurrency",
                        "old": old,
                        "new": node.optimal_concurrency,
                    }
                )

        self._evolution_stats["L1_evolutions"] += 1
        self._evolution_stats["parameters_optimized"] += len(changes)
        self._last_l1_evolve = time.time()

        if changes:
            logger.info(f"[EvoTopo] L1 evolved: {len(changes)} parameter changes")

        return {"level": "L1", "changes": len(changes), "details": changes}

    # ═══════════════════════════════════════════════════════════
    # L2: 规则增补 (分钟级)
    # ═══════════════════════════════════════════════════════════

    def evolve_l2_rules(self) -> dict:
        """
        L2进化: 发现新的高效路由规则并写入策略库

        基于: 最近协作历史中成功率>0.9且使用次数>10的边
        """
        if not self._topology:
            return {"level": "L2", "changes": 0}

        new_rules = []
        for edge in self._topology.get_active_edges():
            if edge.collaboration_count < 10:
                continue
            if edge.success_rate < 0.85:
                continue

            # 检查是否已有规则
            with self._get_conn() as conn:
                existing = conn.execute(
                    "SELECT rule_id FROM routing_rules WHERE source_agent=? AND target_agent=?",
                    (edge.source_id, edge.target_id),
                ).fetchone()

                if not existing:
                    rule_id = f"rule-{edge.source_id}-{edge.target_id}"
                    conn.execute(
                        "INSERT INTO routing_rules (rule_id, source_agent, target_agent, condition, priority, discovered_at, usage_count) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            rule_id,
                            edge.source_id,
                            edge.target_id,
                            f"success_rate>{edge.success_rate:.2f}",
                            edge.weight,
                            time.time(),
                            edge.collaboration_count,
                        ),
                    )
                    new_rules.append(
                        {
                            "rule_id": rule_id,
                            "source": edge.source_id,
                            "target": edge.target_id,
                            "weight": edge.weight,
                        }
                    )

        self._evolution_stats["L2_evolutions"] += 1
        self._last_l2_evolve = time.time()

        if new_rules:
            logger.info(f"[EvoTopo] L2 evolved: {len(new_rules)} new routing rules")

        return {"level": "L2", "changes": len(new_rules), "details": new_rules}

    # ═══════════════════════════════════════════════════════════
    # L3: 拓扑演化 (小时级)
    # ═══════════════════════════════════════════════════════════

    def evolve_l3_topology(self) -> dict:
        """
        L3进化: 结构调整

        操作:
          - 断开长期低效边
          - 提升高成功率边权重
          - 可能的Agent合并建议 (高频协作对)
        """
        if not self._topology:
            return {"level": "L3", "changes": 0}

        changes = []
        self._topology.evolution_generation += 1

        for edge in list(self._topology.edges.values()):
            edge.evolution_generation = self._topology.evolution_generation

            # 清理长期断开的边
            if (
                edge.status == EdgeStatus.DISCONNECTED
                and edge.disconnected_at
                and time.time() - edge.disconnected_at > 86400 * 7
            ):
                del self._topology.edges[edge.edge_id]
                changes.append(
                    {
                        "action": "removed",
                        "edge": edge.edge_id,
                        "reason": "long_disconnected",
                    }
                )
                self._evolution_stats["edges_disconnected"] += 1

            # 恢复已恢复的边
            if edge.status == EdgeStatus.DEGRADED and edge.success_rate > 0.8:
                edge.status = EdgeStatus.ACTIVE
                edge.consecutive_failures = 0
                changes.append(
                    {
                        "action": "recovered",
                        "edge": edge.edge_id,
                        "success_rate": edge.success_rate,
                    }
                )

        # 检测高频协作对 (建议合并或强化)
        high_freq_pairs = []
        for edge in self._topology.get_active_edges():
            if edge.collaboration_count > 50 and edge.success_rate > 0.9:
                high_freq_pairs.append(
                    {
                        "source": edge.source_id,
                        "target": edge.target_id,
                        "count": edge.collaboration_count,
                        "success_rate": edge.success_rate,
                    }
                )

        self._evolution_stats["L3_evolutions"] += 1
        self._last_l3_evolve = time.time()

        # 保存快照
        self._save_snapshot()

        result = {
            "level": "L3",
            "changes": len(changes),
            "details": changes,
            "high_freq_pairs": high_freq_pairs,
            "generation": self._topology.evolution_generation,
        }

        if changes or high_freq_pairs:
            logger.info(
                f"[EvoTopo] L3 evolved: {len(changes)} changes, "
                f"{len(high_freq_pairs)} high-freq pairs"
            )

        return result

    def _save_snapshot(self):
        if not self._topology:
            return
        import uuid

        snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO topology_snapshots (snapshot_id, topology_json, evolution_generation, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    snapshot_id,
                    json.dumps(self._topology.to_dict(), ensure_ascii=False),
                    self._topology.evolution_generation,
                    time.time(),
                ),
            )

    def get_routing_rules(self, limit: int = 50) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM routing_rules ORDER BY priority DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_collaboration_stats(self, hours: int = 24) -> dict:
        cutoff = time.time() - hours * 3600
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM collaboration_history WHERE timestamp > ?",
                (cutoff,),
            ).fetchone()[0]
            success = conn.execute(
                "SELECT COUNT(*) FROM collaboration_history WHERE timestamp > ? AND success=1",
                (cutoff,),
            ).fetchone()[0]
            return {
                "total_collaborations_24h": total,
                "successful_24h": success,
                "success_rate_24h": round(success / max(total, 1), 3),
            }

    def get_stats(self) -> dict:
        stats = {
            "version": self.VERSION,
            "topology": self._topology.to_dict() if self._topology else None,
            "evolution": self._evolution_stats,
            "routing_rules_count": len(self.get_routing_rules()),
        }
        stats.update(self.get_collaboration_stats())
        return stats


# ═══════════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════════

_evo_engine: TopologyEvolutionEngine | None = None
_evo_lock = threading.Lock()


def get_evolution_engine(db_path: str = None) -> TopologyEvolutionEngine:
    global _evo_engine
    with _evo_lock:
        if _evo_engine is None:
            _evo_engine = TopologyEvolutionEngine(db_path)
        return _evo_engine
