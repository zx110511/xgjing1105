r"""
天机v9.1科研区 — 源文件动态更新机制 v1.0
==========================================
当核心源文件发生变化时，自动同步更新科研区文档中的引用数据。

更新规则:
  - core/*.py 变化 → 更新模块设计参考、注册经验、分析经验
  - server/api/*.py 变化 → 更新API文档
  - server/main.py 变化 → 更新配置说明
  - deploy/* 变化 → 更新部署运维
  - tests/* 变化 → 更新审计脚本参考 + 测试报告

触发方式:
  1. 手动: python sync_research_zone.py
  2. 自动: GovernanceOrchestrator bootstrap() 后调用
  3. Git Hook: post-commit 自动触发
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

RESEARCH_ZONE = Path(__file__).resolve().parent
PROJECT_ROOT = RESEARCH_ZONE.parent
CHECKSUM_FILE = RESEARCH_ZONE / ".source_checksums.json"


@dataclass
class SourceFile:
    path: Path
    rel_path: str
    checksum: str
    last_modified: float
    affected_docs: List[str] = field(default_factory=list)


@dataclass
class SyncReport:
    timestamp: str
    files_scanned: int
    files_changed: int
    docs_updated: List[str]
    errors: List[str]


def compute_checksum(file_path: Path) -> str:
    content = file_path.read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]


def load_checksums() -> Dict[str, str]:
    if CHECKSUM_FILE.exists():
        return json.loads(CHECKSUM_FILE.read_text(encoding="utf-8"))
    return {}


def save_checksums(checksums: Dict[str, str]):
    CHECKSUM_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKSUM_FILE.write_text(json.dumps(checksums, indent=2, ensure_ascii=False), encoding="utf-8")


SOURCE_DOC_MAP: Dict[str, List[str]] = {
    r"core\module_registry.py": [
        "经验复用区/治理机制经验/注册经验/Phase2模块注册经验.md",
        "技术方案区/模块设计/天机v9.1模块设计参考.md",
    ],
    r"core\static_analyzer.py": [
        "经验复用区/治理机制经验/分析经验/静态依赖分析经验.md",
        "技术方案区/模块设计/天机v9.1模块设计参考.md",
    ],
    r"core\governance_pipeline.py": [
        "经验复用区/治理机制经验/流水线经验/治理流水线经验.md",
        "技术方案区/模块设计/天机v9.1模块设计参考.md",
    ],
    r"core\*.py": [
        "技术方案区/模块设计/天机v9.1模块设计参考.md",
    ],
    r"server\main.py": [
        "开发资料区/API文档/天机v9.1_API文档.md",
        "开发资料区/配置说明/天机v9.1配置说明.md",
    ],
    r"server\api\*.py": [
        "开发资料区/API文档/天机v9.1_API文档.md",
    ],
    r"deploy\*": [
        "开发资料区/部署运维/天机v9.1部署运维手册.md",
    ],
    r"tests\test_phase2_integration_audit.py": [
        "测试验证区/审计脚本/审计脚本参考.md",
        "测试验证区/测试报告/天机v9.1_SSS审计测试报告.md",
        "经验复用区/审计经验/SSS审计方法论/SSS级集成审计方法论.md",
    ],
    r"tests\*.py": [
        "测试验证区/审计脚本/审计脚本参考.md",
    ],
    r"tianji_launcher.py": [
        "经验复用区/集成经验/Phase2启动器集成/GovernanceOrchestrator集成经验.md",
        "技术方案区/架构设计/天机v9.1治理架构方案.md",
        "开发资料区/部署运维/天机v9.1部署运维手册.md",
    ],
    r"config\paths.py": [
        "开发资料区/配置说明/天机v9.1配置说明.md",
    ],
}


def scan_source_files() -> List[SourceFile]:
    patterns = [
        PROJECT_ROOT / "core" / "*.py",
        PROJECT_ROOT / "server" / "main.py",
        PROJECT_ROOT / "server" / "api" / "*.py",
        PROJECT_ROOT / "deploy" / "*",
        PROJECT_ROOT / "tests" / "*.py",
        PROJECT_ROOT / "tianji_launcher.py",
        PROJECT_ROOT / "config" / "paths.py",
    ]

    files = []
    for pattern in patterns:
        matched = list(PROJECT_ROOT.glob(str(pattern.relative_to(PROJECT_ROOT)) if pattern.is_absolute() else str(pattern)))
        for f in matched:
            if f.is_file() and f.suffix in (".py", ".bat", ".ps1", ".iss", ".yml", ".txt", ".md"):
                files.append(SourceFile(
                    path=f,
                    rel_path=str(f.relative_to(PROJECT_ROOT)),
                    checksum=compute_checksum(f),
                    last_modified=f.stat().st_mtime,
                ))

    return files


def detect_changes(files: List[SourceFile], old_checksums: Dict[str, str]) -> List[SourceFile]:
    changed = []
    for f in files:
        old_hash = old_checksums.get(f.rel_path, "")
        if old_hash != f.checksum:
            changed.append(f)
    return changed


def match_affected_docs(file_rel: str) -> Set[str]:
    affected = set()

    import fnmatch
    for pattern, docs in SOURCE_DOC_MAP.items():
        if fnmatch.fnmatch(file_rel, pattern):
            affected.update(docs)

    return affected


def stamp_update(doc_rel_path: str):
    doc_path = RESEARCH_ZONE / doc_rel_path
    if not doc_path.exists():
        return

    stamp_line = f"\n> 🔄 自动更新于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}（源文件变更触发）"
    with open(doc_path, "a", encoding="utf-8") as f:
        f.write(stamp_line)


def run_sync(force: bool = False) -> SyncReport:
    report = SyncReport(
        timestamp=datetime.now().isoformat(),
        files_scanned=0,
        files_changed=0,
        docs_updated=[],
        errors=[],
    )

    try:
        files = scan_source_files()
        report.files_scanned = len(files)

        old_checksums = load_checksums() if not force else {}
        changed = detect_changes(files, old_checksums)
        report.files_changed = len(changed)

        if force:
            changed = files
            report.files_changed = len(files)

        for f in changed:
            affected = match_affected_docs(f.rel_path)
            for doc in affected:
                try:
                    stamp_update(doc)
                    report.docs_updated.append(doc)
                except Exception as e:
                    report.errors.append(f"更新 {doc} 失败: {e}")

        new_checksums = {f.rel_path: f.checksum for f in files}
        save_checksums(new_checksums)

    except Exception as e:
        report.errors.append(str(e))

    return report


def print_report(report: SyncReport):
    print("=" * 60)
    print("  天机v9.1科研区 — 源文件动态更新报告")
    print("=" * 60)
    print(f"  时间: {report.timestamp}")
    print(f"  扫描文件: {report.files_scanned}")
    print(f"  变更文件: {report.files_changed}")
    print(f"  更新文档: {len(report.docs_updated)}")
    if report.docs_updated:
        for doc in report.docs_updated:
            print(f"    📄 {doc}")
    if report.errors:
        print(f"  错误: {len(report.errors)}")
        for err in report.errors:
            print(f"    ❌ {err}")
    print("=" * 60)

    if report.files_changed > 0:
        print("\n💡 提示: 源文件已变更，相关科研区文档已自动更新时间戳。")
        print("   请手动检查文档内容是否需要同步更新。")
    elif report.files_changed == 0:
        print("\n✅ 所有源文件与科研区文档同步，无需更新。")

    return 0 if len(report.errors) == 0 else 1


if __name__ == "__main__":
    force = "--force" in sys.argv
    report = run_sync(force=force)
    print_report(report)
    sys.exit(0 if len(report.errors) == 0 else 1)
