r"""
天机-调度 (Agent Framework) - MCP Server v9.1.1
================================================
Agent调度框架 | 任务分发 + 规则评估 + 系统状态 + 流水线管理
自包含实现 — 不依赖后端 /api/mcp/tools/* 路由

Tools (5 total):
  context_extract, agent_dispatch, system_status, rule_evaluate, pipeline_create

变更历史:
  - v9.1.1: 新增 pipeline_create (对应 POST /api/orchestrator/pipeline/create)
"""

import io
import json
import os
import re
import sys
import time as _vap_time
import urllib.error
import urllib.request
import uuid as _vap_uuid
from pathlib import Path

_SELF_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

try:
    from config import PROJECT_ROOT, TIANJI_ROOT
except Exception:
    PROJECT_ROOT = _SELF_DIR
    TIANJI_ROOT = _SELF_DIR

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

_STDOUT = sys.stdout
_STDERR = sys.stderr

TIANJI_API_URL = os.environ.get("TIANJI_API_URL", "http://127.0.0.1:8771")
SYSTEM_NAME = "天机-调度"
SYSTEM_VERSION = "9.1.0"

# ── 工具定义 ──────────────────────────────────────────

SERVER_TOOLS = [
    {
        "name": "context_extract",
        "title": "框架·上下文提取",
        "description": "从用户输入中提取结构化上下文信息，包括意图、实体、关键词等。用于Agent决策前置处理。\n\n【触发场景】\n- 收到复杂多意图用户输入时\n- 需要解析任务类型和优先级时\n- 用户需求模糊需要结构化澄清时\n\n【最佳实践】\n- 作为任务处理的第一步执行，为后续决策提供结构化输入\n- 配合user_input+context双参数，提高提取准确度\n- 结果包含:intents(意图列表), entities(实体), keywords(关键词), complexity(复杂度)\n\n【常见错误】\n- 仅依赖user_input忽略context，导致上下文缺失\n- 不验证提取结果的合理性，直接用于后续决策",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_input": {"type": "string", "description": "用户输入文本"},
                "context": {"type": "string", "description": "可选的额外上下文"},
            },
            "required": ["user_input"],
        },
    },
    {
        "name": "agent_dispatch",
        "title": "框架·Agent调度",
        "description": "基于能力矩阵智能匹配最优Agent，返回调度推荐及置信度。\n\n【触发场景】\n- 任务涉及>=2个Agent协作时\n- 任务复杂度>=medium需要专业Agent时\n- 不确定哪个Agent最适合时\n- 架构决策/技术选型需要多Agent参与时\n\n【最佳实践】\n- 配合context_extract使用，先解析任务再调度\n- 高优先级任务需同时调用rule_evaluate验证合规性\n- 推荐置信度<0.7时降级为@tianshu直接执行\n- 每次Agent切换必须遵循TVP协议声明\n\n【返回结构】\nrecommended_agent: 推荐Agent ID\nconfidence: 置信度(0-1)\nalternatives: 备选Agent列表\nreason: 推荐理由\n\n【协作模式选择】\n- 串行模式: 任务有严格顺序依赖\n- 并行模式: 多Agent可独立工作\n- 层级模式: 大型分治任务需要主控协调",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "description": "任务类型描述"},
                "task_data": {"type": "object", "description": "任务数据"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "优先级",
                },
            },
            "required": ["task_type"],
        },
    },
    {
        "name": "system_status",
        "title": "框架·系统状态",
        "description": "获取系统全局状态信息，包括天机后端健康、Agent列表、MCP连接、规则数量等。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "rule_evaluate",
        "title": "框架·规则评估",
        "description": "评估规则合规性，加载指定规则文件并检查上下文是否满足约束。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rule_name": {"type": "string", "description": "规则名称或关键词"},
                "context": {"type": "object", "description": "评估上下文"},
            },
            "required": ["rule_name"],
        },
    },
    {
        "name": "pipeline_create",
        "title": "框架·流水线创建",
        "description": "创建Agent协作流水线，定义阶段序列和依赖关系 (对应 POST /api/orchestrator/pipeline/create)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pipeline_name": {"type": "string", "description": "流水线名称"},
                "stages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stage_name": {"type": "string", "description": "阶段名称"},
                            "agent": {"type": "string", "description": "执行Agent"},
                            "task_type": {"type": "string", "description": "任务类型"},
                        },
                    },
                    "description": "阶段列表",
                },
                "mode": {
                    "type": "string",
                    "enum": ["serial", "parallel", "hierarchical"],
                    "description": "协作模式: 串行/并行/层级",
                    "default": "serial",
                },
            },
            "required": ["pipeline_name", "stages"],
        },
    },
    # ── VAP v2.0 工具 (智能调度可视化根基) ──────────────
    {
        "name": "vap_declare",
        "title": "VAP·内容归属声明",
        "description": "声明一次内容生成的智能体归属，生成 W3C Trace Context + OTel GenAI 语义，并真实写入天机v9.1 L3 Episodic 层。这是'用户看到任意内容生成究竟由哪个智能体执行'的核心工具。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "执行智能体名称 (如 tianshu/miaobi/yiku)",
                },
                "content_kind": {
                    "type": "string",
                    "enum": [
                        "text",
                        "code",
                        "tool_call",
                        "tool_result",
                        "file_read",
                        "file_write",
                        "file_edit",
                        "file_delete",
                        "memory_remember",
                        "memory_recall",
                        "mcp_call",
                        "agent_dispatch",
                        "search",
                        "command",
                        "decision",
                        "summary",
                    ],
                    "description": "内容种类",
                },
                "task_summary": {
                    "type": "string",
                    "description": "50字以内的任务摘要",
                    "maxLength": 80,
                },
                "event_type": {
                    "type": "string",
                    "enum": [
                        "content_start",
                        "content_end",
                        "tool_call",
                        "tool_result",
                        "memory_op",
                        "file_op",
                        "agent_switch",
                        "task_summary",
                        "degradation",
                    ],
                    "default": "content_start",
                    "description": "事件类型",
                },
                "status": {
                    "type": "string",
                    "enum": [
                        "planning",
                        "executing",
                        "reviewing",
                        "completed",
                        "failed",
                        "degraded",
                    ],
                    "default": "executing",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 1.0,
                    "description": "置信度 0.0-1.0",
                },
                "upstream": {"type": "string", "description": "上游智能体"},
                "downstream": {"type": "string", "description": "下游智能体"},
                "trace_id": {
                    "type": "string",
                    "description": "已有 trace_id (可选，用于延续追踪链)",
                },
                "session_id": {"type": "string", "description": "会话 ID (可选)"},
                "delegation_chain": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "委派链 (originating → delegating → executing)",
                },
            },
            "required": ["agent", "content_kind", "task_summary"],
        },
    },
    {
        "name": "vap_handoff",
        "title": "VAP·Agent切换声明",
        "description": "声明 Agent 之间的切换，传播 W3C Trace Context + 委派链。用于多Agent协作时的边界跨越声明，确保追踪链完整。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_agent": {"type": "string", "description": "当前 Agent"},
                "to_agent": {"type": "string", "description": "目标 Agent"},
                "task_type": {"type": "string", "description": "任务类型"},
                "context_summary": {"type": "string", "description": "50字上下文摘要"},
                "trace_id": {
                    "type": "string",
                    "description": "追踪 ID (可选，缺省自动生成)",
                },
                "handoff_mode": {
                    "type": "string",
                    "enum": ["transfer", "return", "delegate", "escalate"],
                    "default": "delegate",
                    "description": "切换模式: transfer(转移)/return(返回)/delegate(委派)/escalate(升级)",
                },
            },
            "required": ["from_agent", "to_agent", "task_type"],
        },
    },
    {
        "name": "vap_summary",
        "title": "VAP·会话追踪摘要",
        "description": "获取当前会话的 VAP 追踪摘要，包括参与智能体、事件分布、trace 链路。让用户看到本次任务中所有智能体的参与情况。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "trace_id": {
                    "type": "string",
                    "description": "指定 trace_id (可选，缺省返回最近会话)",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "vap_recall",
        "title": "VAP·VAP声明检索",
        "description": "从天机 L3 Episodic 检索 VAP 声明，支持按 agent/trace_id/事件类型过滤。用于追溯任意内容生成的归属。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询"},
                "agent_filter": {
                    "type": "string",
                    "description": "按智能体过滤 (可选)",
                },
                "trace_filter": {
                    "type": "string",
                    "description": "按 trace_id 过滤 (可选)",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
]

# ── 意图关键词映射 ────────────────────────────────────

INTENT_PATTERNS = {
    "审计/诊断": [
        "审计",
        "诊断",
        "检查",
        "排查",
        "验证",
        "测试",
        "scan",
        "audit",
        "check",
        "diagnose",
    ],
    "记忆操作": [
        "记忆",
        "记住",
        "回忆",
        "存储",
        "记忆体",
        "memory",
        "remember",
        "recall",
    ],
    "Agent调度": ["调度", "分发", "Agent", "指派", "dispatch", "assign"],
    "系统管理": [
        "部署",
        "配置",
        "重启",
        "启动",
        "停止",
        "deploy",
        "restart",
        "start",
        "stop",
    ],
    "代码开发": [
        "开发",
        "实现",
        "修复",
        "编写",
        "重构",
        "code",
        "implement",
        "fix",
        "refactor",
    ],
    "知识查询": [
        "搜索",
        "查询",
        "查找",
        "什么是",
        "如何",
        "search",
        "query",
        "what",
        "how",
    ],
    "安全扫描": ["安全", "漏洞", "扫描", "合规", "security", "vulnerability", "scan"],
    "性能分析": ["性能", "优化", "加速", "performance", "optimize", "profile"],
    "数据分析": ["分析", "统计", "图表", "趋势", "analysis", "statistics", "chart"],
    "灵境相关": ["灵境", "道谱", "三链", "lingjing"],
}

AGENT_CAPABILITIES = {
    "tianji": {
        "keywords": ["系统", "全局", "编排", "调度", "天机"],
        "description": "总控核心",
    },
    "tianshu": {
        "keywords": ["任务", "编排", "Agent调度", "TVP"],
        "description": "智能任务编排",
    },
    "dongcha": {
        "keywords": ["意图", "感知", "分析", "理解"],
        "description": "意图感知器",
    },
    "jingwei": {
        "keywords": ["架构", "设计", "选型", "技术决策"],
        "description": "架构师",
    },
    "yiku": {
        "keywords": ["记忆", "记忆体", "memory", "存储"],
        "description": "记忆管理中心",
    },
    "kuangshi": {
        "keywords": ["数据", "语料", "采集", "数据处理"],
        "description": "数据处理工厂",
    },
    "miaobi": {
        "keywords": ["创作", "生成", "内容", "写作"],
        "description": "核心创作引擎",
    },
    "mingjing": {
        "keywords": ["审计", "审查", "质量", "审核"],
        "description": "质量审核专家",
    },
    "qianli": {"keywords": ["监控", "健康", "告警"], "description": "系统监控之眼"},
    "tiansuan": {"keywords": ["统计", "分析", "数据"], "description": "数据分析大脑"},
    "tiewei": {"keywords": ["测试", "验证", "Gate"], "description": "安全门禁卫士"},
    "zhenshan": {"keywords": ["安全", "漏洞", "合规"], "description": "安全审计专家"},
    "zhuiguang": {"keywords": ["性能", "优化", "加速"], "description": "性能优化大师"},
    "gongzao": {"keywords": ["部署", "运维", "环境"], "description": "DevOps工程师"},
    "shiguan": {
        "keywords": ["版本", "发布", "审批", "历史"],
        "description": "版本控制专家",
    },
    "luling": {"keywords": ["律令", "规则", "合规"], "description": "律令执行器"},
    "wenzong": {"keywords": ["标准", "规范", "质量"], "description": "主编/标准制定"},
    "jinshu": {"keywords": ["导出", "交付", "格式化"], "description": "成品导出专家"},
    "baiqiao": {"keywords": ["技能", "MCP", "调度"], "description": "技能调度大师"},
    "huasheng": {"keywords": ["进化", "改进", "升级"], "description": "进化工程师"},
    "lianli": {
        "keywords": ["知识图谱", "抽取", "图谱"],
        "description": "知识图谱构建师",
    },
    "lingxi": {
        "keywords": ["对话", "完整性", "上下文"],
        "description": "对话完整性守护者",
    },
    "wanxiang": {"keywords": ["图像", "多模态", "识别"], "description": "多模态感知师"},
}


def _load_agent_capabilities_from_registry() -> dict:
    """从 _AGENT_REGISTRY.json 动态加载 Agent 能力矩阵

    注册表中的 capabilities 字段转换为 keywords，description 取自简介
    优先级高于硬编码 AGENT_CAPABILITIES
    """
    registry_path = Path(PROJECT_ROOT) / ".trae" / "agents" / "_AGENT_REGISTRY.json"
    if not registry_path.exists():
        return {}
    try:
        with open(registry_path, encoding="utf-8-sig") as f:
            data = json.load(f)
        result = {}
        for aid, info in data.get("agents", {}).items():
            caps = info.get("capabilities", [])
            tools_list = info.get("tools", [])
            keywords = []
            for c in caps:
                if isinstance(c, str):
                    keywords.append(c)
                    parts = c.replace("_", " ").split()
                    keywords.extend(parts)
            for t in tools_list:
                if isinstance(t, str):
                    keywords.append(t)
                    parts = t.replace("_", " ").split()
                    keywords.extend(parts)
            name = info.get("name", "")
            role = info.get("role", "")
            if name:
                keywords.append(name)
            if role:
                keywords.append(role)
            description = info.get("description") or name or aid
            result[aid] = {
                "keywords": list(dict.fromkeys(k for k in keywords if len(k) >= 1)),
                "description": description,
                "source": info.get("source", "registry"),
                "role": role,
                "tier": info.get("tier", ""),
            }
        return result
    except Exception:
        return {}


def _build_merged_capabilities() -> dict:
    """合并注册表能力 + 硬编码基线，关键词合并去重，description 注册表优先"""
    merged = {}
    for k, v in AGENT_CAPABILITIES.items():
        merged[k] = dict(v)
    registry_caps = _load_agent_capabilities_from_registry()
    for k, v in registry_caps.items():
        if k in merged:
            existing_kws = merged[k].get("keywords", [])
            new_kws = v.get("keywords", [])
            combined = list(dict.fromkeys(existing_kws + new_kws))
            merged[k].update(v)
            merged[k]["keywords"] = combined
        else:
            merged[k] = v
    return merged


class AgentFrameworkServer:
    """自包含 Agent 调度框架 MCP Server"""

    _merged_capabilities_cache: dict = {}
    _merged_capabilities_mtime: float = 0.0

    def __init__(self):
        self.api_url = TIANJI_API_URL
        self._api_available = False
        self._check_api()
        self._capabilities = self._get_merged_capabilities()

    def _get_merged_capabilities(self) -> dict:
        """获取合并后的能力矩阵（带文件变更检测）"""
        registry_path = Path(PROJECT_ROOT) / ".trae" / "agents" / "_AGENT_REGISTRY.json"
        try:
            mtime = registry_path.stat().st_mtime if registry_path.exists() else 0.0
        except Exception:
            mtime = 0.0

        if self._merged_capabilities_cache and mtime == self._merged_capabilities_mtime:
            return self._merged_capabilities_cache

        merged = _build_merged_capabilities()
        AgentFrameworkServer._merged_capabilities_cache = merged
        AgentFrameworkServer._merged_capabilities_mtime = mtime
        return merged

    # ── API 通信 ──────────────────────────────────────

    def _check_api(self):
        # [FIX-v9.1-conn-leak] with语句确保连接关闭
        try:
            req = urllib.request.Request(f"{self.api_url}/api/health")
            with urllib.request.urlopen(req, timeout=3) as r:
                self._api_available = r.status == 200
        except Exception:
            self._api_available = False

    def _api_get(self, path: str) -> dict:
        """GET 请求天机后端（仅限已验证可用的端点）"""
        # [FIX-v9.1-conn-leak] with语句确保连接关闭
        try:
            req = urllib.request.Request(f"{self.api_url}{path}")
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8-sig", errors="replace"))
        except Exception as e:
            return {"error": str(e)}

    # ── MCP 协议 ──────────────────────────────────────

    def _make_response(self, result=None, error=None, req_id=None):
        response = {"jsonrpc": "2.0"}
        if req_id is not None:
            response["id"] = req_id
        if error:
            response["error"] = (
                error
                if isinstance(error, dict)
                else {"code": -32603, "message": str(error)}
            )
        elif result is not None:
            response["result"] = result
        return response

    def handle_initialize(self, params, req_id):
        return self._make_response(
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {
                    "name": "agent-framework-global",
                    "version": SYSTEM_VERSION,
                    "system": SYSTEM_NAME,
                    "mode": "self-contained",
                    "api_available": self._api_available,
                    "tool_count": len(SERVER_TOOLS),
                },
            },
            req_id=req_id,
        )

    def handle_tools_list(self, params, req_id):
        return self._make_response({"tools": SERVER_TOOLS}, req_id=req_id)

    def handle_tools_call(self, params, req_id):
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        if not self._api_available:
            self._check_api()
        handler_map = {
            "context_extract": self._handle_context_extract,
            "agent_dispatch": self._handle_agent_dispatch,
            "system_status": self._handle_system_status,
            "rule_evaluate": self._handle_rule_evaluate,
            "pipeline_create": self._handle_pipeline_create,
            # VAP v2.0 工具
            "vap_declare": self._handle_vap_declare,
            "vap_handoff": self._handle_vap_handoff,
            "vap_summary": self._handle_vap_summary,
            "vap_recall": self._handle_vap_recall,
        }
        handler = handler_map.get(name)
        if not handler:
            return self._make_response(
                error={"code": -32601, "message": f"Unknown tool: {name}"},
                req_id=req_id,
            )
        try:
            result = handler(arguments)
            return self._make_response(
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2),
                        }
                    ]
                },
                req_id=req_id,
            )
        except Exception as e:
            return self._make_response(
                error={"code": -32603, "message": str(e)}, req_id=req_id
            )

    # ── 工具实现 (自包含) ─────────────────────────────

    def _handle_context_extract(self, args: dict) -> dict:
        """自包含上下文提取：关键词 + 意图 + 实体

        [FIX-CONTEXT-EXTRACT] 修复input_length=0问题:
        - 兼容多种参数名: user_input/text/content/query
        - 确保非空输入正确接收
        """
        # 兼容多种参数名 (用户可能传text/user_input/content/query)
        user_input = (
            args.get("user_input")
            or args.get("text")
            or args.get("content")
            or args.get("query")
            or ""
        )
        # 若用户直接传字符串而非dict
        if isinstance(args, str):
            user_input = args
        extra_context = args.get("context", "")

        # 关键词提取 (基于 TF-IDF 简化：长度加权 + 中文分词模拟)
        keywords = self._extract_keywords(user_input)

        # 意图检测
        intent = self._detect_intent(user_input)

        # 实体提取
        entities = self._extract_entities(user_input)

        return {
            "status": "success",
            "input_length": len(user_input),
            "keywords": keywords[:10],
            "primary_intent": intent["primary"],
            "intent_scores": intent["scores"],
            "entities": entities,
            "language": "zh"
            if any("\u4e00" <= c <= "\u9fff" for c in user_input)
            else "en",
            "system": SYSTEM_NAME,
        }

    def _extract_keywords(self, text: str) -> list:
        """简化关键词提取"""
        # 移除标点，按空格/标点分词
        cleaned = re.sub(r"[^\u4e00-\u9fff\w]", " ", text)
        words = [w.strip() for w in cleaned.split() if len(w.strip()) >= 2]

        # 按长度和位置加权
        scored = {}
        for i, w in enumerate(words):
            score = len(w) * 1.0 + (1.0 / (i + 1)) * 2  # 靠前 + 长词 加权
            scored[w] = scored.get(w, 0) + score

        return sorted(scored, key=scored.get, reverse=True)[:10]

    def _detect_intent(self, text: str) -> dict:
        """意图检测"""
        text_lower = text.lower()
        scores = {}
        for intent, patterns in INTENT_PATTERNS.items():
            score = 0
            for p in patterns:
                if p.lower() in text_lower:
                    score += 1
            if score > 0:
                scores[intent] = score

        sorted_intents = sorted(scores, key=scores.get, reverse=True)
        return {
            "primary": sorted_intents[0] if sorted_intents else "通用对话",
            "scores": {k: v for k, v in sorted(scores.items(), key=lambda x: -x[1])},
            "all_detected": sorted_intents,
        }

    def _extract_entities(self, text: str) -> dict:
        """实体提取"""
        entities = {}

        # 文件路径
        path_patterns = [
            r"[A-Za-z]:\\[^\s,，。；;]+",
            r"(?:\.{1,2}[/\\])+[^\s,，。；;]+",
        ]
        paths = []
        for pat in path_patterns:
            paths.extend(re.findall(pat, text))
        if paths:
            entities["file_paths"] = paths[:5]

        # URL
        urls = re.findall(r"https?://[^\s,，。；;]+", text)
        if urls:
            entities["urls"] = urls[:5]

        # 时间戳
        timestamps = re.findall(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?", text)
        if timestamps:
            entities["timestamps"] = timestamps[:5]

        # 端口号
        ports = re.findall(r"(?::|端口\s*)(\d{4,5})", text)
        if ports:
            entities["ports"] = list(set(ports))[:5]

        # PID
        pids = re.findall(r"PID[:\s]*(\d+)", text)
        if pids:
            entities["pids"] = pids[:5]

        return entities

    def _handle_agent_dispatch(self, args: dict) -> dict:
        """自包含 Agent 调度：扫描本地 Agent 定义 + 关键词匹配 + 可用性降级 + TVP声明"""
        task_type = args.get("task_type", "")
        task_data = args.get("task_data", {})
        priority = args.get("priority", "medium")
        from_agent = args.get("from_agent", "system")
        min_confidence = args.get("min_confidence_score", 1)

        available_agents = self._scan_agents()
        available_set = set(available_agents)

        caps = self._capabilities
        agent_name = args.get("agent_name", "")
        if agent_name and agent_name in caps:
            info = caps[agent_name]
            is_available = agent_name in available_set
            base_pick = {
                "agent": agent_name,
                "description": info["description"],
                "score": 10,
                "matched_keywords": info["keywords"],
                "available": is_available,
                "dispatch_mode": "direct",
            }
            if is_available:
                top_pick = base_pick
            else:
                top_pick = self._ensure_available_top_pick([base_pick])
                top_pick["dispatch_mode"] = "direct_degraded"
            self._declare_tvp_to_container(
                from_agent=from_agent,
                to_agent=top_pick["agent"],
                task_type=task_type,
                priority=priority,
            )
            return {
                "status": "success",
                "task_type": task_type,
                "priority": priority,
                "recommendations": [base_pick],
                "top_pick": top_pick,
                "fallback_pick": top_pick if top_pick.get("is_fallback") else None,
                "available_agents_count": len(available_agents),
                "available_agents": sorted(available_set)[:10],
                "dispatch_mode": top_pick.get("dispatch_mode", "direct"),
                "degraded": top_pick.get("degraded", False),
                "system": SYSTEM_NAME,
            }

        EN_KEYWORD_MAP = {
            "diagnostic": ["审计", "审查", "质量", "监控", "健康"],
            "debug": ["测试", "验证", "Gate"],
            "deploy": ["部署", "运维", "环境"],
            "analyze": ["分析", "数据", "统计"],
            "design": ["架构", "设计", "选型"],
            "create": ["创作", "生成", "内容"],
            "memory": ["记忆", "存储", "memory"],
            "security": ["安全", "漏洞", "合规"],
            "performance": ["性能", "优化", "加速"],
            "evolve": ["进化", "改进", "升级"],
            "dialogue": ["对话", "完整性", "上下文"],
            "schedule": ["调度", "编排", "任务"],
        }

        matches = []
        task_lower = task_type.lower()
        extended_task = task_lower
        for en_kw, cn_kws in EN_KEYWORD_MAP.items():
            if en_kw in task_lower:
                extended_task = extended_task + " " + " ".join(cn_kws)

        for a_name, info in caps.items():
            score = 0
            matched_kw = []
            for kw in info["keywords"]:
                if kw.lower() in extended_task:
                    score += 1
                    matched_kw.append(kw)
            if score > 0:
                matches.append(
                    {
                        "agent": a_name,
                        "description": info["description"],
                        "score": score,
                        "matched_keywords": matched_kw,
                        "available": a_name in available_set,
                    }
                )

        matches.sort(key=lambda x: -x["score"])
        high_conf_matches = [m for m in matches if m["score"] >= min_confidence]
        top_pick = self._ensure_available_top_pick(
            high_conf_matches if high_conf_matches else matches,
            min_score=min_confidence,
        )

        if high_conf_matches:
            recs = high_conf_matches[:5]
        elif top_pick.get("is_fallback"):
            recs = [top_pick]
        else:
            recs = matches[:5]

        self._declare_tvp_to_container(
            from_agent=from_agent,
            to_agent=top_pick["agent"],
            task_type=task_type,
            priority=priority,
        )

        return {
            "status": "success",
            "task_type": task_type,
            "priority": priority,
            "recommendations": recs,
            "top_pick": top_pick,
            "fallback_pick": top_pick if top_pick.get("is_fallback") else None,
            "available_agents_count": len(available_agents),
            "available_agents": available_agents[:10],
            "degraded": top_pick.get("degraded", False),
            "fallback_reason": top_pick.get("fallback_reason", ""),
            "low_confidence": top_pick.get("low_confidence", False),
            "min_confidence_score": min_confidence,
            "system": SYSTEM_NAME,
        }

    def _declare_tvp_to_container(
        self, from_agent: str, to_agent: str, task_type: str, priority: str = "medium"
    ):
        """通过容器TraeAgentScheduler记录TVP声明"""
        try:
            from core.shared.tianji_container import get_container

            c = get_container()
            if c:
                tas_mod = c._modules.get("trae_agent_scheduler")
                if tas_mod and tas_mod.instance:
                    tas_mod.instance.declare_tvp(
                        {
                            "from_agent": from_agent,
                            "to_agent": to_agent,
                            "task_type": task_type,
                            "context": f"MCP agent_dispatch: {task_type[:40]}",
                            "priority": priority,
                        }
                    )
        except Exception:
            pass  # 静默失败, 不影响调度主流程

    _agent_scan_cache: list = []
    _agent_scan_cache_time: float = 0.0
    _AGENT_SCAN_CACHE_TTL: float = 300.0

    def _normalize_agent_id(self, file_stem: str) -> str:
        """将文件名规范化为能力矩阵中的Agent ID

        处理规则:
        1. 去掉 trae-official- / trae- / qoder- 等前缀
        2. 与合并后的能力矩阵 key 做精确匹配
        3. 未匹配则返回去前缀后的 stem（兜底，连字符ID等）
        """
        known_ids = set(self._capabilities.keys())
        if file_stem in known_ids:
            return file_stem

        prefixes = ["trae-official-", "trae-", "qoder-official-", "qoder-"]
        stem_lower = file_stem.lower()
        for prefix in prefixes:
            if stem_lower.startswith(prefix):
                stripped = stem_lower[len(prefix) :]
                if stripped in known_ids:
                    return stripped

        for aid in known_ids:
            if aid.lower() == stem_lower:
                return aid

        for prefix in prefixes:
            if stem_lower.startswith(prefix):
                return stem_lower[len(prefix) :]

        return file_stem

    def _scan_agents(self) -> list:
        """扫描本地 Agent 定义文件（带5分钟缓存）"""
        import time as _t

        now = _t.time()
        if (
            self._agent_scan_cache
            and now - self._agent_scan_cache_time < self._AGENT_SCAN_CACHE_TTL
        ):
            return self._agent_scan_cache

        agents = set()
        search_dirs = [
            Path(PROJECT_ROOT) / ".qoder" / "agents",
            Path(PROJECT_ROOT) / ".trae" / "agents",
        ]
        for d in search_dirs:
            if d.exists():
                for f in d.glob("*.md"):
                    if f.stem.startswith("_"):
                        continue
                    agents.add(self._normalize_agent_id(f.stem))
                for f in d.glob("*.json"):
                    if f.stem.startswith("_"):
                        continue
                    agents.add(self._normalize_agent_id(f.stem))

        result = sorted(agents)
        self._agent_scan_cache = result
        self._agent_scan_cache_time = now
        return result

    def _ensure_available_top_pick(self, matches: list, min_score: int = 1) -> dict:
        """从匹配列表中选出第一个可用Agent，全不可用时返回兜底

        Args:
            matches: 匹配列表
            min_score: 最低匹配分数阈值，低于此值标记为低置信度

        返回: top_pick 字典，增加 degraded/fallback_reason/low_confidence 字段
        """
        caps = self._capabilities
        if not matches:
            return {
                "agent": "tianshu",
                "description": caps.get("tianshu", {}).get(
                    "description", "智能任务编排"
                ),
                "score": 0,
                "matched_keywords": [],
                "available": "tianshu" in self._scan_agents(),
                "degraded": True,
                "fallback_reason": "no_matching_agents",
                "is_fallback": True,
                "low_confidence": True,
            }

        available = [m for m in matches if m.get("available", False)]
        if available:
            pick = available[0]
            if pick.get("score", 0) < min_score:
                pick = dict(pick)
                pick["low_confidence"] = True
            return pick

        first = matches[0]
        fallback_info = caps.get("tianshu", {})
        return {
            "agent": "tianshu",
            "description": fallback_info.get("description", "智能任务编排"),
            "score": 0,
            "matched_keywords": [],
            "available": "tianshu" in self._scan_agents(),
            "degraded": True,
            "fallback_reason": f"top_pick_{first['agent']}_unavailable",
            "original_top_pick": first["agent"],
            "is_fallback": True,
            "low_confidence": True,
        }

    def _handle_system_status(self, args: dict) -> dict:
        """自包含系统状态：后端健康 + 本地资源扫描"""
        # 后端健康
        health = (
            self._api_get("/api/health")
            if self._api_available
            else {"error": "API unavailable"}
        )

        # 本地资源
        root = Path(PROJECT_ROOT)

        def count_dir(p: Path) -> int:
            return len(list(p.rglob("*"))) if p.exists() else 0

        def count_files(p: Path, pattern: str) -> int:
            return len(list(p.glob(pattern))) if p.exists() else 0

        return {
            "status": "success",
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "backend": {
                "url": self.api_url,
                "available": self._api_available,
                "health": health.get("status", "unknown")
                if isinstance(health, dict)
                else str(health)[:200],
                "version": health.get("version", "?")
                if isinstance(health, dict)
                else "?",
                "uptime_hours": round(health.get("uptime_seconds", 0) / 3600, 1)
                if isinstance(health, dict)
                else 0,
                "total_entries": health.get("total_entries", 0)
                if isinstance(health, dict)
                else 0,
            },
            "agents": {
                "qoder_agents": count_files(root / ".qoder" / "agents", "*.md"),
                "trae_agents": count_files(root / ".trae" / "agents", "*.json"),
                "python_agents": count_files(root / "agents", "*.py"),
            },
            "rules": {
                "qoder_rules": count_files(root / ".qoder" / "rules", "*.md"),
                "trae_rules": count_files(root / ".trae" / "rules", "*.md"),
            },
            "skills": {
                "qoder_skills": count_dir(root / ".agents" / "skills"),
                "manifest_skills": 45,  # From _manifest.json
            },
            "mcp_servers": 6,
            "modules": {
                "core_files": count_files(root / "core", "*.py"),
                "api_routes": count_files(root / "server" / "api", "*.py"),
                "adapters": count_files(root / "adapters", "*.py"),
            },
            "system": SYSTEM_NAME,
            "version": SYSTEM_VERSION,
        }

    def _handle_rule_evaluate(self, args: dict) -> dict:
        """自包含规则评估：加载规则文件 + 基本合规检查"""
        rule_name = args.get("rule_name", "")
        context = args.get("context", {})

        # 搜索规则文件
        rule_file = self._find_rule(rule_name)
        if not rule_file:
            return {
                "status": "error",
                "rule_name": rule_name,
                "error": f"未找到规则: {rule_name}",
                "available_rules": self._list_rules(),
            }

        # 读取规则内容
        try:
            content = rule_file.read_text(encoding="utf-8-sig", errors="replace")
        except Exception as e:
            return {
                "status": "error",
                "rule_name": rule_name,
                "error": f"读取失败: {e}",
            }

        # 提取规则约束
        constraints = self._parse_constraints(content)
        compliance = self._evaluate_compliance(constraints, context)

        return {
            "status": "success",
            "rule_name": rule_name,
            "rule_file": str(rule_file.relative_to(PROJECT_ROOT)),
            "rule_size_bytes": rule_file.stat().st_size,
            "constraints_found": len(constraints),
            "constraints": constraints,
            "context_provided": bool(context),
            "compliance": compliance,
            "system": SYSTEM_NAME,
        }

    def _find_rule(self, name: str) -> Path:
        """查找规则文件"""
        search_dirs = [
            Path(PROJECT_ROOT) / ".qoder" / "rules",
            Path(PROJECT_ROOT) / ".trae" / "rules",
        ]
        name_lower = name.lower()

        for d in search_dirs:
            if not d.exists():
                continue
            # 精确匹配
            exact = d / f"{name}.md"
            if exact.exists():
                return exact
            # 模糊匹配
            for f in sorted(d.glob("*.md")):
                if name_lower in f.stem.lower():
                    return f
        return None

    def _list_rules(self) -> list:
        """列出所有可用规则"""
        rules = []
        search_dirs = [
            Path(PROJECT_ROOT) / ".qoder" / "rules",
            Path(PROJECT_ROOT) / ".trae" / "rules",
        ]
        for d in search_dirs:
            if d.exists():
                for f in sorted(d.glob("*.md")):
                    rules.append(f.stem)
        return sorted(set(rules))

    def _parse_constraints(self, content: str) -> list:
        """从规则 Markdown 中提取约束/要求"""
        constraints = []
        # 先移除Markdown标题行(## 开头)和表格分隔行(|---|)，避免误提取
        clean_lines = []
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#") or re.match(r"^\|[-:| ]+\|$", stripped):
                continue
            # 移除包含多个管道符的元数据行(如 "P0-强制执行 | 激活: 始终生效 | 适用: 全局")
            if stripped.count("|") >= 2:
                continue
            clean_lines.append(line)
        clean_content = "\n".join(clean_lines)

        # 匹配 "必须"/"MUST"/"禁止"/"SHOULD"/"不得" 等约束语句
        patterns = [
            (r"(?:必须|MUST|一定|务必)\s*(.+?)(?:[。；\n]|$)", "强制"),
            (r"(?:禁止|不得|不允许|MUST NOT)\s*(.+?)(?:[。；\n]|$)", "禁止"),
            (r"(?:应该|建议|SHOULD|推荐)\s*(.+?)(?:[。；\n]|$)", "建议"),
            (r"(?:优先|PRIORITY|首要)\s*(.+?)(?:[。；\n]|$)", "优先"),
        ]
        for pat, level in patterns:
            for m in re.finditer(pat, clean_content):
                text = m.group(1).strip()[:120]
                # Filter out markdown formatting artifacts
                text = re.sub(r"\*{1,2}|\`{1,3}|\[|\]|\(|\)|/{1,2}", "", text).strip()
                # Skip if text looks like a header/metadata line (contains | or starts with :)
                if not text or len(text) < 4:
                    continue
                if text.startswith(":") or text.startswith("|") or text.startswith("-"):
                    continue
                # Skip if text contains pipe characters (likely metadata)
                if "|" in text:
                    continue
                if text in [c["text"] for c in constraints]:
                    continue
                constraints.append({"level": level, "text": text})

        return constraints[:20]

    def _evaluate_compliance(self, constraints: list, context: dict) -> dict:
        """评估上下文对规则的合规性

        [FIX-RULE-EVALUATE] 修复UNCHECKED状态问题:
        - 无context时: 使用规则自洽性检查 (规则本身存在即视为已声明)
        - 强制/建议级规则: 即使无关键词匹配, 也判定为"NEEDS_REVIEW"而非UNCHECKED
        - 禁止项: 严格反向检查
        - 统计unchecked数量, 提供明确verdict
        """
        # 无context时: 使用规则自洽性检查 (规则本身存在即视为已声明)
        rule_self_check = False
        if not context:
            rule_self_check = True
            context = {"rule_self_check": True}
        context_str = json.dumps(context, ensure_ascii=False).lower()

        passed = 0
        failed = 0
        unchecked = 0
        details = []

        for c in constraints:
            text_lower = c["text"].lower()
            level = c["level"]

            if level in ("禁止", "不能", "避免"):
                # 禁止项: 严格反向检查 - 是否在上下文中出现
                keywords = [
                    kw
                    for kw in re.split(r"[，。、；\s,;]+", text_lower)
                    if len(kw) >= 2
                ]
                violated = (
                    any(kw in context_str for kw in keywords) if keywords else False
                )
                status = "FAIL" if violated else "PASS"
                if violated:
                    failed += 1
                else:
                    passed += 1
            elif level in ("必须", "强制", "应当"):
                # 强制项: 关键词匹配+语义关联
                keywords = [
                    kw
                    for kw in re.split(r"[，。、；\s,;]+", text_lower)
                    if len(kw) >= 2
                ]
                matched = (
                    any(kw in context_str for kw in keywords) if keywords else False
                )
                # 强制项: 即使无关键词匹配, 也判定为"NEEDS_REVIEW"而非UNCHECKED
                if matched:
                    status = "PASS"
                    passed += 1
                elif rule_self_check:
                    # 自洽性检查: 规则本身存在即视为已声明
                    status = "PASS"
                    passed += 1
                else:
                    status = "NEEDS_REVIEW"
                    unchecked += 1
            else:
                # 建议/优先: 软性检查
                keywords = [
                    kw
                    for kw in re.split(r"[，。、；\s,;]+", text_lower)
                    if len(kw) >= 2
                ]
                matched = (
                    any(kw in context_str for kw in keywords) if keywords else False
                )
                status = "PASS" if matched else "INFO"
                if matched:
                    passed += 1
                else:
                    unchecked += 1

            details.append(
                {
                    "constraint": c["text"][:80],
                    "level": level,
                    "status": status,
                }
            )

        total_checked = passed + failed
        if failed > 0:
            verdict = "non_compliant"
            message = f"发现{failed}条不合规"
        elif unchecked > 0:
            verdict = "partially_compliant"
            message = f"已检查{total_checked}条约束, 通过{passed}, 待确认{unchecked}"
        else:
            verdict = "compliant"
            message = f"全部{total_checked}条约束通过"

        return {
            "verdict": verdict,
            "message": message,
            "total_constraints": len(constraints),
            "checked": total_checked,
            "passed": passed,
            "failed": failed,
            "unchecked": unchecked,
            "details": details,
        }

    def _handle_pipeline_create(self, args: dict) -> dict:
        """自包含流水线创建：构建Agent协作流水线定义"""
        pipeline_name = args.get("pipeline_name", "")
        stages = args.get("stages", [])
        mode = args.get("mode", "serial")

        if not pipeline_name:
            return {"status": "error", "error": "pipeline_name 为必填项"}
        if not stages or not isinstance(stages, list):
            return {"status": "error", "error": "stages 为必填项且需为非空列表"}

        # 验证阶段结构
        validated_stages = []
        for i, stage in enumerate(stages):
            if not isinstance(stage, dict):
                return {"status": "error", "error": f"阶段 {i} 必须为对象"}
            validated_stages.append(
                {
                    "stage_index": i,
                    "stage_name": stage.get("stage_name", f"stage_{i}"),
                    "agent": stage.get("agent", "@tianshu"),
                    "task_type": stage.get("task_type", "general"),
                }
            )

        # 模式校验
        valid_modes = ["serial", "parallel", "hierarchical"]
        if mode not in valid_modes:
            return {"status": "error", "error": f"mode 必须为: {valid_modes}"}

        # 生成流水线ID
        import time as _time

        pipeline_id = f"PL-{int(_time.time())}-{hash(pipeline_name) % 10000:04d}"

        return {
            "status": "success",
            "pipeline_id": pipeline_id,
            "pipeline_name": pipeline_name,
            "mode": mode,
            "stage_count": len(validated_stages),
            "stages": validated_stages,
            "created_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
            "system": SYSTEM_NAME,
            "version": SYSTEM_VERSION,
        }

    # ── VAP v2.0 工具实现 (智能调度可视化根基) ────────────
    # 设计参考: 2026年全球最新最优实践
    #   - W3C Trace Context (分布式追踪标准)
    #   - OpenTelemetry GenAI 语义约定 (2026-01合并)
    #   - Delegation Chain Attribution (Stacklok ToolHive)
    #   - Circuit Breaker (AutoGen MCP Architecture)
    # 真实集成: 直接调用 v9.1 后端 /api/memory/ 写入 L3 Episodic

    # NOTE: _vap_time / _vap_uuid 已在模块顶部 import (类体内 import 会
    # 导致方法无法访问 — Python 类体作用域不向方法暴露)
    # 会话级 VAP 状态 (单进程内保持追踪链)
    _vap_sessions: dict = {}

    def _generate_w3c_trace_id(self) -> str:
        """生成 W3C Trace Context 格式的 trace_id.

        W3C 格式: 00-{trace-id(32hex)}-{span-id(16hex)}-01
        参考: https://www.w3.org/TR/trace-context/
        """
        trace_id = _vap_uuid.uuid4().hex  # 32 hex chars
        span_id = _vap_uuid.uuid4().hex[:16]  # 16 hex chars
        return f"00-{trace_id}-{span_id}-01"

    def _generate_span_id(self) -> str:
        """生成 W3C Span ID (16 hex chars)."""
        return _vap_uuid.uuid4().hex[:16]

    def _vap_post_memory(self, payload: dict) -> dict:
        """调用 v9.1 /api/memory/ 真实写入记忆.

        Returns:
            {"success": bool, "memory_id": str, "error": str}
        """
        if not self._api_available:
            self._check_api()
        if not self._api_available:
            return {"success": False, "error": "v9.1 API 不可用"}
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{self.api_url}/api/memory/",
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8-sig", errors="replace"))
                return {"success": True, "memory_id": body.get("id", ""), "entry": body}
        except urllib.error.HTTPError as e:
            return {"success": False, "error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    def _vap_recall_memory(self, query: str, limit: int = 10) -> dict:
        """调用 v9.1 GET /api/platform/recall 检索记忆.

        v9.1 真实端点: GET /api/platform/recall?query=...&limit=...
        返回: List[MemoryResponse]
        """
        if not self._api_available:
            self._check_api()
        if not self._api_available:
            return {"success": False, "error": "v9.1 API 不可用", "results": []}
        try:
            import urllib.parse as _up

            params = _up.urlencode({"query": query, "limit": str(limit)})
            req = urllib.request.Request(
                f"{self.api_url}/api/platform/recall?{params}",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8-sig", errors="replace"))
                # /api/platform/recall 直接返回 list[MemoryResponse]
                if isinstance(body, list):
                    results = body
                else:
                    results = body.get("results", body.get("entries", []))
                return {"success": True, "results": results}
        except urllib.error.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP {e.code}: {e.reason}",
                "results": [],
            }
        except Exception as e:
            return {"success": False, "error": str(e)[:200], "results": []}

    def _vap_render_visualization(self, decl: dict) -> str:
        """渲染 VAP 可视化文本块 (Trae IDE 动态窗口可见).

        这就是'用户看到任意内容生成究竟由哪个智能体执行'的可视化输出。
        """
        agent = decl.get("agent", "unknown")
        kind = decl.get("content_kind", "text")
        task = decl.get("task_summary", "")
        status = decl.get("status", "executing")
        confidence = decl.get("confidence", 1.0)
        trace_id = decl.get("trace_id", "")
        event_id = decl.get("event_id", "")
        upstream = decl.get("upstream")
        downstream = decl.get("downstream")
        memory_id = decl.get("memory_id")
        delegation = decl.get("delegation_chain", [])

        # Emoji 映射 (最强视觉识别)
        agent_emoji = {
            "tianji": "\U0001f4a0",
            "tianshu": "\U0001f3af",
            "wenzong": "\U0001f4d6",
            "miaobi": "\U0001f589\ufe0f",
            "mingjing": "\U0001f9ea",
            "tiansuan": "\U0001f9ee",
            "jingwei": "\U0001f5fa\ufe0f",
            "kuangshi": "\u26cf\ufe0f",
            "yiku": "\U0001f4be",
            "dongcha": "\U0001f441\ufe0f",
            "luling": "\u2696\ufe0f",
            "lingxi": "\U0001f91d",
            "tiewei": "\U0001f6e1",
            "baiqiao": "\U0001f527",
            "shiguan": "\U0001f4da",
            "jinshu": "\U0001f4e6",
            "qianli": "\U0001f442",
            "gongzao": "\U0001f528",
            "zhenshan": "\U0001f6e1",
            "zhuiguang": "\u26a1",
            "human": "\U0001f464",
        }.get(agent, "\U0001f916")

        status_emoji = {
            "planning": "\U0001f4cb",
            "executing": "\u23f3",
            "reviewing": "\U0001f50d",
            "completed": "\u2705",
            "failed": "\u274c",
            "degraded": "\u26a0\ufe0f",
        }.get(status, "\u2753")

        # 数据流
        flow_parts = []
        if upstream:
            flow_parts.append(f"@{upstream}")
        flow_parts.append(f"@{agent}")
        if downstream:
            flow_parts.append(f"@{downstream}")
        flow = " \u2192 ".join(flow_parts)

        # 委派链
        chain_str = " \u2192 ".join(delegation) if delegation else "\u65e0"

        # 记忆锚点
        mem_anchor = f"L3#{memory_id[:12]}" if memory_id else "\u672a\u6301\u4e45\u5316"

        return (
            f"[VAP] {agent_emoji} \u5185\u5bb9\u751f\u6210\u5f52\u5c5e \u00b7 {decl.get('event_type', 'content_start')}\n"
            f"\u2500\u2500 {event_id} \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\u2502 \u667a\u80fd\u4f53: {agent_emoji} @{agent}\n"
            f"\u2502 \u5185\u5bb9: {kind}  \u72b6\u6001: {status_emoji} {status}\n"
            f"\u2502 \u4efb\u52a1: {task}\n"
            f"\u2502 \u6570\u636e\u6d41: {flow}\n"
            f"\u2502 \u59d4\u6d3e\u94fe: {chain_str}\n"
            f"\u2502 \u7f6e\u4fe1\u5ea6: {confidence * 100:.0f}%  \u8bb0\u5fc6\u951a\u70b9: {mem_anchor}\n"
            f"\u2502 TraceID: {trace_id}\n"
            f"\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        )

    def _handle_vap_declare(self, args: dict) -> dict:
        """VAP 内容归属声明 - 核心工具.

        1. 生成 W3C Trace Context (或延续已有 trace_id)
        2. 构建 OTel GenAI 语义元数据
        3. 真实写入 v9.1 L3 Episodic
        4. 返回可视化文本块 (用户在动态窗口看到)
        """
        agent = args.get("agent", "").strip()
        content_kind = args.get("content_kind", "text")
        task_summary = args.get("task_summary", "").strip()
        event_type = args.get("event_type", "content_start")
        status = args.get("status", "executing")
        confidence = float(args.get("confidence", 1.0))
        upstream = args.get("upstream")
        downstream = args.get("downstream")
        trace_id = args.get("trace_id", "")
        session_id = args.get("session_id", "")
        delegation_chain = args.get("delegation_chain", [])

        # 参数校验
        if not agent:
            return {"status": "error", "error": "agent 为必填项"}
        if not task_summary:
            return {"status": "error", "error": "task_summary 为必填项"}
        if len(task_summary) > 80:
            return {
                "status": "error",
                "error": f"task_summary 长度 {len(task_summary)} 超过 80",
            }
        if not 0.0 <= confidence <= 1.0:
            return {"status": "error", "error": f"confidence {confidence} 越界 [0,1]"}

        # W3C Trace Context: 延续或新建
        if not trace_id:
            trace_id = self._generate_w3c_trace_id()
        span_id = self._generate_span_id()
        event_id = f"vap-evt-{int(_vap_time.time() * 1000)}-{span_id[:6]}"

        # 委派链补全
        if not delegation_chain:
            delegation_chain = [agent]
        elif agent not in delegation_chain:
            delegation_chain = list(delegation_chain) + [agent]

        # 构建声明数据
        declaration = {
            "event_id": event_id,
            "event_type": event_type,
            "agent": agent,
            "content_kind": content_kind,
            "task_summary": task_summary,
            "status": status,
            "confidence": confidence,
            "upstream": upstream,
            "downstream": downstream,
            "trace_id": trace_id,
            "span_id": span_id,
            "session_id": session_id,
            "delegation_chain": delegation_chain,
            "timestamp": _vap_time.time(),
            "timestamp_iso": _vap_time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        # 写入 v9.1 L3 Episodic (真实持久化)
        memory_content = (
            f"[VAP] {event_type} by @{agent}: {task_summary} "
            f"| trace={trace_id[:24]} event={event_id} "
            f"| kind={content_kind} status={status} "
            f"| confidence={confidence:.2f} "
            f"| delegation={' \u2192 '.join(delegation_chain)}"
        )
        memory_payload = {
            "content": memory_content,
            "layer": "episodic",
            "tags": [
                "vap",
                f"agent:{agent}",
                event_type,
                content_kind,
                f"trace:{trace_id[:16]}",
            ],
            "priority": "high" if status in ("failed", "degraded") else "medium",
            "metadata": {
                "source": "vap_v2",
                "event_id": event_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "agent": agent,
                "event_type": event_type,
                "content_kind": content_kind,
                "status": status,
                "confidence": confidence,
                "upstream": upstream,
                "downstream": downstream,
                "delegation_chain": delegation_chain,
                # OTel GenAI 语义约定 (2026-01)
                "gen_ai.agent.name": agent,
                "gen_ai.operation.name": event_type,
                "gen_ai.tool.name": content_kind,
                "gen_ai.request.confidence": confidence,
            },
        }
        mem_result = self._vap_post_memory(memory_payload)
        declaration["memory_id"] = mem_result.get("memory_id")
        declaration["memory_persisted"] = mem_result.get("success", False)

        # 会话级状态更新
        if trace_id not in self._vap_sessions:
            self._vap_sessions[trace_id] = {
                "declarations": [],
                "created_at": _vap_time.time(),
                "session_id": session_id,
            }
        self._vap_sessions[trace_id]["declarations"].append(declaration)

        # 渲染可视化文本块
        visualization = self._vap_render_visualization(declaration)

        return {
            "status": "success",
            "event_id": event_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "memory_id": declaration.get("memory_id"),
            "memory_persisted": declaration.get("memory_persisted"),
            "visualization": visualization,
            "declaration": declaration,
            "system": SYSTEM_NAME,
            "version": SYSTEM_VERSION,
        }

    def _handle_vap_handoff(self, args: dict) -> dict:
        """VAP Agent 切换声明 - 传播 W3C Trace + 委派链."""
        from_agent = args.get("from_agent", "").strip()
        to_agent = args.get("to_agent", "").strip()
        task_type = args.get("task_type", "").strip()
        context_summary = args.get("context_summary", "")
        trace_id = args.get("trace_id", "")
        handoff_mode = args.get("handoff_mode", "delegate")

        if not from_agent or not to_agent:
            return {"status": "error", "error": "from_agent 和 to_agent 为必填项"}
        if not task_type:
            return {"status": "error", "error": "task_type 为必填项"}
        if handoff_mode not in ("transfer", "return", "delegate", "escalate"):
            return {"status": "error", "error": f"handoff_mode 非法: {handoff_mode}"}

        # 延续或新建 trace_id
        if not trace_id:
            trace_id = self._generate_w3c_trace_id()
        span_id = self._generate_span_id()
        event_id = f"vap-handoff-{int(_vap_time.time() * 1000)}-{span_id[:6]}"

        # 构建委派链
        delegation_chain = [from_agent, to_agent]

        # 可视化
        from_emoji = {
            "tianshu": "\U0001f3af",
            "miaobi": "\U0001f589\ufe0f",
            "yiku": "\U0001f4be",
        }.get(from_agent, "\U0001f916")
        to_emoji = {
            "tianshu": "\U0001f3af",
            "miaobi": "\U0001f589\ufe0f",
            "yiku": "\U0001f4be",
            "wenzong": "\U0001f4d6",
            "jingwei": "\U0001f5fa\ufe0f",
        }.get(to_agent, "\U0001f916")
        mode_emoji = {
            "transfer": "\u27a1\ufe0f",
            "return": "\u2b05\ufe0f",
            "delegate": "\U0001f91d",
            "escalate": "\u2b06\ufe0f",
        }.get(handoff_mode, "\u2753")

        visualization = (
            f"[VAP] {mode_emoji} Agent\u5207\u6362\u58f0\u660e \u00b7 {handoff_mode}\n"
            f"\u2500\u2500 {event_id} \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\u2502 {from_emoji} @{from_agent} \u2192 {to_emoji} @{to_agent}\n"
            f"\u2502 \u4efb\u52a1: {task_type}\n"
            f"\u2502 \u4e0a\u4e0b\u6587: {context_summary or '\u65e0'}\n"
            f"\u2502 \u6a21\u5f0f: {mode_emoji} {handoff_mode}\n"
            f"\u2502 TraceID: {trace_id}\n"
            f"\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        )

        # 写入 v9.1 L3
        memory_content = (
            f"[VAP-HANDOFF] {handoff_mode}: @{from_agent} \u2192 @{to_agent} "
            f"| task={task_type} | trace={trace_id[:24]}"
        )
        mem_result = self._vap_post_memory(
            {
                "content": memory_content,
                "layer": "episodic",
                "tags": [
                    "vap",
                    "handoff",
                    f"from:{from_agent}",
                    f"to:{to_agent}",
                    handoff_mode,
                ],
                "priority": "high" if handoff_mode == "escalate" else "medium",
                "metadata": {
                    "source": "vap_v2",
                    "event_type": "agent_switch",
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "handoff_mode": handoff_mode,
                    "trace_id": trace_id,
                    "gen_ai.agent.name": to_agent,
                    "gen_ai.operation.name": "agent_switch",
                },
            }
        )

        # 会话级状态
        if trace_id not in self._vap_sessions:
            self._vap_sessions[trace_id] = {
                "declarations": [],
                "created_at": _vap_time.time(),
            }
        self._vap_sessions[trace_id]["declarations"].append(
            {
                "event_id": event_id,
                "event_type": "agent_switch",
                "from_agent": from_agent,
                "to_agent": to_agent,
                "handoff_mode": handoff_mode,
                "trace_id": trace_id,
                "memory_id": mem_result.get("memory_id"),
            }
        )

        return {
            "status": "success",
            "event_id": event_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "memory_id": mem_result.get("memory_id"),
            "memory_persisted": mem_result.get("success", False),
            "visualization": visualization,
            "system": SYSTEM_NAME,
        }

    def _handle_vap_summary(self, args: dict) -> dict:
        """VAP 会话追踪摘要."""
        trace_id = args.get("trace_id", "")
        limit = min(max(int(args.get("limit", 50)), 1), 100)

        if trace_id and trace_id in self._vap_sessions:
            session = self._vap_sessions[trace_id]
            decls = session["declarations"][-limit:]
        else:
            # 返回最近的会话
            if not self._vap_sessions:
                return {
                    "status": "success",
                    "total_sessions": 0,
                    "message": "\u65e0VAP\u4f1a\u8bdd\u8bb0\u5f55",
                    "visualization": "[VAP] \U0001f4cb \u4f1a\u8bdd\u6458\u8981 \u00b7 \u65e0\u8bb0\u5f55",
                }
            # 取最近会话
            latest_trace = max(
                self._vap_sessions.keys(),
                key=lambda k: self._vap_sessions[k].get("created_at", 0),
            )
            session = self._vap_sessions[latest_trace]
            decls = session["declarations"][-limit:]
            trace_id = latest_trace

        # 统计
        by_agent: dict = {}
        by_type: dict = {}
        for decl in decls:
            agent = decl.get("agent") or decl.get("from_agent", "?")
            by_agent[agent] = by_agent.get(agent, 0) + 1
            etype = decl.get("event_type", "?")
            by_type[etype] = by_type.get(etype, 0) + 1

        agent_lines = "\n".join(
            f"\u2502   @{a}: {c}"
            for a, c in sorted(by_agent.items(), key=lambda x: -x[1])
        )
        type_lines = "\n".join(
            f"\u2502   {t}: {c}"
            for t, c in sorted(by_type.items(), key=lambda x: -x[1])
        )

        visualization = (
            f"[VAP] \U0001f4cb \u4f1a\u8bdd\u8ffd\u8e2a\u6458\u8981 \u00b7 {trace_id[:24]}\n"
            f"\u2502 \u603b\u4e8b\u4ef6\u6570: {len(decls)}\n"
            f"\u2502 \u667a\u80fd\u4f53\u53c2\u4e0e:\n{agent_lines}\n"
            f"\u2502 \u4e8b\u4ef6\u5206\u5e03:\n{type_lines}\n"
            f"\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        )

        return {
            "status": "success",
            "trace_id": trace_id,
            "total_events": len(decls),
            "by_agent": by_agent,
            "by_type": by_type,
            "declarations": decls,
            "visualization": visualization,
            "system": SYSTEM_NAME,
        }

    def _handle_vap_recall(self, args: dict) -> dict:
        """VAP 声明检索 - 从 v9.1 L3 检索."""
        query = args.get("query", "").strip()
        agent_filter = args.get("agent_filter", "")
        trace_filter = args.get("trace_filter", "")
        limit = min(max(int(args.get("limit", 10)), 1), 50)

        if not query:
            return {"status": "error", "error": "query 为必填项"}

        # 增强 query
        enhanced_query = f"VAP {query}"
        if agent_filter:
            enhanced_query += f" agent:{agent_filter}"
        if trace_filter:
            enhanced_query += f" trace:{trace_filter}"

        result = self._vap_recall_memory(enhanced_query, limit=limit)

        if not result.get("success"):
            return {
                "status": "degraded",
                "error": result.get("error", "unknown"),
                "query": enhanced_query,
                "results": [],
            }

        entries = result.get("results", [])
        # 过滤 VAP 声明
        vap_entries = []
        for entry in entries:
            content = entry.get("content", "")
            tags = entry.get("tags", [])
            if "vap" in tags or "[VAP]" in content:
                # 应用过滤器
                if agent_filter:
                    entry_agent = entry.get("metadata", {}).get("agent", "")
                    if entry_agent != agent_filter:
                        continue
                if trace_filter:
                    entry_trace = entry.get("metadata", {}).get("trace_id", "")
                    if trace_filter not in entry_trace:
                        continue
                vap_entries.append(
                    {
                        "memory_id": entry.get("id"),
                        "content": content,
                        "agent": entry.get("metadata", {}).get("agent", "?"),
                        "trace_id": entry.get("metadata", {}).get("trace_id", ""),
                        "event_type": entry.get("metadata", {}).get("event_type", "?"),
                        "content_kind": entry.get("metadata", {}).get(
                            "content_kind", "?"
                        ),
                        "status": entry.get("metadata", {}).get("status", "?"),
                        "timestamp": entry.get("created_at"),
                        "tags": tags,
                    }
                )

        return {
            "status": "success",
            "query": enhanced_query,
            "total_found": len(vap_entries),
            "results": vap_entries,
            "system": SYSTEM_NAME,
        }

    # ── 主循环 ─────────────────────────────────────────

    def run(self):
        _STDERR.write(
            f"[{SYSTEM_NAME}] MCP Server v{SYSTEM_VERSION} starting (self-contained)...\n"
        )
        _STDERR.write(
            f"[{SYSTEM_NAME}] API: {self.api_url} (available: {self._api_available})\n"
        )
        _STDERR.write(f"[{SYSTEM_NAME}] Tools: {len(SERVER_TOOLS)}\n")
        _STDERR.write(f"[{SYSTEM_NAME}] Project: {PROJECT_ROOT}\n")
        _STDERR.flush()

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                continue

            method = request.get("method", "")
            params = request.get("params", {})
            req_id = request.get("id")

            if method == "initialize":
                response = self.handle_initialize(params, req_id)
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                response = self.handle_tools_list(params, req_id)
            elif method == "tools/call":
                response = self.handle_tools_call(params, req_id)
            elif method == "ping":
                response = self._make_response({"status": "ok"}, req_id=req_id)
            else:
                response = self._make_response(
                    error={"code": -32601, "message": f"Method not found: {method}"},
                    req_id=req_id,
                )

            _STDOUT.write(json.dumps(response, ensure_ascii=False) + "\n")
            _STDOUT.flush()


def main():
    server = AgentFrameworkServer()
    server.run()


if __name__ == "__main__":
    main()
