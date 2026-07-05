"""
P1: 进化策略落地 — L5 Meta写入与管理
============================================
功能:
1. 验证L5 Meta层写入管道
2. 策略版本管理
3. 自动策略评估与更新
4. 进化闭环触发

使用方法:
  python evolution_l5_manager.py --verify     # 验证L5状态
  python evolution_l5_manager.py --add-policy # 添加新策略
  python evolution_l5_manager.py --evaluate   # 评估当前策略
  python evolution_l5_manager.py --trigger-evolution  # 触发进化
"""

import sqlite3
import json
import time
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

DB_PATH = Path(__file__).resolve().parent.parent / "data" / ".memory" / "icme.db"

@dataclass
class EvolutionPolicy:
    """进化策略"""
    id: str
    name: str
    version: str
    status: str  # active / deprecated / superseded
    category: str
    content: str
    trigger_conditions: Dict[str, Any]
    actions: List[str]
    effectiveness_score: float = 0.0
    created_at: float = field(default_factory=time.time)
    last_evaluated: float = 0.0
    execution_count: int = 0
    success_rate: float = 0.0


class L5EvolutionManager:
    """L5 Meta层进化策略管理器"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def verify_l5_status(self) -> Dict[str, Any]:
        """验证L5 Meta层状态"""
        conn = self.connect()
        cur = conn.cursor()

        status = {
            "timestamp": datetime.now().isoformat(),
            "l5_meta": {
                "total_policies": 0,
                "active": 0,
                "deprecated": 0,
                "by_category": {},
                "sample_policies": [],
            },
            "pipeline_health": {
                "write_tested": False,
                "read_tested": False,
                "last_write_time": None,
                "issues": [],
            },
            "recommendations": [],
        }

        # 统计L5数据
        l5_count = cur.execute(
            "SELECT COUNT(*) FROM memories WHERE layer='meta'"
        ).fetchone()[0]

        status["l5_meta"]["total_policies"] = l5_count

        # 按状态分类
        active_count = cur.execute("""
            SELECT COUNT(*) FROM memories
            WHERE layer='meta' AND metadata LIKE '%"status":"active"%'
        """).fetchone()[0]

        deprecated_count = cur.execute("""
            SELECT COUNT(*) FROM memories
            WHERE layer='meta' AND metadata LIKE '%"status":"deprecated"%'
        """).fetchone()[0]

        status["l5_meta"]["active"] = active_count
        status["l5_meta"]["deprecated"] = deprecated_count

        # 按分类统计
        categories = cur.execute("""
            SELECT
                json_extract(metadata, '$.policy_type') as category,
                COUNT(*) as cnt
            FROM memories
            WHERE layer='meta'
            GROUP BY category
            ORDER BY cnt DESC
        """).fetchall()

        for cat in categories:
            if cat[0]:
                status["l5_meta"]["by_category"][cat[0]] = cat[1]

        # 获取示例策略
        sample_policies = cur.execute("""
            SELECT id, content, metadata, created_at
            FROM memories
            WHERE layer='meta'
            ORDER BY created_at DESC
            LIMIT 5
        """).fetchall()

        for p in sample_policies:
            try:
                meta = json.loads(p[2]) if p[2] else {}
                status["l5_meta"]["sample_policies"].append({
                    "id": p["id"][:8],
                    "content_preview": p["content"][:80] + "...",
                    "policy_type": meta.get("policy_type", "unknown"),
                    "version": meta.get("version", "N/A"),
                    "created_at": datetime.fromtimestamp(p[3]).isoformat(),
                })
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        # 测试管道健康度
        try:
            test_id = f"PIPELINE_TEST_{uuid.uuid4().hex[:6]}"
            now = time.time()

            cur.execute("""
                INSERT INTO memories
                (id, content, layer, tags, priority, created_at, last_accessed,
                 access_count, value_score, size_bytes, metadata)
                VALUES (?, ?, 'meta', ?, 'low', ?, ?, 1, 1.0, ?, ?)
            """, (
                test_id,
                f"[Pipeline Test] L5写入测试 {datetime.now().isoformat()}",
                json.dumps(["pipeline-test", "health-check"], ensure_ascii=False),
                now,
                now,
                100,
                json.dumps({
                    "source": "pipeline_verification",
                    "test_id": test_id,
                    "auto_cleanup": True,
                }, ensure_ascii=False),
            ))

            conn.commit()

            # 验证读取
            verify = cur.execute(
                "SELECT id FROM memories WHERE id=?", (test_id,)
            ).fetchone()

            if verify:
                status["pipeline_health"]["write_tested"] = True
                status["pipeline_health"]["read_tested"] = True
                status["pipeline_health"]["last_write_time"] = datetime.now().isoformat()

                # 清理测试数据
                cur.execute("DELETE FROM memories WHERE id=?", (test_id,))
                conn.commit()
            else:
                status["pipeline_health"]["issues"].append("写入后无法读取")

        except Exception as e:
            status["pipeline_health"]["issues"].append(f"管道测试失败: {e}")

        # 生成建议
        if l5_count == 0:
            status["recommendations"].append("L5层为空，需要初始化基础策略集")
        elif active_count == 0:
            status["recommendations"].append("无活跃策略，需激活或创建新策略")

        if not status["pipeline_health"]["issues"]:
            status["recommendations"].append("✅ L5管道健康，可正常使用")

        self.close()
        return status

    def add_policy(
        self,
        name: str,
        content: str,
        category: str,
        version: str = "1.0",
        trigger_conditions: Optional[Dict] = None,
        actions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        添加新的进化策略到L5

        返回: 创建的策略信息
        """
        conn = self.connect()
        cur = conn.cursor()

        policy_id = str(uuid.uuid4())
        now = time.time()

        full_content = (
            f"[策略 #{name}] v{version}\n"
            f"类别: {category}\n"
            f"内容: {content}\n\n"
            f"触发条件: {json.dumps(trigger_conditions or {}, ensure_ascii=False)}\n"
            f"执行动作: {json.dumps(actions or [], ensure_ascii=False)}"
        )

        metadata = {
            "source": "evolution_manager",
            "policy_type": category,
            "name": name,
            "version": version,
            "status": "active",
            "effective_date": datetime.now().isoformat(),
            "trigger_conditions": trigger_conditions or {},
            "actions": actions or [],
            "auto_evolve": True,
        }

        cur.execute("""
            INSERT INTO memories
            (id, content, layer, tags, priority, created_at, last_accessed,
             access_count, value_score, size_bytes, metadata)
            VALUES (?, ?, 'meta', ?, 'critical', ?, ?, 1, 1.0, ?, ?)
        """, (
            policy_id,
            full_content,
            json.dumps([
                "evolution-policy",
                f"category:{category}",
                f"version:{version}",
                "active",
            ], ensure_ascii=False),
            now,
            now,
            len(full_content.encode('utf-8')),
            json.dumps(metadata, ensure_ascii=False),
        ))

        conn.commit()

        result = {
            "success": True,
            "policy_id": policy_id[:8],
            "name": name,
            "version": version,
            "category": category,
            "created_at": datetime.now().isoformat(),
        }

        self.close()
        return result

    def evaluate_policies(self) -> Dict[str, Any]:
        """
        评估当前策略效果

        基于执行历史和成功率分析
        """
        conn = self.connect()
        cur = conn.cursor()

        evaluation = {
            "timestamp": datetime.now().isoformat(),
            "policies_evaluated": 0,
            "high_performers": [],
            "underperformers": [],
            "recommendations": [],
        }

        # 获取所有活跃策略
        policies = cur.execute("""
            SELECT id, content, metadata, value_score, access_count
            FROM memories
            WHERE layer='meta'
              AND metadata LIKE '%"status":"active"%'
        """).fetchall()

        evaluation["policies_evaluated"] = len(policies)

        for policy in policies:
            try:
                meta = json.loads(policy[2]) if policy[2] else {}

                policy_info = {
                    "id": policy[0][:8],
                    "name": meta.get("name", "unknown"),
                    "type": meta.get("policy_type", "unknown"),
                    "value_score": round(policy[3], 2) if policy[3] else 0,
                    "access_count": policy[4] or 0,
                }

                # 简单评分逻辑（实际应基于更复杂的指标）
                if policy_info["value_score"] >= 0.9 and policy_info["access_count"] >= 3:
                    evaluation["high_performers"].append(policy_info)
                elif policy_info["value_score"] < 0.7 or policy_info["access_count"] == 0:
                    evaluation["underperformers"].append({**policy_info, "issue": "低使用率或低效"})

            except Exception as e:
                print(f"策略评估失败: {e}")

        # 生成建议
        if evaluation["underperformers"]:
            evaluation["recommendations"].append(
                f"发现{len(evaluation['underperformers'])}个低效策略，考虑优化或废弃"
            )

        if evaluation["high_performers"]:
            evaluation["recommendations"].append(
                f"{len(evaluation['high_performers'])}个策略表现优秀，可作为基线参考"
            )

        self.close()
        return evaluation


def main():
    import argparse
    parser = argparse.ArgumentParser(description="L5进化策略管理器")
    parser.add_argument("--verify", action="store_true", help="验证L5状态")
    parser.add_argument("--add-policy", action="store_true", help="添加示例策略")
    parser.add_argument("--evaluate", action="store_true", help="评估策略")
    args = parser.parse_args()

    manager = L5EvolutionManager()

    if args.verify:
        print("\n=== L5 Meta 层验证 ===\n")
        status = manager.verify_l5_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))

    if args.add_policy:
        print("\n=== 添加进化策略 ===\n")

        new_policies = [
            {
                "name": "AUTO_SCALING_L4",
                "content": "当L4 semantic层积累超过100条知识时，自动触发实体关系抽取，构建KnowledgeGraph以加速语义搜索和知识推理能力",
                "category": "auto_scaling",
                "trigger_conditions": {"l4_count": "> 100", "check_interval": "1h"},
                "actions": ["build_knowledge_graph", "update_embeddings"],
            },
            {
                "name": "QUALITY_GATE_ENHANCEMENT",
                "content": "对写入L4/L5的内容强制要求metadata包含extraction_method和confidence字段，低于0.8置信度的内容降级到L3处理，确保高层记忆质量",
                "category": "quality_enhancement",
                "trigger_conditions": {"layer": ["semantic", "meta"], "confidence": "< 0.8"},
                "actions": ["downgrade_to_L3", "log_quality_event"],
            },
            {
                "name": "MEMORY_LIFECYCLE_GOVERNANCE",
                "content": "L5 meta层记录所有策略变更历史，每条策略必须有version字段和effective_date，废弃策略标记为deprecated但保留90天供回溯审计",
                "category": "governance",
                "trigger_conditions": {"event": "policy_change"},
                "actions": ["archive_old_version", "set_retention_timer"],
            },
        ]

        for policy in new_policies:
            result = manager.add_policy(**policy)
            print(f"✅ {result['name']}: {result['policy_id']}")

    if args.evaluate:
        print("\n=== 策略评估 ===\n")
        eval_result = manager.evaluate_policies()
        print(json.dumps(eval_result, indent=2, ensure_ascii=False))

    if not any([args.verify, args.add_policy, args.evaluate]):
        parser.print_help()


if __name__ == "__main__":
    main()
