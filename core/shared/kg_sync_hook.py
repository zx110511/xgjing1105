r"""
记忆↔知识图谱双向同步钩子 v1.0
=================================
天机v9.1 SSS级适配 | 记忆入库自动提取实体→写入KG

功能:
  1. remember() 后自动提取知识三元组 → 写入 knowledge_graph + knowledge_edges
  2. KG实体关联 → 增强记忆检索 (recall时利用KG路径)
  3. ICME固结 → 触发KG时序边更新

使用:
  from core.shared.kg_sync_hook import KGSyncHook
  hook = KGSyncHook(db_path="data/.memory/icme.db")
  hook.on_remember(entry_dict)
  hook.on_consolidate(from_layer, to_layer, entry_id)
"""

import json
import time
import sqlite3
import re
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from collections import defaultdict


class KGSyncHook:
    def __init__(self, db_path: str = "data/.memory/icme.db"):
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._entity_cache: Dict[str, str] = {}
        self._pattern_cache: List[tuple] = []
        self._init_patterns()

    def _init_patterns(self):
        self._pattern_cache = [
            (re.compile(r'(?:模块|module)\s*[:：]\s*(\w+)', re.I), 'module'),
            (re.compile(r'(?:Agent|智能体)\s*[:：]\s*@?(\w+)', re.I), 'agent'),
            (re.compile(r'(?:层|layer)\s*[:：]\s*(\w+)', re.I), 'layer'),
            (re.compile(r'(?:技能|skill)\s*[:：]\s*(\w+)', re.I), 'skill'),
            (re.compile(r'(?:概念|concept)\s*[:：]\s*(.+?)(?:\s*[,，。；;]|$)', re.I), 'concept'),
            (re.compile(r'(?:函数|function)\s*[:：]\s*(\w+)', re.I), 'function'),
            (re.compile(r'(?:类|class)\s*[:：]\s*(\w+)', re.I), 'class'),
            (re.compile(r'(?:配置|config)\s*[:：]\s*(\w+)', re.I), 'config'),
            (re.compile(r'(?:路由|route)\s*[:：]\s*(\w+)', re.I), 'route'),
            (re.compile(r'(?:模型|model)\s*[:：]\s*(\w+)', re.I), 'model'),
            (re.compile(r'(?:事件|event)\s*[:：]\s*(\w+)', re.I), 'event'),
            (re.compile(r'(?:工具|tool)\s*[:：]\s*(\w+)', re.I), 'tool'),
        ]

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=15)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_graph (
                entity_name TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                first_seen REAL,
                last_seen REAL,
                frequency INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relation TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                timestamp REAL,
                PRIMARY KEY (source, target, relation)
            )
        """)
        conn.commit()

    def on_remember(self, entry: Dict[str, Any]) -> int:
        content = entry.get("content", "")
        layer = entry.get("layer", "working")
        tags = entry.get("tags", [])
        entry_id = entry.get("id", "")
        metadata = entry.get("metadata", {})

        if not content or len(content) < 10:
            return 0

        entities_added = 0

        try:
            conn = self._get_conn()
            self._ensure_schema(conn)
            c = conn.cursor()

            extracted = self._extract_entities(content, tags, layer)
            layer_entity = f"layer_{layer}"

            for name, etype in extracted:
                try:
                    existing = c.execute("SELECT frequency FROM knowledge_graph WHERE entity_name = ?", (name,)).fetchone()
                    if existing:
                        c.execute("UPDATE knowledge_graph SET frequency = frequency + 1, last_seen = ? WHERE entity_name = ?",
                                  (time.time(), name))
                    else:
                        props = json.dumps({"source_entry": entry_id, "auto_extracted": True})
                        c.execute("INSERT OR IGNORE INTO knowledge_graph (entity_name, entity_type, properties, first_seen, last_seen, frequency) VALUES (?, ?, ?, ?, ?, 1)",
                                  (name, etype, props, time.time(), time.time()))
                        entities_added += 1
                except Exception:
                    pass

            existing_layer = c.execute("SELECT frequency FROM knowledge_graph WHERE entity_name = ?", (layer_entity,)).fetchone()
            if existing_layer:
                c.execute("UPDATE knowledge_graph SET frequency = frequency + 1, last_seen = ? WHERE entity_name = ?",
                          (time.time(), layer_entity))
            else:
                c.execute("INSERT OR IGNORE INTO knowledge_graph (entity_name, entity_type, properties, first_seen, last_seen, frequency) VALUES (?, ?, ?, ?, ?, 1)",
                          (layer_entity, "layer", json.dumps({"icme_layer": layer}), time.time(), time.time()))

            for name, etype in extracted:
                try:
                    c.execute("INSERT OR IGNORE INTO knowledge_edges (source, target, relation, weight, timestamp) VALUES (?, ?, ?, ?, ?)",
                              (name, layer_entity, "BELONGS_TO", 1.0, time.time()))
                except Exception:
                    pass

            triples = metadata.get("knowledge_triples", [])
            if isinstance(triples, list):
                for triple in triples:
                    if isinstance(triple, dict):
                        subj = triple.get("subject", "")
                        pred = triple.get("predicate", "")
                        obj = triple.get("object", "")
                        if subj and pred and obj:
                            try:
                                for entity_name in [subj, obj]:
                                    existing = c.execute("SELECT frequency FROM knowledge_graph WHERE entity_name = ?", (entity_name,)).fetchone()
                                    if existing:
                                        c.execute("UPDATE knowledge_graph SET frequency = frequency + 1 WHERE entity_name = ?", (entity_name,))
                                    else:
                                        c.execute("INSERT OR IGNORE INTO knowledge_graph (entity_name, entity_type, properties, first_seen, last_seen, frequency) VALUES (?, ?, ?, ?, ?, 1)",
                                                  (entity_name, "concept", json.dumps({"auto_triple": True}), time.time(), time.time()))
                                c.execute("INSERT OR IGNORE INTO knowledge_edges (source, target, relation, weight, timestamp) VALUES (?, ?, ?, ?, ?)",
                                          (subj, obj, pred.upper().replace(" ", "_"), 1.5, time.time()))
                            except Exception:
                                pass

            conn.commit()
            conn.close()
        except Exception:
            pass

        return entities_added

    def on_consolidate(self, from_layer: str, to_layer: str, entry_id: str = ""):
        try:
            conn = self._get_conn()
            self._ensure_schema(conn)
            c = conn.cursor()

            src_entity = f"layer_{from_layer}"
            tgt_entity = f"layer_{to_layer}"

            for ename in [src_entity, tgt_entity]:
                existing = c.execute("SELECT frequency FROM knowledge_graph WHERE entity_name = ?", (ename,)).fetchone()
                if existing:
                    c.execute("UPDATE knowledge_graph SET frequency = frequency + 1, last_seen = ? WHERE entity_name = ?",
                              (time.time(), ename))
                else:
                    c.execute("INSERT OR IGNORE INTO knowledge_graph (entity_name, entity_type, properties, first_seen, last_seen, frequency) VALUES (?, ?, ?, ?, ?, 1)",
                              (ename, "layer", json.dumps({"icme_layer": ename.replace("layer_", "")}), time.time(), time.time()))

            c.execute("INSERT OR IGNORE INTO knowledge_edges (source, target, relation, weight, timestamp) VALUES (?, ?, ?, ?, ?)",
                      (src_entity, tgt_entity, "CONSOLIDATES_TO", 2.0, time.time()))

            if entry_id:
                c.execute("INSERT OR IGNORE INTO knowledge_edges (source, target, relation, weight, timestamp) VALUES (?, ?, ?, ?, ?)",
                          (entry_id, tgt_entity, "MIGRATED_TO", 1.5, time.time()))

            conn.commit()
            conn.close()
        except Exception:
            pass

    def on_forget(self, entry_id: str):
        if not entry_id:
            return
        try:
            conn = self._get_conn()
            self._ensure_schema(conn)
            c = conn.cursor()

            auto_entities = c.execute(
                "SELECT entity_name FROM knowledge_graph WHERE properties LIKE ?",
                (f'%source_entry": "{entry_id}"%',),
            ).fetchall()

            for row in auto_entities:
                ename = row["entity_name"]
                freq = c.execute("SELECT frequency FROM knowledge_graph WHERE entity_name = ?", (ename,)).fetchone()
                if freq and freq["frequency"] <= 1:
                    c.execute("DELETE FROM knowledge_edges WHERE source = ? OR target = ?", (ename, ename))
                    c.execute("DELETE FROM knowledge_graph WHERE entity_name = ?", (ename,))
                else:
                    c.execute("UPDATE knowledge_graph SET frequency = frequency - 1 WHERE entity_name = ?", (ename,))

            c.execute("DELETE FROM knowledge_edges WHERE source = ? AND relation = 'MIGRATED_TO'", (entry_id,))

            conn.commit()
            conn.close()
        except Exception:
            pass

    def on_recall_enhance(self, query: str, results: List[Dict]) -> List[Dict]:
        if not query or not results:
            return results

        try:
            conn = self._get_conn()
            c = conn.cursor()

            query_entities = set()
            for pattern, etype in self._pattern_cache:
                for match in pattern.finditer(query):
                    query_entities.add(match.group(1))

            if not query_entities:
                conn.close()
                return results

            related_ids = set()
            for entity in query_entities:
                rows = c.execute(
                    "SELECT source, target FROM knowledge_edges WHERE source = ? OR target = ? LIMIT 50",
                    (entity, entity),
                ).fetchall()
                for r in rows:
                    related_ids.add(r["source"])
                    related_ids.add(r["target"])

            conn.close()

            if not related_ids:
                return results

            enhanced = []
            for entry in results:
                content = entry.get("content", "") if isinstance(entry, dict) else ""
                boost = 0
                for eid in related_ids:
                    if eid.lower() in content.lower():
                        boost += 0.1
                if isinstance(entry, dict):
                    entry["kg_boost"] = boost
                enhanced.append(entry)

            enhanced.sort(key=lambda x: x.get("kg_boost", 0) if isinstance(x, dict) else 0, reverse=True)
            return enhanced
        except Exception:
            return results

    def _extract_entities(self, content: str, tags: List[str], layer: str) -> List[tuple]:
        entities = []

        for pattern, etype in self._pattern_cache:
            for match in pattern.finditer(content):
                name = match.group(1).strip()
                if name and len(name) >= 2:
                    entities.append((name, etype))

        for tag in tags:
            if tag.startswith("module:"):
                entities.append((tag.replace("module:", ""), "module"))
            elif tag.startswith("agent:"):
                entities.append((tag.replace("agent:", ""), "agent"))
            elif tag.startswith("skill:"):
                entities.append((tag.replace("skill:", ""), "skill"))

        seen = set()
        unique = []
        for name, etype in entities:
            key = (name, etype)
            if key not in seen:
                seen.add(key)
                unique.append(key)

        return unique

    def get_sync_stats(self) -> Dict[str, Any]:
        try:
            conn = self._get_conn()
            c = conn.cursor()

            n = c.execute("SELECT COUNT(*) FROM knowledge_graph").fetchone()[0]
            m = c.execute("SELECT COUNT(*) FROM knowledge_edges").fetchone()[0]
            auto_n = c.execute("SELECT COUNT(*) FROM knowledge_graph WHERE properties LIKE '%auto_extracted%' OR properties LIKE '%auto_triple%'").fetchone()[0]
            cons_m = c.execute("SELECT COUNT(*) FROM knowledge_edges WHERE relation = 'CONSOLIDATES_TO'").fetchone()[0]
            causal_m = c.execute("SELECT COUNT(*) FROM knowledge_edges WHERE relation IN ('CAUSES','LEADS_TO','TRIGGERS','INFLUENCES_CAUSAL','ENABLES','RESULTS_IN')").fetchone()[0]
            temporal_m = c.execute("SELECT COUNT(*) FROM knowledge_edges WHERE relation LIKE 'TEMPORAL_%' OR relation LIKE 'ICME_%'").fetchone()[0]
            layer_n = c.execute("SELECT COUNT(*) FROM knowledge_graph WHERE entity_type = 'layer'").fetchone()[0]
            agent_n = c.execute("SELECT COUNT(*) FROM knowledge_graph WHERE entity_type = 'agent'").fetchone()[0]
            module_n = c.execute("SELECT COUNT(*) FROM knowledge_graph WHERE entity_type = 'module'").fetchone()[0]

            conn.close()
            return {
                "total_entities": n,
                "total_edges": m,
                "auto_extracted_entities": auto_n,
                "consolidation_edges": cons_m,
                "causal_edges": causal_m,
                "temporal_edges": temporal_m,
                "layer_entities": layer_n,
                "agent_entities": agent_n,
                "module_entities": module_n,
                "sync_hooks": ["on_remember", "on_consolidate", "on_forget", "on_recall_enhance"],
            }
        except Exception:
            return {"total_entities": 0, "total_edges": 0, "auto_extracted_entities": 0, "consolidation_edges": 0, "causal_edges": 0, "temporal_edges": 0, "sync_hooks": []}
