# -*- coding: utf-8 -*-
"""
经验法则领域主引擎 — 统一入口
[SSS-PhaseB] 从engine.py拆分，保留核心引擎+执行器

Usage:
    engine = LawDomainEngine()

    # 全量挖掘
    report = engine.full_mining_report()

    # 快速挖掘(单条输入)
    laws = engine.quick_mine("托盘重启后新进程无法启动...")

    # 获取所有生效法则
    active = engine.get_all_active_laws()

    # 强制执行所有P0法则
    result = engine.enforce_p0_laws()
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("tianji.law_domain")

from .core import (
    EmpiricalLaw,
    LawDomain,
    LawPriority,
    LawStatus,
    _LAW_DIR,
)
from .miner import ExperienceMiner
from .generator import LawGenerator, RuleLifecycleManager
from .bridges import LearningBridge, EvolutionBridge


class LawEnforcer:
    """法则执行器基类 — 提供检测脚本生成能力"""

    SCRIPT_TEMPLATES: dict[str, str] = {}

    def __init__(self, law_domain):
        self._domain = law_domain

    def generate_enforcement_script(self, law: EmpiricalLaw) -> str | None:
        """为单个法则生成检测脚本"""
        domain_key = law.domain.value
        type_key = law.law_type.value

        template_key = "generic"
        if domain_key == "path" and type_key == "prevention":
            template_key = "path_audit"
        elif domain_key == "process" and type_key in ("recovery", "prevention"):
            template_key = "process_check"

        template = self.SCRIPT_TEMPLATES.get(template_key, self.SCRIPT_TEMPLATES.get("generic"))
        if not template:
            return None

        return template.format(
            law_id=law.law_id,
            title=law.title,
            domain=law.domain.value,
            law_type=law.law_type.value,
            priority=law.priority.value,
            principle=law.principle,
            steps=json.dumps(law.steps, ensure_ascii=False),
            trigger_scenarios=json.dumps(law.trigger_scenarios, ensure_ascii=False),
            enforcement_methods=json.dumps(law.enforcement_methods, ensure_ascii=False),
            timestamp=datetime.now().isoformat(),
            class_name=f"Law{law.law_id.replace('-', '_')}",
        )

    def batch_generate_scripts(self, output_dir: Path | None = None) -> list[Path]:
        """批量生成所有活跃法则的检测脚本"""
        active_laws = self._domain.lifecycle_manager.get_active_laws()
        out_dir = output_dir or (_LAW_DIR / "enforcement_scripts")
        out_dir.mkdir(parents=True, exist_ok=True)

        generated = []
        for law in active_laws:
            script = self.generate_enforcement_script(law)
            if script:
                script_path = out_dir / f"{law.law_id}.py"
                script_path.write_text(script, encoding="utf-8")
                generated.append(script_path)

        logger.info(f"[法则执行器] 生成 {len(generated)} 个检测脚本 → {out_dir}")
        return generated


class LawDomainEngine:
    """
    经验法则领域主引擎 — 统一入口

    组合子系统: ExperienceMiner + LawGenerator + RuleLifecycleManager + LearningBridge + EvolutionBridge
    """

    VERSION = "2.0.0"

    def __init__(self, memory_api_url: str = "http://127.0.0.1:8771"):
        self._api_url = memory_api_url
        self.miner = ExperienceMiner(memory_api_url)
        self.generator = LawGenerator()
        self.lifecycle_manager = RuleLifecycleManager(self.generator)
        self.learning_bridge = LearningBridge(self)
        self.evolution_bridge = EvolutionBridge(self)
        self.enforcer = LawEnforcer(self)
        self._lock = threading.Lock()

    def full_mining_report(self) -> dict:
        """全量挖掘报告"""
        with self._lock:
            patterns = self.miner._patterns
            laws = list(self.generator._index.get("laws", {}).values())
            active = [l for l in laws if l.get("status") == "active"]
            return {
                "timestamp": datetime.now().isoformat(),
                "engine_version": self.VERSION,
                "experience_patterns_found": len(patterns),
                "high_freq_patterns": sum(1 for p in patterns if p.frequency >= 2),
                "total_laws": len(laws),
                "active_laws": len(active),
                "draft_laws": sum(1 for l in laws if l.get("status") == "draft"),
                "miner_stats": self.miner._stats,
                "generator_stats": self.generator._stats,
                "lifecycle_stats": self.lifecycle_manager._stats,
                "learning_bridge_stats": self.learning_bridge._stats,
                "evolution_bridge_stats": self.evolution_bridge._stats,
            }

    def quick_mine(
        self, text: str, domain_hint: LawDomain = None
    ) -> list[EmpiricalLaw]:
        """快速挖掘(单条文本输入)"""
        fake_memories = [{"content": text, "id": "quick-mine", "layer": "episodic"}]
        patterns = self.miner.mine_from_memory_contents(fake_memories)
        if domain_hint:
            for p in patterns:
                p.domain_hint = domain_hint
        laws = self.generator.generate_from_patterns(patterns, use_llm=False)
        return laws

    def get_all_active_laws(self) -> list[EmpiricalLaw]:
        return self.lifecycle_manager.get_active_laws()

    def get_law_by_id(self, law_id: str) -> EmpiricalLaw | None:
        data = self.generator._index.get("laws", {}).get(law_id)
        if data:
            return EmpiricalLaw.from_dict(data)
        return None

    def enforce_p0_laws(self) -> dict:
        """强制执行所有P0法则"""
        p0_laws = self.lifecycle_manager.get_active_laws(
            priority=LawPriority.P0_CRITICAL
        )
        results = {"total_p0": len(p0_laws), "enforced": 0, "details": []}
        for law in p0_laws:
            detail = {
                "law_id": law.law_id,
                "title": law.title,
                "enforcement_methods": law.enforcement_methods,
                "status": "registered",
            }
            results["details"].append(detail)
            results["enforced"] += 1
        return results

    def export_law_report(self, output_path: Path | None = None) -> Path:
        """导出法则报告"""
        report = self.full_mining_report()
        report["active_laws_detail"] = [
            law.to_dict() for law in self.get_all_active_laws()
        ]
        out = output_path or (
            _LAW_DIR / f"law_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return out

    def get_stats(self) -> dict:
        return self.full_mining_report()

    # --- 学习闭环快捷入口 ---

    def on_task_completed(
        self,
        task_id: str,
        agent_id: str,
        task_description: str,
        complexity_str: str = "normal",
        success: bool = True,
        error_info: str = "",
        duration_ms: float = 0,
    ) -> list[EmpiricalLaw] | None:
        """任务完成时自动触发学习闭环 (完整五阶段)"""
        task_key = self.learning_bridge.on_execute_phase(task_id, agent_id, task_description)
        return self.learning_bridge.on_evaluate_phase(
            task_key, complexity_str, success, error_info, duration_ms
        )

    def run_reflect_cycle(self, cycle_id: str = "") -> dict:
        """执行反思周期"""
        # 先执行CONSOLIDATE阶段
        self.learning_bridge.on_consolidate_phase()
        # 再执行REFLECT阶段
        return self.learning_bridge.on_reflect_phase(cycle_id)

    # --- 进化闭环快捷入口 ---

    def run_evolution_cycle(self, evolution_data: dict = None) -> dict:
        """执行进化审查周期"""
        return self.evolution_bridge.on_evolution_cycle(evolution_data)
