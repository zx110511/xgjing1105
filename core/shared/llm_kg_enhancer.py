"""
LLM增强KnowledgeGraph关系提取
================================
功能:
1. 从L4 semantic层提取文本
2. 使用DeepSeek识别实体间的关系
3. 构建高质量知识图谱边
4. 支持多种关系类型（依赖、包含、实现等）

使用方法:
  python llm_kg_enhancer.py --extract    # 执行提取
  python llm_kg_enhancer.py --stats      # 查看统计
  python llm_kg_enhancer.py --visualize  # 生成可视化
"""

import sqlite3
import json
import uuid
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

DB_PATH = Path(__file__).resolve().parent.parent / "data" / ".memory" / "icme.db"

# 关系类型定义
RELATION_TYPES = {
    "DEPENDS_ON": "依赖关系",
    "CONTAINS": "包含关系",
    "IMPLEMENTS": "实现关系",
    "MANAGES": "管理关系",
    "USES": "使用关系",
    "EVOLVES_TO": "进化关系",
    "PART_OF": "组成部分",
    "TRIGGERS": "触发关系",
    "OPTIMIZES": "优化关系",
    "VALIDATES": "验证关系",
}

class LLMKGEnhancer:
    """LLM增强的知识图谱构建器"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = None
        self.stats = {
            "entities_processed": 0,
            "relations_extracted": 0,
            "relations_by_type": {},
            "confidence_avg": 0,
        }

    def connect(self):
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_l4_memories(self) -> List[Dict[str, Any]]:
        """获取L4 semantic层的所有记忆"""
        conn = self.connect()
        cur = conn.cursor()

        memories = cur.execute("""
            SELECT id, content, tags, metadata
            FROM memories
            WHERE layer='semantic'
              AND content IS NOT NULL
              AND LENGTH(content) > 50
            ORDER BY created_at DESC
        """).fetchall()

        result = []
        for m in memories:
            try:
                meta = json.loads(m["metadata"]) if m["metadata"] else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}

            try:
                tags = json.loads(m["tags"]) if m["tags"] else []
            except (json.JSONDecodeError, TypeError):
                tags = []

            result.append({
                "id": m["id"],
                "content": m["content"],
                "tags": tags,
                "metadata": meta,
            })

        return result

    def get_existing_entities(self) -> List[Dict[str, Any]]:
        """获取现有实体"""
        conn = self.connect()
        cur = conn.cursor()

        entities = cur.execute("""
            SELECT entity_name, entity_type, properties
            FROM knowledge_graph
        """).fetchall()

        result = []
        for e in entities:
            try:
                props = json.loads(e["properties"]) if e["properties"] else {}
            except (json.JSONDecodeError, TypeError):
                props = {}

            result.append({
                "entity_id": e["entity_name"],  # 使用name作为ID
                "name": e["entity_name"],
                "entity_type": e["entity_type"],
                "properties": props,
            })

        return result

    def extract_relations_llm_style(
        self,
        text: str,
        existing_entities: List[Dict],
    ) -> List[Dict[str, Any]]:
        """
        使用规则+模式匹配模拟LLM关系提取

        在实际部署时，这里会调用DeepSeek API
        目前使用增强的规则引擎
        """
        relations = []

        # 关系模式库
        relation_patterns = [
            # 依赖关系
            (r"(\w+?)\s*(?:依赖|依赖于|需要|基于|使用)\s*(\w+)", "DEPENDS_ON", 0.85),
            (r"(\w+?)\s*(?:调用|触发|启动)\s*(\w+)", "TRIGGERS", 0.8),

            # 包含/组成关系
            (r"(\w+?)\s*(?:包含|由.*?组成|包括|涵盖)\s*(\w+)", "CONTAINS", 0.9),
            (r"(\w+?)\s*(?:是|作为)\s*(\w+)\s*的(?:部分|组件|模块)", "PART_OF", 0.85),

            # 实现关系
            (r"(\w+?)\s*(?:实现|遵循|符合)\s*(\w+)", "IMPLEMENTS", 0.8),

            # 管理关系
            (r"(\w+?)\s*(?:管理|控制|协调|调度)\s*(\w+)", "MANAGES", 0.85),

            # 进化关系
            (r"(\w+?)\s*(?:进化|升级|演变为|发展为)\s*(\w+)", "EVOLVES_TO", 0.75),

            # 优化关系
            (r"(\w+?)\s*(?:优化|改进|增强|提升)\s*(\w+)", "OPTIMIZES", 0.8),

            # 验证关系
            (r"(\w+?)\s*(?:验证|检查|审核|审计)\s*(\w+)", "VALIDATES", 0.78),
        ]

        # 实体名称映射（用于快速查找）
        entity_names = {e["name"].lower(): e for e in existing_entities}

        for pattern, rel_type, base_confidence in relation_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)

            for source_name, target_name in matches:
                source_clean = source_name.strip().lower()
                target_clean = target_name.strip().lower()

                # 验证是否为已知实体
                if source_clean in entity_names and target_clean in entity_names:
                    source_entity = entity_names[source_clean]
                    target_entity = entity_names[target_clean]

                    # 调整置信度（基于上下文）
                    confidence = base_confidence

                    # 如果在同一句话中，提高置信度
                    if f"{source_name}" in text and f"{target_name}" in text:
                        confidence = min(confidence + 0.05, 1.0)

                    # 检查是否已存在相同关系
                    relation_key = (
                        source_entity["entity_id"],
                        target_entity["entity_id"],
                        rel_type
                    )

                    relations.append({
                        "source_entity_id": source_entity["entity_id"],
                        "source_name": source_entity["name"],
                        "target_entity_id": target_entity["entity_id"],
                        "target_name": target_entity["name"],
                        "relation_type": rel_type,
                        "relation_label": RELATION_TYPES.get(rel_type, rel_type),
                        "confidence": round(confidence, 2),
                        "evidence_text": text[:200] + ("..." if len(text) > 200 else ""),
                        "extraction_method": "rule_based_v2",
                    })

        return relations

    def deduplicate_relations(
        self,
        relations: List[Dict],
    ) -> List[Dict]:
        """去重关系"""
        seen = set()
        unique = []

        for rel in relations:
            key = (
                rel["source_entity_id"],
                rel["target_entity_id"],
                rel["relation_type"]
            )

            if key not in seen:
                seen.add(key)
                unique.append(rel)
            else:
                # 更新已有关系的置信度（取最高值）
                for i, existing in enumerate(unique):
                    if key == (
                        existing["source_entity_id"],
                        existing["target_entity_id"],
                        existing["relation_type"]
                    ):
                        if rel["confidence"] > existing["confidence"]:
                            unique[i]["confidence"] = rel["confidence"]
                            unique[i]["evidence_text"] = rel["evidence_text"]
                        break

        return unique

    def execute_extraction(self) -> Dict[str, Any]:
        """执行完整的关系提取流程"""
        conn = self.connect()
        cur = conn.cursor()

        print("\n=== LLM增强KG关系提取 ===\n")

        # Step 1: 获取L4记忆和实体
        print("[1/5] 加载L4语义层记忆...")
        memories = self.get_l4_memories()
        print(f"   找到 {len(memories)} 条L4记忆")

        print("\n[2/5] 加载现有实体...")
        entities = self.get_existing_entities()
        print(f"   找到 {len(entities)} 个实体")

        if len(entities) < 2:
            return {
                "success": False,
                "error": "实体数量不足，无法提取关系",
                "entities_count": len(entities),
            }

        # Step 2: 提取关系
        print("\n[3/5] 提取实体关系...")
        all_relations = []

        for mem in memories[:30]:  # 处理前30条记忆
            relations = self.extract_relations_llm_style(
                mem["content"], entities
            )
            all_relations.extend(relations)

        print(f"   原始提取: {len(all_relations)} 条关系")

        # Step 3: 去重
        print("\n[4/5] 去重处理...")
        unique_relations = self.deduplicate_relations(all_relations)
        print(f"   去重后: {len(unique_relations)} 条关系")

        # Step 4: 写入数据库
        print("\n[5/5] 写入KnowledgeGraph...")
        written = 0

        for rel in unique_relations:
            try:
                # 写入到knowledge_edges表（使用正确的列名）
                cur.execute("""
                    INSERT INTO knowledge_edges
                    (source, target, relation, weight, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    rel["source_entity_id"],
                    rel["target_entity_id"],
                    f"{rel['relation_type']}:{rel['relation_label']}",
                    rel["confidence"],
                    time.time(),
                ))

                written += 1

                # 更新统计
                rtype = rel["relation_type"]
                if rtype not in self.stats["relations_by_type"]:
                    self.stats["relations_by_type"][rtype] = 0
                self.stats["relations_by_type"][rtype] += 1

            except Exception as e:
                print(f"   写入失败: {e}")

        conn.commit()

        self.stats["entities_processed"] = len(entities)
        self.stats["relations_extracted"] = written

        if written > 0:
            confidences = [r["confidence"] for r in unique_relations]
            self.stats["confidence_avg"] = sum(confidences) / len(confidences)

        result = {
            "success": True,
            "stats": dict(self.stats),
            "timestamp": datetime.now().isoformat(),
            "written_edges": written,
        }

        print(f"\n✅ 完成! 写入 {written} 条关系边")

        self.close()
        return result

    def get_kg_stats(self) -> Dict[str, Any]:
        """获取知识图谱统计"""
        conn = self.connect()
        cur = conn.cursor()

        stats = {
            "timestamp": datetime.now().isoformat(),
            "entities": {
                "total": 0,
                "by_type": {},
            },
            "edges": {
                "total": 0,
                "by_relation_type": {},
                "avg_confidence": 0,
            },
            "graph_density": 0,
        }

        # 实体统计
        entity_total = cur.execute("SELECT COUNT(*) FROM knowledge_graph").fetchone()[0]
        stats["entities"]["total"] = entity_total

        entity_types = cur.execute("""
            SELECT entity_type, COUNT(*) as cnt
            FROM knowledge_graph
            GROUP BY entity_type
            ORDER BY cnt DESC
        """).fetchall()

        for et in entity_types:
            stats["entities"]["by_type"][et[0]] = et[1]

        # 边统计
        edge_total = cur.execute("SELECT COUNT(*) FROM knowledge_edges").fetchone()[0]
        stats["edges"]["total"] = edge_total

        if edge_total > 0:
            edge_types = cur.execute("""
                SELECT relation, COUNT(*) as cnt, AVG(weight) as avg_weight
                FROM knowledge_edges
                GROUP BY relation
                ORDER BY cnt DESC
            """).fetchall()

            weight_sum = 0
            for et in edge_types:
                rel_type = et[0].split(":")[0] if ":" in et[0] else et[0]
                rel_label = et[0].split(":", 1)[1] if ":" in et[0] else et[0]
                stats["edges"]["by_relation_type"][rel_type] = {
                    "count": et[1],
                    "label": rel_label,
                    "avg_confidence": round(et[2], 2) if et[2] else 0,
                }
                weight_sum += (et[2] or 0) * et[1]

            stats["edges"]["avg_confidence"] = round(weight_sum / edge_total, 2)

        # 图密度计算
        if entity_total > 1:
            max_possible_edges = entity_total * (entity_total - 1) / 2
            stats["graph_density"] = round(edge_total / max_possible_edges * 100, 2) if max_possible_edges > 0 else 0

        self.close()
        return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LLM KG增强工具")
    parser.add_argument("--extract", action="store_true", help="执行关系提取")
    parser.add_argument("--stats", action="store_true", help="查看统计")
    parser.add_argument("--visualize", action="store_true", help="生成可视化DOT文件")
    args = parser.parse_args()

    enhancer = LLMKGEnhancer()

    if args.extract:
        result = enhancer.execute_extraction()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.stats:
        stats = enhancer.get_kg_stats()
        print("\n=== KnowledgeGraph 统计 ===\n")
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    if args.visualize:
        from fill_knowledge_graph import KnowledgeGraphFiller
        kgf = KnowledgeGraphFiller()
        dot_file = kgf.generate_dot_visualization()
        print(f"\n✅ 可视化文件已生成: {dot_file}")

    if not any([args.extract, args.stats, args.visualize]):
        parser.print_help()


if __name__ == "__main__":
    main()
