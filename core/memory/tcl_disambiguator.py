# -*- coding: utf-8-sig -*-
"""TCL规范化 — 消歧器

从 tcl_normalizer.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-tcl-disamb-001] 延迟类型注解求值,避免TerminologyStore NameError

import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field

# [FIX-tcl-disamb-002] 显式导入 NormalizeResult/TermEntry/TerminologyStore (避免 NameError)
from .tcl_models import NormalizeResult, TermEntry
from .tcl_store import TerminologyStore


class TCLDisambiguator:
    """TCL消歧引擎 — Level 2实现"""

    def __init__(self, store: TerminologyStore, llm_bridge=None):
        self._store = store
        self._llm_bridge = llm_bridge

    def disambiguate(self, term: str, context: str = "") -> NormalizeResult:
        """
        多义词消歧

        Args:
            term: 待消歧的术语
            context: 上下文(当前句+前1句，Level 2标准)

        Returns:
            NormalizeResult: 消歧后的归一化结果
        """
        # 查找所有包含此术语的条目(作为别名或子串)
        candidates: list[tuple[TermEntry, float]] = []
        term_lower = term.lower()

        for entry in self._store.get_all_terms():
            score = 0.0
            # 精确别名匹配
            for alias in entry.aliases:
                if alias.lower() == term_lower:
                    score = 0.9
                    break
            # 规范术语子串
            if term_lower in entry.canonical_term.lower():
                score = max(score, 0.7)
            # 定义中包含
            if term_lower in entry.definition.lower():
                score = max(score, 0.5)

            if score > 0:
                # 上下文相关性加分
                if context:
                    ctx_lower = context.lower()
                    domain_keywords = self._get_domain_keywords(entry.domain)
                    for kw in domain_keywords:
                        if kw in ctx_lower:
                            score += 0.15
                    # 定义中的关键词出现在上下文中
                    def_words = entry.definition.lower().split()
                    for w in def_words:
                        if len(w) >= 2 and w in ctx_lower:
                            score += 0.05
                candidates.append((entry, min(score, 1.0)))

        if not candidates:
            return NormalizeResult(original=term, confidence=0.0, method="miss")

        # 按分数排序，取最高
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_entry, best_score = candidates[0]

        return NormalizeResult(
            original=term,
            canonical_id=best_entry.canonical_id,
            canonical_term=best_entry.canonical_term,
            confidence=best_score,
            method="disambiguate",
        )

    def _get_domain_keywords(self, domain: str) -> list[str]:
        """获取领域关键词(用于上下文消歧)"""
        domain_kw_map = {
            "tianji_core": ["记忆", "memory", "ICME", "六层", "层", "晋升", "固结"],
            "development": ["代码", "code", "模块", "module", "基点", "API", "接口"],
            "operations": ["部署", "deploy", "运维", "ops", "监控", "monitor"],
            "security": ["安全", "security", "权限", "permission", "审计", "audit"],
            "knowledge": ["知识", "knowledge", "图谱", "graph", "三元组", "triple"],
        }
        return domain_kw_map.get(domain, [])


# ---------------------------------------------------------------------------
# 天机核心术语种子数据(Level 2: 500条起步)
# ---------------------------------------------------------------------------

TIANJI_CORE_TERMS: list[dict] = [
    # --- 记忆架构 ---
    {
        "canonical_term": "ICME六层记忆架构",
        "aliases": [
            "六层记忆架构",
            "ICME系统",
            "天机记忆引擎",
            "Tianji Memory Engine",
            "六层模型",
            "ICME架构",
            "六层记忆",
            "记忆系统架构",
        ],
        "definition": "天机核心记忆存储架构，包含L0-L5六个认知层次",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "感枢层",
        "aliases": [
            "L0",
            "Sensory",
            "sensory",
            "感枢",
            "L0 Sensory",
            "L0感枢",
            "原始输入层",
            "感官层",
        ],
        "definition": "ICME第0层，原始输入缓存，3秒实时捕获，容量<10MB",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "运枢层",
        "aliases": [
            "L1",
            "Working",
            "working",
            "运枢",
            "L1 Working",
            "L1运枢",
            "工作记忆层",
            "会话上下文层",
        ],
        "definition": "ICME第1层，当前会话上下文，60s固结，容量<50MB",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "近枢层",
        "aliases": [
            "L2",
            "Short-Term",
            "short_term",
            "近枢",
            "L2 Short-Term",
            "L2近枢",
            "短期记忆层",
            "跨会话保持层",
        ],
        "definition": "ICME第2层，跨会话短期信息，120s固结，容量<100MB",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "忆枢层",
        "aliases": [
            "L3",
            "Episodic",
            "episodic",
            "忆枢",
            "L3 Episodic",
            "L3忆枢",
            "情景记忆层",
            "决策记录层",
        ],
        "definition": "ICME第3层，决策记录/AI经验，因果对存储，容量<500MB",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "知枢层",
        "aliases": [
            "L4",
            "Semantic",
            "semantic",
            "知枢",
            "L4 Semantic",
            "L4知枢",
            "语义记忆层",
            "知识图谱层",
        ],
        "definition": "ICME第4层，知识图谱/概念库，600s固结，容量<2GB",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "元枢层",
        "aliases": [
            "L5",
            "Meta",
            "meta",
            "元枢",
            "L5 Meta",
            "L5元枢",
            "元认知层",
            "策略自优化层",
        ],
        "definition": "ICME第5层，策略自优化，900s固结，容量<100MB",
        "domain": "tianji_core",
    },
    # --- 记忆操作 ---
    {
        "canonical_term": "记忆晋升",
        "aliases": [
            "晋升",
            "promote",
            "promotion",
            "层间晋升",
            "记忆升级",
            "固结晋升",
            "层级晋升",
        ],
        "definition": "记忆从低层向高层迁移的过程，由累积量或QualityGate驱动",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "记忆固结",
        "aliases": [
            "固结",
            "consolidate",
            "consolidation",
            "记忆巩固",
            "层内固结",
            "记忆压缩",
        ],
        "definition": "同一层内记忆的压缩和整理，去除冗余、合并相似",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "记忆检索",
        "aliases": [
            "检索",
            "recall",
            "search",
            "查询记忆",
            "记忆查询",
            "recall memory",
            "搜索记忆",
        ],
        "definition": "从ICME六层中查找相关记忆，支持FTS5/向量/图谱多通道",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "记忆写入",
        "aliases": [
            "写入",
            "remember",
            "store",
            "存储记忆",
            "记忆存储",
            "记录记忆",
            "save memory",
        ],
        "definition": "将内容写入ICME记忆系统，经QualityGate门禁审查",
        "domain": "tianji_core",
    },
    # --- 质量门禁 ---
    {
        "canonical_term": "QualityGate门禁",
        "aliases": [
            "门禁",
            "QualityGate",
            "quality_gate",
            "质量门禁",
            "三问推演",
            "写入门禁",
            "QualityGate v5.0",
        ],
        "definition": "记忆写入前的质量审查，三问推演：用户活动意志→知识因果链→反向过滤",
        "domain": "tianji_core",
    },
    # --- L-Asset ---
    {
        "canonical_term": "L-Asset知识资产",
        "aliases": [
            "L-Asset",
            "知识资产",
            "asset",
            "数字资产",
            "AssetAtom",
            "资产原子",
            "L-Asset绑定",
        ],
        "definition": "天机知识资产原子，通过memory_id↔asset_id↔content_hash三重绑定与记忆关联",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "三重绑定协议",
        "aliases": [
            "三重绑定",
            "triple binding",
            "绑定协议",
            "memory_id↔asset_id↔content_hash",
            "资产绑定",
        ],
        "definition": "L-Asset与记忆的绑定机制：memory_id↔asset_id↔content_hash",
        "domain": "tianji_core",
    },
    # --- DeepSeek驾驶者 ---
    {
        "canonical_term": "DeepSeek驾驶者",
        "aliases": [
            "DeepSeek",
            "deepseek",
            "驾驶者",
            "认知引擎",
            "DeepSeek Driver",
            "LLM引擎",
            "大模型引擎",
        ],
        "definition": "天机内置认知引擎，三循环并行：快速反应/深度思考/进化反思",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "快速反应环",
        "aliases": ["循环A", "快速环", "quick loop", "Loop A", "快速反应", "即时响应"],
        "definition": "DeepSeek三循环之一，<100ms，事件→quick_decide→act",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "深度思考环",
        "aliases": [
            "循环B",
            "深度环",
            "deep loop",
            "Loop B",
            "深度思考",
            "SENSE→EVALUATE→DECIDE→ACT→OBSERVE",
        ],
        "definition": "DeepSeek三循环之一，5min周期，SENSE→EVALUATE→DECIDE→ACT→OBSERVE",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "进化反思环",
        "aliases": [
            "循环C",
            "进化环",
            "evolution loop",
            "Loop C",
            "进化反思",
            "LEARN→EVOLVE",
            "反思环",
        ],
        "definition": "DeepSeek三循环之一，1天周期，汇总因果对→LEARN→EVOLVE",
        "domain": "tianji_core",
    },
    # --- 因果对 ---
    {
        "canonical_term": "因果对",
        "aliases": [
            "CausalPair",
            "causal pair",
            "因果关系对",
            "因果记录",
            "cause-effect pair",
        ],
        "definition": "记录记忆变更的因果关系：触发事件(cause)→记忆变更(effect)",
        "domain": "tianji_core",
    },
    # --- 智能体 ---
    {
        "canonical_term": "天枢Agent",
        "aliases": ["@tianshu", "天枢", "tianshu", "总调度", "调度Agent", "主控Agent"],
        "definition": "L2级总调度Agent，可调用除自身外全部22个Agent",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "灵犀Agent",
        "aliases": [
            "@lingxi",
            "灵犀",
            "lingxi",
            "对话守护",
            "上下文守护",
            "对话完整性",
        ],
        "definition": "L1级对话完整性守护Agent，检测语义断裂和主题偏离",
        "domain": "tianji_core",
    },
    # --- MCP ---
    {
        "canonical_term": "MCP协议",
        "aliases": [
            "MCP",
            "Model Context Protocol",
            "MCP Server",
            "MCP工具",
            "MCP协议",
        ],
        "definition": "天机与AI平台通信的标准协议，6服务器46工具",
        "domain": "tianji_core",
    },
    # --- TVP ---
    {
        "canonical_term": "TVP透明调度协议",
        "aliases": ["TVP", "透明调度", "TVP协议", "Agent切换协议", "调度透明"],
        "definition": "Agent切换时的透明声明协议，确保调度100%可追溯",
        "domain": "tianji_core",
    },
    # --- 进化 ---
    {
        "canonical_term": "进化闭环",
        "aliases": [
            "EvolutionLoop",
            "进化循环",
            "OBSERVE→LEARN→EVOLVE",
            "自进化",
            "evolution loop",
        ],
        "definition": "天机自进化核心机制：OBSERVE→LEARN→EVOLVE",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "三级自修改",
        "aliases": [
            "参数调优",
            "规则增补",
            "架构演化",
            "自修改三级",
            "evolution engine",
        ],
        "definition": "天机三级进化能力：参数调优→规则增补→架构演化",
        "domain": "tianji_core",
    },
    # --- 搜索 ---
    {
        "canonical_term": "混合搜索",
        "aliases": [
            "hybrid search",
            "多通道检索",
            "混合检索",
            "FTS5+向量+图谱",
            "融合检索",
        ],
        "definition": "天机多通道检索：FTS5全文+向量语义+知识图谱遍历",
        "domain": "tianji_core",
    },
    # --- 存储 ---
    {
        "canonical_term": "SQLite存储引擎",
        "aliases": ["SQLite", "sqlite", "icme.db", "FTS5", "WAL模式", "SQLite后端"],
        "definition": "天机默认存储后端，FTS5全文搜索+WAL并发",
        "domain": "tianji_core",
    },
    # --- 版本链 ---
    {
        "canonical_term": "资产版本链",
        "aliases": [
            "版本链",
            "version chain",
            "parent_version_id",
            "版本历史",
            "资产版本",
        ],
        "definition": "L-Asset的版本演化轨迹，通过parent_version_id链接",
        "domain": "tianji_core",
    },
    {
        "canonical_term": "资产状态机",
        "aliases": [
            "状态机",
            "ACTIVE→SUPERSEDED→DELETED→ARCHIVED",
            "资产状态",
            "AssetStatus",
        ],
        "definition": "L-Asset生命周期：ACTIVE→SUPERSEDED→DELETED→ARCHIVED",
        "domain": "tianji_core",
    },
    # --- 对齐引擎 ---
    {
        "canonical_term": "对齐引擎",
        "aliases": ["AlignmentEngine", "alignment", "对齐", "级联更新", "6步对齐"],
        "definition": "L-Asset变更的6步对齐流水线：变更→分类→影响分析→级联更新→验证→归档",
        "domain": "tianji_core",
    },
    # --- 一致性守护 ---
    {
        "canonical_term": "一致性守护",
        "aliases": ["ConsistencyGuardian", "一致性校验", "consistency", "4维校验"],
        "definition": "L-Asset 4维一致性校验：references/hashes/layer_consistency/version_chain",
        "domain": "tianji_core",
    },
    # --- 变更追踪 ---
    {
        "canonical_term": "变更追踪器",
        "aliases": [
            "ChangeTracker",
            "change_tracker",
            "变更追踪",
            "ChangeAtom",
            "AI工具调用追踪",
        ],
        "definition": "AI工具调用→ChangeAtom自动生成，追踪create/update/delete/rename",
        "domain": "tianji_core",
    },
    # --- TDAF导出 ---
    {
        "canonical_term": "TDAF导出格式",
        "aliases": [
            "TDAF",
            "tdaf",
            "导出格式",
            "全量导出",
            "增量导出",
            "Tianji Data Archive Format",
        ],
        "definition": "天机数据归档格式，支持全量(按层分批+流式)和增量(since_timestamp)导出",
        "domain": "tianji_core",
    },
    # --- 事件消费 ---
    {
        "canonical_term": "事件消费者",
        "aliases": [
            "EventConsumer",
            "event_consumer",
            "事件消费",
            "pending_events",
            "事件守护线程",
        ],
        "definition": ".pending_events.jsonl守护线程消费，3次重试+指数退避",
        "domain": "tianji_core",
    },
    # --- 消息网关 ---
    {
        "canonical_term": "消息网关",
        "aliases": [
            "MessageGateway",
            "message_gateway",
            "网关",
            "Hermes",
            "消息路由",
            "normalize_message",
        ],
        "definition": "多平台统一消息网关，normalize_message+route_to_agent+platform_adapter",
        "domain": "tianji_core",
    },
    # --- Protocol接口 ---
    {
        "canonical_term": "Protocol接口层",
        "aliases": [
            "Protocol",
            "protocol",
            "接口层",
            "分布式就绪",
            "IStorageEngine",
            "ISearchStrategy",
        ],
        "definition": "天机v10.0.1新增的接口抽象层，支持本地/远程双实现，为分布式就绪奠基",
        "domain": "development",
    },
    # --- 插件 ---
    {
        "canonical_term": "插件管理器",
        "aliases": [
            "PluginManager",
            "plugin_manager",
            "插件",
            "plugin",
            "动态加载",
            "IPlugin",
        ],
        "definition": "天机v10.0.1插件系统，importlib动态加载+生命周期管理",
        "domain": "development",
    },
    # --- 事件总线 ---
    {
        "canonical_term": "事件总线",
        "aliases": [
            "EventBus",
            "event_bus",
            "事件驱动",
            "DomainEvent",
            "publish/subscribe",
        ],
        "definition": "天机v10.0.1事件驱动架构核心，支持LocalEventBus和RemoteEventBus",
        "domain": "development",
    },
    # --- README索引 ---
    {
        "canonical_term": "README索引体系",
        "aliases": [
            "README",
            "readme",
            "索引体系",
            "知识地图",
            "目录索引",
            "README.md",
        ],
        "definition": "每个目录的README.md作为该域的知识地图+导航索引，天机启动时扫描构建",
        "domain": "development",
    },
    # --- 共享内核 ---
    {
        "canonical_term": "共享内核层",
        "aliases": ["shared", "共享内核", "Ω基点", "core/shared", "公共基点"],
        "definition": "天机v10.0.1新增的共享内核层，25个Ω基点(Protocol/异常/事件/插件等)",
        "domain": "development",
    },
]


def seed_terminology(store: TerminologyStore) -> int:
    """播种天机核心术语到术语表"""
    count = 0
    for term_data in TIANJI_CORE_TERMS:
        entry = TermEntry(
            canonical_term=term_data["canonical_term"],
            aliases=term_data.get("aliases", []),
            definition=term_data.get("definition", ""),
            domain=term_data.get("domain", "tianji_core"),
        )
        store.add_term(entry)
        count += 1
    logger.info(f"[TCL] Seeded {count} core terminology entries")
    return count


__all__ = ["TCLDisambiguator", "seed_terminology"]  # [FIX-tcl-disamb-002] 补充seed_terminology导出
