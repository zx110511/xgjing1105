# -*- coding: utf-8-sig -*-
"""tianji_daemon_tianjiautopilot_tasks_main.py — TianjiAutopilotTasks_MainMixin (SSS-PhaseB)

从 tianji_daemon_tianjiautopilot.py 拆分的方法组: tasks_main
源文件: tianji_daemon_tianjiautopilot.py
"""

import os
import sys



from typing import Optional

class TianjiAutopilotTasks_MainMixin:
    """tasks_main方法组Mixin"""

    def _task_consolidate(self):
        try:
            result = self._api_post(
                "/api/memory/storage/manage",
                {
                    "actions": ["preventive_consolidate"],
                    "target_layers": ["sensory", "working", "short_term", "episodic"],
                },
                timeout=60,
            )
            mgmt = result.get("management_actions", [])
            total = sum(
                a.get("consolidated", 0)
                for a in mgmt
                if a.get("action") == "consolidate"
            )
            if total > 0:
                self._stats["consolidations"] += 1
                self._stats["consolidation_entries"] += total
                log.info(f"[AUTOPILOT] Consolidated {total} entries")
            return {"consolidated": total}
        except Exception as e:
            log.debug(f"[AUTOPILOT] Consolidate failed: {e}")
            return {"error": str(e)}

    def _task_evolution(self):
        self._stats["evolution_ticks"] += 1
        try:
            if self._causal_recorder:
                self._causal_recorder.record(
                    action="autopilot_evolution_tick",
                    state_before={},
                    state_after={"cycle": self._cycle_count, "load": self._system_load},
                )
                self._stats["causal_pairs_recorded"] += 1

            data = self._api_get("/api/governance/health")
            return {
                "status": data.get("status", "unknown"),
                "causal_recorded": self._causal_recorder is not None,
            }
        except Exception as e:
            log.debug(f"[AUTOPILOT] Evolution tick failed: {e}")
            return {"error": str(e)}

    def _task_deep_learn(self):
        self._stats["deep_learning_reflections"] += 1
        try:
            if self._learning_engine:
                result = self._learning_engine.execute_learning_cycle()
                if result and result.get("knowledge_extracted"):
                    self._stats["knowledge_extracted"] += result.get(
                        "knowledge_extracted", 0
                    )
                return {
                    "closed_loop": True,
                    "phase": result.get("phase", "EXECUTE") if result else "unknown",
                }
        except Exception as e:
            log.debug(f"[AUTOPILOT] DeepLearn failed: {e}")

        try:
            total = self._api_get("/api/memory/stats").get("total", 0)
            return {
                "total_memories": total,
                "closed_loop": False,
                "fallback": "api_scan",
            }
        except Exception as e2:
            return {"error": str(e2)}

    def _task_kg_build(self):
        self._stats["kg_builds"] += 1
        try:
            data = self._api_get("/api/memory/?limit=50&layer=semantic")
            entries = (
                data
                if isinstance(data, list)
                else data.get("memories", data.get("items", []))
            )

            triples_added = 0
            for entry in entries[:20]:
                if not isinstance(entry, dict):
                    continue
                content = entry.get("content", "")
                if len(content) < 20:
                    continue
                try:
                    self._api_post(
                        "/api/knowledge-graph/extract",
                        {
                            "text": content[:2000],
                            "source_id": entry.get("id", ""),
                        },
                        timeout=15,
                    )
                    triples_added += 1
                except Exception:
                    pass

            self._stats["kg_triples_added"] += triples_added
            if triples_added > 0:
                log.info(f"[AUTOPILOT] KG build: {triples_added} entries processed")
            return {"entries_processed": triples_added}
        except Exception as e:
            log.debug(f"[AUTOPILOT] KG build failed: {e}")
            return {"error": str(e)}

    def _task_agent_dispatch(self, payload: dict = None):
        self._stats["agent_dispatches"] += 1
        try:
            if self._scheduler_ref:
                self._scheduler_ref.delegate(
                    task_description=f"Autopilot cycle {self._cycle_count} - system maintenance",
                    complexity="medium",
                )
                self._stats["scheduler_tasks_dispatched"] += 1
                return {"scheduler": "intelligent", "dispatched": True}
        except Exception as e:
            log.debug(f"[AUTOPILOT] Scheduler dispatch failed: {e}")

        try:
            data = self._api_get("/api/orchestrator/status")
            summary = data.get("summary", {})
            pending = summary.get("pending_tasks", 0)
            return {"pending_tasks": pending, "scheduler": "api_fallback"}
        except Exception as e2:
            return {"error": str(e2)}

    def _task_security(self):
        self._stats["security_scans"] += 1
        try:
            data = self._api_get("/api/enforcement/stats")
            violations = 0
            if isinstance(data, dict):
                violations = data.get(
                    "violations_count", data.get("total_intercepts", 0)
                )
                if violations > 0:
                    self._stats["security_violations"] += violations
                    log.warning(
                        f"[AUTOPILOT] Security: {violations} violations detected"
                    )
            return {
                "enforcement_active": data.get("enabled", True)
                if isinstance(data, dict)
                else False,
                "violations": violations,
            }
        except Exception as e:
            log.debug(f"[AUTOPILOT] Security scan failed: {e}")
            return {"error": str(e)}

    def _task_compliance(self):
        self._stats["compliance_checks"] += 1
        try:
            data = self._api_get("/api/enforcement/stats")
            standards = data.get("standards", {}) if isinstance(data, dict) else {}
            violations = 0
            if isinstance(standards, dict):
                for std_name, std_data in standards.items():
                    if (
                        isinstance(std_data, dict)
                        and std_data.get("compliance_rate", 1.0) < 0.9
                    ):
                        violations += 1
            if violations > 0:
                self._stats["compliance_violations"] += violations
                log.warning(
                    f"[AUTOPILOT] Compliance: {violations} standards below threshold"
                )
            return {
                "standards_checked": len(standards)
                if isinstance(standards, dict)
                else 0,
                "violations": violations,
            }
        except Exception as e:
            log.debug(f"[AUTOPILOT] Compliance check failed: {e}")
            return {"error": str(e)}

    def _task_extract(self, payload: dict = None):
        self._stats["extract_tasks"] += 1
        content = (payload or {}).get("content", "")
        if len(content) < 50:
            return {"skipped": True, "reason": "content_too_short"}

        try:
            self._api_post(
                "/api/memory/",
                {
                    "content": content,
                    "layer": "semantic",
                    "tags": ["auto-extracted", "knowledge"],
                    "priority": "medium",
                },
                timeout=15,
            )
            self._stats["extract_success"] += 1
            return {"extracted": True, "method": "api"}
        except Exception:
            try:
                sys.path.insert(0, str(TIANJI_ROOT))
                from core.shared.knowledge_extractor import KnowledgeExtractor

                extractor = KnowledgeExtractor()
                triples = extractor.extract_with_patterns(content)
                if triples:
                    self._stats["extract_fallback"] += 1
                    return {
                        "extracted": True,
                        "method": "local_pattern",
                        "triples": len(triples),
                    }
                return {"extracted": False, "method": "local_pattern", "triples": 0}
            except Exception as e2:
                log.debug(f"[AUTOPILOT] Extract fallback failed: {e2}")
                return {"error": str(e2)}
