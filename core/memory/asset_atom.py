# -*- coding: utf-8-sig -*-
"""asset_atom.py — re-export兼容层 (SSS-PhaseB拆分后)

实际定义已拆分至子模块，本文件保持导入路径兼容。
"""
from __future__ import annotations  # [FIX-asset-005] 延迟类型注解求值,避免前向引用NameError

from .asset_atom_models import *
from .asset_atom_registry import *
from .asset_atom_change import *
from .asset_atom_snapshot import *

__all__ = ["AssetStatus", "ContentType", "Provenance", "AssetAtom", "AssetRegistry", "ChangeAtom", "AssetSnapshot", "DiffEngine", "AssetSnapshotManager"]
