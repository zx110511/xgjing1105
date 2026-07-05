# -*- coding: utf-8-sig -*-
"""天机 LLM 策略子包 — core.llm  [v10-ready]

将原 core/llm_bridge.py 的 LLM 桥接逻辑插件化为 ILLMStrategy 实现。

导出:
    - DeepSeekLLMStrategy   : 本地默认策略 (DeepSeek 模型, 单进程)
    - RemoteLLMStrategy     : 远程多模型网关 stub (灵境, v10 预留)
    - ClassificationEngine  : 内容分类能力单元
    - KnowledgeExtractionEngine : 知识提取能力单元
    - PLUGIN_INFO           : 插件注册元信息 (category="llm")

分布式切换:
    单进程  -> DeepSeekLLMStrategy
    分布式  -> RemoteLLMStrategy (灵境多模型路由网关)

架构定位: core/llm/ LLM策略子包
版本: 1.0.0
"""
from __future__ import annotations

from .classification import ClassificationEngine
from .knowledge_extraction import KnowledgeExtractionEngine
from .deepseek_strategy import DeepSeekLLMStrategy, PLUGIN_INFO
from .remote_stub import RemoteLLMStrategy

__all__ = [
    "DeepSeekLLMStrategy",
    "RemoteLLMStrategy",
    "ClassificationEngine",
    "KnowledgeExtractionEngine",
    "PLUGIN_INFO",
]
