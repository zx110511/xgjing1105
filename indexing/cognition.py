"""
认知流水线 - 集成自nexus-memory
认知层级: raw → explicit → derived → digest → contradiction → representation
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import Counter
from pathlib import Path
import json


@dataclass
class CognitiveMemory:
    id: str
    content: str
    cognitive_level: str
    category: str = "general"
    labels: List[str] = field(default_factory=list)
    confidence: float = 1.0
    evidence_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionDigest:
    session_key: str
    digest_kind: str
    content: str
    memory_count: int = 0
    token_count: int = 0
    created_at: float = field(default_factory=time.time)


@dataclass
class WorkingRepresentation:
    query: str
    digests: List[SessionDigest] = field(default_factory=list)
    recent_memories: List[CognitiveMemory] = field(default_factory=list)
    semantic_matches: List[CognitiveMemory] = field(default_factory=list)
    derived_insights: List[CognitiveMemory] = field(default_factory=list)
    contradictions: List[CognitiveMemory] = field(default_factory=list)
    total_items: int = 0


class CognitionPipeline:
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.cognition_file = data_path / "cognition.json"
        self._sessions: Dict[str, List[CognitiveMemory]] = {}
        self._digests: Dict[str, List[SessionDigest]] = {}
        self._derived: List[CognitiveMemory] = []
        self._contradictions: List[CognitiveMemory] = []
        self._load_from_disk()

    def _load_from_disk(self):
        if self.cognition_file.exists():
            try:
                data = json.loads(self.cognition_file.read_text(encoding="utf-8"))
                for item in data.get("derived", []):
                    self._derived.append(CognitiveMemory(**item))
                for item in data.get("contradictions", []):
                    self._contradictions.append(CognitiveMemory(**item))
                for key, digests in data.get("digests", {}).items():
                    self._digests[key] = [SessionDigest(**d) for d in digests]
            except Exception as e:
                print(f"[Cognition] Load error: {e}")

    def _save_to_disk(self):
        try:
            data = {
                "derived": [
                    {
                        "id": m.id,
                        "content": m.content,
                        "cognitive_level": m.cognitive_level,
                        "category": m.category,
                        "labels": m.labels,
                        "confidence": m.confidence,
                        "evidence_ids": m.evidence_ids,
                        "created_at": m.created_at,
                        "metadata": m.metadata,
                    }
                    for m in self._derived
                ],
                "contradictions": [
                    {
                        "id": m.id,
                        "content": m.content,
                        "cognitive_level": m.cognitive_level,
                        "confidence": m.confidence,
                        "created_at": m.created_at,
                    }
                    for m in self._contradictions
                ],
                "digests": {
                    key: [
                        {
                            "session_key": d.session_key,
                            "digest_kind": d.digest_kind,
                            "content": d.content,
                            "memory_count": d.memory_count,
                            "token_count": d.token_count,
                            "created_at": d.created_at,
                        }
                        for d in digests
                    ]
                    for key, digests in self._digests.items()
                },
            }
            self.cognition_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[Cognition] Save error: {e}")

    def derive(self, raw_memories: List, namespace: str = "general") -> List[CognitiveMemory]:
        derived = []
        for mem in raw_memories[-20:]:
            content = mem.content if hasattr(mem, "content") else mem.get("content", "")
            mem_id = mem.id if hasattr(mem, "id") else mem.get("id", "")
            if len(content) > 50:
                derived.append(
                    CognitiveMemory(
                        id=f"derived-{mem_id}",
                        content=f"[Derived] {content[:200]}...",
                        cognitive_level="explicit",
                        category="facts",
                        labels=["derived", f"namespace:{namespace}"],
                        confidence=0.8,
                        evidence_ids=[mem_id],
                    )
                )
        self._derived.extend(derived)
        self._save_to_disk()
        return derived

    def digest(self, session_key: str, memories: List, kind: str = "short") -> SessionDigest:
        if not memories:
            return SessionDigest(session_key=session_key, digest_kind=kind, content="")

        agents = set()
        key_terms = []

        for mem in memories:
            content = mem.content if hasattr(mem, "content") else mem.get("content", "")
            labels = mem.labels if hasattr(mem, "labels") else mem.get("labels", [])
            for label in labels:
                if label.startswith("agent:"):
                    agents.add(label.split(":", 1)[1])
                elif label.startswith("entity:"):
                    key_terms.append(label.split(":", 1)[1])

        summary = f"[{kind.upper()} DIGEST] Session: {session_key}\n"
        summary += f"Memories: {len(memories)} | Agents: {', '.join(agents) or 'none'}\n"
        summary += f"Key entities: {', '.join(key_terms[:10]) or 'none'}"

        d = SessionDigest(
            session_key=session_key,
            digest_kind=kind,
            content=summary,
            memory_count=len(memories),
            token_count=len(summary.split()),
        )
        if session_key not in self._digests:
            self._digests[session_key] = []
        self._digests[session_key].append(d)
        self._save_to_disk()
        return d

    def dream(self, memories: List, namespace: str = "general", max_iterations: int = 3) -> dict:
        stats = {
            "memories_derived": 0,
            "connections_found": 0,
            "contradictions_detected": 0,
            "digests_updated": 0,
        }

        if len(memories) < 2:
            return stats

        recent = sorted(memories, key=lambda m: m.created_at if hasattr(m, "created_at") else 0, reverse=True)
        recent = recent[:50]

        derived = self.derive(recent, namespace)
        stats["memories_derived"] = len(derived)

        content_texts = []
        for m in recent:
            c = m.content if hasattr(m, "content") else m.get("content", "")
            content_texts.append(c.lower())

        for i in range(len(content_texts)):
            for j in range(i + 1, len(content_texts)):
                if i != j and len(content_texts[i]) > 20 and len(content_texts[j]) > 20:
                    words_i = set(content_texts[i].split())
                    words_j = set(content_texts[j].split())
                    denom = max(len(words_i | words_j), 1)
                    overlap = len(words_i & words_j) / denom
                    if overlap > 0.4:
                        stats["connections_found"] += 1
                        if overlap > 0.8 and content_texts[i] != content_texts[j]:
                            stats["contradictions_detected"] += 1
                            self._contradictions.append(
                                CognitiveMemory(
                                    id=f"contra-{time.time()}",
                                    content="Potential contradiction between memories",
                                    cognitive_level="contradiction",
                                    confidence=0.5,
                                )
                            )

        for session_key, session_mems in self._sessions.items():
            if session_mems:
                self.digest(session_key, session_mems[-20:], "short")
                stats["digests_updated"] += 1

        self._save_to_disk()
        return stats

    def reflect(self, query: str, memories: List, namespace: str = "general") -> dict:
        if not memories:
            return {"reflection": "No memories available", "insights": []}

        categories = Counter()
        for m in memories:
            cat = m.category if hasattr(m, "category") else m.get("category", "general")
            categories[cat] += 1

        query_lower = query.lower()
        relevant = [
            m
            for m in memories
            if query_lower in (m.content if hasattr(m, "content") else m.get("content", "")).lower()
        ]

        return {
            "reflection": f"Found {len(relevant)} relevant memories out of {len(memories)} total",
            "insights": [
                f"Category distribution: {dict(categories)}",
                f"Query matches: {len(relevant)}",
                f"Derived insights accumulated: {len(self._derived)}",
                f"Contradictions tracked: {len(self._contradictions)}",
            ],
            "relevant_count": len(relevant),
            "total_count": len(memories),
        }

    def build_representation(
        self, query: str, memories: List, namespace: str = "general", max_items: int = 24
    ) -> WorkingRepresentation:
        query_lower = query.lower()

        semantic_matches = []
        for m in memories:
            content = m.content if hasattr(m, "content") else m.get("content", "")
            if query_lower in content.lower():
                semantic_matches.append(
                    CognitiveMemory(
                        id=m.id if hasattr(m, "id") else m.get("id", ""),
                        content=content,
                        cognitive_level="explicit",
                        category=m.category if hasattr(m, "category") else m.get("category", "general"),
                        labels=m.labels if hasattr(m, "labels") else m.get("labels", []),
                    )
                )

        semantic_matches.sort(key=lambda m: m.created_at, reverse=True)
        semantic_matches = semantic_matches[:max_items]

        all_digests = []
        for digests in self._digests.values():
            all_digests.extend(digests)

        return WorkingRepresentation(
            query=query,
            digests=all_digests[-5:],
            semantic_matches=semantic_matches,
            derived_insights=self._derived[-10:],
            contradictions=self._contradictions[-5:],
            total_items=len(semantic_matches)
            + len(all_digests[-5:])
            + len(self._derived[-10:])
            + len(self._contradictions[-5:]),
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "derived_count": len(self._derived),
            "contradictions_count": len(self._contradictions),
            "sessions_count": len(self._sessions),
            "digests_count": sum(len(d) for d in self._digests.values()),
        }
