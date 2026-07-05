# -*- coding: utf-8-sig -*-
"""
激进精简执行脚本 - 第一批: 删除MCP直接映射型技能
策略: 先备份到.audit/archive/，再删除
"""

import json
import os
import shutil
from datetime import datetime

skills_dir = r"d:\元初系统\天机v9.1\.trae\skills"
archive_dir = os.path.join(
    skills_dir,
    ".audit",
    "archive",
    f"batch1_mcp_mapped_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
)

# 第一批删除清单: MCP工具直接映射型 (15个)
to_delete = [
    "agent-dispatch",
    "auto-memory-capture",
    "context-extract",
    "data-analyze",
    "memory-file-capture",
    "memory-recall",
    "memory-remember",
    "memory-smart-dispatch",
    "ops-deploy",
    "perf-profile",
    "rule-check",
    "security-audit",
    "skill-route",
    "system-diagnose",
    "test-gate",
]


def main():
    os.makedirs(archive_dir, exist_ok=True)

    print("=" * 72)
    print("激进精简 - 第一批: 删除MCP直接映射型技能")
    print("=" * 72)
    print(f"\n📦 备份目录: {archive_dir}")
    print(f"🗑️  删除数量: {len(to_delete)} 个")
    print()

    success_count = 0
    failed = []

    for skill_name in to_delete:
        skill_path = os.path.join(skills_dir, skill_name)
        if not os.path.exists(skill_path):
            print(f"  ⚠️  {skill_name} - 不存在，跳过")
            continue

        try:
            # 备份
            dest = os.path.join(archive_dir, skill_name)
            shutil.copytree(skill_path, dest)

            # 删除
            shutil.rmtree(skill_path)

            print(f"  ✅ {skill_name} - 已备份并删除")
            success_count += 1
        except Exception as e:
            print(f"  ❌ {skill_name} - 失败: {e}")
            failed.append(skill_name)

    # 生成删除记录
    record = {
        "batch": 1,
        "description": "删除MCP直接映射型技能",
        "timestamp": datetime.now().isoformat(),
        "total": len(to_delete),
        "success": success_count,
        "failed": failed,
        "deleted_skills": to_delete,
        "archive_path": archive_dir,
    }

    record_path = os.path.join(skills_dir, ".audit", "radical_slimming_batch1.json")
    with open(record_path, "w", encoding="utf-8-sig") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 72}")
    print("📊 执行结果:")
    print(f"  成功: {success_count}/{len(to_delete)}")
    if failed:
        print(f"  失败: {failed}")
    print(f"\n💾 删除记录: {record_path}")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()
