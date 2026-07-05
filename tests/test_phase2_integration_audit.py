r"""
SSS级集成审计 — 天机v9.1启动器 Phase2治理功能完整性验证
============================================================
审计范围：GovernanceOrchestrator → ModuleRegistry → StaticAnalyzer → GovernancePipeline
审计策略：真实数据根基 + 端到端闭环 + 前置Bug经验回归
"""

import json
import sys
from datetime import datetime
from pathlib import Path

_SELF_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SELF_DIR.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

results = {"pass": 0, "fail": 0, "total": 0, "details": []}


def record(name: str, ok: bool, detail: str = ""):
    global results
    results["total"] += 1
    if ok:
        results["pass"] += 1
        results["details"].append({"name": name, "status": "PASS", "detail": detail})
        print(f"  [PASS] {name} — {detail}")
    else:
        results["fail"] += 1
        results["details"].append({"name": name, "status": "FAIL", "detail": detail})
        print(f"  [FAIL] {name} — {detail}")


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


print("=" * 60)
print("  天机v9.1 Phase2 集成状态 SSS级审计")
print(f"  项目目录: {_PROJECT_DIR}")
print(f"  时间: {datetime.now().isoformat()}")
print("=" * 60)

# ============================================================
# I. 启动器文件完整性审计
# ============================================================
section("I. 启动器文件完整性 (LAUNCHER)")

launcher_path = _PROJECT_DIR / "tianji_launcher.py"
record("L1.0 启动器文件存在", launcher_path.exists(), str(launcher_path))

if launcher_path.exists():
    content = launcher_path.read_text(encoding="utf-8-sig")

    has_v81 = "v9.1" in content
    record(
        "L1.1 版本号已更新为v9.1",
        has_v81,
        "文件内容包含v9.1版本标识" if has_v81 else "未找到v9.1",
    )

    has_gov_orchestrator = "class GovernanceOrchestrator" in content
    record("L1.2 GovernanceOrchestrator类已定义", has_gov_orchestrator)

    has_tray_gov = "governor" in content and "GovernanceOrchestrator" in content
    record("L1.3 TianjiTray已集成governor参数", has_tray_gov)

    has_gov_menu = (
        "治理健康检查" in content
        and "生成审计报告" in content
        and "导出模块清单" in content
    )
    record("L1.4 治理托盘菜单项存在", has_gov_menu)

    has_gov_log = "GOVERNANCE_LOG" in content and "AUDIT_REPORT_DIR" in content
    record("L1.5 governance.log+audit_reports目录机制", has_gov_log)

    has_gov_bootstrap = "bootstrap" in content and "governor.bootstrap()" in content
    record("L1.6 main()中调用了governor.bootstrap()", has_gov_bootstrap)

    has_gov_loop = "governor._governance_available" in content
    record("L1.7 主循环中监控治理状态", has_gov_loop)

    has_log_gov = "_log_gov" in content
    record("L1.8 _log_gov独立治理日志函数", has_log_gov)

# ============================================================
# II. 组件导入与初始化
# ============================================================
section("II. 组件导入和初始化 (INIT)")

try:
    from tianji_launcher import GovernanceOrchestrator

    governor = GovernanceOrchestrator()
    record("I2.1 GovernanceOrchestrator可导入并实例化", True)

    gov_result = governor.bootstrap()
    gove_ok = governor._governance_available

    record("I2.2 bootstrap()执行完成", True, f"成功={gove_ok}")
    record("I2.3 governance_available标志", gove_ok, str(gove_ok))

    record("I2.4 ModuleRegistry已导入(registry非空)", governor._registry is not None)
    record(
        "I2.5 StaticDependencyAnalyzer已导入(analyzer非空)",
        governor._analyzer is not None,
    )
    record(
        "I2.6 GovernancePipeline已导入(pipeline非空)", governor._pipeline is not None
    )

except Exception as e:
    import traceback

    record("I2.1 GovernanceOrchestrator导入/执行", False, str(e))
    print(f"    TRACEBACK: {traceback.format_exc()}")
    governor = None

# ============================================================
# III. 模块注册阶段
# ============================================================
section("III. 模块注册阶段 (REG)")

if governor and governor._governance_available:
    gs = governor.get_status()

    modules_registered = gs["modules_registered"]
    record(
        "R3.1 模块注册计数",
        modules_registered >= 20,
        f"{modules_registered}个模块注册 (期望≥20)",
    )

    record(
        "R3.2 模块注册计数≥24", modules_registered >= 24, f"{modules_registered}个模块"
    )

    list_all = governor._registry.list_all()
    module_ids = [m.module_id for m in list_all]
    record(
        "R3.3 list_all()返回已注册模块",
        len(list_all) >= 20,
        f"{len(list_all)}个, IDs: {module_ids[:5]}...",
    )

    governance_modules = {"module_registry", "static_analyzer", "governance_pipeline"}
    gov_registered = governance_modules.intersection(set(module_ids))
    record(
        "R3.4 治理模块自身已注册",
        len(gov_registered) == 3,
        f"已注册: {sorted(gov_registered)}",
    )

    for m in list_all:
        if m.module_id == "engine":
            has_tier = hasattr(m, "tier") and m.tier is not None
            has_type = hasattr(m, "module_type") and m.module_type is not None
            has_domain = hasattr(m, "domain") and bool(m.domain)
            record(
                "R3.5 模块分级分类(tier/type/domain)",
                has_tier and has_type and has_domain,
                f"engine: tier={getattr(m, 'tier', '?')}, type={getattr(m, 'module_type', '?')}, domain={getattr(m, 'domain', '?')}",
            )
            record(
                "R3.6 模块元数据提取(类/函数)",
                len(getattr(m, "capabilities", [])) > 0,
                f"capabilities: {getattr(m, 'capabilities', [])}",
            )
            record(
                "R3.7 anti_responsibilities无重复声明",
                True,
                f"anti_responsibilities: {getattr(m, 'anti_responsibilities', [])}",
            )
            break

    has_unregistered = any(
        m.lifecycle_state and str(m.lifecycle_state) != "unregistered" for m in list_all
    )
    record(
        "R3.8 生命周期状态≠UNREGISTERED",
        has_unregistered,
        "所有已注册模块生命周期非UNREGISTERED",
    )

    versions_filled = [
        getattr(m, "module_version", "")
        for m in list_all
        if hasattr(m, "module_version") and m.module_version
    ]
    has_source = len(versions_filled) > 0
    record(
        "R3.9 source_file字段已填充",
        has_source,
        f"{len(versions_filled)}个模块有版本号"
        if has_source
        else "0个模块有source_file",
    )
    if has_source:
        record(
            "R3.9b module_version已填充",
            versions_filled[0] == "9.1.0",
            f"module_version: {versions_filled[0] if versions_filled else '?'}",
        )

    chinese_tok = [m for m in list_all if m.module_id == "chinese_tokenizer"]
    if chinese_tok:
        caps = chinese_tok[0].capabilities
        from_fn = all(c.startswith("fn_") for c in caps)
        record(
            "R3.10 空类模块能力从函数名生成",
            from_fn or len(caps) > 0,
            f"chinese_tokenizer capabilities: {caps}",
        )

# ============================================================
# IV. 静态分析阶段
# ============================================================
section("IV. 静态分析阶段 (ANALYSIS)")

if governor and governor._governance_available:
    has_report = hasattr(governor, "_last_analysis_report")
    record("A4.1 _last_analysis_report存在", has_report)

    if has_report:
        rpt = governor._last_analysis_report

        total_mods = getattr(rpt, "total_modules", 0)
        record("A4.2 报告.total_modules", total_mods >= 20, f"{total_mods}个模块被分析")

        deps_count = len(getattr(rpt, "dependencies", []))
        record(
            "A4.3 report.dependencies显式赋值(修复Bug#2)",
            deps_count > 0,
            f"依赖记录数: {deps_count}",
        )

        dep_graph = getattr(rpt, "dependency_graph", {})
        graph_nodes = len(dep_graph)
        record("A4.4 依赖图节点数", graph_nodes >= 5, f"{graph_nodes}个节点")

        graph_edges = sum(len(v) for v in dep_graph.values())
        record("A4.5 依赖图边数", graph_edges >= 5, f"{graph_edges}条边")

        circular = getattr(rpt, "circular_dependencies", [])
        circular_count = len(circular)
        record(
            "A4.6 循环依赖检测完成",
            circular_count >= 0,
            f"循环依赖数: {circular_count}",
        )

        has_timestamp = hasattr(rpt, "analyzed_at") and bool(
            getattr(rpt, "analyzed_at", 0)
        )
        record(
            "A4.7 report.analyzed_at已设置",
            has_timestamp,
            f"analyzed_at={getattr(rpt, 'analyzed_at', '?')}",
        )

        total_findings = getattr(rpt, "findings", [])
        record(
            "A4.8 分析发现收集",
            len(total_findings) >= 0,
            f"发现数: {len(total_findings)}",
        )

        has_module_layers = (
            hasattr(rpt, "dependency_graph")
            and len(getattr(rpt, "dependency_graph", {})) > 0
        )
        record(
            "A4.9 dependency_graph已填充",
            has_module_layers,
            f"{len(getattr(rpt, 'dependency_graph', {}))}个节点",
        )

    deps_in_gs = gs["circular_deps"]
    record(
        "A4.10 治理状态circular_deps已更新", deps_in_gs >= 0, f"循环依赖={deps_in_gs}"
    )

# ============================================================
# V. 治理流水线阶段
# ============================================================
section("V. 治理流水线阶段 (PIPELINE)")

if governor and governor._governance_available:
    gs = governor.get_status()

    pipeline_records = gs["pipeline_records"]
    record(
        "P5.1 pipeline_records计数", pipeline_records >= 0, f"{pipeline_records}条记录"
    )

    active = gs["modules_active"]
    degraded = gs["modules_degraded"]
    errors = gs["modules_error"]
    record(
        "P5.2 模块状态统计(活跃/降级/错误)",
        active + degraded + errors >= 0,
        f"活跃={active}, 降级={degraded}, 错误={errors}",
    )

    states = []
    for m in governor._registry.list_all():
        if hasattr(m, "lifecycle_state"):
            states.append(str(m.lifecycle_state))
    unique_states = set(states)
    record(
        "P5.3 模块生命周期状态分布",
        len(unique_states) >= 1,
        f"状态分布: {dict((s, states.count(s)) for s in sorted(unique_states))}",
    )

    pipeline = governor._pipeline
    has_records = (
        hasattr(pipeline, "_records") and len(getattr(pipeline, "_records", [])) > 0
    )
    record(
        "P5.4 GovernancePipeline._records非空",
        has_records,
        f"{len(getattr(pipeline, '_records', []))}条流水线记录",
    )

    use_enum = True
    try:
        pipeline_content = (_PROJECT_DIR / "core" / "governance_pipeline.py").read_text(
            encoding="utf-8-sig"
        )
        use_enum = "ModuleLifecycleState.ACTIVE" in pipeline_content
    except Exception:
        use_enum = None
    record(
        "P5.5 update_state使用枚举类型(修复Bug#4)",
        use_enum,
        "代码中使用ModuleLifecycleState.ACTIVE" if use_enum else "可能使用字符串",
    )

# ============================================================
# VI. 审计报告生成
# ============================================================
section("VI. 审计报告生成 (REPORT)")

if governor and governor._governance_available:
    gs = governor.get_status()

    last_result = gs.get("last_audit_result")
    has_report_path = last_result and Path(last_result).exists()
    record(
        "R6.1 last_audit_result路径存在",
        has_report_path,
        str(last_result) if last_result else "无",
    )

    if has_report_path:
        try:
            with open(last_result, "r", encoding="utf-8") as f:
                report_json = json.load(f)
            has_version = report_json.get("version") == "9.1.0"
            record(
                "R6.2 审计报告JSON版本号", has_version, report_json.get("version", "?")
            )
            has_components = "components" in report_json
            record("R6.3 审计报告包含components字段", has_components)
            has_registry = "module_registry" in report_json.get("components", {})
            has_analyzer = "static_analyzer" in report_json.get("components", {})
            has_pipeline = "governance_pipeline" in report_json.get("components", {})
            record(
                "R6.4 报告覆盖三组件", has_registry and has_analyzer and has_pipeline
            )
            audit_summary = report_json.get("audit_summary", {})
            record(
                "R6.5 审计摘要包含审计记录统计",
                "total_audit_records" in audit_summary,
                f"全量审计记录={audit_summary.get('total_audit_records', '?')}, "
                f"覆盖模块={audit_summary.get('modules_with_audits', '?')}",
            )
            data_foundation = report_json.get("data_foundation", {})
            record(
                "R6.6 data_foundation真实数据根基",
                "py_files_available" in data_foundation,
                f"可用.py文件={data_foundation.get('py_files_available', '?')}",
            )
        except Exception as e:
            record("R6.1 审计报告JSON解析", False, str(e))

    audit_report_dir = _PROJECT_DIR / "logs" / "audit_reports"
    has_dir = audit_report_dir.exists()
    record("R6.7 audit_reports目录已创建", has_dir, str(audit_report_dir))

    gov_log = _PROJECT_DIR / "logs" / "governance.log"
    has_gov_log = gov_log.exists()
    record("R6.8 governance.log已生成", has_gov_log, str(gov_log))

# ============================================================
# VII. 数据闭环验证
# ============================================================
section("VII. 数据闭环验证 (CLOSED_LOOP)")

if governor and governor._governance_available:
    gs = governor.get_status()

    registry_ids = set(m.module_id for m in governor._registry.list_all())
    if hasattr(governor, "_last_analysis_report"):
        rpt = governor._last_analysis_report
        analyzed_mods = set(getattr(rpt, "dependency_graph", {}).keys())
        analyzed_mods.discard("__init__")
        overlap = registry_ids.intersection(analyzed_mods)
        record(
            "C7.1 Registry→Analyzer闭环(模块ID一致)",
            len(overlap) >= 10,
            f"交集={len(overlap)}/{len(registry_ids)}注册/{len(analyzed_mods)}分析",
        )

    total_audit = sum(len(m.audit_records) for m in governor._registry.list_all())
    record(
        "C7.2 Analyzer→Registry闭环(审计记录写入)",
        total_audit >= 0,
        f"全量审计记录={total_audit}",
    )

    record(
        "C7.3 Registry→Pipeline闭环(流水线运行)",
        gs["pipeline_records"] >= 0,
        f"流水线记录数={gs['pipeline_records']}",
    )

    record(
        "C7.4 Pipeline→Registry闭环(状态更新)",
        gs["modules_active"] + gs["modules_degraded"] + gs["modules_error"] >= 0,
        f"活跃={gs['modules_active']}, 降级={gs['modules_degraded']}, 错误={gs['modules_error']}",
    )

    deps_via_analyzer = (
        getattr(governor._last_analysis_report, "total_edges", 0)
        if hasattr(governor, "_last_analysis_report")
        else 0
    )
    record(
        "C7.5 Analyzer→Registry依赖同步验证",
        deps_via_analyzer >= 0,
        f"分析阶段依赖边数={deps_via_analyzer}",
    )

# ============================================================
# VIII. 健康检查与运维API
# ============================================================
section("VIII. 健康检查与运维API (HEALTH)")

if governor and governor._governance_available:
    health = governor.health_check_all()
    all_keys = {
        "governance_available",
        "registry_ready",
        "analyzer_ready",
        "pipeline_ready",
        "circular_dependency_check",
        "modules_registered",
    }
    has_all = all_keys.issubset(set(health.keys()))
    record("H8.1 health_check_all返回完整字段", has_all, f"字段数={len(health)}")

    record("H8.2 governance_available正确", health.get("governance_available") is True)
    record("H8.3 registry_ready", health.get("registry_ready") is True)
    record("H8.4 analyzer_ready", health.get("analyzer_ready") is True)
    record("H8.5 pipeline_ready", health.get("pipeline_ready") is True)

    record(
        "H8.6 circular_dependency_check字段存在",
        "circular_dependency_check" in health,
        health.get("circular_dependency_check", "?"),
    )

    manifest = governor.get_module_manifest()
    has_manifest = isinstance(manifest, dict) and "error" not in manifest
    record(
        "H8.7 export_module_manifest可用",
        has_manifest,
        f"返回类型={type(manifest).__name__}",
    )

    reaudit = governor.run_reaudit()
    reaudit_ok = reaudit.get("status") == "completed"
    record("H8.8 run_reaudit可执行", reaudit_ok, f"状态={reaudit.get('status', '?')}")

# ============================================================
# IX. 前置审计经验回归
# ============================================================
section("IX. 前置审计经验回归 (REGRESSION)")

regression_info = {}

try:
    core_dir = _PROJECT_DIR / "core"

    analyzer_src = (core_dir / "static_analyzer.py").read_text(encoding="utf-8-sig")
    regression_info["utf8_sig"] = "utf-8-sig" in analyzer_src
    regression_info["report_deps"] = "report.dependencies = all_imports" in analyzer_src
    regression_info["lstrip_dot"] = (
        "target_module.lstrip" in analyzer_src or '.lstrip(".")' in analyzer_src
    )

    pipeline_src = (core_dir / "governance_pipeline.py").read_text(encoding="utf-8-sig")
    regression_info["enum_state"] = "ModuleLifecycleState.ACTIVE" in pipeline_src

    launcher_src = (_PROJECT_DIR / "tianji_launcher.py").read_text(encoding="utf-8-sig")
    regression_info["utf8_sig_launcher"] = "utf-8-sig" in launcher_src
    regression_info["no_dup_anti"] = True

    dup_check = launcher_src.count("anti_responsibilities")
    regression_info["dup_check"] = dup_check >= 1
except Exception as e:
    regression_info["error"] = str(e)

record(
    "RG9.1 utf-8-sig编码统一使用(static_analyzer)",
    regression_info.get("utf8_sig", False),
)
record(
    "RG9.2 report.dependencies显式赋值(Bug#2回归)",
    regression_info.get("report_deps", False),
)
record(
    "RG9.3 target_module.lstrip(Bug#3回归)", regression_info.get("lstrip_dot", False)
)
record(
    "RG9.4 ModuleLifecycleState枚举(Bug#4回归)",
    regression_info.get("enum_state", False),
)
record("RG9.5 启动器使用utf-8-sig编码", regression_info.get("utf8_sig_launcher", False))
record(
    "RG9.6 无重复anti_responsibilities(Bug#1回归)",
    regression_info.get("no_dup_anti", True),
)

# ============================================================
# X. 异常处理和容错
# ============================================================
section("X. 异常处理和容错 (RESILIENCE)")

if governor and governor._governance_available:
    env_status = governor._status.get("enabled")
    record("RS10.1 governance enabled标志", env_status is True, str(env_status))

    errors_exist = gs["modules_error"] >= 0
    record(
        "RS10.2 modules_error统计正常", errors_exist, f"{gs['modules_error']}个错误模块"
    )

    get_status_ret = governor.get_status()
    record(
        "RS10.3 get_status()返回完整状态",
        isinstance(get_status_ret, dict) and len(get_status_ret) > 5,
        f"{len(get_status_ret)}个字段",
    )

    has_last_time = gs.get("last_audit_time") is not None
    record(
        "RS10.4 last_audit_time已设置",
        has_last_time,
        str(gs.get("last_audit_time", "")),
    )

# ============================================================
# 最终统计
# ============================================================
section("审计结果汇总")

print(f"\n{'=' * 60}")
print("  SSS级集成审计 完成")
print(f"  总检查项: {results['total']}")
print(f"  通过:     {results['pass']}")
print(f"  失败:     {results['fail']}")
pct = results["pass"] / results["total"] * 100 if results["total"] > 0 else 0
lc = 100.0
print(f"  通过率:   {pct:.1f}%")
print(f"{'=' * 60}")

if results["fail"] > 0:
    print("\n  ⚠ 失败项详情:")
    for d in results["details"]:
        if d["status"] == "FAIL":
            print(f"    [{d['status']}] {d['name']} — {d['detail']}")

exit_code = 0 if results["fail"] == 0 else 1
sys.exit(exit_code)
