import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=== Part 3: 托盘启动器集成验证 ===")
print()

print("--- 核心组件导入测试 ---")
from core.enforcement.governance_orchestrator import GovernanceOrchestrator
print("GovernanceOrchestrator: OK")
from core.shared.module_registry import ModuleRegistry
print("ModuleRegistry: OK")
from core.shared.static_analyzer import StaticAnalyzer
print("StaticAnalyzer: OK")
from core.enforcement.governance_pipeline import GovernancePipeline
print("GovernancePipeline: OK")
print()

print("--- 启动器文件分析 ---")
import ast
LAUNCHER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tianji_launcher.py')
with open(LAUNCHER, 'r', encoding='utf-8-sig') as f:
    code = f.read()

tree = ast.parse(code)
imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
print(f"启动器总import数: {len(imports)}")

gov_lines = [l.strip() for l in code.split('\n') if 'governance' in l.lower() or 'Governance' in l or 'registry' in l.lower() or 'Registry' in l or 'Pipeline' in l or 'Analyzer' in l]
print(f"治理/注册/分析相关行数: {len(gov_lines)}")
for i, l in enumerate(gov_lines[:15]):
    print(f"  L{i+1}: {l[:110]}")
print()

print("--- 启动器治理功能入口 ---")
if 'governance_menu' in code.lower() or '治理' in code:
    print("治理菜单: 已集成")
else:
    print("治理菜单: 未找到 (需检查)")
print()
print("=== Part 3 验证完成 ===")
