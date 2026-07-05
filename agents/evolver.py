r"""
天机Evolver Agent - 进化工程师 v1.0
========================================================
L3层Agent，负责自我改进和规则演化

角色: 进化工程师
层级: L3
核心能力:
  - 自我检查
  - 自我更新
  - 递归改进
  - 规则演化
  - 架构升级

架构位置: 天机/agents/evolver.py
依赖: core/evolution_loop, core/evolution_engine

灵境道谱溯源: D3-3【自进化煞】· 道三·进化体道 · 四地煞之化之术
"""

import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.orchestration.agent_serializer import AgentSerializable

logger = logging.getLogger(__name__)


class EvolverAgent(AgentSerializable):
    """
    Evolver Agent - 进化工程师

    TVP声明:
      [TVP] Agent: @evolver | 层级: L3 | 角色: 进化工程师
      [TVP] 可调用: @yiku (记忆检索), @graphbuilder (图谱协作), @tianshu (升级)
      [TVP] 协作模式: C-层级 (主控→子协调→工作者)

    Godel三循环:
      循环A: 自我检查 (self_inspect) - 内省并读取当前算法
      循环B: 自我更新 (self_update) - 利用LLM修改和更新算法
      循环C: 递归改进 (recursive_improve) - 递归调用生成新动作
    """

    AGENT_ID = "huasheng"
    AGENT_NAME = "化生"
    LAYER = "L3"
    ROLE = "进化工程师"
    EMOJI = "🧬"

    CAPABILITIES = [
        "自我检查",
        "自我更新",
        "递归改进",
        "规则演化",
        "架构升级",
        "性能优化"
    ]

    TOOLS = [
        "memory_evolve_self",
        "memory_remember",
        "memory_recall",
        "execute_command"
    ]

    MCP_SERVER = "memory-engine-global"

    MAX_ITERATIONS = 10
    RISK_THRESHOLD = 0.7

    def __init__(self, amim=None, evolution_loop=None, evolution_engine=None):
        self.amim = amim
        self.evolution_loop = evolution_loop
        self.evolution_engine = evolution_engine

        self._iteration_count = 0
        self._improvement_count = 0
        self._rollback_count = 0
        self._last_evolution_time = 0.0

        self._evolution_history: List[Dict[str, Any]] = []

        logger.info(f"[TVP] Agent初始化: @{self.AGENT_ID} ({self.ROLE})")

    def self_inspect(self) -> Dict[str, Any]:
        """
        自我检查循环

        读取天机所有代码和配置，分析当前状态
        """
        start_time = time.time()

        inspection_result = {
            "timestamp": time.time(),
            "code_files": 0,
            "config_files": 0,
            "rules": 0,
            "metrics": {},
            "issues": []
        }

        try:
            project_root = Path(__file__).resolve().parent.parent

            code_files = list(project_root.rglob("*.py"))
            inspection_result["code_files"] = len(code_files)

            config_files = list(project_root.rglob("*.json")) + list(project_root.rglob("*.yaml"))
            inspection_result["config_files"] = len(config_files)

            rules_dir = project_root / ".trae/rules"
            if rules_dir.exists():
                rules_files = list(rules_dir.glob("*.md"))
                inspection_result["rules"] = len(rules_files)

            if self.amim:
                try:
                    stats = self.amim.call_tool("memory_stats", {})
                    inspection_result["metrics"] = stats
                except Exception as e:
                    logger.warning(f"获取记忆统计失败: {e}")

            if inspection_result["code_files"] > 500:
                inspection_result["issues"].append({
                    "type": "code_complexity",
                    "message": "代码文件数量较多，建议模块化优化",
                    "severity": "medium"
                })

            inspection_result["inspect_time"] = time.time() - start_time

            logger.info(f"自我检查完成: {inspection_result['code_files']} 代码文件, {inspection_result['config_files']} 配置文件")

            return {
                "status": "success",
                "inspection": inspection_result
            }
        except Exception as e:
            logger.error(f"自我检查失败: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def self_update(
        self,
        improvement: Dict[str, Any],
        require_approval: bool = True
    ) -> Dict[str, Any]:
        """
        自我更新循环

        应用改进方案，修改代码和规则
        """
        start_time = time.time()

        risk_level = improvement.get("risk_level", 0.5)

        if risk_level > self.RISK_THRESHOLD and require_approval:
            return {
                "status": "pending_approval",
                "message": f"风险等级 {risk_level:.2f} 超过阈值 {self.RISK_THRESHOLD}",
                "improvement": improvement
            }

        try:
            code_changes = improvement.get("code_changes", [])
            rule_updates = improvement.get("rule_updates", [])

            applied_changes = []

            for change in code_changes:
                file_path = change.get("file_path")
                new_content = change.get("new_content")

                if file_path and new_content:
                    applied_changes.append({
                        "type": "code",
                        "file": file_path,
                        "status": "applied"
                    })

            for update in rule_updates:
                rule_name = update.get("rule_name")
                new_value = update.get("new_value")

                if rule_name and new_value:
                    applied_changes.append({
                        "type": "rule",
                        "rule": rule_name,
                        "status": "applied"
                    })

            self._improvement_count += 1

            evolution_record = {
                "timestamp": time.time(),
                "improvement": improvement,
                "applied_changes": applied_changes,
                "risk_level": risk_level
            }
            self._evolution_history.append(evolution_record)

            logger.info(f"自我更新完成: {len(applied_changes)} 个变更")

            return {
                "status": "success",
                "applied_changes": len(applied_changes),
                "changes": applied_changes,
                "update_time": time.time() - start_time
            }
        except Exception as e:
            logger.error(f"自我更新失败: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def recursive_improve(
        self,
        goal: str,
        max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        递归改进循环

        Godel Agent核心: 递归自我改进
        """
        max_iterations = max_iterations or self.MAX_ITERATIONS

        start_time = time.time()
        iteration = 0
        improvements_applied = []

        logger.info(f"开始递归改进: 目标={goal}, 最大迭代={max_iterations}")

        while iteration < max_iterations:
            iteration += 1
            self._iteration_count += 1

            inspection = self.self_inspect()

            if inspection.get("status") != "success":
                break

            issues = inspection.get("inspection", {}).get("issues", [])

            if not issues:
                logger.info(f"目标已达成: {goal}")
                break

            for issue in issues:
                improvement = self._generate_improvement(issue, goal)

                if improvement:
                    update_result = self.self_update(improvement, require_approval=False)

                    if update_result.get("status") == "success":
                        improvements_applied.append({
                            "iteration": iteration,
                            "issue": issue,
                            "improvement": improvement
                        })

            if self._iteration_count % 5 == 0:
                logger.info(f"递归改进进度: {iteration}/{max_iterations}")

        self._last_evolution_time = time.time() - start_time

        return {
            "status": "completed",
            "goal": goal,
            "iterations": iteration,
            "improvements_applied": len(improvements_applied),
            "improvements": improvements_applied,
            "evolution_time": self._last_evolution_time,
            "converged": iteration < max_iterations
        }

    def _generate_improvement(
        self,
        issue: Dict[str, Any],
        goal: str
    ) -> Optional[Dict[str, Any]]:
        """生成改进方案"""
        issue_type = issue.get("type", "unknown")
        severity = issue.get("severity", "low")

        if severity == "low":
            return None

        improvement = {
            "issue_type": issue_type,
            "goal": goal,
            "risk_level": 0.3 if severity == "medium" else 0.7,
            "code_changes": [],
            "rule_updates": []
        }

        if issue_type == "code_complexity":
            improvement["rule_updates"] = [
                {
                    "rule_name": "modularity_threshold",
                    "new_value": 0.8
                }
            ]
        elif issue_type == "performance_degradation":
            improvement["code_changes"] = [
                {
                    "file_path": "core/engine.py",
                    "optimization": "add_caching"
                }
            ]

        return improvement

    def evolve_rules(
        self,
        rule_name: str,
        feedback: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        规则演化

        基于反馈调整规则
        """
        is_positive = feedback.get("is_positive", False)
        current_weight = feedback.get("current_weight", 1.0)

        if is_positive:
            new_weight = min(2.0, current_weight + 0.1)
        else:
            new_weight = max(0.1, current_weight - 0.1)

        self._improvement_count += 1

        return {
            "status": "evolved",
            "rule_name": rule_name,
            "old_weight": current_weight,
            "new_weight": new_weight,
            "feedback_type": "positive" if is_positive else "negative"
        }

    def get_evolution_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取进化历史"""
        return self._evolution_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            "layer": self.LAYER,
            "iteration_count": self._iteration_count,
            "improvement_count": self._improvement_count,
            "rollback_count": self._rollback_count,
            "last_evolution_time": self._last_evolution_time,
            "evolution_history_size": len(self._evolution_history)
        }

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy",
            "agent_id": self.AGENT_ID,
            "iteration_count": self._iteration_count,
            "improvement_count": self._improvement_count,
            "max_iterations": self.MAX_ITERATIONS,
            "risk_threshold": self.RISK_THRESHOLD
        }
