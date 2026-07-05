# -*- coding: utf-8-sig -*-
"""
Phase 3.3.5: 删除第二批4个高潜力技能文件（已归位到法则系统）
第二批删除: agent-transparent-dispatch, dialogue-quality, editor-review, tianji-orchestrate
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
    f"batch2_high_potential_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
)

to_delete = [
    "agent-transparent-dispatch",
    "dialogue-quality",
    "editor-review",
    "tianji-orchestrate",
]

# 归位映射
migrate_map = {
    "agent-transparent-dispatch": "智能体法则 - TVP透明调度协议 → 调度可视化与可追溯",
    "dialogue-quality": "质量法则 - 第五章 对话质量检查 (@lingxi主责)",
    "editor-review": "质量法则 - 第六章 内容审查规范 (@mingjing主责)",
    "tianji-orchestrate": "智能体法则 - 第九章 天机总控调度 (L0层)",
}


def main():
    os.makedirs(archive_dir, exist_ok=True)

    print("=" * 78)
    print("  🔥 Phase 3.3.5: 第二批技能删除 (高潜力归位)")
    print("=" * 78)
    print(f"  归档目录: {archive_dir}")
    print(f"  删除数量: {len(to_delete)} 个")
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

            print(f"  ✅ {skill_name}")
            print(f"     → 归位到: {migrate_map.get(skill_name, '未知')}")
            success_count += 1
        except Exception as e:
            print(f"  ❌ {skill_name} - 失败: {e}")
            failed.append(skill_name)

    # 统计当前剩余
    remaining = [
        d
        for d in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, d)) and not d.startswith(".")
    ]

    # 生成记录
    record = {
        "batch": 2,
        "description": "删除高潜力技能（已归位到法则系统）",
        "timestamp": datetime.now().isoformat(),
        "total": len(to_delete),
        "success": success_count,
        "failed": failed,
        "deleted_skills": to_delete,
        "migrate_map": migrate_map,
        "archive_path": archive_dir,
        "remaining_skills": sorted(remaining),
        "remaining_count": len(remaining),
        "total_original": 38,
        "total_deleted": 38 - len(remaining),
        "slimming_rate": (38 - len(remaining)) / 38,
    }

    record_path = os.path.join(skills_dir, ".audit", "radical_slimming_batch2.json")
    with open(record_path, "w", encoding="utf-8-sig") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 78}")
    print("  📊 执行结果:")
    print(f"  本批删除: {success_count}/{len(to_delete)} 个")
    print(f"  累计删除: {38 - len(remaining)} / 38 个")
    print(f"  精简率: {((38 - len(remaining)) / 38 * 100):.1f}%")
    print(f"  剩余技能: {len(remaining)} 个")
    print(f"\n  💾 删除记录: {record_path}")
    print(f"{'=' * 78}")

    # 打印剩余技能分类
    print("\n  📋 剩余技能列表:")
    novel = [s for s in remaining if s.startswith("novel") or s == "dialogue-quality"]
    corpus = [s for s in remaining if s.startswith("corpus")]
    lingjing = [s for s in remaining if s.startswith("lingjing")]
    system = [s for s in remaining if s not in novel + corpus + lingjing]

    print(f"    📖 小说创作类 ({len(novel)}): {', '.join(sorted(novel))}")
    print(f"    📚 语料管理类 ({len(corpus)}): {', '.join(sorted(corpus))}")
    print(f"    🏛️ 灵境概念类 ({len(lingjing)}): {', '.join(sorted(lingjing))}")
    print(f"    ⚙️ 系统治理类 ({len(system)}): {', '.join(sorted(system))}")


if __name__ == "__main__":
    main()
