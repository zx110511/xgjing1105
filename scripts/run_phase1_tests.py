"""
scripts/run_phase1_tests.py - Phase1测试止血：CI集成+覆盖率门禁
用法: python scripts/run_phase1_tests.py [--strict] [--module MODULE]
"""
import subprocess
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Phase1测试模块
PHASE1_MODULES = {
    "A1": "tests/test_core/test_engine_complete.py",
    "A2": "tests/test_core/test_sqlite_store.py",
    "A3": "tests/test_core/test_quality_gate.py",
    "A4a": "tests/test_core/test_models.py",
    "A4b": "tests/test_core/test_config.py",
}

# 覆盖率门禁阈值
COVERAGE_GATE = 80  # 全局最低覆盖率%
MODULE_COVERAGE_GATE = 60  # 单模块最低覆盖率%


def run_module(module_key: str, module_path: str) -> dict:
    """运行单个测试模块并收集结果"""
    cmd = [
        sys.executable, "-m", "pytest",
        module_path,
        "-v", "--tb=short",
        f"--cov=core", "--cov-report=term-missing",
        "--cov-report=json",
        "-p", "no:cacheprovider",
    ]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    return {
        "key": module_key,
        "path": module_path,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "passed": result.returncode == 0,
    }


def parse_coverage() -> float:
    """从coverage.json解析全局覆盖率"""
    cov_path = PROJECT_ROOT / "coverage.json"
    if not cov_path.exists():
        return 0.0
    try:
        with open(cov_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        totals = data.get("totals", {})
        return totals.get("percent_covered", 0.0)
    except Exception:
        return 0.0


def main():
    strict = "--strict" in sys.argv
    module_filter = None
    for arg in sys.argv[1:]:
        if arg.startswith("--module="):
            module_filter = arg.split("=", 1)[1].upper()

    print("=" * 60)
    print("天机v9.1 Phase1 测试止血 - CI集成")
    print("=" * 60)

    results = []
    modules_to_run = PHASE1_MODULES.items()
    if module_filter:
        modules_to_run = [(k, v) for k, v in modules_to_run if k.upper() == module_filter]

    for key, path in modules_to_run:
        print(f"\n>>> 运行 {key}: {path}")
        r = run_module(key, path)
        results.append(r)
        status = "PASS" if r["passed"] else "FAIL"
        print(f"    {key}: {status}")

    # 汇总
    print("\n" + "=" * 60)
    print("Phase1 测试结果汇总")
    print("=" * 60)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['key']}: {r['path']}")

    print(f"\n通过: {passed}/{total}  失败: {failed}/{total}")

    # 覆盖率门禁
    coverage = parse_coverage()
    print(f"\n全局覆盖率: {coverage:.1f}% (门禁: {COVERAGE_GATE}%)")

    gate_passed = coverage >= COVERAGE_GATE
    if strict and not gate_passed:
        print(f"覆盖率门禁未通过! {coverage:.1f}% < {COVERAGE_GATE}%")
    else:
        print("覆盖率门禁通过" if gate_passed else f"覆盖率低于门禁({coverage:.1f}%), 但非严格模式")

    # 最终判定
    all_passed = failed == 0 and (gate_passed or not strict)
    print(f"\n最终判定: {'ALL PASS' if all_passed else 'HAS FAILURES'}")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
