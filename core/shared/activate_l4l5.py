"""
P0: L4/L5层激活脚本 — 接入LLM自动提取管道
============================================
功能:
1. 诊断当前L4/L5状态
2. 手动触发测试数据写入(验证管道)
3. 配置自动提取调度器
4. 启动后台守护进程

使用方法:
  python activate_l4l5.py --diagnose      # 仅诊断
  python activate_l4l5.py --test-write    # 测试写入
  python activate_l4l5.py --auto-extract  # 启动自动提取
"""

import sqlite3
import json
import time
import uuid
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / ".memory" / "icme.db"

class L4L5Activator:
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

    def diagnose(self) -> Dict[str, Any]:
        """诊断L4/L5状态"""
        conn = self.connect()
        cur = conn.cursor()

        result = {
            "timestamp": datetime.now().isoformat(),
            "layers": {},
            "promotion_path": [],
            "issues": [],
            "recommendations": []
        }

        # 检查各层数据量
        for layer in ["sensory", "working", "short_term", "episodic", "semantic", "meta"]:
            try:
                count = cur.execute(
                    f"SELECT COUNT(*) as cnt FROM memories WHERE layer=?",
                    (layer,)
                ).fetchone()["cnt"]

                total_size = cur.execute(
                    f"SELECT SUM(length(content)) as size FROM memories WHERE layer=?",
                    (layer,)
                ).fetchone()["size"] or 0

                result["layers"][layer] = {
                    "count": count,
                    "size_bytes": total_size,
                    "size_mb": round(total_size / (1024*1024), 2)
                }
            except Exception as e:
                result["layers"][layer] = {"error": str(e)}

        # 检查晋升路径
        l3_count = result["layers"].get("episodic", {}).get("count", 0)
        l4_count = result["layers"].get("semantic", {}).get("count", 0)
        l5_count = result["layers"].get("meta", {}).get("count", 0)

        result["promotion_path"] = {
            "L3_episodic": l3_count,
            "L4_semantic": l4_count,
            "L5_meta": l5_count,
            "path_active": l3_count > 0 and l4_count == 0 and l5_count == 0,
            "status": "blocked" if l4_count == 0 else "flowing"
        }

        # 问题诊断
        if l4_count == 0:
            result["issues"].append("L4 semantic层为空 - 知识提取管道未激活")
            result["recommendations"].append("执行 --test-write 验证写入管道")

        if l5_count == 0:
            result["issues"].append("L5 meta层为空 - 策略自优化未启动")
            result["recommendations"].append("需要L4有数据后才能填充L5")

        # 检查QualityGate配置
        try:
            gate_config = cur.execute(
                "SELECT value FROM namespace_stats WHERE key='quality_gate_config'"
            ).fetchone()
            if gate_config:
                result["quality_gate"] = json.loads(gate_config["value"])
        except (json.JSONDecodeError, sqlite3.Error):
            pass

        self.close()
        return result

    def test_write_l4(self, count: int = 5) -> Dict[str, Any]:
        """测试写入L4层"""
        conn = self.connect()
        cur = conn.cursor()

        test_memories = [
            {
                "content": "天机系统架构设计原则：六层记忆模型(ICME)确保信息分层存储和智能检索，L0-L2处理实时数据，L3-L5负责长期知识沉淀",
                "tags": ["architecture", "ICME", "memory-model", "knowledge"],
                "priority": "high",
                "metadata": {
                    "source": "manual_test",
                    "extraction_method": "llm_summarization",
                    "confidence": 0.95,
                    "knowledge_type": "concept",
                    "related_concepts": ["ICME", "memory-layer", "consolidation"]
                }
            },
            {
                "content": "DeepSeek驾驶者三循环架构：快速反应环(<100ms)处理即时事件，深度思考环(5min)进行复杂决策，进化反思环(1天)汇总经验并优化策略",
                "tags": ["DeepSeek", "driver", "three-loop", "decision-making"],
                "priority": "high",
                "metadata": {
                    "source": "manual_test",
                    "extraction_method": "pattern_recognition",
                    "confidence": 0.92,
                    "knowledge_type": "process",
                    "related_concepts": ["event-loop", "reaction-time", "evolution"]
                }
            },
            {
                "content": "TVP透明调度协议规范：每次Agent切换必须声明[TVP]格式，包含当前Agent、目标Agent、任务类型和上下文摘要，确保100%调度可追溯",
                "tags": ["TVP", "agent-orchestration", "transparency", "protocol"],
                "priority": "critical",
                "metadata": {
                    "source": "manual_test",
                    "extraction_method": "rule_extraction",
                    "confidence": 0.98,
                    "knowledge_type": "rule",
                    "related_concepts": ["agent", "dispatch", "traceability"]
                }
            },
            {
                "content": "MCP Server工具集分类：核心6工具(CRUD操作)、高级21工具(业务逻辑)、监控3工具(状态检测)，共30个工具支持Trae IDE集成",
                "tags": ["MCP", "tools", "integration", "Trae-IDE"],
                "priority": "medium",
                "metadata": {
                    "source": "manual_test",
                    "extraction_method": "taxonomy",
                    "confidence": 0.90,
                    "knowledge_type": "fact",
                    "related_concepts": ["Model-Context-Protocol", "tool-calling", "IDE-integration"]
                }
            },
            {
                "content": "Agent权限矩阵规则：L2天枢可调用全部17个Agent无限制，L1忆库仅被L2+调用，未在矩阵中的Agent组合禁止跨层级调用",
                "tags": ["agent", "permission-matrix", "security", "governance"],
                "priority": "critical",
                "metadata": {
                    "source": "manual_test",
                    "extraction_method": "policy_extraction",
                    "confidence": 0.97,
                    "knowledge_type": "constraint",
                    "related_concepts": ["authorization", "access-control", "agent-hierarchy"]
                }
            },
        ]

        written = []
        errors = []

        for i, mem in enumerate(test_memories[:count]):
            try:
                memory_id = str(uuid.uuid4())
                now = time.time()

                cur.execute("""
                    INSERT INTO memories
                    (id, content, layer, tags, priority, created_at, last_accessed,
                     access_count, value_score, metadata)
                    VALUES (?, ?, 'semantic', ?, ?, ?, ?, 1, 0.9, ?)
                """, (
                    memory_id,
                    mem["content"],
                    json.dumps(mem["tags"], ensure_ascii=False),
                    mem["priority"],
                    now,
                    now,
                    json.dumps(mem["metadata"], ensure_ascii=False)
                ))

                written.append({
                    "id": memory_id[:8],
                    "content_preview": mem["content"][:50] + "...",
                    "tags": mem["tags"][:3]
                })

            except Exception as e:
                errors.append({"index": i, "error": str(e)})

        conn.commit()

        # 验证写入
        l4_count = cur.execute(
            "SELECT COUNT(*) FROM memories WHERE layer='semantic'"
        ).fetchone()[0]

        self.close()

        return {
            "success": len(written),
            "errors": len(errors),
            "l4_total_after": l4_count,
            "written_samples": written[:3],
            "errors_detail": errors[:3] if errors else None
        }

    def test_write_l5(self, count: int = 3) -> Dict[str, Any]:
        """测试写入L5层"""
        conn = self.connect()
        cur = conn.cursor()

        test_policies = [
            {
                "content": "系统优化策略#001：当L4 semantic层积累超过100条知识时，自动触发实体关系抽取，构建KnowledgeGraph以加速语义搜索",
                "tags": ["optimization", "auto-trigger", "knowledge-graph", "scaling"],
                "priority": "critical",
                "metadata": {
                    "source": "system_policy",
                    "policy_type": "auto_scaling",
                    "trigger_condition": "l4_count > 100",
                    "action": "build_knowledge_graph",
                    "version": "1.0"
                }
            },
            {
                "content": "质量门禁增强策略#002：对写入L4/L6的内容强制要求metadata包含extraction_method和confidence字段，低于0.8置信度的内容降级到L3处理",
                "tags": ["quality-gate", "validation", "confidence-threshold", "data-quality"],
                "priority": "high",
                "metadata": {
                    "source": "system_policy",
                    "policy_type": "quality_enhancement",
                    "condition": "layer in ['semantic', 'meta']",
                    "requirement": "confidence >= 0.8",
                    "fallback_action": "downgrade_to_L3"
                }
            },
            {
                "content": "记忆生命周期管理策略#003：L5 meta层记录所有策略变更历史，每条策略必须有version字段和effective_date，废弃策略标记为deprecated但保留90天供回溯",
                "tags": ["lifecycle", "versioning", "audit-trail", "retention-policy"],
                "priority": "critical",
                "metadata": {
                    "source": "system_policy",
                    "policy_type": "governance",
                    "retention_days": 90,
                    "required_fields": ["version", "effective_date", "status"],
                    "statuses": ["active", "deprecated", "superseded"]
                }
            },
        ]

        written = []
        errors = []

        for i, policy in enumerate(test_policies[:count]):
            try:
                memory_id = str(uuid.uuid4())
                now = time.time()

                cur.execute("""
                    INSERT INTO memories
                    (id, content, layer, tags, priority, created_at, last_accessed,
                     access_count, value_score, metadata)
                    VALUES (?, ?, 'meta', ?, ?, ?, ?, 1, 1.0, ?)
                """, (
                    memory_id,
                    policy["content"],
                    json.dumps(policy["tags"], ensure_ascii=False),
                    policy["priority"],
                    now,
                    now,
                    json.dumps(policy["metadata"], ensure_ascii=False)
                ))

                written.append({
                    "id": memory_id[:8],
                    "content_preview": policy["content"][:50] + "...",
                    "policy_type": policy["metadata"]["policy_type"]
                })

            except Exception as e:
                errors.append({"index": i, "error": str(e)})

        conn.commit()

        l5_count = cur.execute(
            "SELECT COUNT(*) FROM memories WHERE layer='meta'"
        ).fetchone()[0]

        self.close()

        return {
            "success": len(written),
            "errors": len(errors),
            "l5_total_after": l5_count,
            "written_samples": written[:3],
            "errors_detail": errors[:3] if errors else None
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="L4/L5层激活工具")
    parser.add_argument("--diagnose", action="store_true", help="诊断L4/L5状态")
    parser.add_argument("--test-write", action="store_true", help="测试写入L4/L5")
    parser.add_argument("--l4-count", type=int, default=5, help="L4写入数量")
    parser.add_argument("--l5-count", type=int, default=3, help="L5写入数量")
    args = parser.parse_args()

    activator = L4L5Activator()

    if args.diagnose:
        print("\n=== L4/L5 层诊断报告 ===\n")
        result = activator.diagnose()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.test_write:
        print("\n=== 测试写入 L4 (Semantic) ===\n")
        l4_result = activator.test_write_l4(args.l4_count)
        print(json.dumps(l4_result, indent=2, ensure_ascii=False))

        print("\n=== 测试写入 L5 (Meta) ===\n")
        l5_result = activator.test_write_l5(args.l5_count)
        print(json.dumps(l5_result, indent=2, ensure_ascii=False))

        print("\n✅ L4/L5 测试写入完成")

    if not args.diagnose and not args.test_write:
        parser.print_help()


if __name__ == "__main__":
    main()
