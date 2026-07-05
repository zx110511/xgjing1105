# -*- coding: utf-8-sig -*-
"""天机v10.0.1 通用类型定义  [v10-ready]

系统全局类型别名，确保类型一致性。

版本: 1.0.0
"""
from __future__ import annotations
from typing import Any, TypeAlias

# === 核心ID类型 ===  [v10-ready]
EntryId: TypeAlias = str        # 记忆条目ID
AssetId: TypeAlias = str        # 知识资产ID
ContentHash: TypeAlias = str    # 内容哈希
SessionId: TypeAlias = str      # 会话ID
AgentId: TypeAlias = str        # Agent ID
EventId: TypeAlias = str        # 事件ID
PluginId: TypeAlias = str       # 插件ID
NodeId: TypeAlias = str         # 图谱节点ID

# === 层级类型 ===  [v10-ready]
LayerName: TypeAlias = str      # 层名: sensory/working/short_term/episodic/semantic/meta

# === 数据类型 ===  [v10-ready]
Metadata: TypeAlias = dict[str, Any]     # 元数据字典
Tags: TypeAlias = list[str]              # 标签列表
Embedding: TypeAlias = list[float]       # 向量嵌入
Triple: TypeAlias = tuple[str, str, str] # 知识三元组 (subject, predicate, object)
SearchResult: TypeAlias = list[dict[str, Any]]  # 搜索结果列表

# === 回调类型 ===  [v10-ready]
from typing import Callable
EventHandler: TypeAlias = Callable[[Any], None]  # 事件处理器
GateDecision: TypeAlias = dict[str, Any]         # 门禁判决

# === 配置类型 ===  [v10-ready]
LayerConfig: TypeAlias = dict[str, Any]  # 层级配置
