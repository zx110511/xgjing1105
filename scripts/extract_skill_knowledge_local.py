# -*- coding: utf-8-sig -*-
"""
提取高阶领域技能的核心知识，保存为结构化JSON
服务不可用时暂存本地，恢复后同步到L4 Semantic
"""

import json
import os
from datetime import datetime

skills_dir = r"d:\元初系统\天机v9.1\.trae\skills"
output_dir = r"d:\元初系统\天机v9.1\.trae\skills\.audit\extracted_knowledge"
os.makedirs(output_dir, exist_ok=True)

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


def extract_skill_full(skill_name: str) -> dict:
    """完整提取技能文件内容"""
    skill_path = os.path.join(skills_dir, skill_name, "SKILL.md")
    if not os.path.exists(skill_path):
        return None

    with open(skill_path, encoding="utf-8-sig") as f:
        content = f.read()

    lines = content.split("\n")
    result = {
        "skill_id": skill_name,
        "purpose": "",
        "triggers": [],
        "steps": [],
        "parameters": [],
        "output_format": "",
        "best_practices": [],
        "bound_agents": [],
        "partners": [],
        "rules": [],
        "full_content": content,
    }

    section = None
    step_section = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## 目的"):
            section = "purpose"
            continue
        elif stripped.startswith("## 触发场景"):
            section = "triggers"
            continue
        elif stripped.startswith("## 执行步骤"):
            section = "steps"
            step_section = None
            continue
        elif stripped.startswith("## 参数说明"):
            section = "parameters"
            continue
        elif stripped.startswith("## 输出格式") or stripped.startswith(
            "## 返回结果格式"
        ):
            section = "output"
            continue
        elif stripped.startswith("## 最佳实践"):
            section = "best_practices"
            continue
        elif stripped.startswith("## 绑定Agent"):
            section = "bound_agents"
            continue
        elif stripped.startswith("## 协作伙伴"):
            section = "partners"
            continue
        elif stripped.startswith("## 强制规则关联"):
            section = "rules"
            continue
        elif stripped.startswith("## "):
            section = None
            continue

        if section == "purpose" and stripped:
            result["purpose"] += stripped + " "
        elif section == "triggers" and stripped.startswith("- "):
            result["triggers"].append(stripped[2:].strip())
        elif section == "steps":
            if stripped.startswith("### "):
                step_section = stripped[4:].strip()
            elif stripped.startswith("- ") and step_section:
                result["steps"].append(
                    {
                        "step": step_section,
                        "item": stripped[2:].strip(),
                    }
                )
        elif (
            section == "parameters"
            and stripped.startswith("| ")
            and not stripped.startswith("| ---")
        ):
            parts = [p.strip() for p in stripped.split("|")]
            parts = [p for p in parts if p]
            if len(parts) >= 2 and parts[0] != "参数":
                result["parameters"].append(
                    {
                        "name": parts[0],
                        "type": parts[1] if len(parts) > 1 else "",
                        "required": parts[2] if len(parts) > 2 else "",
                        "default": parts[3] if len(parts) > 3 else "",
                        "description": parts[4] if len(parts) > 4 else "",
                    }
                )
        elif section == "best_practices" and (
            stripped.startswith("- ✅") or stripped.startswith("- ⚠️")
        ):
            result["best_practices"].append(stripped[2:].strip())
        elif section == "bound_agents" and stripped:
            result["bound_agents"].append(stripped)
        elif section == "partners" and stripped:
            result["partners"].append(stripped)
        elif section == "rules" and stripped.startswith("- "):
            result["rules"].append(stripped[2:].strip())

    result["purpose"] = result["purpose"].strip()
    return result


def main():
    print("=" * 72)
    print("高阶领域技能知识提取（本地暂存版）")
    print("=" * 72)

    all_knowledge = {}
    total_skills = 0

    for domain_key, domain_info in skill_categories.items():
        print(f"\n📂 {domain_info['name']}")

        skills_data = []
        for skill_name in domain_info["skills"]:
            data = extract_skill_full(skill_name)
            if data:
                skills_data.append(data)
                total_skills += 1
                print(f"  ✅ {skill_name}")
            else:
                print(f"  ⚠️  {skill_name} - 跳过")

        all_knowledge[domain_key] = {
            "domain_name": domain_info["name"],
            "owner_agent": domain_info["owner_agent"],
            "domain": domain_info["domain"],
            "skills": skills_data,
            "skill_count": len(skills_data),
        }

        # 保存各领域单独文件
        domain_file = os.path.join(output_dir, f"{domain_key}.json")
        with open(domain_file, "w", encoding="utf-8-sig") as f:
            json.dump(all_knowledge[domain_key], f, ensure_ascii=False, indent=2)

    # 保存总文件
    total_file = os.path.join(output_dir, "all_domain_knowledge.json")
    with open(total_file, "w", encoding="utf-8-sig") as f:
        json.dump(all_knowledge, f, ensure_ascii=False, indent=2)

    # 生成Markdown摘要
    md_file = os.path.join(output_dir, "知识归位摘要.md")
    with open(md_file, "w", encoding="utf-8-sig") as f:
        f.write("# 高阶领域技能知识归位摘要\n\n")
        f.write(f"**提取时间**: {datetime.now().isoformat()}\n")
        f.write(f"**总技能数**: {total_skills}\n")
        f.write(f"**领域数**: {len(skill_categories)}\n\n")
        f.write("**状态**: 本地暂存，待服务恢复后同步到L4 Semantic\n\n")

        for domain_key, domain_data in all_knowledge.items():
            f.write(f"## {domain_data['domain_name']}\n\n")
            f.write(f"- **归属Agent**: {domain_data['owner_agent']}\n")
            f.write(f"- **技能数**: {domain_data['skill_count']}\n")
            f.write(
                f"- **技能列表**: {', '.join(s['skill_id'] for s in domain_data['skills'])}\n\n"
            )

    print(f"\n{'=' * 72}")
    print("📊 提取完成:")
    print(f"  总技能数: {total_skills}")
    print(f"  领域数: {len(skill_categories)}")
    print(f"  输出目录: {output_dir}")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()
