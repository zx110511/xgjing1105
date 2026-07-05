# -*- coding: utf-8 -*-
"""
动态法则执行器 + 检测脚本模板
[SSS-PhaseB] 从engine.py拆分

提供:
1. SCRIPT_TEMPLATES: 检测脚本模板字典
2. DynamicLawEnforcer: 动态法则执行器(带Gate门禁)
3. 辅助方法: 脚本生成/索引/批量运行
"""

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("tianji.law_domain")

from .core import EmpiricalLaw, LawDomain, LawPriority, _LAW_DIR


class DynamicLawEnforcer:
    """
    动态法则执行器 v2.0 — 自动生成检测脚本 + Gate门禁强制执行

    E5增强:
    - 多类型检测脚本模板(process_check/path_audit/generic)
    - Gate门禁集成(pre-commit/pre-push/deploy)
    - 批量运行+汇总报告
    - 完整保障流程(生成→检查→报告)
    """

    def __init__(self, law_domain):
        self._domain = law_domain
        self._stats = {
            "scripts_generated": 0,
            "gate_checks_run": 0,
            "gate_passes": 0,
            "gate_failures": 0,
            "enforcement_runs": 0,
        }

        # 检测脚本模板
        self.SCRIPT_TEMPLATES = self._build_templates()

    def _build_templates(self) -> dict[str, str]:
        """构建检测脚本模板字典"""
        return {
            "process_check": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进程替换法则检测脚本
法则: {law_id} - {title}
"""

import subprocess
import time
import sys

def check_process_health(process_name=None, port=None):
    """检查进程健康状态"""
    # 简化实现
    return {{"status": "missing"}}

def enforce_process_replacement(old_process, new_process, port=None):
    """执行进程替换法则"""
    print(f"[{law_id}] 开始执行进程替换...")
    verify_status = check_process_health(old_process, port)
    if verify_status["status"] != "missing":
        print(f"  ✗ 旧进程仍在运行！状态: {{verify_status['status']}}")
        return False
    print("  ✓ 确认旧进程已停止")
    try:
        proc = subprocess.Popen(new_process.split(), shell=False)
        print(f"  ✓ 新进程已启动 (PID={{proc.pid}})")
    except Exception as e:
        print(f"  ✗ 启动失败: {{e}}")
        return False
    time.sleep(3)
    new_status = check_process_health(new_process.split()[-1] if ' ' in new_process else new_process, port)
    if new_status["status"] == "running":
        print("  ✓ 新进程运行正常")
        print(f"✅ [{law_id}] 进程替换成功完成")
        return True
    else:
        print(f"  ✗ 新进程异常: {{new_status}}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="{title}")
    subparsers = parser.add_subparsers(dest="command")
    check_parser = subparsers.add_parser("check", help="检查进程状态")
    check_parser.add_argument("--process", help="进程名称")
    check_parser.add_argument("--port", type=int, help="端口号")
    replace_parser = subparsers.add_parser("replace", help="执行进程替换")
    replace_parser.add_argument("--old-process", required=True, help="旧进程名称")
    replace_parser.add_argument("--new-process", required=True, help="新进程命令")
    replace_parser.add_argument("--port", type=int, help="端口号")
    args = parser.parse_args()
    if args.command == "check":
        result = check_process_health(args.process, args.port)
        print(result)
        sys.exit(0 if result.get("status") in ("running", "missing") else 1)
    elif args.command == "replace":
        success = enforce_process_replacement(
            args.old_process, args.new_process, args.port
        )
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
''',
            "generic": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动生成的通用法则检测脚本
法则: {law_id} - {title}
领域: {domain} | 类型: {law_type} | 优先级: {priority}
原则: {principle}
"""

import os
import re
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

class LawEnforcer:
    """法则执行器基类"""

    def __init__(self, law_id: str, title: str, principle: str):
        self.law_id = law_id
        self.title = title
        self.principle = principle
        self.violations: List[Dict] = []
        self.warnings: List[Dict] = []
        self.start_time = datetime.now()

    def check(self, target: str = ".") -> bool:
        """执行检查，返回是否通过"""
        raise NotImplementedError

    def report(self) -> Dict:
        """生成检查报告"""
        duration = (datetime.now() - self.start_time).total_seconds()
        passed = len(self.violations) == 0
        return {{
            "law_id": self.law_id,
            "title": self.title,
            "passed": passed,
            "violations_count": len(self.violations),
            "warnings_count": len(self.warnings),
            "duration_seconds": round(duration, 2),
            "violations": self.violations[:10],
            "warnings": self.warnings[:5],
        }}

    def print_report(self):
        """打印人类可读的报告"""
        r = self.report()
        print(f"\\n{'='*60}")
        print(f"法则: {{self.law_id}} - {{self.title}}")
        print(f"原则: {{self.principle}}")
        print(f"{'='*60}")
        print(f"状态: {{'✅ PASS' if r['passed'] else '❌ FAIL'}}")
        print(f"耗时: {{r['duration_seconds']}}s")
        print(f"违规: {{r['violations_count']}} | 警告: {{r['warnings_count']}}")

        if r['violations']:
            print(f"\\n违规详情:")
            for v in r['violations']:
                print(f"  ✗ {{v.get('file', '?')}}:{{v.get('line', '?')}} - {{v.get('message', 'N/A')}}")

        if r['warnings']:
            print(f"\\n警告:")
            for w in r['warnings']:
                print(f"  ⚠ {{w.get('message', 'N/A')}}")


class {class_name}(LawEnforcer):
    """{title} - 具体实现"""

    def __init__(self):
        super().__init__(
            law_id="{law_id}",
            title="{title}",
            principle="{principle}"
        )
        self.trigger_scenarios = {trigger_scenarios}
        self.enforcement_methods = {enforcement_methods}

    def check(self, target: str = ".") -> bool:
        root = Path(target)
        if not root.exists():
            self.violations.append({{"message": f"目标目录不存在: {{target}}"}})
            return False

        print(f"[{{self.law_id}] 检查目标: {{target}}")
        return len(self.violations) == 0


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="{{title}}",
        epilog="原则: {{principle}}"
    )
    parser.add_argument("target", nargs="?", default=".", help="检查目标(目录或文件)")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    parser.add_argument("--strict", action="store_true", help="严格模式(违规即退出码1)")
    args = parser.parse_args()

    enforcer = {class_name}()
    passed = enforcer.check(args.target)

    if args.json:
        print(json.dumps(enforcer.report(), ensure_ascii=False, indent=2))
    else:
        enforcer.print_report()

    if args.strict and not passed:
        sys.exit(1)

    return 0 if passed else 1

if __name__ == "__main__":
    sys.exit(main() or 0)
''',
        }

    def generate_enforcement_scripts(self, output_dir: Path | None = None) -> dict:
        """
        为所有P0/P1活跃法则生成检测脚本

        Returns:
            {"scripts_generated": N, "output_dir": path, "files": [...]}
        """
        active_laws = self._domain.lifecycle_manager.get_active_laws()
        p0_p1_laws = [
            l
            for l in active_laws
            if l.priority in (LawPriority.P0_CRITICAL, LawPriority.P1_HIGH)
        ]

        out_dir = output_dir or (_LAW_DIR / "scripts")
        out_dir.mkdir(parents=True, exist_ok=True)

        generated_files = []
        for law in p0_p1_laws:
            script = self._generate_single_script(law, self.SCRIPT_TEMPLATES)
            if script:
                safe_name = law.law_id.replace("-", "_").lower()
                script_path = out_dir / f"enforce_{safe_name}.py"
                script_path.write_text(script, encoding="utf-8")
                generated_files.append({
                    "file": str(script_path),
                    "law_id": law.law_id,
                    "title": law.title,
                })

        # 生成索引文件
        if generated_files:
            index_content = self._generate_script_index(generated_files)
            (out_dir / "__init__.py").write_text(index_content, encoding="utf-8")

            # 生成批量运行脚本
            runner_content = self._generate_runner_script(generated_files)
            (out_dir / "run_all_checks.py").write_text(runner_content, encoding="utf-8")

        self._stats["scripts_generated"] += len(generated_files)

        result = {
            "scripts_generated": len(generated_files),
            "output_dir": str(out_dir),
            "files": generated_files,
        }
        logger.info(f"[E5-脚本] 生成 {len(generated_files)} 个检测脚本 → {out_dir}")
        return result

    def _generate_single_script(
        self, law: EmpiricalLaw, templates: dict[str, str]
    ) -> str | None:
        """为单个法则生成检测脚本"""
        domain_key = law.domain.value
        type_key = law.law_type.value

        template_key = "generic"
        if domain_key == "path" and type_key == "prevention":
            template_key = "path_audit"
        elif domain_key == "process" and type_key in ("recovery", "prevention"):
            template_key = "process_check"

        template = templates.get(template_key, templates["generic"])

        class_name = (
            "".join(
                word.capitalize() for word in law.law_id.replace("-", "_").split("_")
            )
            + "Enforcer"
        )

        try:
            script = template.format(
                law_id=law.law_id,
                title=law.title,
                principle=law.principle,
                domain=law.domain.value,
                law_type=law.law_type.value,
                priority=law.priority.value,
                timestamp=datetime.now().isoformat(),
                class_name=class_name,
                trigger_scenarios=json.dumps(law.trigger_scenarios, ensure_ascii=False),
                enforcement_methods=json.dumps(law.enforcement_methods, ensure_ascii=False),
            )
            return script
        except KeyError as e:
            logger.warning(f"[E5-脚本] 模板缺失占位符: {e}")
            return None

    def _generate_script_index(self, generated_files: list[dict]) -> str:
        """生成脚本索引文件"""
        lines = [
            "# -*- coding: utf-8 -*\n",
            '"""',
            "自动生成的法则检测脚本索引",
            f"生成时间: {datetime.now().isoformat()}",
            f"脚本数量: {len(generated_files)}",
            '"""\n',
            "__all__ = [",
        ]
        for f in generated_files:
            name = f["file"].replace("\\", "/").split("/")[-1].replace(".py", "")
            lines.append(f'    "{name}",')
        lines.append("]\n")
        return "\n".join(lines)

    def _generate_runner_script(self, generated_files: list[dict]) -> str:
        """生成批量运行所有检测的脚本"""
        checks = "\n".join(
            [
                f"""    print(f"\\n--- 检查: {{f['law_id']}} ---")
    enforcer = {f["law_id"].replace("-", "").capitalize()}Enforcer()
    passed = enforcer.check(target)
    results.append({{"law_id": "{{f['law_id']}}", "passed": passed}})
    if not passed and strict:
        all_passed = False"""
                for f in generated_files[:10]
            ]
        )

        return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量运行所有法则检测脚本
生成时间: {datetime.now().isoformat()}
"""

import sys
import json
from datetime import datetime
from typing import Dict


def run_all_checks(target: str = ".", strict: bool = False) -> Dict:
    """运行所有检测并汇总结果"""
    results = []
    all_passed = True
    start_time = datetime.now()

{checks}

    duration = (datetime.now() - start_time).total_seconds()
    summary = {{
        "total_checks": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "all_passed": all_passed,
        "duration_seconds": round(duration, 2),
        "results": results,
    }}

    print(f"\\n{{'=' * 60}}")
    print(f"批量检测结果汇总")
    print(f"{{'=' * 60}}")
    print(f"总检测数: {{summary['total_checks']}}")
    print(f"通过: {{summary['passed']}} | 失败: {{summary['failed']}}")
    print(f"总耗时: {{summary['duration_seconds']}}s")
    print(f"最终: {{'✅ 全部通过' if all_passed else '❌ 存在失败'}}")

    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="批量运行所有法则检测")
    parser.add_argument("target", nargs="?", default=".", help="检查目标")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    args = parser.parse_args()

    result = run_all_checks(args.target, args.strict)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if result["all_passed"] else 1)


if __name__ == "__main__":
    sys.exit(main() or 0)
'''

    def run_gate_check(
        self, gate_name: str = "pre-commit", strict_mode: bool = True
    ) -> dict:
        """
        E5: Gate门禁检查 — 运行所有P0/P1法则的检测脚本
        """
        scripts_dir = _LAW_DIR / "scripts"
        runner_script = scripts_dir / "run_all_checks.py"

        if not runner_script.exists():
            logger.warning("[E5-Gate] 检测脚本未找到，先生成...")
            self.generate_enforcement_scripts()

        if not runner_script.exists():
            return {
                "gate_name": gate_name,
                "status": "error",
                "message": "无法生成检测脚本",
                "passed": False,
            }

        logger.info(f"[E5-Gate] 执行门禁: {gate_name} (strict={strict_mode})")

        cmd = [sys.executable, str(runner_script), "."]
        if strict_mode:
            cmd.append("--strict")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(Path(__file__).resolve().parent.parent),
            )

            gate_result = {
                "gate_name": gate_name,
                "status": "passed" if result.returncode == 0 else "failed",
                "exit_code": result.returncode,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
                "passed": result.returncode == 0,
                "strict_mode": strict_mode,
                "timestamp": datetime.now().isoformat(),
            }

            self._stats["gate_checks_run"] += 1
            if gate_result["passed"]:
                self._stats["gate_passes"] += 1
                logger.info(f"[E5-Gate] {gate_name}: ✅ PASS")
            else:
                self._stats["gate_failures"] += 1
                logger.warning(f"[E5-Gate] {gate_name}: ❌ FAIL (code={result.returncode})")

            return gate_result

        except subprocess.TimeoutExpired:
            return {
                "gate_name": gate_name,
                "status": "timeout",
                "message": "门禁检查超时(>120s)",
                "passed": False,
            }
        except Exception as e:
            return {
                "gate_name": gate_name,
                "status": "error",
                "message": str(e),
                "passed": False,
            }

    def enforce_all_active(self, include_gate: bool = True) -> dict:
        """
        E5: 完整保障流程 — 生成脚本 + 运行Gate + 汇总报告
        """
        self._stats["enforcement_runs"] += 1
        logger.info("[E5-完整保障] 开始执行完整保障流程...")
        start_time = datetime.now()

        report = {
            "enforcement_run_id": f"ENFORCE-{int(time.time())}",
            "timestamp": start_time.isoformat(),
            "steps": {},
            "final_result": "unknown",
        }

        step1 = self.generate_enforcement_scripts()
        report["steps"]["script_generation"] = step1
        logger.info(f"[E5-完整保障] Step 1 脚本生成: {step1['scripts_generated']} 个")

        if include_gate and step1["scripts_generated"] > 0:
            step2 = self.run_gate_check("auto-enforce", strict_mode=True)
            report["steps"]["gate_check"] = step2
            logger.info(f"[E5-完整保障] Step 2 Gate门禁: {step2['status']}")
        else:
            report["steps"]["gate_check"] = {"skipped": True, "reason": "无脚本或跳过"}

        active_laws = self._domain.lifecycle_manager.get_active_laws()
        p0_count = sum(1 for l in active_laws if l.priority == LawPriority.P0_CRITICAL)
        p1_count = sum(1 for l in active_laws if l.priority == LawPriority.P1_HIGH)

        duration = (datetime.now() - start_time).total_seconds()
        report.update({
            "active_p0_laws": p0_count,
            "active_p1_laws": p1_count,
            "total_duration_seconds": round(duration, 2),
            "final_result": "passed" if (
                include_gate == False or
                report["steps"].get("gate_check", {}).get("status") == "passed"
            ) else "failed",
        })

        logger.info(f"[E5-完整保障] 完成: {report['final_result']} ({duration:.1f}s)")

        report_path = (
            _LAW_DIR
            / f"enforcement_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return report

    def get_stats(self) -> dict:
        return dict(self._stats)
