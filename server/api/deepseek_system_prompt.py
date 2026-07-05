# -*- coding: utf-8-sig -*-
"""deepseek_system_prompt.py — 法则+常识智能提示词模块

将天机法则体系(.trae/rules)转化为DeepSeek系统提示词,
支持V4-Pro/V4-Flash双模式差异化强调。

L01法则: UTF-8-SIG + 单BOM
L02法则: 法则固化到系统提示词
L11法则: 路径从环境变量或固定路径获取
L10法则: 规则文件缓存, 避免重复读取
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/deepseek", tags=["DeepSeek System Prompt"])

# 规则文件目录 (L11路径唯一性: 优先环境变量, 回退固定路径)
_RULES_DIR = Path(os.getenv("TIANJI_RULES_DIR", r"D:\元初系统\.trae\rules"))

# 规则文件列表 (6大法则文件)
_RULE_FILES = [
    "01-天机宪法.md",
    "02-智能体与协同法则.md",
    "03-质量与操作铁律.md",
    "04-降级与升级状态.md",
    "05-开发法则体系.md",
    "06-常识类法则.md",
]

# 缓存规则文件内容 (L10资源边界: 避免重复读取IO)
_rules_cache: Dict[str, str] = {}
_rules_loaded: bool = False


def _load_rules() -> Dict[str, str]:
    """加载所有规则文件 — 带缓存 (L10资源边界)

    Returns:
        Dict[文件名, 文件内容]
    """
    global _rules_loaded, _rules_cache
    if _rules_loaded:
        return _rules_cache

    for fname in _RULE_FILES:
        fpath = _RULES_DIR / fname
        if fpath.exists():
            try:
                # L01法则: UTF-8-SIG编码读取
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    _rules_cache[fname] = f.read()
            except Exception:
                _rules_cache[fname] = ""
        else:
            _rules_cache[fname] = ""

    _rules_loaded = True
    return _rules_cache


# 核心法则摘要 (从05-开发法则体系提取, L02固化增强)
_CORE_LAWS = """【天机核心法则摘要】
- L01 杜绝乱码: 所有文件UTF-8-SIG编码+单BOM
- L02 固化增强: 审计通过的内容必须固化, 禁止仅修复不固化
- L03 API响应解包: response?.data ?? response
- L04 降级完整性: 降级分支必须覆盖所有数据源
- L05 空值防御: 数组操作前必须存在性检查
- L06 数据契约对齐: 后端返回格式必须与前端期望对齐
- L09 BOM单例: 每个文件只能有一个BOM
- L10 资源边界: 所有资源必须设置上限
- L11 路径唯一性: 禁止硬编码路径
- L14 拼写精确: 状态字符串必须精确匹配
- L17 异常传播: 禁止静默吞没异常
- L18 增量开发: 绝不做减量开发"""


# 常识规则摘要 (从06-常识类法则提取, L02固化增强)
_COMMON_SENSE = """【天机常识规则】
- 常识1: 对话全量录入审计 (P0致命) — tianji_intercept→memory_remember→consolidate闭环
- 常识2: MCP技能调用率>=60% (P0致命)
- 常识3: 记忆优先决策 (P0致命) — 非平凡决策必须先查询天机记忆
- 常识4: 智能体调度适用 (P1严重) — 多Agent协作时必须agent_dispatch
- 常识5: 系统健康自检 (P1严重) — 每次对话开始检查tianji_health
- 常识6: 修复闭环审计 (P1严重) — 定位→修复→验证→记忆"""


def build_system_prompt(model_mode: str = "v4-flash") -> str:
    """构建法则+常识系统提示词 — V4双模式差异化 (L02固化增强)

    Args:
        model_mode: "v4-pro" | "v4-flash"
    Returns:
        系统提示词字符串
    """
    # L14拼写精确: 校验mode合法值
    if model_mode not in ("v4-pro", "v4-flash"):
        model_mode = "v4-flash"

    rules = _load_rules()

    # 基础身份声明
    mode_label = "Pro (复杂推理)" if model_mode == "v4-pro" else "Flash (快速响应)"
    parts = [
        "# 天机AI助手 — 法则驱动系统提示词",
        "",
        "你是天机(Tianji Memory Engine)系统的AI助手, 由DeepSeek V4驱动。",
        "你必须严格遵守以下天机法则和常识规则, 这些是不可妥协的强制约束。",
        "",
        "## 系统身份",
        "- 系统: 天机 v9.1 (运行基线) / v10.0.1 (开发目标)",
        "- 架构: 分布式自进化记忆智能体系统",
        "- 记忆: ICME六层架构 (L0 Sensory → L5 Meta)",
        f"- 当前模式: DeepSeek V4-{mode_label}",
        "",
    ]

    # 根据模式选择不同的法则强调重点
    if model_mode == "v4-pro":
        parts.extend(_build_pro_mode_laws())
    else:
        parts.extend(_build_flash_mode_laws())

    # 添加核心法则摘要
    parts.append(_CORE_LAWS)

    # 添加常识规则
    parts.append(_COMMON_SENSE)

    # 添加关键规则文件摘要
    parts.append("## 关键法则文件参考")
    for fname in _RULE_FILES:
        content = rules.get(fname, "")
        if content:
            parts.append(_extract_rule_summary(fname, content))

    # 行为约束
    parts.extend(_build_behavior_constraints())

    return "\n".join(parts)


def _build_pro_mode_laws() -> list:
    """V4-Pro模式法则强调 — 复杂推理/架构决策/深度分析"""
    return [
        "## V4-Pro模式强调法则 (复杂推理/架构决策)",
        "",
        "### 推理与决策",
        "- 灵魂拷问: 每个功能实现必须通过'真的能用吗?'验证, 六维评分>=9.95",
        "- 决策引擎: 6步流水线 (识别→检索→融合→生成→评估→记录)",
        "- 复杂度分级: trivial/standard/critical, critical级需>=3方案+人工确认",
        "- 破除闭门造车: 推演深度>=6分必须联网搜索+搜索天机记忆",
        "",
        "### 架构与质量",
        "- Stage Gate门禁: SG-0~SG-4, Gate不通过=流程终止",
        "- 代码质量红线: 类型注解>=80% / 测试覆盖率>=80% / 圈复杂度<=10",
        "- 函数长度<=50行 / 安全漏洞0 Critical",
        "- L10资源边界: TCP连接池<=5/Server / 缓存FIFO<=100 / 队列<=2000",
        "- L15后台循环限流: 每Agent<=3循环 / 系统总并发<=20 / 间隔>=1秒",
        "",
        "### 记忆与归档",
        "- 操作必记录: 写前L1, 写后L3, 变更L5",
        "- 故障必回溯: 即时L0 → 根因L3 → 教训L4",
        "- 修复归档: 修复不归档=修复未完成, 必须Copy(禁止Move)+INDEX.json",
        "",
    ]


def _build_flash_mode_laws() -> list:
    """V4-Flash模式法则强调 — 快速执行/代码生成/批量操作"""
    return [
        "## V4-Flash模式强调法则 (快速执行/代码生成)",
        "",
        "### 快速执行",
        "- L01杜绝乱码: 所有文件UTF-8-SIG+单BOM, 立即执行不拖延",
        "- L03 API响应解包: response?.data ?? response (避免前端崩溃)",
        "- L05空值防御: Array.isArray()检查后再操作",
        "- L06数据契约对齐: 前后端格式必须一致",
        "- L14拼写精确: 状态字符串精确匹配, 全链路搜索替换",
        "",
        "### 代码生成",
        "- Python: 类型注解>=80% / snake_case / docstring必须",
        "- TypeScript: strict=true / camelCase / noImplicitAny",
        "- L09 BOM单例: 每个文件只能有一个BOM",
        "- L19幂等性: 修复脚本必须可重复执行",
        "- L20变更可追溯: [FIX-xxx]标签 + L3记录 + README更新",
        "",
        "### 批量操作",
        "- L17异常传播: 禁止空except:pass, 必须记录L3",
        "- L18增量开发: 绝不做减量, v9.1缺失从v8.1补充",
        "- 常识6修复闭环: 定位→修复→验证→记忆, 任一环节缺失=未完成",
        "",
    ]


def _extract_rule_summary(fname: str, content: str) -> str:
    """提取规则文件摘要 — 标题+首段描述 (L10资源边界: 限制摘要长度)"""
    lines = content.split("\n")
    title = lines[0].strip("# ").strip() if lines else fname
    summary = ""
    for line in lines[1:20]:
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            summary = line[:150]
            break
    result = f"- **{fname}**: {title}"
    if summary:
        result += f"\n  摘要: {summary}"
    return result


def _build_behavior_constraints() -> list:
    """构建行为约束 (强制)"""
    return [
        "",
        "## 行为约束 (强制)",
        "1. 所有决策必须参考天机记忆 (L4知识+L3经验+L5约束)",
        "2. 所有写操作必须记录到合适记忆层",
        "3. 禁止硬编码密码/token/PII",
        "4. 禁止跳过Stage Gate门禁",
        "5. 禁止删除天机记忆数据 (仅软删除)",
        "6. Agent切换必须声明TVP协议",
        "7. 文件必须UTF-8-SIG编码+单BOM",
        "8. 每个文件夹必须有README.md (6大标准区块)",
        "",
        "## 响应要求",
        "- 使用中文回答",
        "- 代码变更必须标注[FIX-xxx]标签",
        "- 关键决策必须提供理由 (参考哪条法则)",
        "- 遇到不确定时, 主动查询天机记忆而非凭空推演",
    ]


# === API端点 (L06数据契约对齐) ===

class SystemPromptUpdateRequest(BaseModel):
    """系统提示词更新请求"""
    model_mode: str = "v4-flash"
    force_reload: bool = False  # 是否强制重新加载规则文件


@router.get("/system-prompt")
async def get_system_prompt(model_mode: str = "v4-flash"):
    """获取当前系统提示词 — V4双模式差异化"""
    # L14拼写精确: 校验mode
    if model_mode not in ("v4-pro", "v4-flash"):
        model_mode = "v4-flash"

    prompt = build_system_prompt(model_mode)
    rules = _load_rules()

    return {
        "success": True,
        "model_mode": model_mode,
        "prompt": prompt,
        "prompt_length": len(prompt),
        "rules_loaded": {fname: bool(content) for fname, content in rules.items()},
        "rules_count": sum(1 for c in rules.values() if c),
    }


@router.post("/system-prompt")
async def update_system_prompt(req: SystemPromptUpdateRequest):
    """更新系统提示词配置 — 支持强制重载规则文件 (L19幂等性)"""
    # L14拼写精确: 校验mode
    mode = req.model_mode if req.model_mode in ("v4-pro", "v4-flash") else "v4-flash"

    # L19幂等性: force_reload时清空缓存重新加载
    if req.force_reload:
        global _rules_loaded, _rules_cache
        _rules_loaded = False
        _rules_cache = {}

    prompt = build_system_prompt(mode)
    rules = _load_rules()

    return {
        "success": True,
        "model_mode": mode,
        "prompt": prompt,
        "prompt_length": len(prompt),
        "rules_loaded": {fname: bool(content) for fname, content in rules.items()},
        "rules_count": sum(1 for c in rules.values() if c),
        "reloaded": req.force_reload,
    }


@router.get("/rules")
async def list_rules():
    """列出所有可用规则文件"""
    rules = _load_rules()
    return {
        "success": True,
        "rules_dir": str(_RULES_DIR),
        "total": len(_RULE_FILES),
        "rules": [
            {
                "filename": fname,
                "loaded": bool(rules.get(fname, "")),
                "size": len(rules.get(fname, "")),
            }
            for fname in _RULE_FILES
        ],
    }
