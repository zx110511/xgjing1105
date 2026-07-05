# -*- coding: utf-8-sig -*-
"""auto_ops.py — re-export兼容层 (SSS-PhaseB拆分后)

实际定义已拆分至子模块，本文件保持导入路径兼容。
"""

from typing import Optional


from .auto_ops_models import *
from .auto_ops_healer import *
from .auto_ops_baseline import *
from .auto_ops_coordinator import *

__all__ = ["HealingAction", "HealingSeverity", "AnomalyType", "ScaleDirection", "HealingRecord", "MetricSnapshot", "AnomalyReport", "ScaleRecommendation", "AutoHealer", "BaselineEngine", "AutoOpsCoordinator", "init_ops_coordinator"]  # [FIX-autoops-001] 补充init_ops_coordinator导出(main_ops引用)
