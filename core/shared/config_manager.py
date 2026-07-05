# -*- coding: utf-8-sig -*-
"""配置 — 配置管理器

从 config.py 拆分 (SSS-PhaseB)
"""

import logging
import os
import sys
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    from .version import SYSTEM_IDENTITY as _VERSION_IDENTITY
    from .version import __edition__, __version__, get_version_string
    from ..processors.evolution_loop import CausalPairRecorder, EvolutionLoop
except ImportError:
    _VERSION_IDENTITY = None
    __edition__ = "unknown"
    __version__ = "0.0.0"
    get_version_string = lambda: "0.0.0"
    CausalPairRecorder = None
    EvolutionLoop = None

from .config_models import *

class ConfigManager:
    """
    配置管理中心 v9.1 — 天机配置的统一入口 + 自进化闭环

    职责:
      1. 统一管理 ICMEConfig / MemoryLayerConfig / QualityGateConfig
      2. StoragePathConfig 存储路径全生命周期 (D9-1 存储路径煞)
      3. 配置变更追踪 + EvolutionLoop 自进化
      4. 健康检查 + 合规审计

    灵境道谱溯源: D9-1【存储路径煞】· 道九·配置体
    """

    def __init__(
        self,
        config: ICMEConfig | None = None,
        recorder: Any | None = None,
        learning_engine: Any | None = None,
    ):
        self._config = config or DEFAULT_CONFIG
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._storage = StoragePathConfig(root=self._config.data_path)
        self._change_log: list[dict[str, Any]] = []
        self._change_count = 0
        self._error_count = 0

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="config_manager",
                    effectiveness_fn=self._calc_config_effectiveness,
                    learn_fn=self._learn_from_config,
                    evolve_fn=self._evolve_config,
                    mutable_config={
                        "consolidation_interval_minutes": self._config.consolidation_interval_minutes,
                        "session_timeout_minutes": self._config.session_timeout_minutes,
                        "max_context_tokens": self._config.max_context_tokens,
                        "quality_gate_min_content_length": self._config.quality_gate.min_content_length,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception as e:
                logger.warning(f"ConfigManager EvolutionLoop init failed: {e}")

    @property
    def config(self) -> ICMEConfig:
        return self._config

    @property
    def storage(self) -> StoragePathConfig:
        return self._storage

    def ensure_storage(self) -> dict[str, Path]:
        paths = self._storage.ensure()
        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="ensure_storage",
                    state_before={"sub_paths_ready": False},
                    state_after={"sub_paths_ready": True, "path_count": len(paths)},
                )
            except Exception:
                pass
        return paths

    def validate_storage(self) -> dict[str, Any]:
        result = self._storage.validate()
        if self._evo_loop is not None:
            try:
                issue_count = len(result.get("issues", []))
                self._evo_loop.record_action(
                    action="validate_storage",
                    state_before={"issues": 0},
                    state_after={
                        "issues": issue_count,
                        "root_readable": result["root_readable"],
                    },
                )
            except Exception:
                pass
        return result

    def audit_storage(self) -> dict[str, Any]:
        result = self._storage.audit()
        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="audit_storage",
                    state_before={"violations": 0},
                    state_after={
                        "violations": result["violation_count"],
                        "clean": result["clean"],
                    },
                )
            except Exception:
                pass
        return result

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        old_snapshot = {
            "consolidation_interval_minutes": self._config.consolidation_interval_minutes,
            "session_timeout_minutes": self._config.session_timeout_minutes,
            "max_context_tokens": self._config.max_context_tokens,
        }
        for key, value in updates.items():
            if hasattr(self._config, key):
                old_val = getattr(self._config, key)
                setattr(self._config, key, value)
                self._change_log.append(
                    {
                        "key": key,
                        "old": old_val,
                        "new": value,
                        "timestamp": __import__("time").time(),
                    }
                )
                self._change_count += 1
                logger.info(f"[ConfigManager] 配置变更: {key} {old_val}→{value}")

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="update_config",
                    state_before=old_snapshot,
                    state_after={
                        "consolidation_interval_minutes": self._config.consolidation_interval_minutes,
                        "session_timeout_minutes": self._config.session_timeout_minutes,
                        "max_context_tokens": self._config.max_context_tokens,
                    },
                )
            except Exception:
                pass

        return {"changes": len(updates), "change_count": self._change_count}

    def get_layer_config(self, layer_name: str) -> MemoryLayerConfig | None:
        return self._config.get_layer(layer_name)

    def health(self) -> dict[str, Any]:
        storage_ok = True
        try:
            self._storage.root.mkdir(parents=True, exist_ok=True)
        except Exception:
            storage_ok = False
            self._error_count += 1

        return {
            "status": "healthy" if storage_ok else "degraded",
            "version": get_version_string(),
            "edition": f"{__edition__}-v{get_version_string(short=True)}",
            "storage_root": str(self._storage.root),
            "storage_accessible": storage_ok,
            "layers_configured": len(self._config.layers),
            "change_count": self._change_count,
            "error_count": self._error_count,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
            "consolidation_interval_minutes": self._config.consolidation_interval_minutes,
            "session_timeout_minutes": self._config.session_timeout_minutes,
            "protocol_mode": TIANJI_V91_PROTOCOL_MODE,
            "event_wiring": TIANJI_V91_EVENT_WIRING,
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "version": "8.1",
            "storage": str(self._storage.root),
            "change_count": self._change_count,
            "error_count": self._error_count,
            "layers": [layer.name for layer in self._config.layers],
            "quality_gate": {
                "min_content_length": self._config.quality_gate.min_content_length,
                "max_similarity_for_duplicate": self._config.quality_gate.max_similarity_for_duplicate,
            },
            "health": self.health(),
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
        }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_config_effectiveness(
        self, action: str, state_before: dict[str, Any], state_after: dict[str, Any]
    ) -> float:
        if action == "ensure_storage":
            return (
                0.5
                if state_after.get("path_count", 0) >= len(_STORAGE_SUB_PATHS)
                else -0.3
            )
        elif action == "validate_storage":
            issues = state_after.get("issues", 0)
            return max(-0.5, -0.1 * issues) if issues > 0 else 0.3
        elif action == "audit_storage":
            violations = state_after.get("violations", 0)
            return max(-0.6, -0.15 * violations) if violations > 0 else 0.4
        elif action == "update_config":
            delta = abs(
                state_after.get("session_timeout_minutes", 60)
                - state_before.get("session_timeout_minutes", 60)
            )
            return min(0.3, delta * 0.02) if delta > 0 else 0.0
        return 0.0

    def _learn_from_config(
        self, causal_pairs: list[Any], effectiveness_summary: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "change_frequency": self._change_count,
        }

    def _evolve_config(
        self, learn_result: dict[str, Any], mutable_config: dict[str, Any]
    ) -> dict[str, Any]:
        changes = {}
        avg_eff = learn_result.get("avg_effectiveness", 0.0)
        if (
            avg_eff < -0.2
            and mutable_config.get("consolidation_interval_minutes", 5) < 30
        ):
            changes["consolidation_interval_minutes"] = min(
                30, mutable_config.get("consolidation_interval_minutes", 5) + 2
            )
        if (
            avg_eff > 0.3
            and mutable_config.get("consolidation_interval_minutes", 5) > 2
        ):
            changes["consolidation_interval_minutes"] = max(
                2, mutable_config.get("consolidation_interval_minutes", 5) - 1
            )
        return {"rules_modified": changes, "skills_created": []}


__all__ = ["ConfigManager"]
