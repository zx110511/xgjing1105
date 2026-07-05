# -*- coding: utf-8-sig -*-
"""
Phase 3.1: 将高阶领域技能知识同步到L4 Semantic
服务恢复后执行，4个领域的知识批量写入
"""

import json
import os
import time
from datetime import datetime

import requests

TIANJI_API = "http://127.0.0.1:8771"
knowledge_dir = r"d:\元初系统\天机v9.1\.trae\skills\.audit\extracted_knowledge"

domain_files = [
    ("novel_production", "小说工业化生产", "novel_creation", "wenzong/miaobi/mingjing"),
    ("corpus_management", "语料库管理", "corpus_management", "kuangshi"),
    ("system_governance", "系统治理", "system_governance", "zhenshan/qianli/tianshu"),
    ("lingjing_framework", "灵境概念体系", "lingjing_framework", "tianshu/jingwei"),
]


def build_knowledge_content(
    domain_key: str, domain_name: str, data: dict, owner_agent: str
) -> str:
    """构建领域知识的Markdown内容"""
    skills = data.get("skills", [])

    content = f"# 领域技能库: {domain_name}\n\n"
    content += f"## 归属Agent\n{owner_agent}\n\n"
    content += f"## 包含技能 ({len(skills)}个)\n\n"

    for skill in skills:
        content += f"### {skill['skill_id']}\n"
        content += f"**目的**: {skill.get('purpose', '无描述')}\n\n"

        if skill.get("triggers"):
            content += "**触发场景**:\n"
            for t in skill["triggers"][:5]:
                content += f"- {t}\n"
            content += "\n"

        if skill.get("steps_summary") or skill.get("steps"):
            content += "**关键步骤**:\n"
            steps = skill.get("steps_summary", [])
            if not steps and skill.get("steps"):
                steps = [s.get("step", "") for s in skill["steps"][:5]]
            for s in steps[:5]:
                content += f"- {s}\n"
            content += "\n"

        if skill.get("best_practices"):
            content += "**最佳实践**:\n"
            for bp in skill["best_practices"][:5]:
                content += f"- {bp}\n"
            content += "\n"

    content += "\n## 元数据\n"
    content += f"- 领域: {domain_key}\n"
    content += f"- 技能数量: {len(skills)}\n"
    content += f"- 沉淀时间: {datetime.now().isoformat()}\n"
    content += "- 来源: 激进精简-技能文件价值归位\n"

    return content


def store_to_memory(content: str, layer: str, tags: list, metadata: dict) -> bool:
    """写入记忆，带重试"""
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{TIANJI_API}/api/mcp/tools/store_memory",
                json={
                    "content": content,
                    "layer": layer,
                    "tags": tags,
                    "priority": "high",
                    "metadata": metadata,
                },
                timeout=30,
            )
            result = resp.json()
            return result.get("status") == "success"
        except Exception as e:
            print(f"    尝试 {attempt + 1}/3 失败: {e}")
            if attempt < 2:
                time.sleep(2)
    return False


def main():
    print("=" * 78)
    print("  Phase 3.1: 高阶领域技能知识 → L4 Semantic 同步")
    print("=" * 78)
    print()

    total = len(domain_files)
    success_count = 0
    failed = []

    for i, (domain_key, domain_name, domain_id, owner_agent) in enumerate(
        domain_files, 1
    ):
        file_path = os.path.join(knowledge_dir, f"{domain_key}.json")

        if not os.path.exists(file_path):
            print(f"  [{i}/{total}] ⚠️  {domain_name} - 文件不存在，跳过")
            failed.append(domain_key)
            continue

        print(f"  [{i}/{total}] 📥 {domain_name}")
        print(f"         文件: {os.path.basename(file_path)}")

        try:
            with open(file_path, encoding="utf-8-sig") as f:
                data = json.load(f)

            content = build_knowledge_content(
                domain_key, domain_name, data, owner_agent
            )

            tags = [
                f"domain:{domain_id}",
                "skill_knowledge",
                "radical_slimming",
                domain_name,
                "l4_semantic",
            ]

            metadata = {
                "source": "skill_file_migration",
                "domain": domain_id,
                "skill_count": data.get("skill_count", 0),
                "owner_agent": owner_agent,
                "migration_time": datetime.now().isoformat(),
            }

            ok = store_to_memory(content, "semantic", tags, metadata)

            if ok:
                print("         ✅ 成功写入L4 Semantic")
                success_count += 1
            else:
                print("         ❌ 写入失败")
                failed.append(domain_key)

            # 间隔避免压垮服务
            time.sleep(1)

        except Exception as e:
            print(f"         ❌ 异常: {e}")
            failed.append(domain_key)

    # 验证: 检索一下刚写入的内容
    print()
    print("  🔍 验证写入结果...")
    try:
        resp = requests.post(
            f"{TIANJI_API}/api/mcp/tools/memory_recall",
            json={
                "query": "领域技能库 激进精简",
                "layers": ["semantic"],
                "limit": 5,
            },
            timeout=15,
        )
        result = resp.json()
        if result.get("status") == "success":
            results = result.get("results", [])
            print(f"         检索到 {len(results)} 条相关记忆")
            for r in results[:3]:
                content_preview = r.get("content", "")[:80]
                print(f"           - [{r.get('layer', '?')}] {content_preview}...")
    except Exception as e:
        print(f"         ⚠️  验证失败: {e}")

    print()
    print("=" * 78)
    print("  📊 同步结果:")
    print(f"  总领域数: {total}")
    print(f"  成功: {success_count}")
    print(f"  失败: {len(failed)}")
    if failed:
        print(f"  失败列表: {', '.join(failed)}")
    print("  知识来源: 23个高阶领域技能文件")
    print("  目标层: L4 Semantic")
    print("=" * 78)

    # 保存记录
    record = {
        "phase": "3.1",
        "description": "高阶领域技能知识同步到L4 Semantic",
        "timestamp": datetime.now().isoformat(),
        "total_domains": total,
        "success": success_count,
        "failed": failed,
        "source_skills": 23,
        "target_layer": "semantic",
    }

    record_path = os.path.join(knowledge_dir, "..", "phase3_1_sync_record.json")
    record_path = os.path.normpath(record_path)
    with open(record_path, "w", encoding="utf-8-sig") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
