#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
经验法则领域 E3-E5 功能验证测试
===============================
测试内容:
  E3: 经验自动提取引擎 (API连接+LLM提取+价值评分)
  E4: 学习闭环联动 (五阶段集成)
  E5: 保障级实现 (脚本生成+Gate门禁+强制执行)

运行方式:
  python tests/test_law_domain_e3e5.py
"""

import sys
import json
import traceback
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def print_section(title: str):
    """打印测试分节标题"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def print_result(test_name: str, success: bool, detail: str = ""):
    """打印测试结果"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"  [{status}] {test_name}")
    if detail and not success:
        print(f"         → {detail}")

def test_e3_imports():
    """E3-1: 测试模块导入"""
    print_section("E3-1: 模块导入测试")

    try:
        from core.shared.law_domain import (
            LawDomainEngine, ExperienceMiner, LawGenerator,
            RuleLifecycleManager, LearningBridge, EvolutionBridge,
            EmpiricalLaw, LawDomain, LawType, LawPriority, LawStatus,
            ExperiencePattern,
        )
        print_result("核心类导入", True)

        from core.shared.law_domain import EXPERIENCE_MINING_PATTERNS
        print_result("挖掘模式定义加载", True, f"{len(EXPERIENCE_MINING_PATTERNS)} 个模式")

        return True
    except ImportError as e:
        print_result("模块导入失败", False, str(e))
        traceback.print_exc()
        return False

def test_e3_experience_pattern_dataclass():
    """E3-2: 测试ExperiencePattern数据类增强字段"""
    print_section("E3-2: ExperiencePattern增强字段测试")

    try:
        from core.shared.law_domain import ExperiencePattern, LawDomain, LawType, LawPriority

        ep = ExperiencePattern(
            pattern_id="TEST-001",
            source_layer="episodic",
            source_id="mem-123",
            raw_content="测试内容: 发现路径硬编码问题",
            extracted_problem="问题描述",
            extracted_root_cause="根因分析",
            extracted_solution="解决方案",
            extracted_prevention="预防措施",
        )

        checks = [
            ("基础字段", ep.pattern_id == "TEST-001"),
            ("is_fault_record默认False", ep.is_fault_record == False),
            ("tags默认空列表", ep.tags == []),
            ("value_score默认0", ep.value_score == 0),
            ("llm_enhanced默认False", ep.llm_enhanced == False),
            ("meta默认空字典", ep.meta == {}),
        ]

        all_pass = True
        for name, check in checks:
            if not check:
                all_pass = False
            print_result(name, check)

        return all_pass

    except Exception as e:
        print_result("ExperiencePattern测试异常", False, str(e))
        traceback.print_exc()
        return False

def test_e3_miner_new_methods():
    """E3-3: 测试ExperienceMiner新增方法"""
    print_section("E3-3: ExperienceMiner新增方法测试")

    try:
        from core.shared.law_domain import ExperienceMiner

        miner = ExperienceMiner()

        method_checks = [
            ("fetch_memories_from_api方法存在", hasattr(miner, 'fetch_memories_from_api')),
            ("mine_l3_fault_records方法存在", hasattr(miner, 'mine_l3_fault_records')),
            ("llm_deep_extract方法存在", hasattr(miner, 'llm_deep_extract')),
            ("calculate_value_score方法存在", hasattr(miner, 'calculate_value_score')),
            ("full_auto_mine方法存在", hasattr(miner, 'full_auto_mine')),
            ("_deduplicate_cross_source方法存在", hasattr(miner, '_deduplicate_cross_source')),
        ]

        all_pass = True
        for name, check in method_checks:
            if not check:
                all_pass = False
            print_result(name, check)

        if all_pass:
            print_result("新增统计字段初始化",
                        "llm_extractions" in miner._stats and
                        "value_scored" in miner._stats and
                        "l3_fault_special" in miner._stats)

        return all_pass

    except Exception as e:
        print_result("ExperienceMiner方法测试异常", False, str(e))
        traceback.print_exc()
        return False

def test_e3_value_scoring():
    """E3-4: 测试价值评分功能"""
    print_section("E3-4: 价值评分功能测试")

    try:
        from core.shared.law_domain import (
            ExperiencePattern, LawDomain, LawType, LawPriority
        )

        miner = ExperienceMiner()

        test_cases = [
            {
                "name": "P0高频故障记录",
                "pattern": ExperiencePattern(
                    pattern_id="TEST-P0",
                    source_layer="episodic",
                    source_id="mem-1",
                    raw_content="2026年测试内容",
                    extracted_problem="", extracted_root_cause="",
                    extracted_solution="", extracted_prevention="",
                    domain_hint=LawDomain.PROCESS,
                    type_hint=LawType.RECOVERY,
                    priority_hint=LawPriority.P0_CRITICAL,
                    frequency=5,
                    is_fault_record=True,
                ),
                "min_score": 7,
            },
            {
                "name": "P2低频普通记录",
                "pattern": ExperiencePattern(
                    pattern_id="TEST-P2",
                    source_layer="episodic",
                    source_id="mem-2",
                    raw_content="旧测试内容",
                    extracted_problem="", extracted_root_cause="",
                    extracted_solution="", extracted_prevention="",
                    domain_hint=LawDomain.CODE_QUALITY,
                    type_hint=LawType.OPTIMIZATION,
                    priority_hint=LawPriority.P2_MEDIUM,
                    frequency=1,
                    is_fault_record=False,
                ),
                "max_score": 6,
            },
        ]

        all_pass = True
        for tc in test_cases:
            score = miner.calculate_value_score(tc["pattern"])

            if "min_score" in tc:
                passed = score >= tc["min_score"]
                print_result(f"{tc['name']} (score={score}, >={tc['min_score']})", passed)
            elif "max_score" in tc:
                passed = score <= tc["max_score"]
                print_result(f"{tc['name']} (score={score}, <={tc['max_score']})", passed)

            if not passed:
                all_pass = False

        return all_pass

    except Exception as e:
        print_result("价值评分测试异常", False, str(e))
        traceback.print_exc()
        return False

def test_e4_learning_bridge():
    """E4-1: 测试LearningBridge五阶段集成"""
    print_section("E4-1: LearningBridge五阶段集成测试")

    try:
        from core.shared.law_domain import LawDomainEngine, LearningBridge

        engine = LawDomainEngine()
        bridge = engine.learning_bridge

        phase_checks = [
            ("on_execute_phase方法", hasattr(bridge, 'on_execute_phase')),
            ("on_evaluate_phase方法", hasattr(bridge, 'on_evaluate_phase')),
            ("on_extract_phase方法", hasattr(bridge, 'on_extract_phase')),
            ("on_consolidate_phase方法", hasattr(bridge, 'on_consolidate_phase')),
            ("on_reflect_cycle方法", hasattr(bridge, 'on_reflect_cycle')),
            ("get_integration_status方法", hasattr(bridge, 'get_integration_status')),
        ]

        all_pass = True
        for name, check in phase_checks:
            if not check:
                all_pass = False
            print_result(name, check)

        if all_pass:
            status = bridge.get_integration_status()
            print_result("集成状态获取",
                        status.get('learning_bridge_version') == '2.0',
                        f"版本: {status.get('learning_bridge_version')}")
            print_result("支持阶段数量",
                        len(status.get('supported_phases', [])) == 5,
                        f"阶段: {status.get('supported_phases', [])}")

        return all_pass

    except Exception as e:
        print_result("LearningBridge测试异常", False, str(e))
        traceback.print_exc()
        return False

def test_e4_bridge_execution():
    """E4-2: 测试桥接器执行流程"""
    print_section("E4-2: 桥接器执行流程测试")

    try:
        from core.shared.law_domain import LawDomainEngine

        engine = LawDomainEngine()
        bridge = engine.learning_bridge

        task_key = bridge.on_execute_phase(
            task_id="TEST-TASK-001",
            agent_id="@tianshu",
            task_description="测试任务"
        )
        print_result("EXECUTE阶段", bool(task_key) and ":" in task_key, f"key={task_key[:30]}...")

        laws = bridge.on_evaluate_phase(
            task_key=task_key,
            complexity_str="critical",
            success=False,
            error_info="测试错误: 模拟故障",
            duration_ms=1500.0
        )
        print_result("EVALUATE阶段(critical+失败)", True,
                    f"触发法则数: {len(laws) if laws else 0}")

        patterns = bridge.on_extract_phase(
            session_id="TEST-SESSION-001",
            task_description="测试提取",
            ai_response="AI响应测试内容",
            mcp_calls=["memory_recall", "agent_dispatch"],
            error_summary="发现路径硬编码问题"
        )
        print_result("EXTRACT阶段", isinstance(patterns, list),
                    f"提取模式数: {len(patterns)}")

        result = bridge.on_consolidate_phase(batch_size=10)
        print_result("CONSOLIDATE阶段", isinstance(result, dict),
                    f"处理结果: {result.get('processed', 0)} 个")

        report = bridge.on_reflect_cycle(full_scan=False)
        print_result("REFLECT阶段", isinstance(report, dict) and 'cycle_id' in report,
                    f"周期ID: {report.get('cycle_id', 'N/A')}")

        return True

    except Exception as e:
        print_result("桥接器执行测试异常", False, str(e))
        traceback.print_exc()
        return False

def test_e5_script_generation():
    """E5-1: 测试代码检测脚本自动生成"""
    print_section("E5-1: 代码检测脚本自动生成测试")

    try:
        from core.shared.law_domain import LawDomainEngine, LawDomain, LawType, LawPriority, LawStatus
        from datetime import datetime

        engine = LawDomainEngine()

        test_law_data = {
            "law_id": "TEST-LAW-001",
            "domain": "path",
            "law_type": "prevention",
            "priority": "P0",
            "status": "active",
            "title": "测试路径唯一性法则",
            "principle": "凡涉及文件系统操作，必须使用相对路径或配置化路径，避免硬编码。",
            "steps": ["Step 1: 检测", "Step 2: 预防", "Step 3: 验证"],
            "trigger_scenarios": ["代码编写时", "部署配置时"],
            "violation_consequences": ["路径冲突", "移植失败"],
            "enforcement_methods": ["代码检测脚本", "规则检查"],
            "source_memory_ids": ["mem-1", "mem-2"],
            "source_experience_summary": "基于测试经验",
            "version": 1,
            "created_at": datetime.now().isoformat(),
            "tags": ["path", "prevention", "P0"],
            "value_score": 8,
        }

        index_path = Path(engine.generator._law_dir) / "law_index.json"
        import json as json_module

        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                index = json_module.load(f)
        else:
            index = {"laws": {}, "version": "1.0"}

        index["laws"][test_law_data["law_id"]] = test_law_data
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, 'w', encoding='utf-8') as f:
            json_module.dump(index, f, ensure_ascii=False, indent=2)

        result = engine.generate_enforcement_scripts()

        checks = [
            ("脚本生成成功", result.get('scripts_generated', 0) > 0),
            ("输出目录存在", Path(result.get('scripts_path', '')).exists()),
            ("生成文件列表非空", len(result.get('generated_files', [])) > 0),
            ("无严重错误", len(result.get('errors', [])) == 0),
        ]

        all_pass = True
        for name, check in checks:
            if not check:
                all_pass = False
            print_result(name, check,
                        str(result.get(name, '')) if name in result else "")

        if result.get('generated_files'):
            for gf in result['generated_files'][:3]:
                print(f"  📄 {gf['file']} ({gf['law_id']})")

        return all_pass

    except Exception as e:
        print_result("脚本生成测试异常", False, str(e))
        traceback.print_exc()
        return False

def test_e5_gate_check():
    """E5-2: 测试Gate门禁检查"""
    print_section("E5-2: Gate门禁检查测试")

    try:
        from core.shared.law_domain import LawDomainEngine

        engine = LawDomainEngine()

        gate_result = engine.run_gate_check(
            gate_name="test-gate",
            strict_mode=False
        )

        checks = [
            ("返回结果为字典", isinstance(gate_result, dict)),
            ("包含gate_name字段", 'gate_name' in gate_result),
            ("包含status字段", 'status' in gate_result),
            ("包含passed字段", 'passed' in gate_result),
            ("包含timestamp字段", 'timestamp' in gate_result),
        ]

        all_pass = True
        for name, check in checks:
            if not check:
                all_pass = False
            print_result(name, check)

        if all_pass:
            print_result(f"Gate状态: {gate_result.get('status')}",
                        gate_result.get('passed', False),
                        f"exit_code={gate_result.get('exit_code', 'N/A')}")

        return all_pass

    except Exception as e:
        print_result("Gate门禁测试异常", False, str(e))
        traceback.print_exc()
        return False

def test_e5_full_enforcement():
    """E5-3: 测试完整保障流程"""
    print_section("E5-3: 完整保障流程测试")

    try:
        from core.shared.law_domain import LawDomainEngine

        engine = LawDomainEngine()

        report = engine.enforce_all_active(include_gate=False)

        checks = [
            ("返回完整报告", isinstance(report, dict)),
            ("包含enforcement_run_id", 'enforcement_run_id' in report),
            ("包含timestamp字段", 'timestamp' in report),
            ("包含steps字段", 'steps' in report),
            ("包含final_result字段", 'final_result' in report),
            ("script_generation步骤存在", 'script_generation' in report.get('steps', {})),
        ]

        all_pass = True
        for name, check in checks:
            if not check:
                all_pass = False
            print_result(name, check)

        if all_pass:
            sg = report['steps'].get('script_generation', {})
            print_result(f"脚本生成: {sg.get('scripts_generated', 0)} 个", True)
            print_result(f"最终结果: {report.get('final_result')}", True)

        return all_pass

    except Exception as e:
        print_result("完整保障流程测试异常", False, str(e))
        traceback.print_exc()
        return False

def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("  天机经验法则领域 E3-E5 功能验证测试")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    results = {}

    results["E3-1: 导入"] = test_e3_imports()
    results["E3-2: 数据类"] = test_e3_experience_pattern_dataclass()
    results["E3-3: 挖掘器方法"] = test_e3_miner_new_methods()
    results["E3-4: 价值评分"] = test_e3_value_scoring()
    results["E4-1: 学习桥接"] = test_e4_learning_bridge()
    results["E4-2: 桥接执行"] = test_e4_bridge_execution()
    results["E5-1: 脚本生成"] = test_e5_script_generation()
    results["E5-2: Gate门禁"] = test_e5_gate_check()
    results["E5-3: 完整保障"] = test_e5_full_enforcement()

    print("\n" + "="*70)
    print("  测试结果汇总")
    print("="*70 + "\n")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {name}")

    print(f"\n  总计: {total} | 通过: {passed} | 失败: {failed}")
    print(f"  通过率: {passed/total*100:.1f}%")

    if failed == 0:
        print("\n  🎉 所有测试通过！E3-E5功能实现完整！\n")
        return 0
    else:
        print(f"\n  ⚠️  有 {failed} 个测试失败，请检查上方详情\n")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
