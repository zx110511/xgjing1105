import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.enforcement.governance_orchestrator import GovernanceOrchestrator, get_governor

print("GovernanceOrchestrator 导入成功")
g = GovernanceOrchestrator(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
result = g.bootstrap()
print(f"Bootstrap: {result}")

s = g.get_status()
print(f"模块注册: {s['modules_registered']}")
print(f"分析发现: {s['analysis_findings']}")
print(f"循环依赖: {s['circular_deps']}")
print(f"流水线记录: {s['pipeline_records']}")
print(f"启用状态: {s['enabled']}")

h = g.health_check_all()
print(f"注册就绪: {h['registry_ready']}")
print(f"分析就绪: {h['analyzer_ready']}")
print(f"流水线就绪: {h['pipeline_ready']}")
print(f"依赖验证: {h['circular_dependency_check']}")

manifest = g.export_module_manifest()
print(f"模块清单: {len(manifest['modules'])}个模块")
print(f"审计报告: {len(manifest['audit_reports'])}份")

print()
print("=== GovernanceOrchestrator 独立模块验证通过 ===")
