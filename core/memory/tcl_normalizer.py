# -*- coding: utf-8-sig -*-
"""tcl_normalizer.py — re-export兼容层 (SSS-PhaseB拆分后)

实际定义已拆分至子模块，本文件保持导入路径兼容。
"""
from __future__ import annotations  # [FIX-tcl-norm-001] 延迟类型注解求值

from .tcl_models import *
from .tcl_store import *
from .tcl_normalizer_core import *
from .tcl_disambiguator import *

__all__ = ["TermEntry", "NormalizeResult", "TerminologyStore", "TCLNormalizer", "TCLDisambiguator", "seed_terminology"]  # [FIX-tcl-norm-002] 补充seed_terminology导出(hybrid_engine_init引用)
