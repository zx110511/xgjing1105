# -*- coding: utf-8-sig -*-
"""学习闭环 — 技能提取器

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
from .learning_loop_models import (
    TaskComplexity, LearningPhase, KnowledgeType,
    LearningRecord, ExtractedKnowledge, ReflectionResult,
)
from .learning_loop_knowledge import KnowledgeClassifiedIndex, KnowledgeCategory

class SkillExtractor:
    """
    技能提炼器 — 从学习记录和知识中自动提炼可复用技能

    触发条件:
      - 复杂/关键任务完成
      - 同一操作模式出现3次以上
      - 错误被成功修复2次以上

    输出:
      - 技能模板(代码片段、工具组合)
      - 技能元数据(依赖、适用场景、置信度)
    """

    def __init__(self, index: Optional[KnowledgeClassifiedIndex] = None):
        self._index = index
        self._skill_candidates: Dict[str, int] = {}
        self._skills: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def observe_pattern(self, action_name: str,
                        success: bool, tags: List[str] = None):
        with self._lock:
            key = action_name
            if key not in self._skill_candidates:
                self._skill_candidates[key] = {"count": 0, "successes": 0, "tags": []}
            self._skill_candidates[key]["count"] += 1
            if success:
                self._skill_candidates[key]["successes"] += 1
            if tags:
                self._skill_candidates[key]["tags"].extend(tags)

    def extract_skill(self, action_name: str, template: str,
                      description: str, dependencies: List[str] = None) -> Optional[Dict[str, Any]]:
        with self._lock:
            candidate = self._skill_candidates.get(action_name, {})
            count = candidate.get("count", 0)
            successes = candidate.get("successes", 0)
            success_rate = successes / max(count, 1)

            if count >= 3 and success_rate >= 0.66:
                skill = {
                    "name": action_name,
                    "template": template,
                    "description": description,
                    "dependencies": dependencies or [],
                    "confidence": round(success_rate * 0.7 + min(count / 10, 0.3), 4),
                    "source_tags": list(set(candidate.get("tags", []))),
                    "usage_count": count,
                    "success_rate": success_rate,
                    "created_at": time.time(),
                }
                self._skills.append(skill)

                if self._index:
                    ck = CategorizedKnowledge(
                        category=KnowledgeCategory.SKILL,
                        title=f"技能: {action_name}",
                        body=f"{description}\n\n模板: {template}",
                        source_session="auto_extract",
                        source_agent="SkillExtractor",
                        confidence=skill["confidence"],
                        tags=skill["source_tags"],
                        keywords=[action_name] + (dependencies or []),
                        skill_template=template,
                    )
                    self._index.add(ck)

                del self._skill_candidates[action_name]
                return skill
        return None

    def get_skills(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._skills)

    def get_candidates(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_candidates": len(self._skill_candidates),
                "candidates": {
                    k: {"count": v["count"], "success_rate": round(
                        v["successes"] / max(v["count"], 1), 2
                    )} for k, v in self._skill_candidates.items()
                },
                "extracted_skills": len(self._skills),
            }

    def save(self, path: Path):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "skills": self._skills,
                    "candidates": {
                        k: v for k, v in self._skill_candidates.items()
                    },
                }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        except Exception:
            pass

    def load(self, path: Path):
        try:
            if not path.exists():
                return
            raw = json.loads(path.read_text(encoding="utf-8"))
            with self._lock:
                self._skills = raw.get("skills", [])
                self._skill_candidates = raw.get("candidates", {})
        except Exception:
            pass


__all__ = ["SkillExtractor"]
