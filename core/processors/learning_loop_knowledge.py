# -*- coding: utf-8-sig -*-
"""学习闭环 — 知识分类索引

从 learning_loop.py 拆分 (SSS-PhaseB)
"""

import json
import time
import hashlib
import threading
import logging
from pathlib import Path
from typing import Any, Optional, Dict, List, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
try:
    from core.shared.deepseek_driver import TianjiEvent, EventType
except ImportError:
    TianjiEvent = None
    EventType = None
import urllib.request
try:
    from ..shared.skill_registry import SkillSchema, SkillCategory, SkillStatus
except ImportError:
    SkillSchema = None
    SkillCategory = None
    SkillStatus = None

class KnowledgeCategory(str, Enum):
    PATTERN = "pattern"
    SOLUTION = "solution"
    DECISION = "decision"
    ERROR_PATTERN = "error_pattern"
    WORKFLOW = "workflow"
    BEST_PRACTICE = "best_practice"
    SKILL = "skill"
    INSIGHT = "insight"


@dataclass
class CategorizedKnowledge:
    category: KnowledgeCategory
    title: str
    body: str
    source_session: str
    source_agent: str
    confidence: float = 0.5
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    memory_id: str = ""
    reusable: bool = True
    skill_template: str = ""

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "title": self.title,
            "body": self.body[:500],
            "source_session": self.source_session,
            "source_agent": self.source_agent,
            "confidence": self.confidence,
            "tags": self.tags,
            "keywords": self.keywords,
            "reusable": self.reusable,
            "has_skill_template": bool(self.skill_template),
        }


class KnowledgeClassifiedIndex:
    """
    知识分库索引 — 按8个类别分类存储和检索知识

    8个知识类别:
      - pattern: 行为模式(重复出现的操作序列)
      - solution: 解决方案(针对特定问题的方法)
      - decision: 决策记录(架构决策、设计选择)
      - error_pattern: 错误模式(错误类型、修复方法)
      - workflow: 工作流(多步骤操作流程)
      - best_practice: 最佳实践(经过验证的推荐做法)
      - skill: 可复用技能(代码模板、工具组合)
      - insight: 深度洞察(反思、趋势分析、关联发现)
    """

    MAX_PER_CATEGORY = 500

    def __init__(self, index_path: Optional[Path] = None):
        self._index: Dict[KnowledgeCategory, List[CategorizedKnowledge]] = {
            c: [] for c in KnowledgeCategory
        }
        self._lock = threading.Lock()
        self._index_path = index_path
        self._stats: Dict[str, int] = {c.value: 0 for c in KnowledgeCategory}
        self._stats["total"] = 0

        if self._index_path and self._index_path.exists():
            self._load()

    def add(self, knowledge: CategorizedKnowledge) -> bool:
        with self._lock:
            cat_list = self._index[knowledge.category]
            if len(cat_list) >= self.MAX_PER_CATEGORY:
                cat_list.pop(0)
            cat_list.append(knowledge)
            self._stats[knowledge.category.value] = len(cat_list)
            self._stats["total"] += 1
        return True

    def search(self, query: str, category: Optional[KnowledgeCategory] = None,
               limit: int = 10) -> List[CategorizedKnowledge]:
        results = []
        with self._lock:
            categories = [category] if category else list(KnowledgeCategory)
            query_lower = query.lower()
            for cat in categories:
                for k in self._index[cat]:
                    score = 0
                    if query_lower in k.title.lower():
                        score += 10
                    if query_lower in k.body.lower():
                        score += 5
                    for kw in k.keywords:
                        if query_lower in kw.lower():
                            score += 3
                    for tag in k.tags:
                        if query_lower in tag.lower():
                            score += 2
                    if score > 0:
                        results.append((score, k))

        results.sort(key=lambda x: x[0], reverse=True)
        return [k for _, k in results[:limit]]

    def get_by_category(self, category: KnowledgeCategory,
                         limit: int = 20) -> List[CategorizedKnowledge]:
        with self._lock:
            return list(self._index[category])[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total": self._stats["total"],
                "by_category": {c.value: len(self._index[c]) for c in KnowledgeCategory},
                "avg_confidence": round(
                    sum(k.confidence for cats in self._index.values() for k in cats)
                    / max(self._stats["total"], 1), 4
                ),
            }

    def _save(self):
        if not self._index_path:
            return
        try:
            data = {}
            for cat, items in self._index.items():
                data[cat.value] = [it.to_dict() for it in items]
            self._index_path.parent.mkdir(parents=True, exist_ok=True)
            self._index_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _load(self):
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
            for cat_name, items in raw.items():
                cat = KnowledgeCategory(cat_name)
                for item in items:
                    k = CategorizedKnowledge(
                        category=cat,
                        title=item.get("title", ""),
                        body=item.get("body", ""),
                        source_session=item.get("source_session", ""),
                        source_agent=item.get("source_agent", ""),
                        confidence=item.get("confidence", 0.5),
                        tags=item.get("tags", []),
                        keywords=item.get("keywords", []),
                    )
                    self._index[cat].append(k)
                self._stats[cat_name] = len(self._index[cat])
                self._stats["total"] += len(self._index[cat])
        except Exception:
            pass




__all__ = ["KnowledgeCategory", "CategorizedKnowledge", "KnowledgeClassifiedIndex"]
