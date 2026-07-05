"""
注册表对账器 (Registry Reconciler) v1.0
========================================
定期对比 SkillRegistry 和 CapabilityRegistry，发现技能与Agent能力的不匹配问题。

核心职责:
  1. 定义对账规则 — 技能分类与Agent能力的匹配关系
  2. 执行对账 — reconcile() 方法对比两个注册表
  3. 自动调度 — 每30分钟自动执行一次
  4. 异常记录 — 不匹配时记录日志并写入L3 Episodic层
  5. 修复建议 — 生成差异详情和建议修复方案

架构位置: 天机/core/shared/registry_reconciler.py
依赖:
  - core/shared/skill_registry.py (SkillRegistry)
  - core/orchestration/registry.py (CapabilityRegistry)
  - core/shared/mcp_bridge.py (_TOOL_CATEGORIES)
"""

import json
import logging
import threading
import time
from enum import Enum
from typing import Any

logger = logging.getLogger("tianji.registry_reconciler")


class ReconcileStatus(str, Enum):
    """对账状态枚举"""

    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    PARTIAL = "partial"


class DiffType(str, Enum):
    """差异类型枚举"""

    SKILL_WITHOUT_AGENT = "skill_without_agent"
    AGENT_WITHOUT_SKILL = "agent_without_skill"
    MISMATCHED_CAPABILITY = "mismatched_capability"
    MISSING_TOOL = "missing_tool"
    UNUSED_SKILL = "unused_skill"


class ReconcileDiff:
    """对账差异项"""

    def __init__(
        self,
        diff_type: DiffType,
        detail: str,
        skill_name: str = "",
        agent_id: str = "",
        severity: str = "medium",
        suggestion: str = "",
    ):
        self.diff_type = diff_type
        self.detail = detail
        self.skill_name = skill_name
        self.agent_id = agent_id
        self.severity = severity
        self.suggestion = suggestion
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_type": self.diff_type.value,
            "detail": self.detail,
            "skill_name": self.skill_name,
            "agent_id": self.agent_id,
            "severity": self.severity,
            "suggestion": self.suggestion,
            "timestamp": self.timestamp,
        }


# 技能分类与Agent能力的匹配规则
# SkillCategory → Agent能力关键词映射
SKILL_CAPABILITY_MAPPING: dict[str, list[str]] = {
    "memory": ["记忆", "存储", "检索", "巩固", "ICME", "语义检索"],
    "corpus": ["语料", "数据", "统计", "分析", "导入", "清洗", "标注"],
    "novel": ["创作", "写作", "创意", "角色", "世界观", "审校"],
    "system": ["系统", "监控", "部署", "运维", "安全", "性能", "规则"],
    "context": ["上下文", "意图", "实体", "情感", "分析", "识别"],
    "export": ["导出", "格式", "美化", "模板", "输出"],
}

# 工具分类与技能分类的匹配规则
TOOL_CATEGORY_SKILL_MAPPING: dict[str, list[str]] = {
    "memory_ops": ["memory"],
    "search": ["memory", "corpus"],
    "llm_intel": ["context", "novel"],
    "knowledge_graph": ["memory", "corpus"],
    "context": ["context"],
    "system": ["system"],
    "conversation": ["context"],
    "export": ["export"],
    "agent": ["system"],
    "advanced_memory": ["memory"],
    "command": ["system"],
    "ops": ["system"],
    "security": ["system"],
    "performance": ["system"],
}


class RegistryReconciler:
    """
    注册表对账器 — 定期对比SkillRegistry和CapabilityRegistry

    对账规则:
      1. Skill的required_agents必须在CapabilityRegistry中存在
      2. Agent的capabilities必须覆盖其关联的SkillCategory
      3. Agent的tools必须支持其关联的SkillCategory所需的工具分类
      4. Skill的required_mcp_servers必须对应到Agent的tools

    自动调度:
      - 默认每30分钟执行一次对账
      - 可通过start()/stop()控制调度
    """

    DEFAULT_INTERVAL = 30 * 60

    def __init__(
        self,
        skill_registry: Any | None = None,
        capability_registry: Any | None = None,
        memory_api_url: str = "http://127.0.0.1:8771",
        interval: float = DEFAULT_INTERVAL,
    ):
        self._skill_registry = skill_registry
        self._capability_registry = capability_registry
        self._memory_api_url = memory_api_url
        self._interval = interval
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._running = False
        self._last_reconcile_time = 0.0
        self._stats = {
            "total_reconciles": 0,
            "total_diffs": 0,
            "consistent_count": 0,
            "inconsistent_count": 0,
            "partial_count": 0,
            "last_reconcile_result": None,
        }

    @property
    def running(self) -> bool:
        return self._running

    def _ensure_registries(self):
        """延迟加载注册表实例"""
        if self._skill_registry is None:
            from .skill_registry import SkillRegistry

            self._skill_registry = SkillRegistry()

        if self._capability_registry is None:
            from ..orchestration.registry import CapabilityRegistry

            self._capability_registry = CapabilityRegistry()

    def start(self):
        """启动自动对账调度"""
        with self._lock:
            if self._running:
                logger.info("[RegistryReconciler] 已在运行中")
                return
            self._running = True

        logger.info(
            f"[RegistryReconciler] 启动自动对账调度 (间隔: {self._interval / 60:.0f}分钟)"
        )
        self._schedule_next()

    def stop(self):
        """停止自动对账调度"""
        with self._lock:
            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None

        logger.info("[RegistryReconciler] 已停止自动对账调度")

    def _schedule_next(self):
        """调度下一次对账"""
        if not self._running:
            return

        self._timer = threading.Timer(self._interval, self._run_reconcile)
        self._timer.daemon = True
        self._timer.start()

    def _run_reconcile(self):
        """内部执行对账并调度下一次"""
        try:
            self.reconcile()
        except Exception as e:
            logger.error(f"[RegistryReconciler] 自动对账执行失败: {e}")
        finally:
            self._schedule_next()

    def reconcile(self) -> dict[str, Any]:
        """
        执行对账 — 对比SkillRegistry和CapabilityRegistry

        Returns:
            对账结果字典，包含状态、差异列表和建议
        """
        self._ensure_registries()

        with self._lock:
            self._stats["total_reconciles"] += 1
            self._last_reconcile_time = time.time()

        logger.info("[RegistryReconciler] 开始执行对账")

        diffs: list[ReconcileDiff] = []

        diffs.extend(self._check_skill_agent_existence())
        diffs.extend(self._check_capability_coverage())
        diffs.extend(self._check_tool_support())
        diffs.extend(self._check_mcp_server_mapping())
        diffs.extend(self._check_unused_skills())

        result = self._build_result(diffs)

        if diffs:
            logger.warning(f"[RegistryReconciler] 对账发现 {len(diffs)} 个差异")
            self._log_diffs(diffs)
            self._write_to_episodic(result)
        else:
            logger.info("[RegistryReconciler] 对账完成，状态一致")

        with self._lock:
            self._stats["total_diffs"] += len(diffs)
            status = result.get("status", "")
            if status == ReconcileStatus.CONSISTENT.value:
                self._stats["consistent_count"] += 1
            elif status == ReconcileStatus.INCONSISTENT.value:
                self._stats["inconsistent_count"] += 1
            else:
                self._stats["partial_count"] += 1
            self._stats["last_reconcile_result"] = result

        return result

    def _check_skill_agent_existence(self) -> list[ReconcileDiff]:
        """检查1: Skill的required_agents是否在CapabilityRegistry中存在"""
        diffs = []
        skills = self._skill_registry.list_skills()
        agent_ids = set(self._capability_registry.list_agents())

        for skill in skills:
            for agent_id in skill.required_agents:
                if agent_id not in agent_ids:
                    diffs.append(
                        ReconcileDiff(
                            diff_type=DiffType.SKILL_WITHOUT_AGENT,
                            detail=f"Skill '{skill.name}' 依赖的Agent '{agent_id}' 不存在于CapabilityRegistry",
                            skill_name=skill.name,
                            agent_id=agent_id,
                            severity="high",
                            suggestion=f"请在CapabilityRegistry中注册Agent '{agent_id}'，或从Skill的required_agents中移除",
                        )
                    )

        return diffs

    def _check_capability_coverage(self) -> list[ReconcileDiff]:
        """检查2: Agent的capabilities是否覆盖其关联的SkillCategory"""
        diffs = []
        from .skill_registry import AGENT_SKILL_MAP

        for agent_id, allowed_categories in AGENT_SKILL_MAP.items():
            if not self._capability_registry.exists(agent_id):
                continue

            agent_capabilities = set(
                self._capability_registry.get_capabilities(agent_id)
            )

            for category in allowed_categories:
                expected_keywords = SKILL_CAPABILITY_MAPPING.get(category.value, [])
                if not expected_keywords:
                    continue

                matched = False
                for keyword in expected_keywords:
                    if any(keyword in cap for cap in agent_capabilities):
                        matched = True
                        break

                if not matched:
                    diffs.append(
                        ReconcileDiff(
                            diff_type=DiffType.MISMATCHED_CAPABILITY,
                            detail=f"Agent '{agent_id}' 的能力未覆盖Skill分类 '{category.value}' 的预期能力关键词: {expected_keywords}",
                            skill_name=category.value,
                            agent_id=agent_id,
                            severity="medium",
                            suggestion=f"请为Agent '{agent_id}' 添加包含以下关键词之一的能力: {expected_keywords}",
                        )
                    )

        return diffs

    def _check_tool_support(self) -> list[ReconcileDiff]:
        """检查3: Agent的tools是否支持其关联的SkillCategory所需的工具分类"""
        diffs = []
        from .mcp_bridge import _TOOL_CATEGORIES
        from .skill_registry import AGENT_SKILL_MAP

        for agent_id, allowed_categories in AGENT_SKILL_MAP.items():
            if not self._capability_registry.exists(agent_id):
                continue

            agent_tools = set(self._capability_registry.get_tools(agent_id))

            for category in allowed_categories:
                required_tool_categories = TOOL_CATEGORY_SKILL_MAPPING.get(
                    category.value, []
                )
                if not required_tool_categories:
                    continue

                missing_tools = []
                for tool_category in required_tool_categories:
                    tools_in_category = _TOOL_CATEGORIES.get(tool_category, [])
                    if tools_in_category and not agent_tools.intersection(
                        tools_in_category
                    ):
                        missing_tools.append(f"{tool_category} ({tools_in_category})")

                if missing_tools:
                    diffs.append(
                        ReconcileDiff(
                            diff_type=DiffType.MISSING_TOOL,
                            detail=f"Agent '{agent_id}' 的工具未覆盖Skill分类 '{category.value}' 所需的工具分类: {missing_tools}",
                            skill_name=category.value,
                            agent_id=agent_id,
                            severity="medium",
                            suggestion=f"请为Agent '{agent_id}' 添加以下工具分类中的至少一个工具: {missing_tools}",
                        )
                    )

        return diffs

    def _check_mcp_server_mapping(self) -> list[ReconcileDiff]:
        """检查4: Skill的required_mcp_servers是否能映射到Agent的tools"""
        diffs = []
        from .mcp_bridge import _EXTERNAL_TOOL_SERVER

        skills = self._skill_registry.list_skills()

        for skill in skills:
            for mcp_server in skill.required_mcp_servers:
                tools_for_server = [
                    tool
                    for tool, server in _EXTERNAL_TOOL_SERVER.items()
                    if server == mcp_server
                ]

                if not tools_for_server:
                    diffs.append(
                        ReconcileDiff(
                            diff_type=DiffType.MISSING_TOOL,
                            detail=f"Skill '{skill.name}' 依赖的MCP Server '{mcp_server}' 没有对应的工具定义",
                            skill_name=skill.name,
                            severity="high",
                            suggestion=f"请在mcp_bridge.py中为MCP Server '{mcp_server}' 注册工具定义",
                        )
                    )
                    continue

                if skill.required_agents:
                    for agent_id in skill.required_agents:
                        if not self._capability_registry.exists(agent_id):
                            continue

                        agent_tools = set(self._capability_registry.get_tools(agent_id))
                        if not agent_tools.intersection(tools_for_server):
                            diffs.append(
                                ReconcileDiff(
                                    diff_type=DiffType.MISSING_TOOL,
                                    detail=f"Agent '{agent_id}' 缺少Skill '{skill.name}' 依赖的MCP Server '{mcp_server}' 的工具: {tools_for_server}",
                                    skill_name=skill.name,
                                    agent_id=agent_id,
                                    severity="medium",
                                    suggestion=f"请为Agent '{agent_id}' 添加以下工具之一: {tools_for_server}",
                                )
                            )

        return diffs

    def _check_unused_skills(self) -> list[ReconcileDiff]:
        """检查5: 检测长期未使用的Skill"""
        diffs = []
        threshold_hours = 24 * 7

        for skill in self._skill_registry.list_skills():
            if skill.access_count == 0:
                age_hours = (time.time() - skill.registered_at) / 3600
                if age_hours > threshold_hours:
                    diffs.append(
                        ReconcileDiff(
                            diff_type=DiffType.UNUSED_SKILL,
                            detail=f"Skill '{skill.name}' 注册后从未被访问 (已存在 {age_hours:.0f} 小时)",
                            skill_name=skill.name,
                            severity="low",
                            suggestion=f"检查Skill '{skill.name}' 是否被正确集成到Agent的技能列表中，或考虑标记为DEPRECATED",
                        )
                    )

        return diffs

    def _build_result(self, diffs: list[ReconcileDiff]) -> dict[str, Any]:
        """构建对账结果"""
        if not diffs:
            status = ReconcileStatus.CONSISTENT
        elif all(d.severity == "low" for d in diffs):
            status = ReconcileStatus.PARTIAL
        else:
            status = ReconcileStatus.INCONSISTENT

        summary = {
            "total_skills": len(self._skill_registry.list_skills()),
            "total_agents": len(self._capability_registry.list_agents()),
            "total_compositions": len(self._skill_registry.list_compositions()),
        }

        grouped_diffs: dict[str, list[dict]] = {}
        for diff in diffs:
            key = diff.diff_type.value
            if key not in grouped_diffs:
                grouped_diffs[key] = []
            grouped_diffs[key].append(diff.to_dict())

        suggestions = []
        if grouped_diffs.get(DiffType.SKILL_WITHOUT_AGENT.value):
            suggestions.append("检查Skill的required_agents配置，确保引用的Agent存在")
        if grouped_diffs.get(DiffType.MISMATCHED_CAPABILITY.value):
            suggestions.append("为Agent添加缺失的能力描述")
        if grouped_diffs.get(DiffType.MISSING_TOOL.value):
            suggestions.append("为Agent添加必要的工具授权")
        if grouped_diffs.get(DiffType.UNUSED_SKILL.value):
            suggestions.append("检查未使用Skill的集成情况或考虑废弃")

        return {
            "status": status.value,
            "reconcile_time": time.time(),
            "diffs_count": len(diffs),
            "diffs": [d.to_dict() for d in diffs],
            "grouped_diffs": grouped_diffs,
            "summary": summary,
            "suggestions": suggestions,
        }

    def _log_diffs(self, diffs: list[ReconcileDiff]):
        """记录差异到日志"""
        for diff in diffs:
            log_func = (
                logger.error
                if diff.severity == "high"
                else logger.warning
                if diff.severity == "medium"
                else logger.info
            )
            log_func(f"[RegistryReconciler] [{diff.severity.upper()}] {diff.detail}")

    def _write_to_episodic(self, result: dict[str, Any]):
        """将对账结果写入L3 Episodic层"""
        if result["status"] == ReconcileStatus.CONSISTENT.value:
            return

        try:
            import urllib.request

            content = json.dumps(
                {
                    "type": "registry_reconcile_result",
                    "status": result["status"],
                    "reconcile_time": result["reconcile_time"],
                    "diffs_count": result["diffs_count"],
                    "summary": result["summary"],
                    "grouped_diffs": result["grouped_diffs"],
                    "suggestions": result["suggestions"],
                },
                ensure_ascii=False,
                indent=2,
            )

            data = json.dumps(
                {
                    "content": content,
                    "layer": "episodic",
                    "tags": [
                        "registry_reconcile",
                        "system_maintenance",
                        result["status"],
                    ],
                    "priority": "high"
                    if result["status"] == "inconsistent"
                    else "medium",
                },
                ensure_ascii=False,
            ).encode("utf-8")

            req = urllib.request.Request(
                f"{self._memory_api_url}/api/memory/",
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            r = urllib.request.urlopen(req, timeout=5)
            if r.status in (200, 201):
                logger.info("[RegistryReconciler] 对账结果已写入L3 Episodic层")
        except Exception as e:
            logger.error(f"[RegistryReconciler] 写入L3 Episodic层失败: {e}")

    def get_stats(self) -> dict[str, Any]:
        """获取对账统计信息"""
        with self._lock:
            return {
                **self._stats,
                "running": self._running,
                "interval_seconds": self._interval,
                "last_reconcile_time": self._last_reconcile_time,
            }

    def get_last_result(self) -> dict[str, Any] | None:
        """获取上次对账结果"""
        with self._lock:
            return self._stats.get("last_reconcile_result")


# 全局单例
_reconciler_instance: RegistryReconciler | None = None


def get_registry_reconciler() -> RegistryReconciler:
    """获取全局RegistryReconciler单例"""
    global _reconciler_instance
    if _reconciler_instance is None:
        _reconciler_instance = RegistryReconciler()
    return _reconciler_instance


def start_reconciler():
    """启动全局对账器"""
    reconciler = get_registry_reconciler()
    reconciler.start()
    return reconciler


def stop_reconciler():
    """停止全局对账器"""
    reconciler = get_registry_reconciler()
    reconciler.stop()
    return reconciler


def run_one_reconcile() -> dict[str, Any]:
    """执行单次对账（不启动定时调度）"""
    reconciler = get_registry_reconciler()
    return reconciler.reconcile()
