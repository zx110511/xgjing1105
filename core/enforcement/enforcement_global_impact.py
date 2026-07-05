# -*- coding: utf-8-sig -*-
"""enforcement_global_impact.py — re-export兼容层 (SSS-PhaseB拆分后)

实际定义已拆分至子模块，本文件保持导入路径兼容。
"""

from .enforcement_gi_models import *
from .enforcement_gi_analyzer import *

__all__ = ["ImpactTier", "ImpactDimension", "ModuleImpact", "SubWeightDetail", "WeightBreakdown", "StandardGap", "ConsumerDemand", "ModuleEvolutionSpec", "GlobalImpactAnalyzer"]
