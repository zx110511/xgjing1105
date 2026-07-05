"""Phase2验证: core/目录实际扫描"""
from core.lingxi.dependency_scanner import scan_and_report
from core.lingxi.docstring_generator import process_directory as doc_process
from core.lingxi.type_annotator import process_directory as type_process

# 1. 依赖扫描
print("=" * 60)
print("=== 天机v9.1 core/ 依赖扫描报告 ===")
print("=" * 60)
report = scan_and_report("core", base_package="core")
print(f"文件数: {report.total_files}")
print(f"Import数: {report.total_imports}")
print(f"函数数: {report.total_functions}")
print(f"类数: {report.total_classes}")
print(f"循环依赖: {len(report.cycles)}个")
for i, cycle in enumerate(report.cycles[:5]):
    print(f"  循环{i+1}: {' -> '.join(cycle)}")
print(f"死代码: {len(report.dead_code)}个")
for dc in report.dead_code[:10]:
    print(f"  {dc.kind}: {dc.name} ({dc.file}:{dc.line}) refs={dc.references}")
top_coupling = sorted(report.coupling.items(), key=lambda x: x[1], reverse=True)[:5]
print("耦合度Top5:")
for mod, coupling in top_coupling:
    print(f"  {mod}: {coupling:.3f}")

# 2. Docstring扫描(dry-run)
print()
print("=" * 60)
print("=== Docstring缺失扫描 ===")
print("=" * 60)
doc_report = doc_process("core", dry_run=True)
print(f"扫描文件: {doc_report.total_scanned}")
print(f"缺失docstring: {doc_report.missing_count}")

# 3. 类型注解扫描(dry-run)
print()
print("=" * 60)
print("=== 类型注解缺失扫描 ===")
print("=" * 60)
type_report = type_process("core", dry_run=True)
print(f"扫描文件: {type_report.total_scanned}")
print(f"缺失注解函数: {type_report.missing_count}")
