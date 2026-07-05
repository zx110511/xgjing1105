import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

tvp_path = Path(r"d:\元初系统\天机v9.1\core\tvp_bridge.py")

print("=== M16 TVPBridge v1.1 语法编译 ===")
try:
    py_compile.compile(str(tvp_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(tvp_path, "r", encoding="utf-8-sig") as f:
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
print(f"    Methods/Functions: {len(funcs)}")

checks = {
    "TVPBridge类": "TVPBridge" in classes,
    "weave_tvp_into_scheduler()": "weave_tvp_into_scheduler" in funcs,
    "_resolve_tvp()": "_resolve_tvp" in funcs,
    "declare_delegation_decision()": "declare_delegation_decision" in funcs,
    "declare_subagent_start()": "declare_subagent_start" in funcs,
    "declare_subagent_complete()": "declare_subagent_complete" in funcs,
    "declare_cron_trigger()": "declare_cron_trigger" in funcs,
    "declare_cron_complete()": "declare_cron_complete" in funcs,
    "declare_interrupt()": "declare_interrupt" in funcs,
    "declare_tool_call()": "declare_tool_call" in funcs,
    "get_pipeline_summary()": "get_pipeline_summary" in funcs,
    "get_stats()": "get_stats" in funcs,
    "health()": "health" in funcs,
    "tick()": "tick" in funcs,
    "_calc_tvp_effectiveness()": "_calc_tvp_effectiveness" in funcs,
    "_learn_from_tvp()": "_learn_from_tvp" in funcs,
    "_evolve_tvp_config()": "_evolve_tvp_config" in funcs,
    "D4-3 道谱溯源": "D4-3" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(delegation_decision)": 'action="delegation_decision"' in source,
    "record_action(subagent_start)": 'action="subagent_start"' in source,
    "record_action(subagent_complete)": 'action="subagent_complete"' in source,
    "record_action(interrupt)": 'action="interrupt"' in source,
}

print("\n=== M16 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)