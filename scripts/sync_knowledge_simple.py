# -*- coding: utf-8-sig -*-
"""
Phase 3.1 简化版: 直接写入4条领域知识到L4 Semantic
"""

import time

import requests

TIANJI_API = "http://127.0.0.1:8771"

# 4个领域的知识摘要
domains = [
    {
        "name": "小说工业化生产",
        "skills": "novel-chapter-create, novel-consistency-check, novel-format-export, novel-multi-schedule, novel-setting-consistency-deep, novel-version-track, novel-worldbuilding-expand",
        "owner": "wenzong/miaobi/mingjing",
        "key_points": [
            "S0-S6工业化生产流程：需求→架构→创作→审校→集成→导出→归档",
            "S2创作必须实时记录到L3 Episodic",
            "S3审校评分>=9.95分才能进入S4",
            "S6必须包含经验沉淀+知识复用",
        ],
    },
    {
        "name": "语料库管理",
        "skills": "corpus-batch-import, corpus-extract, corpus-quality-score, corpus-retrieve",
        "owner": "kuangshi",
        "key_points": [
            "批量导入必须去重并记录来源",
            "语料提取需保留原文链接和版权信息",
            "质量评分>=0.8才能入库",
            "检索支持关键词+语义双模式",
        ],
    },
    {
        "name": "系统治理",
        "skills": "memory-audit, memory-test, system-audit",
        "owner": "zhenshan/qianli/tianshu/yiku/tiewei",
        "key_points": [
            "系统审计覆盖7维度：记忆/Agent/规则/安全/性能/运维/进化",
            "记忆审计检查ICME六层完整性和一致性",
            "测试必须达到覆盖率>=80%+六维验证>=9.95分",
            "审计问题必须触发进化反思环",
        ],
    },
    {
        "name": "灵境概念体系",
        "skills": "lingjing-14questions, lingjing-9dao-orchestrate, lingjing-dao-compliance, lingjing-memory, lingjing-triple-chain",
        "owner": "tianshu/jingwei",
        "key_points": [
            "14问灵魂拷问：新功能开发/架构变更前必须通过",
            "九域四十地煞二十二天罡：天机概念基线",
            "道合规验证：所有架构变更必须与灵境道对齐",
            "三链协同：记忆链+进化链+因果链共同驱动系统演化",
        ],
    },
]

success_count = 0

for i, domain in enumerate(domains, 1):
    content = f"# 领域技能库: {domain['name']}\n\n"
    content += f"## 归属Agent\n{domain['owner']}\n\n"
    content += f"## 包含技能\n{domain['skills']}\n\n"
    content += "## 核心要点\n"
    for p in domain["key_points"]:
        content += f"- {p}\n"
    content += "\n## 元数据\n"
    content += "- 来源: 激进精简-技能文件价值归位\n"
    content += "- 时间: 2026-07-03\n"

    tags = [
        f"domain:{domain['name']}",
        "skill_knowledge",
        "radical_slimming",
        "l4_semantic",
        "领域技能库",
    ]

    print(f"[{i}/4] 写入: {domain['name']}...", end=" ")

    try:
        resp = requests.post(
            f"{TIANJI_API}/api/mcp/tools/store_memory",
            json={
                "content": content,
                "layer": "semantic",
                "tags": tags,
                "priority": "high",
                "metadata": {
                    "source": "skill_file_migration",
                    "domain": domain["name"],
                    "owner_agent": domain["owner"],
                    "skills": domain["skills"],
                },
            },
            timeout=15,
        )
        result = resp.json()
        if result.get("status") == "success":
            print("✅ 成功")
            success_count += 1
        else:
            print(f"❌ 失败: {result}")
    except Exception as e:
        print(f"❌ 异常: {e}")

    time.sleep(0.5)

# 验证
print("\n🔍 验证: 检索'领域技能库'...")
try:
    resp = requests.post(
        f"{TIANJI_API}/api/mcp/tools/search_memories",
        json={
            "query": "领域技能库",
            "limit": 5,
        },
        timeout=15,
    )
    result = resp.json()
    if result.get("status") == "success":
        results = result.get("results", [])
        print(f"   检索到 {len(results)} 条结果")
        for r in results[:3]:
            preview = r.get("content", "")[:60].replace("\n", " ")
            print(f"   - {preview}...")
except Exception as e:
    print(f"   ⚠️  验证失败: {e}")

print(f"\n✅ 完成: {success_count}/4 个领域知识已写入L4 Semantic")
