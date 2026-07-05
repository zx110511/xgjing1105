# -*- coding: utf-8-sig -*-
"""
技能文件分类审计脚本
分类:
1. MCP工具直接映射型 (skill name ~ tool name)
2. 高阶领域技能型 (不直接对应单个MCP工具)
3. 概念/体系技能型 (灵境系列等)
"""

import json
import os

skills_dir = r"d:\元初系统\天机v9.1\.trae\skills"

# MCP工具名列表 (从tool_help获取的71个)
mcp_tools = [
    "memory_remember",
    "memory_recall",
    "memory_forget",
    "memory_stats",
    "memory_capacity",
    "memory_consolidate",
    "search_memories",
    "get_memory",
    "list_memories",
    "build_working_representation",
    "run_reflective_cycle",
    "get_session_digest",
    "explain_memory_lineage",
    "tianji_health",
    "tianji_help",
    "tianji_classify",
    "tianji_auto_tag",
    "tianji_summarize",
    "tianji_extract_knowledge",
    "tianji_expand_query",
    "tianji_semantic_search",
    "tianji_normalize",
    "tianji_disambiguate",
    "tianji_intercept",
    "tianji_export",
    "tianji_summarize_conversation",
    "tianji_tool_owner",
    "tianji_amim_status",
    "tianji_operation_header",
    "trae_stream_capture",
    "trae_stream_snapshot",
    "trae_monitoring_stats",
    "memory_build_graph",
    "memory_query_graph",
    "memory_evolve_self",
    "memory_learn_skill",
    "memory_capture_multimodal",
    "context_extract",
    "agent_dispatch",
    "system_status",
    "rule_evaluate",
    "execute_command",
    "check_command",
    "stop_command",
    "list_processes",
    "get_process_info",
    "kill_process",
    "run_script",
    "get_script_status",
    "list_scripts",
    "deploy_service",
    "check_deployment",
    "rollback_deployment",
    "get_resource_usage",
    "scale_service",
    "list_services",
    "profile_function",
    "get_performance_metrics",
    "analyze_bottleneck",
    "get_memory_profile",
    "get_cpu_profile",
    "list_profiling_sessions",
    "scan_vulnerabilities",
    "check_compliance",
    "get_security_report",
    "scan_dependencies",
    "check_permissions",
    "list_security_policies",
    "store_memory",
    "delete_memory",
    "search_perspective_memories",
]


def skill_name_to_tool_name(skill_dir_name: str) -> str:
    """将技能目录名转换为可能的MCP工具名"""
    return skill_dir_name.replace("-", "_")


def main():
    skill_folders = [
        d
        for d in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, d)) and not d.startswith(".")
    ]

    category_1 = []  # MCP工具直接映射型
    category_2 = []  # 高阶领域技能型
    category_3 = []  # 概念/体系技能型

    for skill in sorted(skill_folders):
        tool_name = skill_name_to_tool_name(skill)
        if tool_name in mcp_tools:
            category_1.append(skill)
        elif skill.startswith("lingjing"):
            category_3.append(skill)
        elif skill.startswith("novel") or skill.startswith("corpus"):
            category_2.append(skill)
        else:
            # 进一步判断: 读取SKILL.md看是否提到MCP工具名
            skill_md = os.path.join(skills_dir, skill, "SKILL.md")
            if os.path.exists(skill_md):
                with open(skill_md, encoding="utf-8-sig") as f:
                    content = f.read()
                # 检查是否提到某个MCP工具
                mentioned_tools = [
                    t
                    for t in mcp_tools
                    if t in content or t.replace("_", "-") in content
                ]
                if mentioned_tools and len(mentioned_tools) <= 3:
                    category_1.append(
                        f"{skill} (映射: {', '.join(mentioned_tools[:3])})"
                    )
                else:
                    category_2.append(skill)
            else:
                category_2.append(skill)

    print("=" * 72)
    print("技能文件分类审计")
    print("=" * 72)
    print(f"\n📊 总计: {len(skill_folders)} 个技能文件夹")
    print(f"\n--- Category 1: MCP工具直接映射型 ({len(category_1)}个) ---")
    for s in category_1:
        print(f"  ✅ {s}")
    print(f"\n--- Category 2: 高阶领域技能型 ({len(category_2)}个) ---")
    for s in category_2:
        print(f"  🔶 {s}")
    print(f"\n--- Category 3: 概念/体系技能型 ({len(category_3)}个) ---")
    for s in category_3:
        print(f"  🔷 {s}")

    # 还有特殊的
    print("\n--- 特殊目录 ---")
    special = [d for d in os.listdir(skills_dir) if d.startswith(".")]
    for s in special:
        print(f"  ⚫ {s}")

    # 保存结果
    result = {
        "total": len(skill_folders),
        "category_1_mcp_mapped": category_1,
        "category_2_domain": category_2,
        "category_3_concept": category_3,
        "special": special,
    }
    with open(
        os.path.join(skills_dir, ".audit", "skill_classification.json"),
        "w",
        encoding="utf-8-sig",
    ) as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("\n💾 结果已保存到 .audit/skill_classification.json")


if __name__ == "__main__":
    main()
