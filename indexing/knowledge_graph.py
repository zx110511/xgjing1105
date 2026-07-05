r"""
天机v9.1 - 知识图谱构建器 v1.1
================================
从记忆条目中自动提取实体关系, 构建轻量知识图谱
支持JSON导出、SQLite持久化和关联查询

M32升级: EvolutionLoop闭环 + record_action喂入 + health() + 双注入
灵境道谱溯源: D8-1【知识图谱煞】· 道八·认知体道 · 四地煞之识之术
  - 实体-关系自动提取+共现网络构建+图谱演化追踪
  - 源文件: indexing/knowledge_graph.py → KnowledgeGraph
"""

import json
import time
import re
import threading
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict

try:
    from core.processors.evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None


class KnowledgeGraph:
    def __init__(self, data_path: Path, sqlite_store: Any = None,
                 recorder: Optional[Any] = None,
                 learning_engine: Optional[Any] = None):
        self.data_path = data_path / "knowledge_graph"
        self.data_path.mkdir(parents=True, exist_ok=True)
        self._sqlite_store = sqlite_store
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._errors = 0
        self._graph: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []
        self._entity_index: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()
        self._dirty = False
        self._auto_save_interval = 30
        self._last_auto_save = time.time()

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="knowledge_graph",
                    effectiveness_fn=self._calc_kg_effectiveness,
                    learn_fn=self._learn_from_kg,
                    evolve_fn=self._evolve_kg_config,
                    mutable_config={
                        "auto_save_interval": 30,
                        "min_entity_length": 2,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception:
                pass

        self._load()

    def add_entity(self, name: str, entity_type: str = "concept", properties: Dict = None):
        with self._lock:
            if name not in self._graph:
                self._graph[name] = {
                    "name": name,
                    "type": entity_type,
                    "properties": properties or {},
                    "first_seen": time.time(),
                    "last_seen": time.time(),
                    "frequency": 0,
                }
            self._graph[name]["frequency"] += 1
            self._graph[name]["last_seen"] = time.time()
            self._dirty = True
            self._maybe_auto_save()

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="add_entity",
                        state_before={"entity_name": name, "new": False},
                        state_after={"entity_name": name,
                                     "entity_type": entity_type,
                                     "frequency": self._graph[name]["frequency"]},
                    )
                except Exception:
                    pass

    def add_relation(self, source: str, target: str, relation: str, weight: float = 1.0):
        with self._lock:
            self.add_entity(source, "concept")
            self.add_entity(target, "concept")

            edge = {
                "source": source,
                "target": target,
                "relation": relation,
                "weight": weight,
                "timestamp": time.time(),
            }
            self._edges.append(edge)
            self._entity_index[source].add(target)
            self._entity_index[target].add(source)
            self._dirty = True

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="add_relation",
                        state_before={"edges": len(self._edges) - 1},
                        state_after={"source": source,
                                     "target": target,
                                     "relation": relation,
                                     "weight": weight,
                                     "edges": len(self._edges)},
                    )
                except Exception:
                    pass

    def extract_from_text(self, text: str, source_id: str):
        entities = self._extract_named_entities(text)

        with self._lock:
            for entity_name, entity_type in entities:
                self.add_entity(entity_name, entity_type)

            entity_names = [e[0] for e in entities]
            for i, e1 in enumerate(entity_names):
                for e2 in entity_names[i+1:]:
                    self._add_cooccurrence(e1, e2)

            pattern_relations = [
                (r'(.{2,10})是(.{2,10})', "is_a"),
                (r'(.{2,10})属于(.{2,10})', "belongs_to"),
                (r'(.{2,10})包含(.{2,10})', "contains"),
                (r'(.{2,10})调用(.{2,10})', "calls"),
                (r'(.{2,10})使用(.{2,10})', "uses"),
            ]

            for pattern, rel_type in pattern_relations:
                for match in re.finditer(pattern, text):
                    e1 = match.group(1).strip()
                    e2 = match.group(2).strip()
                    if 2 <= len(e1) <= 20 and 2 <= len(e2) <= 20:
                        self.add_relation(e1, e2, rel_type, 1.5)

            if source_id:
                for e1 in entity_names[:5]:
                    self._graph[e1].setdefault("source_ids", []).append(source_id)

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="extract_from_text",
                        state_before={"entities": len(self._graph),
                                      "edges": len(self._edges)},
                        state_after={"extracted_entities": len(entities),
                                     "entities": len(self._graph),
                                     "edges": len(self._edges),
                                     "source_id": source_id},
                    )
                except Exception:
                    pass

    def query_entity(self, name: str) -> Optional[Dict]:
        if name in self._graph:
            entity = dict(self._graph[name])
            entity["related"] = list(self._entity_index.get(name, set()))
            entity["relations"] = [
                e for e in self._edges
                if e["source"] == name or e["target"] == name
            ][:20]

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="query_entity",
                        state_before={"query": name},
                        state_after={"entity_found": True,
                                     "entity_name": name,
                                     "type": entity.get("type", ""),
                                     "related_count": len(entity.get("related", []))},
                    )
                except Exception:
                    pass

            return entity
        return None

    def search_entities(self, query: str, limit: int = 20) -> List[Dict]:
        results = []
        query_lower = query.lower()
        for name, entity in self._graph.items():
            if query_lower in name.lower():
                results.append({
                    "name": name,
                    "type": entity["type"],
                    "frequency": entity["frequency"],
                    "score": 1.0 if query_lower == name.lower() else 0.7,
                })
        results.sort(key=lambda x: (x["score"], x["frequency"]), reverse=True)
        return results[:limit]

    def get_graph_stats(self) -> Dict:
        return {
            "entities": len(self._graph),
            "edges": len(self._edges),
            "entity_types": self._count_entity_types(),
            "top_entities": self._top_entities(10),
        }

    def health(self) -> Dict[str, Any]:
        return {
            "status": "ready",
            "version": "1.1",
            "entities": len(self._graph),
            "edges": len(self._edges),
            "dirty": self._dirty,
            "errors": self._errors,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
        }

    def get_stats(self) -> Dict:
        stats = self.get_graph_stats()
        stats["health"] = self.health()
        stats["version"] = "1.1"
        stats["evo_loop"] = self._evo_loop.get_stats() if self._evo_loop else {}
        return stats

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_kg_effectiveness(self, action: str,
                                state_before: Dict[str, Any],
                                state_after: Dict[str, Any]) -> float:
        if action == "extract_from_text":
            extracted = state_after.get("extracted_entities", 0)
            return 0.5 + min(0.3, extracted * 0.05) if extracted > 0 else 0.3
        elif action == "add_entity":
            return 0.6
        elif action == "add_relation":
            return 0.4 + min(0.3, state_after.get("weight", 1.0) * 0.2)
        elif action == "query_entity":
            return 0.7 if state_after.get("entity_found") else 0.1
        return 0.0

    def _learn_from_kg(self, causal_pairs: List[Any],
                        effectiveness_summary: Dict[str, Any]) -> Dict[str, Any]:
        entity_types = self._count_entity_types()
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "total_entities": len(self._graph),
            "total_edges": len(self._edges),
            "entity_type_distribution": entity_types,
            "top_entities": [e["name"] for e in self._top_entities(5)],
        }

    def _evolve_kg_config(self, learn_result: Dict[str, Any],
                           mutable_config: Dict[str, Any]) -> Dict[str, Any]:
        changes = {}
        total_entities = learn_result.get("total_entities", 0)
        if total_entities > 5000:
            changes["auto_save_interval"] = max(10,
                min(30, mutable_config.get("auto_save_interval", 30) - 5))
        else:
            changes["auto_save_interval"] = 30
        return {"rules_modified": changes, "skills_created": []}

    def export_graph(self) -> Dict:
        return {
            "entities": {
                name: {
                    "type": e["type"],
                    "frequency": e["frequency"],
                    "first_seen": e["first_seen"],
                    "last_seen": e["last_seen"],
                    "properties": e.get("properties", {}),
                }
                for name, e in self._graph.items()
            },
            "edges": [
                {
                    "source": e["source"],
                    "target": e["target"],
                    "relation": e["relation"],
                    "weight": e["weight"],
                }
                for e in self._edges
            ],
            "stats": self.get_graph_stats(),
            "exported_at": time.time(),
        }

    def save(self):
        with self._lock:
            data = self.export_graph()
            filepath = self.data_path / "knowledge_graph.json"
            filepath.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._dirty = False
            self._last_auto_save = time.time()

    def _load(self):
        filepath = self.data_path / "knowledge_graph.json"
        if filepath.exists():
            data = json.loads(filepath.read_text(encoding="utf-8-sig"))
            for name, entity_data in data.get("entities", {}).items():
                self._graph[name] = entity_data
                self._graph[name].setdefault("first_seen", time.time())
                self._graph[name].setdefault("last_seen", time.time())
            for edge in data.get("edges", []):
                self._edges.append(edge)
                self._entity_index[edge["source"]].add(edge["target"])
                self._entity_index[edge["target"]].add(edge["source"])

    def _maybe_auto_save(self):
        if self._dirty and time.time() - self._last_auto_save > self._auto_save_interval:
            self.save()

    def _add_cooccurrence(self, e1: str, e2: str):
        for edge in self._edges:
            if {edge["source"], edge["target"]} == {e1, e2} and edge["relation"] == "cooccurs_with":
                edge["weight"] += 0.2
                edge["timestamp"] = time.time()
                return
        self.add_relation(e1, e2, "cooccurs_with", 0.5)

    def _extract_named_entities(self, text: str) -> List[Tuple[str, str]]:
        entities = []
        patterns = [
            (r'@(\w{2,30})', "agent"),
            (r'#(\w{2,30})', "tag"),
            (r'【(.+?)】', "concept"),
            (r'文件[:：]?\s*`?([^\s`]{3,60})`?', "file"),
            (r'函数[:：]?\s*`?([a-zA-Z_]\w{2,40})`?', "function"),
        ]
        seen = set()
        for pattern, entity_type in patterns:
            for match in re.finditer(pattern, text):
                name = match.group(1).strip()
                if name not in seen and 2 <= len(name) <= 60:
                    entities.append((name, entity_type))
                    seen.add(name)
        return entities

    def _count_entity_types(self) -> Dict[str, int]:
        counts = defaultdict(int)
        for e in self._graph.values():
            counts[e.get("type", "unknown")] += 1
        return dict(counts)

    def _top_entities(self, n: int = 10) -> List[Dict]:
        sorted_entities = sorted(
            self._graph.items(),
            key=lambda x: x[1].get("frequency", 0),
            reverse=True,
        )
        return [
            {"name": name, "type": e["type"], "frequency": e["frequency"]}
            for name, e in sorted_entities[:n]
        ]
