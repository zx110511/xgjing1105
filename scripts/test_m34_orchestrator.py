import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

orch_path = Path(r"d:\元初系统\天机v9.1\agents\orchestrator.py")

print("=== M34 AgentOrchestrator v1.1 语法编译 ===")
try:
    py_compile.compile(str(orch_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(orch_path, "r", encoding="utf-8-sig") as f:
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
    "PipelineState枚举": "PipelineState" in classes,
    "TaskPriority枚举": "TaskPriority" in classes,
    "Task dataclass": "Task" in classes,
    "OrchestratorAgent类": "OrchestratorAgent" in classes,
    "register_agent()": "register_agent" in funcs,
    "schedule_task()": "schedule_task" in funcs,
    "schedule_tasks()": "schedule_tasks" in funcs,
    "get_next_task()": "get_next_task" in funcs,
    "transition_to()": "transition_to" in funcs,
    "execute_pipeline()": "execute_pipeline" in funcs,
    "get_pipeline_status()": "get_pipeline_status" in funcs,
    "health()": "health" in funcs,
    "tick()": "tick" in funcs,
    "_calc_orch_effectiveness()": "_calc_orch_effectiveness" in funcs,
    "_learn_from_orch()": "_learn_from_orch" in funcs,
    "_evolve_orch_config()": "_evolve_orch_config" in funcs,
    "D9-2 道谱溯源": "D9-2" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from core.processors.evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(schedule_task)": 'action="schedule_task"' in source,
    "record_action(transition_to)": 'action="transition_to"' in source,
    "record_action(execute_pipeline)": 'action="execute_pipeline"' in source,
    "record_action(execute_state)": 'action="execute_state"' in source,
}

print("\n=== M34 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)