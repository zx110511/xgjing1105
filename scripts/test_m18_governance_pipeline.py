import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

gp_path = Path(r"d:\元初系统\天机v9.1\core\governance_pipeline.py")

print("=== M18 GovernancePipeline v1.1 语法编译 ===")
try:
    py_compile.compile(str(gp_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(gp_path, "r", encoding="utf-8-sig") as f:
    source = f.read()

try:
    tree = ast.parse(source)
    print(f"✅ AST parse: PASS ({len(tree.body)} top-level nodes)")
except SyntaxError as e:
    print(f"❌ AST parse: FAIL — {e}")
    sys.exit(1)

classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

print(f"    Classes: {len(classes)} — {classes}")
print(f"    Functions/Methods: {len(funcs)}")

checks = {
    "GovernancePipeline": "GovernancePipeline" in classes,
    "AuditCheckerRegistry": "AuditCheckerRegistry" in classes,
    "PipelinePhase枚举": "PipelinePhase" in classes,
    "PhaseStatus枚举": "PhaseStatus" in classes,
    "AuditVerdict枚举": "AuditVerdict" in classes,
    "ApprovalLevel枚举": "ApprovalLevel" in classes,
    "StageGate": "StageGate" in classes,
    "AuditCheck": "AuditCheck" in classes,
    "AuditReport": "AuditReport" in classes,
    "GovernanceRecord": "GovernanceRecord" in classes,
    "plan()": "plan" in funcs,
    "audit()": "audit" in funcs,
    "implement()": "implement" in funcs,
    "approve()": "approve" in funcs,
    "run_full_pipeline()": "run_full_pipeline" in funcs,
    "enrich_audit_context_with_analysis()": "enrich_audit_context_with_analysis" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_pipeline_effectiveness()": "_calc_pipeline_effectiveness" in funcs,
    "_learn_from_pipeline()": "_learn_from_pipeline" in funcs,
    "_evolve_pipeline_config()": "_evolve_pipeline_config" in funcs,
    "D4-4 道谱溯源": "D4-4" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(plan)": 'action="plan"' in source,
    "record_action(audit)": 'action="audit"' in source,
    "record_action(implement)": 'action="implement"' in source,
    "record_action(approve)": 'action="approve"' in source,
    "stats(total_plans)": '"total_plans"' in source,
    "stats(total_implements)": '"total_implements"' in source,
    "stats(total_approvals)": '"total_approvals"' in source,
}

print("\n=== M18 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)
