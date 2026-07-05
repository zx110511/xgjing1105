# -*- coding: utf-8-sig -*-
"""tianji_mcp_server.py — 天机记忆引擎MCP Server主入口

TianjiMCPServer通过多继承Mixin组合各方法组，提供39个记忆工具。
支持两种运行模式:
  - 包导入模式: from mcp.tianji_mcp_server import TianjiMCPServer
  - 直接运行/MCP stdio模式: python mcp/tianji_mcp_server.py

工具变更历史:
  - v9.1.0: 初始41工具
  - v9.1.1: 移除4个重复工具(context_extract/agent_dispatch/system_status/rule_evaluate)
            → 由 agent-framework-global MCP Server 独立提供
  - v9.1.1: 新增2个工具(memory_update/search_quick) → 填补API端点覆盖缺口
  - 最终: 39工具 (41 - 4 + 2 = 39)
  - 全局: 6个MCP Server合计71个独立工具
"""

import io
import os
import sys
import urllib.request  # [FIX-MCP-WARMUP] 预热HTTP连接池需要

# [FIX-MCP-PROXY-BLOCK] 必须在所有urllib调用前清空代理环境变量
# Trae IDE启动MCP server时会继承HTTP_PROXY/HTTPS_PROXY环境变量，
# 导致urllib默认走代理，请求被路由到不存在的代理服务器，60s超时。
# 此处强制清空，确保所有HTTP请求直连127.0.0.1:8771。
for _proxy_var in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
):
    os.environ.pop(_proxy_var, None)
os.environ["NO_PROXY"] = "127.0.0.1,localhost,*"
os.environ["no_proxy"] = "127.0.0.1,localhost,*"

# ── 模块级常量 (SSS-PhaseB拆分后补全) ──────────────────

_STDOUT = sys.stdout
_STDERR = sys.stderr

TIANJI_API_URL = os.environ.get("TIANJI_API_URL", "http://127.0.0.1:8771")
TIANJI_HEALTH_URL = f"{TIANJI_API_URL}/api/health"
SYSTEM_NAME = "天机-忆库"
SYSTEM_VERSION = "9.1.0"
SYSTEM_TAG = "MEM-ENGINE"

TOOL_AGENT_MAPPING: dict = {}

# ── 工具定义 (41个工具) ───────────────────────────────

BASIC_TOOLS = [
    {
        "name": "memory_remember",
        "title": "记忆·写入",
        "description": "将内容写入天机ICME六层记忆系统指定层级。\n\n【触发场景】\n- 完成写操作后需要记录结果时\n- 重要决策、事件、经验需要持久化时\n- 对话结束前需要归档会话内容时\n\n【最佳实践】\n- 选择正确的层级: 操作结果→episodic, 知识概念→semantic, 系统策略→meta\n- 必须提供标签(>=2个)，便于后续检索\n- 内容长度>=30字符，确保信息密度\n\n【常见错误】\n- 忘记指定layer，默认写入working层导致信息易丢失\n- 标签太少导致检索困难",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要记住的内容"},
                "layer": {
                    "type": "string",
                    "description": "目标层级: sensory/working/short_term/episodic/semantic/meta",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表",
                },
                "priority": {
                    "type": "string",
                    "description": "优先级: low/medium/high/critical",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "memory_recall",
        "title": "记忆·检索",
        "description": "从天机记忆系统中语义检索匹配的记忆条目。\n\n【触发场景】\n- 决策前需要查询历史经验时\n- 用户要求查找/搜索/回忆相关内容时\n- 创作前加载上下文/设定/角色卡时\n- 故障排查需要追溯历史记录时\n\n【最佳实践】\n- 使用具体关键词而非泛化查询，提高命中率\n- 组合多个关键词提高精度\n- 指定layers缩小搜索范围提升性能\n- 检查relevance_score < 0.5的结果可能不相关\n- 大量结果时增加limit分批获取\n\n【返回结构】\nresults: [{entry_id, content, layer, relevance_score, tags, timestamp}]\ntotal: 总数\nquery_used: 实际使用的查询词",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询文本"},
                "limit": {"type": "integer", "description": "返回数量上限"},
                "layers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "限定层级",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_forget",
        "title": "记忆·遗忘",
        "description": "软删除指定记忆条目（标记为已遗忘，不物理删除）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "记忆条目ID"},
            },
            "required": ["entry_id"],
        },
    },
    {
        "name": "memory_stats",
        "title": "记忆·统计",
        "description": "获取天机记忆系统各层容量和使用统计。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "memory_capacity",
        "title": "记忆·容量",
        "description": "查询各记忆层当前容量和配额状态。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "memory_consolidate",
        "title": "记忆·整合",
        "description": "触发指定层级的记忆整合（Working→ShortTerm→Episodic）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_layer": {"type": "string", "description": "源层级"},
            },
        },
    },
    {
        "name": "search_memories",
        "title": "记忆·搜索",
        "description": "全量搜索记忆条目，支持关键词和语义匹配。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询"},
                "limit": {"type": "integer", "description": "结果上限"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_memory",
        "title": "记忆·获取单条",
        "description": "根据ID获取单条记忆的完整内容。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "记忆ID"},
            },
            "required": ["entry_id"],
        },
    },
    {
        "name": "list_memories",
        "title": "记忆·列举",
        "description": "分页列举记忆条目。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "每页数量"},
                "offset": {"type": "integer", "description": "偏移量"},
            },
        },
    },
]

ADVANCED_TOOLS = [
    # ── TCL处理工具 ──
    {
        "name": "tianji_classify",
        "title": "TCL·分类",
        "description": "智能分析内容并推荐最佳存储层级、标签和优先级。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "待分类内容"},
                "context": {"type": "string", "description": "上下文信息"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "tianji_auto_tag",
        "title": "TCL·自动标签",
        "description": "基于内容自动生成标签和元数据。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "待标注内容"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "tianji_summarize",
        "title": "TCL·摘要",
        "description": "生成内容的结构化摘要。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "待摘要内容"},
                "max_length": {"type": "integer", "description": "摘要最大长度"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "tianji_extract_knowledge",
        "title": "TCL·知识抽取",
        "description": "从内容中抽取结构化知识三元组。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "待抽取内容"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "tianji_expand_query",
        "title": "TCL·查询扩展",
        "description": "将简单查询扩展为多维度检索条件。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "原始查询"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "tianji_semantic_search",
        "title": "TCL·语义搜索",
        "description": "深度语义理解的记忆检索。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "语义查询"},
                "limit": {"type": "integer", "description": "结果上限"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "tianji_intercept",
        "title": "TCL·拦截注入",
        "description": "在记忆写入前注入上下文和决策信息。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "原始内容"},
                "context": {"type": "string", "description": "拦截上下文"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "tianji_normalize",
        "title": "TCL·规范化",
        "description": "将内容规范化为TCL标准格式。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "待规范化内容"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "tianji_disambiguate",
        "title": "TCL·消歧",
        "description": "对模糊内容进行消歧处理，确定唯一解释。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "待消歧内容"},
                "candidates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "候选解释",
                },
            },
            "required": ["content"],
        },
    },
    # ── 构建与表征 ──
    {
        "name": "build_working_representation",
        "title": "构建·工作表征",
        "description": "基于查询构建当前会话的工作表征（语义聚合+洞察生成）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "构建查询"},
                "max_items": {"type": "integer", "description": "最大条目数"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "run_reflective_cycle",
        "title": "构建·反思循环",
        "description": "运行反思循环，生成梦境统计和自我改进建议。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_session_digest",
        "title": "构建·会话摘要",
        "description": "获取指定会话的结构化摘要。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_key": {"type": "string", "description": "会话标识"},
                "digest_kind": {
                    "type": "string",
                    "description": "摘要类型: brief/full/both",
                },
            },
        },
    },
    {
        "name": "explain_memory_lineage",
        "title": "构建·记忆谱系",
        "description": "追溯指定记忆的完整来源和演化路径。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "记忆ID"},
            },
            "required": ["entry_id"],
        },
    },
    # ── 系统管理 ──
    {
        "name": "tianji_health",
        "title": "系统·健康检查",
        "description": "检查天机系统各组件健康状态。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tianji_help",
        "title": "系统·帮助",
        "description": "获取天机系统使用帮助和工具索引。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tianji_export",
        "title": "系统·导出",
        "description": "导出记忆数据为指定格式。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "description": "导出格式: json/csv/markdown",
                },
                "layers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "导出层级",
                },
            },
        },
    },
    {
        "name": "tianji_summarize_conversation",
        "title": "系统·对话摘要",
        "description": "对长对话进行结构化摘要。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "conversation": {"type": "string", "description": "对话内容"},
            },
            "required": ["conversation"],
        },
    },
    # ── Agent调度框架 (已迁移至 agent-framework-global MCP Server) ──
    # 以下4个工具已从 memory-engine 移除，由 agent-framework-global 独立提供:
    #   - context_extract  (调度·上下文提取)
    #   - agent_dispatch   (调度·Agent分发)
    #   - system_status    (调度·系统状态)
    #   - rule_evaluate    (调度·规则评估)
    # 去重原因: 避免与 agent_framework.py 重复定义，遵循单一职责原则
    # ── 新增: 记忆更新与快速搜索 (填补API端点覆盖缺口) ──
    {
        "name": "memory_update",
        "title": "记忆·更新",
        "description": "更新指定记忆条目的内容、标签或优先级 (对应 PUT /api/memories/{id})。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "记忆条目ID"},
                "content": {"type": "string", "description": "新内容 (可选)"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "新标签列表 (可选)",
                },
                "priority": {"type": "string", "description": "新优先级 (可选)"},
            },
            "required": ["entry_id"],
        },
    },
    # ── P1-2: Agent自管理记忆工具 (MemGPT模式) [v10-ready] ──
    # 借鉴Letta MemGPT架构, 让Agent主动编辑memory blocks
    {
        "name": "memory_insert",
        "title": "记忆·主动插入 (MemGPT模式)",
        "description": "Agent主动向指定layer插入新记忆块。与memory_remember不同: remember是被动写入, insert是Agent主动构建记忆结构。带审计追踪。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要插入的记忆内容"},
                "layer": {
                    "type": "string",
                    "description": "目标层级: sensory/working/short_term/episodic/semantic/meta",
                    "default": "working",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表",
                },
                "priority": {
                    "type": "string",
                    "description": "优先级: low/medium/high/critical",
                    "default": "medium",
                },
                "metadata": {"type": "object", "description": "元数据字典"},
                "agent_id": {
                    "type": "string",
                    "description": "执行插入的Agent身份",
                    "default": "self",
                },
                "reason": {
                    "type": "string",
                    "description": "Agent插入这条记忆的原因 (审计用)",
                },
            },
            "required": ["content", "layer"],
        },
    },
    {
        "name": "memory_replace",
        "title": "记忆·替换 (MemGPT模式)",
        "description": "Agent主动替换指定记忆条目的内容。使用supersede机制: 旧记忆标记为superseded, 新记忆链接到旧记忆形成版本链。带完整审计追踪。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "要替换的记忆条目ID"},
                "new_content": {"type": "string", "description": "新内容"},
                "reason": {"type": "string", "description": "替换原因 (审计用)"},
                "agent_id": {
                    "type": "string",
                    "description": "执行替换的Agent身份",
                    "default": "self",
                },
                "invalidate_old": {
                    "type": "boolean",
                    "description": "是否软删除旧记忆 (默认True, 保留可追溯)",
                    "default": True,
                },
            },
            "required": ["entry_id", "new_content"],
        },
    },
    {
        "name": "memory_rethink",
        "title": "记忆·反思重写 (MemGPT模式)",
        "description": "Agent完全重写一个记忆块。比memory_replace更激进: 不保留旧内容结构, 完全重新组织。强制要求rethink_reason, 强制Agent反思。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "要重写的记忆条目ID"},
                "rewritten_content": {
                    "type": "string",
                    "description": "完全重写后的新内容",
                },
                "rethink_reason": {
                    "type": "string",
                    "description": "重写理由 (强制Agent反思)",
                },
                "agent_id": {
                    "type": "string",
                    "description": "执行重写的Agent身份",
                    "default": "self",
                },
                "preserve_tags": {
                    "type": "boolean",
                    "description": "是否保留原标签 (默认True)",
                    "default": True,
                },
            },
            "required": ["entry_id", "rewritten_content", "rethink_reason"],
        },
    },
    # ── P1-3: 多Agent记忆共享层 (Mem0/Zep模式) [v10-ready] ──
    {
        "name": "memory_share",
        "title": "记忆·跨Agent共享 (Mem0/Zep模式)",
        "description": "Agent将自己的记忆共享给其他Agent。支持team/global两种范围, 支持TTL过期。共享后目标Agent可通过memory_recall_shared检索。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "要共享的记忆条目ID"},
                "owner_agent": {"type": "string", "description": "共享方Agent身份"},
                "target_agents": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "目标Agent列表 (空=所有Agent可访问)",
                },
                "share_scope": {
                    "type": "string",
                    "description": "共享范围: team/global",
                    "default": "team",
                },
                "share_reason": {"type": "string", "description": "共享原因 (审计用)"},
                "ttl_seconds": {
                    "type": "integer",
                    "description": "共享有效期(秒), 0=永久",
                    "default": 0,
                },
            },
            "required": ["entry_id", "owner_agent"],
        },
    },
    {
        "name": "memory_recall_shared",
        "title": "记忆·检索共享 (Mem0/Zep模式)",
        "description": "Agent检索其他Agent共享的记忆。自动按target_agents和share_scope过滤, 自动跳过过期记忆。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "requesting_agent": {
                    "type": "string",
                    "description": "请求方Agent身份",
                },
                "query": {
                    "type": "string",
                    "description": "检索查询 (空=列出所有可访问共享记忆)",
                },
                "owner_agent_filter": {
                    "type": "string",
                    "description": "仅检索指定owner共享的记忆",
                },
                "share_scope_filter": {
                    "type": "string",
                    "description": "范围过滤: team/global",
                },
                "limit": {"type": "integer", "description": "结果上限", "default": 10},
            },
            "required": ["requesting_agent"],
        },
    },
    {
        "name": "memory_list_shared",
        "title": "记忆·列出共享",
        "description": "列出当前Agent可访问的所有共享记忆。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "requesting_agent": {
                    "type": "string",
                    "description": "请求方Agent身份",
                },
                "include_expired": {
                    "type": "boolean",
                    "description": "是否包含过期记忆",
                    "default": False,
                },
                "limit": {"type": "integer", "description": "结果上限", "default": 20},
            },
            "required": ["requesting_agent"],
        },
    },
    {
        "name": "search_quick",
        "title": "记忆·快速搜索",
        "description": "基于关键词的快速记忆搜索，轻量级检索 (对应 GET /api/search/quick)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "结果上限", "default": 10},
            },
            "required": ["query"],
        },
    },
    # ── AMIM (Agent-MCP集成) ──
    {
        "name": "tianji_tool_owner",
        "title": "AMIM·工具归属",
        "description": "查询指定工具的归属Agent和委托链路。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": "工具名称"},
            },
            "required": ["tool_name"],
        },
    },
    {
        "name": "tianji_amim_status",
        "title": "AMIM·集成状态",
        "description": "获取Agent-MCP集成管理器的完整状态。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tianji_operation_header",
        "title": "AMIM·操作头",
        "description": "生成标准化操作头用于跨Agent追踪。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "description": "操作名"},
                "agent": {"type": "string", "description": "执行Agent"},
            },
            "required": ["operation"],
        },
    },
    # ── Trae集成 ──
    {
        "name": "trae_stream_capture",
        "title": "Trae·流捕获",
        "description": "捕获Trae IDE对话流并存储到L0 Sensory层。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stream_data": {"type": "string", "description": "流数据"},
            },
            "required": ["stream_data"],
        },
    },
    {
        "name": "trae_stream_snapshot",
        "title": "Trae·流快照",
        "description": "创建当前对话流的快照点。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "trae_monitoring_stats",
        "title": "Trae·监控统计",
        "description": "获取Trae集成的监控统计数据。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # ── 知识图谱 ──
    {
        "name": "memory_build_graph",
        "title": "图谱·构建",
        "description": "从记忆数据中构建知识图谱。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_layer": {"type": "string", "description": "源数据层级"},
            },
        },
    },
    {
        "name": "memory_query_graph",
        "title": "图谱·查询",
        "description": "在知识图谱上执行图查询。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "图查询语句"},
            },
            "required": ["query"],
        },
    },
    # ── 进化引擎 ──
    {
        "name": "memory_evolve_self",
        "title": "进化·自演化",
        "description": "触发记忆系统的自演化周期。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "memory_learn_skill",
        "title": "进化·技能学习",
        "description": "从操作历史中学习新技能模式。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "技能名称"},
            },
            "required": ["skill_name"],
        },
    },
    {
        "name": "memory_capture_multimodal",
        "title": "进化·多模态捕获",
        "description": "捕获和存储多模态内容（图像、音频等）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "内容描述"},
                "modality": {
                    "type": "string",
                    "description": "模态类型: image/audio/video",
                },
                "data_ref": {"type": "string", "description": "数据引用路径"},
            },
            "required": ["content", "modality"],
        },
    },
]

ALL_TOOLS = BASIC_TOOLS + ADVANCED_TOOLS

# ── 双模式导入 ────────────────────────────────────────

if __name__ == "__main__" or __package__ is None:
    _MCP_DIR = os.path.dirname(os.path.abspath(__file__))
    _ROOT_DIR = os.path.dirname(_MCP_DIR)
    if _ROOT_DIR not in sys.path:
        sys.path.insert(0, _ROOT_DIR)
    if _MCP_DIR not in sys.path:
        sys.path.insert(0, _MCP_DIR)

if __package__ is None or __name__ == "__main__":
    from tianji_mcp_server_build_repr import (
        TianjiMCPServerBuild_ReprMixin,  # type: ignore
    )
    from tianji_mcp_server_core import TianjiMCPServerCoreMixin  # type: ignore
    from tianji_mcp_server_evo import TianjiMCPServerEvoMixin  # type: ignore
    from tianji_mcp_server_memory_graph import (
        TianjiMCPServerMemory_GraphMixin,  # type: ignore
    )
    from tianji_mcp_server_memory_ops import (
        TianjiMCPServerMemory_OpsMixin,  # type: ignore
    )
    from tianji_mcp_server_system import TianjiMCPServerSystemMixin  # type: ignore
    from tianji_mcp_server_tcl import TianjiMCPServerTclMixin  # type: ignore
    from tianji_mcp_server_trae import TianjiMCPServerTraeMixin  # type: ignore
else:
    from .tianji_mcp_server_build_repr import TianjiMCPServerBuild_ReprMixin
    from .tianji_mcp_server_core import TianjiMCPServerCoreMixin
    from .tianji_mcp_server_evo import TianjiMCPServerEvoMixin
    from .tianji_mcp_server_memory_graph import TianjiMCPServerMemory_GraphMixin
    from .tianji_mcp_server_memory_ops import TianjiMCPServerMemory_OpsMixin
    from .tianji_mcp_server_system import TianjiMCPServerSystemMixin
    from .tianji_mcp_server_tcl import TianjiMCPServerTclMixin
    from .tianji_mcp_server_trae import TianjiMCPServerTraeMixin


class TianjiMCPServer(
    TianjiMCPServerCoreMixin,
    TianjiMCPServerMemory_OpsMixin,
    TianjiMCPServerBuild_ReprMixin,
    TianjiMCPServerTclMixin,
    TianjiMCPServerSystemMixin,
    TianjiMCPServerMemory_GraphMixin,
    TianjiMCPServerTraeMixin,
    TianjiMCPServerEvoMixin,
):
    """TianjiMCPServer — 天机记忆引擎MCP Server (39工具)"""

    pass


__all__ = ["TianjiMCPServer"]


# ── MCP stdio 入口 (直接运行时作为MCP Server) ───────────
if __name__ == "__main__":
    # [FIX-MCP-CRASH] 兼容Trae MCP配置中的 --server <name> 参数（mcp.json可能残留）
    sys.argv = [sys.argv[0]]

    # Windows stdio编码安全
    if sys.platform == "win32":
        try:
            sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8-sig")
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", line_buffering=True
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", line_buffering=True
            )
        except Exception:
            pass

    server = TianjiMCPServer()
    _STDERR.write(
        f"[{SYSTEM_TAG}] Memory Engine MCP Server v{SYSTEM_VERSION} starting...\n"
    )
    _STDERR.write(f"[{SYSTEM_TAG}] API: {TIANJI_API_URL}\n")
    _STDERR.write(f"[{SYSTEM_TAG}] Tools: {len(ALL_TOOLS)}\n")
    _STDERR.flush()

    # [FIX-MCP-WARMUP] 启动时预热HTTP连接池+AMIM，避免首次MCP调用超时
    try:
        import threading

        # [FIX-MCP-PROXY] 预热也使用无代理opener
        _warmup_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def _warmup():
            import time as _t

            _t.sleep(0.3)  # 等待 server 完全初始化
            try:
                # 预热1: 健康检查（建立HTTP keep-alive连接）
                req = urllib.request.Request(f"{TIANJI_API_URL}/api/health")
                _warmup_opener.open(req, timeout=5).read()
                # 预热2: 轻量记忆检索（预热SQLite读路径+FTS5索引）
                warm_req = urllib.request.Request(
                    f"{TIANJI_API_URL}/api/platform/recall?query=__warmup__&limit=1"
                )
                _warmup_opener.open(warm_req, timeout=5).read()
                # 预热3: 触发AMIM初始化（如可用）
                if server._amim is not None:
                    _ = server._amim.agent_count
                _STDERR.write(
                    f"[{SYSTEM_TAG}] Warmup done: HTTP pool + AMIM pre-initialized\n"
                )
                _STDERR.flush()
            except Exception as _we:
                _STDERR.write(f"[{SYSTEM_TAG}] Warmup skipped: {_we}\n")
                _STDERR.flush()

        threading.Thread(target=_warmup, daemon=True).start()
    except Exception:
        pass

    server.run()
