# -*- coding: utf-8-sig -*-
"""
Phase 2.3: 将高阶领域技能的核心价值沉淀到L4 Semantic记忆层
把23个剩余技能文件的核心知识提取为结构化经验，写入记忆系统
"""

import json
import os
import sys

import requests

sys.path.insert(0, r"d:\元初系统\天机v9.1")

TIANJI_API = "http://127.0.0.1:8771"

skills_dir = r"d:\元初系统\天机v9.1\.trae\skills"

# 剩余技能分类
skill_categories = {
    "novel_production": {
        "name": "小说工业化生产",
        "skills": [
            "novel-chapter-create",
            "novel-consistency-check",
            "novel-format-export",
            "novel-multi-schedule",
            "novel-setting-consistency-deep",
            "novel-version-track",
            "novel-worldbuilding-expand",
            "dialogue-quality",
        ],
        "owner_agent": "wenzong/miaobi/mingjing",
        "domain": "novel_creation",
    },
    "corpus_management": {
        "name": "语料库管理",
        "skills": [
            "corpus-batch-import",
            "corpus-extract",
            "corpus-quality-score",
            "corpus-retrieve",
        ],
        "owner_agent": "kuangshi",
        "domain": "corpus_management",
    },
    "system_governance": {
        "name": "系统治理",
        "skills": [
            "system-audit",
            "memory-audit",
            "memory-test",
            "editor-review",
            "agent-transparent-dispatch",
            "tianji-orchestrate",
        ],
        "owner_agent": "zhenshan/qianli/tianshu",
        "domain": "system_governance",
    },
    "lingjing_framework": {
        "name": "灵境概念体系",
        "skills": [
            "lingjing-14questions",
            "lingjing-9dao-orchestrate",
            "lingjing-dao-compliance",
            "lingjing-memory",
            "lingjing-triple-chain",
        ],
        "owner_agent": "tianshu/jingwei",
        "domain": "lingjing_framework",
    },
}


def extract_skill_knowledge(skill_name: str) -> dict:
    """从技能文件中提取核心知识"""
    skill_path = os.path.join(skills_dir, skill_name, "SKILL.md")
    if not os.path.exists(skill_path):
        return None

    with open(skill_path, encoding="utf-8-sig") as f:
        content = f.read()

    # 简单提取: 目的、触发场景、执行步骤摘要、最佳实践
    lines = content.split("\n")
    purpose = ""
    triggers = []
    steps = []
    best_practices = []

    section = None
    for line in lines:
        line = line.strip()
        if line.startswith("## 目的"):
            section = "purpose"
            continue
        elif line.startswith("## 触发场景"):
            section = "triggers"
            continue
        elif line.startswith("## 执行步骤"):
            section = "steps"
            continue
        elif line.startswith("## 最佳实践"):
            section = "best_practices"
            continue
        elif line.startswith("## "):
            section = None
            continue

        if section == "purpose" and line:
            purpose += line + " "
        elif section == "triggers" and line.startswith("- "):
            triggers.append(line[2:].strip())
        elif section == "steps" and line.startswith("### "):
            steps.append(line[4:].strip())
        elif section == "best_practices" and (
            line.startswith("- ✅") or line.startswith("- ⚠️")
        ):
            best_practices.append(line[2:].strip())

    return {
        "skill_id": skill_name,
        "purpose": purpose.strip(),
        "triggers": triggers[:5],  # 取前5个
        "steps_summary": steps[:5],  # 取前5步
        "best_practices": best_practices[:5],  # 取前5个
    }


def store_to_memory(domain: str, domain_name: str, skills_data: list, owner_agent: str):
    """将领域技能知识批量写入L4 Semantic层"""
    knowledge_content = f"""# 领域技能库: {domain_name}

## 归属Agent
{owner_agent}

## 包含技能 ({len(skills_data)}个)
"""

    for skill in skills_data:
        knowledge_content += f"""
### {skill["skill_id"]}
**目的**: {skill["purpose"]}

**触发场景**:
"""
        for t in skill["triggers"]:
            knowledge_content += f"- {t}\n"

        if skill["steps_summary"]:
            knowledge_content += "\n**关键步骤**:\n"
            for s in skill["steps_summary"]:
                knowledge_content += f"- {s}\n"

        if skill["best_practices"]:
            knowledge_content += "\n**最佳实践**:\n"
            for bp in skill["best_practices"]:
                knowledge_content += f"- {bp}\n"

    knowledge_content += f"""
## 元数据
- 领域: {domain}
- 技能数量: {len(skills_data)}
- 沉淀时间: 2026-07-03
- 来源: 激进精简-技能文件价值归位
"""

    # 写入记忆
    try:
        resp = requests.post(
            f"{TIANJI_API}/api/mcp/tools/store_memory",
            json={
                "content": knowledge_content,
                "layer": "semantic",
                "tags": [
                    f"domain:{domain}",
                    "skill_knowledge",
                    "radical_slimming",
                    domain_name,
                ],
                "priority": "high",
                "metadata": {
                    "source": "skill_file_migration",
                    "domain": domain,
                    "skill_count": len(skills_data),
                    "owner_agent": owner_agent,
                },
            },
            timeout=10,
        )
        result = resp.json()
        return result.get("status") == "success"
    except Exception as e:
        print(f"  ❌ 写入失败: {e}")
        return False


def main():
    print("=" * 72)
    print("Phase 2.3: 高阶领域技能价值归位 → L4 Semantic")
    print("=" * 72)

    total_skills = 0
    success_count = 0

    for domain_key, domain_info in skill_categories.items():
        print(f"\n📂 领域: {domain_info['name']} ({domain_key})")
        print(f"   归属Agent: {domain_info['owner_agent']}")
        print(f"   技能数: {len(domain_info['skills'])}")

        skills_data = []
        for skill_name in domain_info["skills"]:
            knowledge = extract_skill_knowledge(skill_name)
            if knowledge:
                skills_data.append(knowledge)
                total_skills += 1
                print(f"   ✅ 提取: {skill_name}")
            else:
                print(f"   ⚠️  跳过: {skill_name} (文件不存在)")

        if skills_data:
            ok = store_to_memory(
                domain=domain_info["domain"],
                domain_name=domain_info["name"],
                skills_data=skills_data,
                owner_agent=domain_info["owner_agent"],
            )
            if ok:
                success_count += len(skills_data)
                print("   💾 已沉淀到L4 Semantic")
            else:
                print("   ❌ 沉淀失败")

    print(f"\n{'=' * 72}")
    print("📊 归位结果:")
    print(f"  提取技能: {total_skills} 个")
    print(f"  成功沉淀: {success_count} 个")
    print(f"  领域数: {len(skill_categories)} 个")
    print(f"{'=' * 72}")

    # 生成归位记录
    record = {
        "phase": "2.3",
        "description": "高阶领域技能价值归位到L4 Semantic",
        "timestamp": "2026-07-03T10:00:00",
        "total_skills": total_skills,
        "domains": list(skill_categories.keys()),
    }
    record_path = os.path.join(skills_dir, ".audit", "value_migration.json")
    with open(record_path, "w", encoding="utf-8-sig") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
