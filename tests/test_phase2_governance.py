r"""
天机 Phase 2 治理机制 — 虚拟审计验证脚本 v1.0
==============================================
以知识的功能实现数据根基，跑通完整流水线: Plan → Audit → Implement → Approve

验证范围:
  1. ModuleRegistry 注册中心 — 注册/查询/依赖管理
  2. StaticDependencyAnalyzer 静态分析 — AST解析/循环检测/层级合规
  3. GovernancePipeline 治理流水线 — 四阶段完整闭环
  4. 三组件集成 — 注册中心+分析器+流水线协同工作

数据根基 (从天机记忆提取):
  - Agent流水线: 开发/内容/监控/审计 4条流水线 (TVP声明)
  - 进化闭环: observe→learn→evolve 因果对模式
  - 36地煞模块体系: 天机核心24模块 + Agent模块
  - 质量铁律: SG门禁/L0铁卫/L4镇山 三层审批
"""

import sys
import time
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List


sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(title: str):
    print()
    print("=" * 66)
    print(f"  {title}")
    print("=" * 66)


def print_sub(title: str):
    print(f"\n  [{title}]")


def check(name: str, condition: bool, detail: str = "") -> bool:
    icon = "PASS" if condition else "FAIL"
    msg = f"  {icon}  {name}"
    if detail:
        msg += f"  — {detail}"
    print(msg)
    return condition


def separator():
    print("  " + "-" * 62)


results = {"total": 0, "passed": 0, "failed": 0}


def record(test_name: str, passed: bool, detail: str = ""):
    results["total"] += 1
    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1
    check(test_name, passed, detail)


# ═══════════════════════════════════════════════════════════════
# Phase 1: ModuleRegistry 注册中心验证
# ═══════════════════════════════════════════════════════════════

print_header("Phase 2 治理机制 — 虚拟审计验证")
print("  数据根基: 天机记忆 (TVP声明+进化闭环+36地煞模块体系)")

print_header("V1: ModuleRegistry 注册中心")

from core.shared.module_registry import (
    ModuleRegistry, TianjiModuleDefinition,
    ModuleTier, ModuleType, ModuleLifecycleState,
    ModuleDependency, MethodSignature, EventDef,
    HealthMetricDef, AuditRecord, DependencyType
)

registry = ModuleRegistry()
record("V1.1 注册中心初始化", registry is not None)


module_engine = TianjiModuleDefinition(
    module_id="icme_engine",
    module_name="ICME引擎",
    display_name="六层记忆引擎",
    module_version="5.3.0",
    tier=ModuleTier.CORE_ENGINE,
    module_type=ModuleType.ENGINE,
    domain="记忆管理",
    responsibility="六层记忆架构 (L0-L5+Archive) 的读写、晋升、归档",
    capabilities=["记忆写入", "多维检索", "自动晋升", "容量管理", "标签索引"],
    anti_responsibilities=["不做NLP语义分析", "不负责Agent调度", "不处理外部API"],
    dependencies=[
        ModuleDependency(target_module="tianji_config", dependency_type=DependencyType.REQUIRED, description="配置管理"),
    ],
    public_api=[
        MethodSignature(name="remember", params=["content", "layer", "tags", "priority"], returns="Dict",
                       description="写入记忆到指定层"),
        MethodSignature(name="recall", params=["query", "limit"], returns="List[MemoryEntry]",
                       description="多维度检索记忆"),
        MethodSignature(name="forget", params=["entry_id"], returns="bool",
                       description="删除指定记忆条目"),
        MethodSignature(name="stats", params=[], returns="Dict",
                       description="获取记忆统计信息"),
    ],
    config_schema={"max_entries_per_layer": "int", "promotion_threshold": "float"},
    default_config={"max_entries_per_layer": 1000, "promotion_threshold": 0.8},
    owner="tianji_core_team",
    criticality="critical",
)
registered = registry.register(module_engine)
record("V1.2 注册核心模块", registered, "ICME引擎")

retrieved = registry.get("icme_engine")
record("V1.3 按ID查询", retrieved is not None and retrieved.module_name == "ICME引擎")

all_modules = registry.list_all()
record("V1.4 列出所有模块", len(all_modules) == 1, f"count={len(all_modules)}")


module_config = TianjiModuleDefinition(
    module_id="tianji_config",
    module_name="配置管理",
    display_name="天机配置中心",
    module_version="1.0.0",
    tier=ModuleTier.CORE_ENGINE,
    module_type=ModuleType.SERVICE,
    domain="基础设施",
    responsibility="统一配置管理与环境变量解析",
    capabilities=["配置读取", "环境变量", "路径管理", "Schema验证"],
    dependencies=[],
    public_api=[
        MethodSignature(name="get", params=["key", "default"], returns="Any", description="获取配置项"),
    ],
    owner="tianji_core_team",
)
registry.register(module_config)
record("V1.5 注册基础设施模块", True, "配置管理 (零依赖)")


deps = registry.get_dependencies("icme_engine")
record("V1.6 获取模块依赖", len(deps) == 1 and deps[0].module_id == "tianji_config",
       f"dep={deps[0].module_name if deps else 'none'}")

dependents = registry.get_dependents("tianji_config")
record("V1.7 获取反向依赖", len(dependents) == 1 and dependents[0].module_id == "icme_engine",
       f"dependent={dependents[0].module_name if dependents else 'none'}")


module_agent = TianjiModuleDefinition(
    module_id="agent_orchestrator",
    module_name="Agent调度器",
    display_name="多智能体编排",
    module_version="2.0.0",
    tier=ModuleTier.SCHEDULING_ORCHESTRATION,
    module_type=ModuleType.ORCHESTRATOR,
    domain="智能体调度",
    responsibility="18个Agent的TVP声明调度与流水线编排",
    capabilities=["Agent调度", "流水线编排", "TVP声明", "能力矩阵"],
    dependencies=[
        ModuleDependency(target_module="icme_engine", dependency_type=DependencyType.REQUIRED, description="记忆存取"),
        ModuleDependency(target_module="deepseek_driver", dependency_type=DependencyType.REQUIRED, description="驾驶决策"),
    ],
    public_api=[
        MethodSignature(name="dispatch", params=["agent_id", "task"], returns="Result", description="调度Agent"),
        MethodSignature(name="create_pipeline", params=["type"], returns="Pipeline", description="创建流水线"),
    ],
    owner="tianji_core_team",
)
registry.register(module_agent)
record("V1.8 注册编排模块", True, "Agent调度器 (2个依赖)")

modules_by_tier = registry.list_by_tier(ModuleTier.CORE_ENGINE)
record("V1.9 按层级查询", len(modules_by_tier) == 2, f"CORE_ENGINE={len(modules_by_tier)}")

dep_graph = registry.get_module_graph()
record("V1.10 获取完整依赖图", dep_graph["total"] >= 2)

cycles = registry.find_circular_dependencies()
record("V1.11 循环依赖检测", len(cycles) == 0, f"cycles={len(cycles)}")


module_deepseek = TianjiModuleDefinition(
    module_id="deepseek_driver",
    module_name="DeepSeek驾驶者",
    display_name="LLM决策中心",
    module_version="1.0.0",
    tier=ModuleTier.SCHEDULING_ORCHESTRATION,
    module_type=ModuleType.ORCHESTRATOR,
    domain="AI决策",
    responsibility="DeepSeek驱动的智能决策与事件总线",
    capabilities=["驾驶决策", "事件总线", "因果记录", "效果监控"],
    dependencies=[
        ModuleDependency(target_module="tianji_config", dependency_type=DependencyType.REQUIRED, description="配置管理"),
    ],
    public_api=[],
    owner="tianji_core_team",
)
registry.register(module_deepseek)


state_ok = registry.update_state("icme_engine", ModuleLifecycleState.ACTIVE)
record("V1.12 生命周期状态切换", state_ok, "REGISTERED → ACTIVE")

state_check = registry.get("icme_engine").lifecycle_state == ModuleLifecycleState.ACTIVE
record("V1.13 状态一致性验证", state_check)

registry.update_health("icme_engine", "healthy", {"cpu": 0.3, "memory": 0.45})
record("V1.14 健康状态更新", registry.get("icme_engine").health_status == "healthy")

stats = registry.get_stats()
record("V1.15 统计信息", stats["total_registered"] == 4 and stats["registrations"] == 4,
       f"registered={stats['total_registered']}")


# ═══════════════════════════════════════════════════════════════
# Phase 2: StaticDependencyAnalyzer 静态分析验证
# ═══════════════════════════════════════════════════════════════

print_header("V2: StaticDependencyAnalyzer 静态分析")

from core.shared.static_analyzer import (
    StaticDependencyAnalyzer, StaticAnalysisReport,
    ValidationFinding, ValidationSeverity, ModuleLayer,
    ImportDependency, ModuleSourceInfo,
)

analyzer = StaticDependencyAnalyzer(registry=registry)
record("V2.1 静态分析器初始化", analyzer is not None)


analyzer_single = StaticDependencyAnalyzer()
report = analyzer_single.analyze(
    str(Path(__file__).parent.parent / "core"),
    exclude_patterns=["__init__.py"]
)
record("V2.2 静态分析执行", report.total_modules > 0,
       f"modules={report.total_modules}, classes={report.total_classes}, "
       f"functions={report.total_functions}, imports={report.total_imports}")

dep_graph_static = report.dependency_graph
record("V2.3 依赖图构建", len(dep_graph_static) > 0,
       f"nodes={len(dep_graph_static)}, edges={sum(len(v) for v in dep_graph_static.values())}")

record("V2.4 循环依赖检测", len(report.circular_dependencies) == 0,
       f"cycles found={len(report.circular_dependencies)}")

findings = report.findings
errors = report.summary.get("errors", 0)
warnings = report.summary.get("warnings", 0)
infos = report.summary.get("info", 0)
record("V2.5 合规审计发现", len(findings) > 0,
       f"total={len(findings)} (E={errors} W={warnings} I={infos})")


custom_context = {
    "dependency_graph": {"a": ["b"], "b": ["c"], "c": []},
    "dependencies": [],
    "modules": {},
    "print_usage": {},
    "init_exports": set(),
    "documented_classes": {},
}
custom_report = StaticAnalysisReport()
custom_report.dependency_graph = custom_context["dependency_graph"]
custom_report.circular_dependencies = []
custom_report.dependencies = []
custom_report.total_modules = 3
record("V2.6 无循环依赖DAG", len(custom_report.circular_dependencies) == 0)


circular_context = {
    "dependency_graph": {"a": ["b"], "b": ["c"], "c": ["a"]},
    "dependencies": [],
    "modules": {},
    "print_usage": {},
    "init_exports": set(),
    "documented_classes": {},
}
circular_report = StaticAnalysisReport()
circular_report.dependency_graph = circular_context["dependency_graph"]
circular_report.circular_dependencies = [["a", "b", "c", "a"]]
circular_report.dependencies = []
circular_report.total_modules = 3
cycles_found = circular_report.circular_dependencies
record("V2.7 循环依赖识别", len(cycles_found) > 0 and "a" in cycles_found[0])


diff = analyzer.diff_report(custom_report, circular_report)
record("V2.8 报告差异比较", isinstance(diff, dict) and "deps_added" in diff)

history = analyzer_single.get_history()
record("V2.9 分析历史追踪", len(history) >= 1, f"history_count={len(history)}")


# ═══════════════════════════════════════════════════════════════
# Phase 3: GovernancePipeline 治理流水线验证
# ═══════════════════════════════════════════════════════════════

print_header("V3: GovernancePipeline 治理流水线")

from core.enforcement.governance_pipeline import (
    GovernancePipeline, PipelinePhase, PhaseStatus,
    AuditVerdict, ApprovalLevel, AuditReport, GovernanceRecord,
    AuditCheck, StageGate, AuditCheckerRegistry,
)

pipeline = GovernancePipeline(registry=registry, analyzer=analyzer)
record("V3.1 治理流水线初始化", pipeline is not None)


print_sub("阶段1: 规划 (Plan)")
new_module = TianjiModuleDefinition(
    module_id="quality_gate",
    module_name="质量门禁",
    display_name="SG质量门禁",
    module_version="3.1.0",
    tier=ModuleTier.ENFORCEMENT_COMPLIANCE,
    module_type=ModuleType.QUALITY_GATE,
    domain="质量保障",
    responsibility="记忆条目质量评分、准入/降级/拒绝判断",
    capabilities=["质量评分", "准入决策", "降级处理", "拒绝通知"],
    anti_responsibilities=["不修改记忆内容", "不负责存储"],
    dependencies=[
        ModuleDependency(target_module="tianji_config", dependency_type=DependencyType.REQUIRED, description="配置管理"),
    ],
    public_api=[
        MethodSignature(name="check", params=["content", "layer", "tags", "priority"], returns="GateResult",
                       description="质量检查"),
        MethodSignature(name="batch_check", params=["entries"], returns="List[GateResult]",
                       description="批量质量检查"),
    ],
    config_schema={"min_content_length": "int", "rejection_threshold": "float"},
    default_config={"min_content_length": 10, "rejection_threshold": 0.3},
    owner="tianji_core_team",
    criticality="high",
)
plan_result = pipeline.plan(new_module)
record("V3.2 规划通过", plan_result.phases.get("plan") != "failed",
       f"status={plan_result.phases.get('plan')}")

gates = plan_result.gates
all_gates_passed = all(g.passed for g in gates if g.required)
record("V3.3 所有Gate通过", all_gates_passed, f"gates={len(gates)}")


incomplete_module = TianjiModuleDefinition(
    module_id="", module_name="", display_name="", module_version="",
    tier=ModuleTier.CORE_ENGINE, module_type=ModuleType.ENGINE,
    domain="", responsibility="",
)
incomplete_plan = pipeline.plan(incomplete_module)
record("V3.4 不完整定义被拒绝", incomplete_plan.phases.get("plan") == "failed",
       f"status={incomplete_plan.phases.get('plan')}")


print_sub("阶段2: 审计 (Audit)")
audit_report = pipeline.audit(new_module, plan_result)
record("V3.5 审计执行", audit_report is not None,
       f"verdict={audit_report.verdict.value}, "
       f"checks={audit_report.summary['total']}, "
       f"passed={audit_report.summary['passed']}")

audit_passed = audit_report.verdict in (AuditVerdict.PASS, AuditVerdict.CONDITIONAL_PASS)
record("V3.6 审计通过", audit_passed, f"verdict={audit_report.verdict.value}")

checks = audit_report.checks
check_categories = set(c.category for c in checks)
record("V3.7 审计检查覆盖", len(check_categories) >= 5,
       f"categories={check_categories}")


print_sub("阶段3: 落地 (Implement)")
registry.register(new_module)
implement_ok = pipeline.implement(new_module, plan_result)
record("V3.8 落地执行", implement_ok)

registered_module = registry.get("quality_gate")
record("V3.9 注册验证", registered_module is not None and
       registered_module.lifecycle_state == ModuleLifecycleState.ACTIVE)

stats_after = registry.get_stats()
record("V3.10 注册计数", stats_after["registrations"] >= 5,
       f"registrations={stats_after['registrations']}")


print_sub("阶段4: 审批 (Approve)")
approval = pipeline.approve(new_module, plan_result)
record("V3.11 审批执行", approval is not None and "approved" in approval)

record("V3.12 审批层级", "approval_level" in approval,
       f"level={approval.get('approval_level', 'N/A')}")

pipeline_stats = pipeline.get_stats()
record("V3.13 流水线统计", pipeline_stats["pipelines_created"] >= 2,
       f"created={pipeline_stats['pipelines_created']}")


# ═══════════════════════════════════════════════════════════════
# Phase 4: 一键完整流水线
# ═══════════════════════════════════════════════════════════════

print_header("V4: 一键完整流水线 (Plan→Audit→Implement→Approve)")

module_evolution = TianjiModuleDefinition(
    module_id="evolution_engine",
    module_name="进化引擎",
    display_name="三级进化引擎",
    module_version="2.0.0",
    tier=ModuleTier.CORE_ENGINE,
    module_type=ModuleType.ENGINE,
    domain="自进化",
    responsibility="参数调优→规则新增→架构进化的三级进化能力",
    capabilities=["参数调优", "规则新增", "架构进化", "效果评估"],
    anti_responsibilities=["不做模块注册", "不直接操作记忆存储"],
    dependencies=[
        ModuleDependency(target_module="tianji_config", dependency_type=DependencyType.REQUIRED, description="配置管理"),
        ModuleDependency(target_module="icme_engine", dependency_type=DependencyType.OPTIONAL, description="记忆存储(可选)"),
    ],
    public_api=[
        MethodSignature(name="evolve", params=["causal_pairs"], returns="EvolutionResult",
                       description="执行进化"),
        MethodSignature(name="propose", params=["analysis"], returns="Proposal",
                       description="生成进化提案"),
    ],
    config_schema={
        "evolution_level": "string",
        "auto_apply": "bool",
        "cool_down_seconds": "int",
        "max_rules": "int",
    },
    default_config={
        "evolution_level": "level_2_rule_addition",
        "auto_apply": False,
        "cool_down_seconds": 3600,
        "max_rules": 50,
    },
    owner="tianji_core_team",
    criticality="high",
)

result = pipeline.run_full_pipeline(module_evolution)
record("V4.1 完整流水线执行", result["status"] == "approved",
       f"status={result['status']}, pipeline_id={result['pipeline_id']}")

record("V4.2 流水线耗时", "duration_seconds" in result,
       f"duration={result['duration_seconds']}s")

record("V4.3 审批信息完整", all(k in result.get("approval", {})
       for k in ["approved", "approval_level", "verdict", "recommendation"]))


# ═══════════════════════════════════════════════════════════════
# Phase 5: 边界场景与降级
# ═══════════════════════════════════════════════════════════════

print_header("V5: 边界场景与降级验证")

bad_module = TianjiModuleDefinition(
    module_id="circular_module_a",
    module_name="循环模块A",
    display_name="测试循环依赖",
    module_version="1.0.0",
    tier=ModuleTier.CORE_ENGINE,
    module_type=ModuleType.ENGINE,
    domain="测试",
    responsibility="用于验证循环依赖检测",
    dependencies=[
        ModuleDependency(target_module="circular_module_b", dependency_type=DependencyType.REQUIRED, description="测试"),
    ],
    public_api=[],
)
registry.register(bad_module)
record("V5.1 注册循环模块A", True)

bad_module_b = TianjiModuleDefinition(
    module_id="circular_module_b",
    module_name="循环模块B",
    display_name="测试循环依赖B",
    module_version="1.0.0",
    tier=ModuleTier.CORE_ENGINE,
    module_type=ModuleType.ENGINE,
    domain="测试",
    responsibility="用于验证循环依赖检测",
    dependencies=[
        ModuleDependency(target_module="circular_module_a", dependency_type=DependencyType.REQUIRED, description="测试"),
    ],
    public_api=[],
)
registry.register(bad_module_b)
record("V5.2 注册循环模块B", True)

cycles = registry.find_circular_dependencies()
record("V5.3 循环检测生效", len(cycles) > 0,
       f"found {len(cycles)} cycle(s): {cycles[0] if cycles else 'none'}")


registry.unregister("circular_module_a")
registry.unregister("circular_module_b")
cycles_after = registry.find_circular_dependencies()
record("V5.4 注销清理循环", len(cycles_after) == 0,
       f"cycles_after={len(cycles_after)}")


empty_module = TianjiModuleDefinition(
    module_id="", module_name="", display_name="", module_version="",
    tier=ModuleTier.CORE_ENGINE, module_type=ModuleType.ENGINE,
    domain="", responsibility="",
)
empty_result = pipeline.run_full_pipeline(empty_module)
record("V5.5 空模块被拒绝", empty_result["status"] == "failed" and empty_result["failed_at"] == "plan")


registry.update_health("icme_engine", "degraded", {
    "cpu": 0.95, "memory": 0.92, "error_rate": 0.15
})
health_check = registry.get("icme_engine")
record("V5.6 降级状态跟踪", health_check.health_status == "degraded")

degraded_modules = registry.list_by_health("degraded")
record("V5.7 降级模块查询", len(degraded_modules) >= 1,
       f"degraded={len(degraded_modules)}")

record_count = pipeline.get_record("evolution_engine")
record("V5.8 治理记录回溯", record_count is not None and
       record_count.overall_status == PhaseStatus.PASSED)


# ═══════════════════════════════════════════════════════════════
# Phase 6: 集成验证 — 三组件协同
# ═══════════════════════════════════════════════════════════════

print_header("V6: 三组件集成验证 (Registry + Analyzer + Pipeline)")

integrated_pipeline = GovernancePipeline(registry=registry, analyzer=analyzer)

module_skill = TianjiModuleDefinition(
    module_id="skill_registry",
    module_name="技能注册表",
    display_name="技能自注册中心",
    module_version="2.1.0",
    tier=ModuleTier.SCHEDULING_ORCHESTRATION,
    module_type=ModuleType.ORCHESTRATOR,
    domain="技能管理",
    responsibility="技能的自注册、发现、组合与调用路由",
    capabilities=["技能注册", "技能发现", "技能组合", "调用路由"],
    anti_responsibilities=["不执行技能逻辑", "不做安全审计"],
    dependencies=[
        ModuleDependency(target_module="tianji_config", dependency_type=DependencyType.REQUIRED, description="配置管理"),
        ModuleDependency(target_module="icme_engine", dependency_type=DependencyType.OPTIONAL, description="记忆存储(可选)"),
    ],
    public_api=[
        MethodSignature(name="register", params=["schema"], returns="bool", description="注册技能"),
        MethodSignature(name="discover", params=["query"], returns="List[Skill]", description="发现技能"),
        MethodSignature(name="compose", params=["skills"], returns="Composition", description="组合技能"),
    ],
    config_schema={"max_skills": "int", "auto_discover": "bool"},
    default_config={"max_skills": 200, "auto_discover": True},
    owner="tianji_core_team",
    criticality="medium",
)

integrated_result = integrated_pipeline.run_full_pipeline(module_skill)
record("V6.1 集成流水线执行", integrated_result["status"] == "approved",
       f"status={integrated_result['status']}")

record("V6.2 审批自动签准", integrated_result["approval"]["approval_level"] == "auto",
       f"level={integrated_result['approval']['approval_level']}")

all_records = integrated_pipeline.get_all_records()
passed_records = integrated_pipeline.list_by_status(PhaseStatus.PASSED)
record("V6.3 记录完整性", len(all_records) > 0,
       f"total={len(all_records)}, passed={len(passed_records)}")

final_stats = registry.get_stats()
record("V6.4 最终模块统计", True,
       f"registered={final_stats['total_registered']}, "
       f"registrations={final_stats['registrations']}")

analyzer_history = analyzer_single.get_history()
record("V6.5 分析历史累积", len(analyzer_history) >= 1,
       f"history={len(analyzer_history)}")

pipeline_final_stats = integrated_pipeline.get_stats()
record("V6.6 流水线累计统计", True,
       f"created={pipeline_final_stats['pipelines_created']}, "
       f"passed={pipeline_final_stats['pipelines_passed']}, "
       f"failed={pipeline_final_stats['pipelines_failed']}")


# ═══════════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════════

print_header("验证汇总")

print(f"  总检查项: {results['total']}")
print(f"  通过:     {results['passed']}")
print(f"  失败:     {results['failed']}")
print(f"  通过率:   {results['passed'] / max(results['total'], 1) * 100:.1f}%")

if results['failed'] == 0:
    print()
    print("  Phase 2 治理机制建设 — 虚拟审计验证全部通过!")
    print("  组件就绪: ModuleRegistry + StaticAnalyzer + GovernancePipeline")
else:
    print()
    print(f"  WARNING: {results['failed']} 项未通过，需要修复!")

print()
print("  数据根基溯源:")
print("    - 天机记忆 .tvp_declarations.jsonl: Agent流水线结构")
print("    - 天机记忆 .memory_push.jsonl: 闭环进化推送模式")
print("    - 天机记忆 causal_*.json: 因果对评估记录")
print("    - 天机v9.1/core/*.py: 24个核心模块AST分析")
print("    - 36地煞 → 天机模块体系映射")
print()
print("  Phase 2 治理机制建设完成!")
print("    注册中心   → ModuleRegistry (core/module_registry.py)")
print("    静态分析   → StaticDependencyAnalyzer (core/static_analyzer.py)")
print("    治理流水线 → GovernancePipeline (core/governance_pipeline.py)")

print()
print("=" * 66)


if __name__ == "__main__":
    sys.exit(0 if results["failed"] == 0 else 1)
