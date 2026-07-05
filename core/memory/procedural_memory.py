r"""
天机程序记忆系统 (Tianji Procedural Memory) v1.0
========================================================
技能/规则/行为模式的存储和演化

设计哲学:
  程序记忆是ICME六层之外的第七记忆维度
  专门存储可执行的技能、可演化的规则、可学习的模式
  与ICME的L5 Meta层协同，但独立管理

核心类型:
  - Skill: 可执行技能，包含代码+参数+前后条件
  - Rule: 可演化规则，包含权重+反馈机制
  - Pattern: 可学习模式，包含触发条件+响应行为

架构位置: 天机/core/procedural_memory.py

灵境道谱溯源: D3-4【程序记忆煞】· 道三·进化体道 · 四地煞之化之术
"""

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SkillStatus(str, Enum):
    DRAFT = "draft"
    VERIFIED = "verified"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EVOLVED = "evolved"


class RuleType(str, Enum):
    CONSTRAINT = "constraint"
    HEURISTIC = "heuristic"
    PREFERENCE = "preference"
    SAFETY = "safety"


@dataclass
class ProceduralSkill:
    """可执行技能"""

    id: str = ""
    name: str = ""
    description: str = ""
    category: str = "general"
    code: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    success_rate: float = 0.0
    usage_count: int = 0
    status: SkillStatus = SkillStatus.DRAFT
    tags: list[str] = field(default_factory=list)
    learned_from: str = ""
    learned_at: float = field(default_factory=time.time)
    evolved_at: float = 0.0
    evolution_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(
                f"{self.name}:{self.category}:{time.time()}".encode()
            ).hexdigest()[:16]

    def record_usage(self, success: bool = True):
        self.usage_count += 1
        alpha = 0.1
        self.success_rate = (
            self.success_rate * (1 - alpha) + (1.0 if success else 0.0) * alpha
        )

    def evolve(self, new_code: str, reason: str = ""):
        self.evolution_history.append(
            {"timestamp": time.time(), "old_code": self.code[:100], "reason": reason}
        )
        self.code = new_code
        self.evolved_at = time.time()
        self.status = SkillStatus.EVOLVED

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "code": self.code,
            "parameters": self.parameters,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "status": self.status.value,
            "tags": self.tags,
            "learned_from": self.learned_from,
            "learned_at": self.learned_at,
            "evolved_at": self.evolved_at,
            "metadata": self.metadata,
        }


@dataclass
class EvolvableRule:
    """可演化规则"""

    id: str = ""
    name: str = ""
    description: str = ""
    rule_type: RuleType = RuleType.HEURISTIC
    condition: str = ""
    action: str = ""
    weight: float = 1.0
    min_weight: float = 0.1
    max_weight: float = 2.0
    confidence: float = 0.8
    activation_count: int = 0
    success_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    feedback_history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(
                f"{self.name}:{self.rule_type.value}:{time.time()}".encode()
            ).hexdigest()[:16]

    def activate(self, success: bool = True):
        self.activation_count += 1
        if success:
            self.success_count += 1

        if self.activation_count > 0:
            self.confidence = self.success_count / self.activation_count

    def apply_feedback(self, is_positive: bool, adjustment: float = 0.1):
        if is_positive:
            self.weight = min(self.max_weight, self.weight + adjustment)
        else:
            self.weight = max(self.min_weight, self.weight - adjustment)

        self.feedback_history.append(
            {
                "timestamp": time.time(),
                "is_positive": is_positive,
                "adjustment": adjustment,
                "new_weight": self.weight,
            }
        )
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type.value,
            "condition": self.condition,
            "action": self.action,
            "weight": self.weight,
            "confidence": self.confidence,
            "activation_count": self.activation_count,
            "success_count": self.success_count,
        }


@dataclass
class LearnedPattern:
    """可学习模式"""

    id: str = ""
    trigger: str = ""
    response: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    frequency: int = 0
    last_matched: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(f"{self.trigger}:{time.time()}".encode()).hexdigest()[
                :16
            ]

    def match(self, input_text: str) -> float:
        if self.trigger in input_text:
            self.last_matched = time.time()
            self.frequency += 1
            return 1.0
        return 0.0


class ProceduralMemoryStore:
    """程序记忆存储引擎"""

    def __init__(self, storage_path: str = "data/.memory/procedural_memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._skills: dict[str, ProceduralSkill] = {}
        self._rules: dict[str, EvolvableRule] = {}
        self._patterns: dict[str, LearnedPattern] = {}

        self._lock = threading.RLock()
        self._load_all()

        logger.info(
            f"程序记忆存储初始化: {len(self._skills)} 技能, {len(self._rules)} 规则, {len(self._patterns)} 模式"
        )

    def _load_all(self):
        self._load_skills()
        self._load_rules()
        self._load_patterns()

    def _load_skills(self):
        skill_file = self.storage_path / "skills.json"
        if skill_file.exists():
            try:
                with open(skill_file, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    skill = ProceduralSkill(**item)
                    skill.status = SkillStatus(item.get("status", "draft"))
                    self._skills[skill.id] = skill
            except Exception as e:
                logger.error(f"加载技能失败: {e}")

    def _save_skills(self):
        skill_file = self.storage_path / "skills.json"
        with open(skill_file, "w", encoding="utf-8") as f:
            json.dump(
                [s.to_dict() for s in self._skills.values()],
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _load_rules(self):
        rule_file = self.storage_path / "rules.json"
        if rule_file.exists():
            try:
                with open(rule_file, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    rule = EvolvableRule(**item)
                    rule.rule_type = RuleType(item.get("rule_type", "heuristic"))
                    self._rules[rule.id] = rule
            except Exception as e:
                logger.error(f"加载规则失败: {e}")

    def _save_rules(self):
        rule_file = self.storage_path / "rules.json"
        with open(rule_file, "w", encoding="utf-8") as f:
            json.dump(
                [r.to_dict() for r in self._rules.values()],
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _load_patterns(self):
        pattern_file = self.storage_path / "patterns.json"
        if pattern_file.exists():
            try:
                with open(pattern_file, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    pattern = LearnedPattern(**item)
                    self._patterns[pattern.id] = pattern
            except Exception as e:
                logger.error(f"加载模式失败: {e}")

    def _save_patterns(self):
        pattern_file = self.storage_path / "patterns.json"
        with open(pattern_file, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {k: v for k, v in p.__dict__.items()}
                    for p in self._patterns.values()
                ],
                f,
                ensure_ascii=False,
                indent=2,
            )

    def add_skill(self, skill: ProceduralSkill) -> str:
        with self._lock:
            self._skills[skill.id] = skill
            self._save_skills()
            logger.info(f"技能添加: {skill.name} (状态: {skill.status.value})")
            return skill.id

    def get_skill(self, skill_id: str) -> ProceduralSkill | None:
        return self._skills.get(skill_id)

    def find_skills_by_tags(self, tags: list[str]) -> list[ProceduralSkill]:
        results = []
        for skill in self._skills.values():
            if any(tag in skill.tags for tag in tags):
                results.append(skill)
        return results

    def evolve_skill(
        self, skill_id: str, new_code: str, reason: str = ""
    ) -> ProceduralSkill | None:
        with self._lock:
            skill = self._skills.get(skill_id)
            if skill:
                skill.evolve(new_code, reason)
                self._save_skills()
            return skill

    def add_rule(self, rule: EvolvableRule) -> str:
        with self._lock:
            self._rules[rule.id] = rule
            self._save_rules()
            return rule.id

    def get_active_rules(
        self, rule_type: RuleType | None = None
    ) -> list[EvolvableRule]:
        rules = list(self._rules.values())
        if rule_type:
            rules = [r for r in rules if r.rule_type == rule_type]
        return sorted(rules, key=lambda r: r.weight, reverse=True)

    def apply_rule_feedback(
        self, rule_id: str, is_positive: bool, adjustment: float = 0.1
    ) -> EvolvableRule | None:
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule:
                rule.apply_feedback(is_positive, adjustment)
                self._save_rules()
            return rule

    def add_pattern(self, pattern: LearnedPattern) -> str:
        with self._lock:
            self._patterns[pattern.id] = pattern
            self._save_patterns()
            return pattern.id

    def find_pattern(self, input_text: str) -> LearnedPattern | None:
        best_match = None
        best_score = 0.0
        for pattern in self._patterns.values():
            score = pattern.match(input_text)
            if score > best_score:
                best_score = score
                best_match = pattern
        return best_match if best_match else None

    def get_stats(self) -> dict[str, Any]:
        active_skills = sum(
            1 for s in self._skills.values() if s.status == SkillStatus.ACTIVE
        )
        return {
            "skill_count": len(self._skills),
            "active_skills": active_skills,
            "rule_count": len(self._rules),
            "pattern_count": len(self._patterns),
            "avg_skill_success_rate": (
                sum(s.success_rate for s in self._skills.values())
                / max(len(self._skills), 1)
            ),
        }
