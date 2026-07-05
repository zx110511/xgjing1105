# -*- coding: utf-8 -*-
"""core/processors/config — 转发层 (SSS-PhaseE修复)

将 core.shared.config 的 DEFAULT_CONFIG 等关键配置
重新导出为 core.processors.config，解决 local_gate_strategy.py
的相对导入依赖。
"""
from core.shared.config import DEFAULT_CONFIG  # noqa: F401

__all__ = ["DEFAULT_CONFIG"]
