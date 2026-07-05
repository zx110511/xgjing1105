# -*- coding: utf-8 -*-
"""
法则生成器 + 生命周期管理 — 将经验模式转化为结构化经验法则
[SSS-PhaseB] 从engine.py拆分

生成流程:
1. 接收ExperiencePattern列表
2. DeepSeek LLM 分析每个模式，提取结构化要素
3. 生成EmpiricalLaw草稿(DRAFT状态)
4. 自动分配编号(域名前缀+序号)
5. 写入法则索引

生命周期: DRAFT→VALIDATED→ACTIVE→DEPRECATED
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("tianji.law_domain")

from .core import (
    EmpiricalLaw,
    LawDomain,
    LawPriority,
    LawStatus,
    LawType,
    _LAW_DIR,
    _LAW_INDEX,
)


class LawGenerator:
    """
    法则生成器 — 将经验模式转化为结构化经验法则
    """

    def __init__(self, law_dir: Path = _LAW_DIR):
        self._law_dir = law_dir
        self._law_dir.mkdir(parents=True, exist_ok=True)
        self._index = self._load_index()
        self._stats = {"laws_generated": 0, "laws_from_llm": 0, "laws_from_template": 0}

    def _load_index(self) -> dict:
        if _LAW_INDEX.exists():
            try:
                return json.loads(_LAW_INDEX.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"version": "1.0", "laws": {}, "next_seq": {}}

    def _save_index(self):
        _LAW_INDEX.write_text(
            json.dumps(self._index, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _next_law_id(self, domain: LawDomain) -> str:
        prefix = LawDomain.prefix(domain)
        seq_key = domain.value
        seq = self._index["next_seq"].get(seq_key, 1)
        law_id = f"{prefix}-LAW-{seq:03d}"
        self._index["next_seq"][seq_key] = seq + 1
        return law_id

    def generate_from_patterns(
        self, patterns: list, use_llm: bool = False
    ) -> list[EmpiricalLaw]:
        """从经验模式列表生成法则"""
        from .miner import ExperiencePattern

        laws: list[EmpiricalLaw] = []
        grouped: dict[str, list[ExperiencePattern]] = {}
        for p in patterns:
            if p.already_has_law:
                continue
            key = f"{p.domain_hint.value}:{p.type_hint.value}"
            grouped.setdefault(key, []).append(p)

        for key, group in grouped.items():
            domain_str, type_str = key.split(":")
            domain = LawDomain(domain_str)
            ltype = LawType(type_str)
            priority = group[0].priority_hint

            if use_llm and len(group) >= 1:
                law = self._generate_via_llm(group, domain, ltype, priority)
                self._stats["laws_from_llm"] += 1
            else:
                law = self._generate_via_template(group, domain, ltype, priority)
                self._stats["laws_from_template"] += 1

            if law:
                laws.append(law)
                self._register_law(law)
                self._stats["laws_generated"] += 1

        self._save_index()
        return laws

    def _generate_via_template(
        self,
        patterns: list,
        domain: LawDomain,
        ltype: LawType,
        priority: LawPriority,
    ) -> EmpiricalLaw | None:
        if not patterns:
            return None
        primary = patterns[0]
        all_sources = [p.source_id for p in patterns]
        combined_content = "\n---\n".join([p.raw_content for p in patterns[:3]])

        title = self._auto_title(domain, ltype, patterns)
        principle = self._auto_principle(domain, ltype, patterns)
        steps = self._auto_steps(domain, ltype, patterns)
        scenarios = self._auto_scenarios(patterns)
        consequences = self._auto_consequences(domain, ltype)
        methods = self._auto_enforcement(domain, ltype, priority)

        law_id = self._next_law_id(domain)
        law = EmpiricalLaw(
            law_id=law_id,
            domain=domain,
            law_type=ltype,
            priority=priority,
            status=LawStatus.DRAFT,
            title=title,
            principle=principle,
            steps=steps,
            trigger_scenarios=scenarios,
            violation_consequences=consequences,
            enforcement_methods=methods,
            source_memory_ids=all_sources,
            source_experience_summary=f"从{len(patterns)}条经验记录中提炼",
            tags=[domain.value, ltype.value, priority.value, f"freq-{len(patterns)}"],
        )
        return law

    def _generate_via_llm(
        self,
        patterns: list,
        domain: LawDomain,
        ltype: LawType,
        priority: LawPriority,
    ) -> EmpiricalLaw | None:
        try:
            from core.shared.deepseek_driver import DeepSeekDriver

            driver = DeepSeekDriver()
            prompt = self._build_llm_generation_prompt(patterns, domain, ltype, priority)
            response = driver.quick_decide(prompt, context="law_generation")
            if response and response.strip():
                law_data = json.loads(response) if response.startswith("{") else None
                if law_data:
                    law_id = self._next_law_id(domain)
                    law = EmpiricalLaw(
                        law_id=law_id,
                        domain=domain,
                        law_type=ltype,
                        priority=priority,
                        status=LawStatus.DRAFT,
                        title=law_data.get("title", ""),
                        principle=law_data.get("principle", ""),
                        steps=law_data.get("steps", []),
                        trigger_scenarios=law_data.get("trigger_scenarios", []),
                        violation_consequences=law_data.get("violation_consequences", []),
                        enforcement_methods=law_data.get("enforcement_methods", []),
                        source_memory_ids=[p.source_id for p in patterns],
                        source_experience_summary=f"LLM生成({len(patterns)}条经验)",
                        tags=[domain.value, ltype.value, priority.value, "llm-generated"],
                    )
                    return law
        except Exception as e:
            logger.warning(f"[法则生成] LLM生成失败，回退到模板: {e}")
        return self._generate_via_template(patterns, domain, ltype, priority)

    def _build_llm_generation_prompt(
        self,
        patterns: list,
        domain: LawDomain,
        ltype: LawType,
        priority: LawPriority,
    ) -> str:
        experiences_text = "\n\n".join(
            [f"[经验{i + 1}] {p.raw_content[:300]}" for i, p in enumerate(patterns[:5])]
        )
        return f"""你是天机系统的经验法则提炼专家。以下是从历史故障和教训中挖掘到的{len(patterns)}条相关经验。

## 经验原始内容
{experiences_text}

## 目标信息
- 领域: {domain.value}
- 类型: {ltype.value}
- 优先级: {priority.value}

请以JSON格式返回(严格JSON，不要其他文字):
{{
  "title": "简洁标题(10字内)",
  "principle": "核心原则(1-2句话)",
  "steps": ["步骤1", "步骤2", ...],
  "trigger_scenarios": ["触发场景1", ...],
  "violation_consequences": ["违规后果1", ...],
  "enforcement_methods": ["执行方法1", ...]
}}"""

    # --- 自动生成辅助方法 ---

    def _auto_title(self, domain: LawDomain, ltype: LawType, patterns: list) -> str:
        type_names = {
            LawType.PREVENTION: "预防",
            LawType.RECOVERY: "恢复",
            LawType.OPTIMIZATION: "优化",
            LawType.GOVERNANCE: "治理",
        }
        domain_names = {
            LawDomain.PROCESS: "进程",
            LawDomain.PATH: "路径",
            LawDomain.MEMORY: "记忆",
            LawDomain.SECURITY: "安全",
            LawDomain.CODE_QUALITY: "代码质量",
            LawDomain.DEPLOY: "部署",
            LawDomain.AGENT: "智能体",
        }
        return f"{domain_names.get(domain, '通用')}{type_names.get(ltype, '法则')}"

    def _auto_principle(self, domain: LawDomain, ltype: LawType, patterns: list) -> str:
        return f"基于{len(patterns)}条经验提炼的{domain.value}域{ltype.value}类法则"

    def _auto_steps(self, domain: LawDomain, ltype: LawType, patterns: list) -> list[str]:
        return [f"步骤{i+1}: 待完善" for i in range(min(3, len(patterns)))]

    def _auto_scenarios(self, patterns: list) -> list[str]:
        return ["待定义触发场景"]

    def _auto_consequences(self, domain: LawDomain, ltype: LawType) -> list[str]:
        return ["可能导致系统异常"]

    def _auto_enforcement(
        self, domain: LawDomain, ltype: LawType, priority: LawPriority
    ) -> list[str]:
        methods = []
        if priority in (LawPriority.P0_CRITICAL, LawPriority.P1_HIGH):
            methods.append("Gate门禁强制检测")
        methods.append("定期巡检")
        if ltype == LawType.PREVENTION:
            methods.append("代码审查规则")
        return methods

    def _register_law(self, law: EmpiricalLaw):
        self._index["laws"][law.law_id] = law.to_dict()
        law_file = self._law_dir / f"{law.law_id}.json"
        law_file.write_text(
            json.dumps(law.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )


class RuleLifecycleManager:
    """
    法则生命周期管理器 — 管理 DRAFT→VALIDATED→ACTIVE→DEPRECATED 流程

    状态转换规则:
    DRAFT     → VALIDATED: 人工审核通过 或 LLM自检通过
    VALIDATED → ACTIVE:     正式激活，开始计数activation_count
    ACTIVE    → DEPRECATED: 被新法则替代 或 不再适用
    ACTIVE    → SUPERSEDED: 被更高版本替代
    """

    def __init__(self, generator: LawGenerator):
        self._generator = generator
        self._stats = {
            "draft_validated": 0,
            "validated_activated": 0,
            "active_deprecated": 0,
            "active_superseded": 0,
        }

    def validate_law(self, law_id: str, validator: str = "auto") -> bool:
        """DRAFT → VALIDATED"""
        index = self._generator._index
        if law_id not in index["laws"]:
            return False
        law_data = index["laws"][law_id]
        law = EmpiricalLaw.from_dict(law_data)
        if law.status != LawStatus.DRAFT:
            return False
        law.status = LawStatus.VALIDATED
        law.validated_at = datetime.now().isoformat()
        law.meta["validator"] = validator
        index["laws"][law_id] = law.to_dict()
        self._generator._save_index()
        self._stats["draft_validated"] += 1
        logger.info(f"[法则生命周期] {law_id}: DRAFT→VALIDATED (by {validator})")
        return True

    def activate_law(self, law_id: str) -> bool:
        """DRAFT/VALIDATED → ACTIVE"""
        index = self._generator._index
        if law_id not in index["laws"]:
            return False
        law_data = index["laws"][law_id]
        law = EmpiricalLaw.from_dict(law_data)
        if law.status not in (LawStatus.DRAFT, LawStatus.VALIDATED):
            return False
        law.status = LawStatus.ACTIVE
        law.activated_at = datetime.now().isoformat()
        index["laws"][law_id] = law.to_dict()
        self._generator._save_index()
        self._stats["validated_activated"] += 1
        logger.info(f"[法则生命周期] {law_id}: {law.status.value}→ACTIVE")
        return True

    def deactivate_law(
        self, law_id: str, reason: str = "", superseded_by: str = ""
    ) -> bool:
        """ACTIVE → DEPRECATED/SUPERSEDED"""
        index = self._generator._index
        if law_id not in index["laws"]:
            return False
        law_data = index["laws"][law_id]
        law = EmpiricalLaw.from_dict(law_data)
        if law.status != LawStatus.ACTIVE:
            return False
        if superseded_by:
            law.status = LawStatus.SUPERSEDED
            law.meta["superseded_by"] = superseded_by
            self._stats["active_superseded"] += 1
        else:
            law.status = LawStatus.DEPRECATED
            self._stats["active_deprecated"] += 1
        law.meta["deactivation_reason"] = reason
        law.meta["deactivated_at"] = datetime.now().isoformat()
        index["laws"][law_id] = law.to_dict()
        self._generator._save_index()
        logger.info(f"[法则生命周期] {law_id}: ACTIVE→{law.status.value} ({reason})")
        return True

    def get_active_laws(
        self, domain: LawDomain | None = None, priority: LawPriority | None = None
    ) -> list[EmpiricalLaw]:
        """获取所有生效法则"""
        laws = []
        for lid, ldata in self._generator._index.get("laws", {}).items():
            law = EmpiricalLaw.from_dict(ldata)
            if law.status != LawStatus.ACTIVE:
                continue
            if domain and law.domain != domain:
                continue
            if priority and law.priority != priority:
                continue
            laws.append(law)
        return sorted(laws, key=lambda l: (l.priority.value, l.law_id))

    def get_stats(self) -> dict:
        return dict(self._stats)
