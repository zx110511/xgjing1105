# -*- coding: utf-8-sig -*-
"""
Phase 3.3 预评估：高阶领域技能精简潜力分析
分析23个剩余技能中，哪些可以进一步归位/删除/合并
"""

import json
import os

skills_dir = r"d:\元初系统\天机v9.1\.trae\skills"

# 23个剩余技能
remaining_skills = [
    # 小说创作类 (8个)
    "novel-chapter-create",
    "novel-consistency-check",
    "novel-format-export",
    "novel-multi-schedule",
    "novel-setting-consistency-deep",
    "novel-version-track",
    "novel-worldbuilding-expand",
    "dialogue-quality",
    # 语料管理类 (4个)
    "corpus-batch-import",
    "corpus-extract",
    "corpus-quality-score",
    "corpus-retrieve",
    # 灵境概念类 (5个)
    "lingjing-14questions",
    "lingjing-9dao-orchestrate",
    "lingjing-dao-compliance",
    "lingjing-memory",
    "lingjing-triple-chain",
    # 系统治理类 (6个)
    "agent-transparent-dispatch",
    "editor-review",
    "memory-audit",
    "memory-test",
    "system-audit",
    "tianji-orchestrate",
]


def analyze_skill(skill_name: str) -> dict:
    """分析单个技能的精简潜力"""
    skill_path = os.path.join(skills_dir, skill_name, "SKILL.md")
    if not os.path.exists(skill_path):
        return None

    with open(skill_path, encoding="utf-8-sig") as f:
        content = f.read()

    # 分析指标
    analysis = {
        "skill_id": skill_name,
        "file_size": len(content),
        "has_purpose": "## 目的" in content,
        "has_triggers": "## 触发场景" in content,
        "has_steps": "## 执行步骤" in content,
        "has_params": "## 参数说明" in content,
        "has_best_practices": "## 最佳实践" in content,
        "mentions_mcp_tools": "工具:" in content
        or "memory_" in content
        or "tianji_" in content,
        "mentions_agents": "@" in content,
        "is_mostly_concept": False,
        "is_mostly_process": False,
        "can_be_merged": False,
        "merge_into": "",
        "can_be_deleted": False,
        "delete_reason": "",
        "slimming_potential": "low",  # low/medium/high
    }

    # 判断类型
    if skill_name.startswith("lingjing"):
        analysis["is_mostly_concept"] = True
        analysis["slimming_potential"] = "low"  # 概念体系，不可替代
    elif skill_name.startswith("novel-") or skill_name == "dialogue-quality":
        analysis["is_mostly_process"] = True
        # 小说创作类: 检查是否可以合并到Agent能力声明
        analysis["can_be_merged"] = True
        analysis["merge_into"] = "wenzong/miaobi/mingjing Agent能力声明"
        analysis["slimming_potential"] = "medium"
    elif skill_name.startswith("corpus-"):
        analysis["is_mostly_process"] = True
        analysis["can_be_merged"] = True
        analysis["merge_into"] = "kuangshi Agent能力声明"
        analysis["slimming_potential"] = "medium"
    else:
        # 系统治理类
        analysis["is_mostly_process"] = True
        analysis["slimming_potential"] = "high"  # 很多可以归位到法则系统

    # 具体判断
    if skill_name == "dialogue-quality":
        analysis["can_be_merged"] = True
        analysis["merge_into"] = "质量法则 + lingxi Agent"
        analysis["slimming_potential"] = "high"

    if skill_name == "agent-transparent-dispatch":
        analysis["can_be_merged"] = True
        analysis["merge_into"] = "智能体法则 TVP协议章节"
        analysis["slimming_potential"] = "high"

    if skill_name == "editor-review":
        analysis["can_be_merged"] = True
        analysis["merge_into"] = "质量法则 + mingjing Agent"
        analysis["slimming_potential"] = "high"

    if skill_name == "memory-audit":
        analysis["can_be_merged"] = True
        analysis["merge_into"] = "质量法则 + yiku Agent"
        analysis["slimming_potential"] = "medium"

    if skill_name == "memory-test":
        analysis["can_be_merged"] = True
        analysis["merge_into"] = "质量法则 + tiewei Agent"
        analysis["slimming_potential"] = "medium"

    if skill_name == "system-audit":
        analysis["can_be_merged"] = True
        analysis["merge_into"] = "质量法则 + zhenshan Agent"
        analysis["slimming_potential"] = "medium"

    if skill_name == "tianji-orchestrate":
        analysis["can_be_merged"] = True
        analysis["merge_into"] = "智能体法则 + tianshu Agent"
        analysis["slimming_potential"] = "high"

    return analysis


def main():
    print("=" * 78)
    print("  Phase 3.3 预评估：高阶领域技能精简潜力分析")
    print("=" * 78)

    results = []
    for skill in sorted(remaining_skills):
        analysis = analyze_skill(skill)
        if analysis:
            results.append(analysis)

    # 分类统计
    high_potential = [r for r in results if r["slimming_potential"] == "high"]
    medium_potential = [r for r in results if r["slimming_potential"] == "medium"]
    low_potential = [r for r in results if r["slimming_potential"] == "low"]

    print(f"\n📊 总览: {len(results)}个技能")
    print(f"  高精简潜力: {len(high_potential)}个")
    print(f"  中精简潜力: {len(medium_potential)}个")
    print(f"  低精简潜力: {len(low_potential)}个")
    print()

    print("=" * 78)
    print("  🔴 高精简潜力 (可直接归位到法则/Agent)")
    print("=" * 78)
    for r in high_potential:
        print(f"\n  {r['skill_id']}")
        print(f"    → 归位到: {r['merge_into']}")
        print("    → 理由: 流程性强，核心价值可被法则系统+Agent能力声明替代")

    print(f"\n{'=' * 78}")
    print("  🟡 中精简潜力 (需要保留部分结构)")
    print("=" * 78)
    for r in medium_potential:
        print(f"\n  {r['skill_id']}")
        print(f"    → 归位到: {r['merge_into']}")
        print("    → 理由: 有领域特殊性，需要Agent能力声明补充")

    print(f"\n{'=' * 78}")
    print("  🟢 低精简潜力 (概念体系，不可替代)")
    print("=" * 78)
    for r in low_potential:
        print(f"\n  {r['skill_id']}")
        print("    → 保留理由: 灵境概念体系，天机独有，无法被替代")

    # 理论最大精简空间
    print(f"\n{'=' * 78}")
    print("  📈 理论最大精简空间")
    print("=" * 78)
    print(f"  当前剩余: {len(results)}个")
    print(f"  可归位 (高+中): {len(high_potential) + len(medium_potential)}个")
    print(f"  最低保留 (灵境概念): {len(low_potential)}个")
    print(
        f"  理论精简率: {((len(high_potential) + len(medium_potential)) / len(results) * 100):.1f}%"
    )

    # 建议
    print(f"\n{'=' * 78}")
    print("  💡 建议")
    print("=" * 78)
    print("""
  阶段一 (已完成): 删除15个MCP直接映射型技能 ✅
  阶段二 (建议): 将13个高/中潜力技能归位到法则系统+Agent能力声明
  阶段三 (保留): 5个灵境概念技能永久保留，作为天机概念体系的技能入口

  最终目标: 5个技能 (灵境五件套) + 法则系统 + Agent能力声明 = 同等能力
  精简率: (38-5)/38 = 86.8%
""")

    # 保存评估结果
    output = {
        "total_skills": len(results),
        "high_potential": [r["skill_id"] for r in high_potential],
        "medium_potential": [r["skill_id"] for r in medium_potential],
        "low_potential": [r["skill_id"] for r in low_potential],
        "recommendation": "保留5个灵境概念技能，其余18个逐步归位到法则系统+Agent能力声明",
        "final_target_skill_count": 5,
        "theoretical_slimming_rate": (len(high_potential) + len(medium_potential))
        / len(results),
    }

    output_path = os.path.join(skills_dir, ".audit", "phase3_3_assessment.json")
    with open(output_path, "w", encoding="utf-8-sig") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n  💾 评估报告已保存: {output_path}")
    print(f"{'=' * 78}")


if __name__ == "__main__":
    main()
