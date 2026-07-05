# -*- coding: utf-8-sig -*-
"""tianji_daemon_tianjiautopilot_tasks_ops.py — TianjiAutopilotTasks_OpsMixin (SSS-PhaseB)

从 tianji_daemon_tianjiautopilot.py 拆分的方法组: tasks_ops
源文件: tianji_daemon_tianjiautopilot.py
"""

import os
import sys



from typing import Optional

class TianjiAutopilotTasks_OpsMixin:
    """tasks_ops方法组Mixin"""

    def _task_anomaly(self):
        self._stats["anomaly_checks"] += 1
        try:
            if self._baseline_engine:
                data = self._api_get("/api/memory/stats")
                total = data.get("total", 0)
                self._anomaly_buffer.append({"time": time.time(), "total": total})
                if len(self._anomaly_buffer) > 100:
                    self._anomaly_buffer = self._anomaly_buffer[-50:]

                if len(self._anomaly_buffer) >= 10:
                    values = [e["total"] for e in self._anomaly_buffer[-10:]]
                    mean_val = sum(values) / len(values)
                    std_val = (
                        sum((v - mean_val) ** 2 for v in values) / len(values)
                    ) ** 0.5

                    if std_val > 0:
                        latest = values[-1]
                        z_score = (latest - mean_val) / std_val
                        if abs(z_score) > 2.0:
                            self._stats["anomalies_detected"] += 1
                            self._stats["anomaly_zscore"] = round(z_score, 2)
                            log.warning(
                                f"[AUTOPILOT] ANOMALY: z-score={z_score:.2f}, total={latest}, mean={mean_val:.1f}"
                            )
                            return {
                                "anomaly": True,
                                "z_score": round(z_score, 2),
                                "total": latest,
                                "mean": round(mean_val, 1),
                            }

                return {"anomaly": False, "buffer_size": len(self._anomaly_buffer)}
            return {"anomaly": False, "baseline_engine": "unavailable"}
        except Exception as e:
            log.debug(f"[AUTOPILOT] Anomaly check failed: {e}")
            return {"error": str(e)}

    def _task_autoheal(self):
        self._stats["autoheal_attempts"] += 1
        tried = False
        try:
            if self._auto_healer:
                data = self._api_get("/api/governance/health")
                if data.get("status") != "healthy":
                    result = self._auto_healer.repair(all_modules=True)
                    tried = True
                    if result and result.get("repaired", 0) > 0:
                        self._stats["autoheal_successes"] += 1
                        log.info(
                            f"[AUTOPILOT] AUTOHEAL: repaired={result.get('repaired', 0)}"
                        )
                        return {"healed": True, "repaired": result.get("repaired", 0)}
                    else:
                        self._stats["autoheal_rejections"] += 1
                        return {"healed": False, "reason": "no_repair_needed"}
            return {"healed": False, "autohealer": "unavailable"}
        except Exception as e:
            if tried:
                self._stats["autoheal_rejections"] += 1
            log.debug(f"[AUTOPILOT] Autoheal failed: {e}")
            return {"error": str(e)}

    def _task_skill_learn(self):
        self._stats["skill_learn_cycles"] += 1
        try:
            if self._skill_learner:
                data = self._api_get("/api/memory/?limit=30&layer=semantic")
                entries = (
                    data
                    if isinstance(data, list)
                    else data.get("memories", data.get("items", []))
                )

                patterns_found = 0
                for entry in entries[:10]:
                    content = (
                        entry.get("content", "")
                        if isinstance(entry, dict)
                        else str(entry)
                    )
                    if len(content) > 100:
                        try:
                            skill, report = (
                                self._skill_learner.learn_from_demonstration(
                                    name=f"autopilot-skill-{self._cycle_count}-{patterns_found}",
                                    demonstration=content[:500],
                                    category="auto-extracted",
                                    auto_verify=True,
                                )
                            )
                            if skill and report.get("verified"):
                                self._stats["skills_created"] += 1
                                self._stats["skills_verified"] += 1
                                patterns_found += 1
                        except Exception:
                            pass

                if patterns_found > 0:
                    log.info(
                        f"[AUTOPILOT] SKILL_LEARN: {patterns_found} skills created"
                    )
                return {"skills_created": patterns_found}
            return {"skills_created": 0, "skill_learner": "unavailable"}
        except Exception as e:
            log.debug(f"[AUTOPILOT] Skill learning failed: {e}")
            return {"error": str(e)}

    def _task_preference(self):
        self._stats["preference_analyses"] += 1
        try:
            if self._preference_learner:
                data = self._api_get("/api/memory/?limit=20&layer=episodic")
                entries = (
                    data
                    if isinstance(data, list)
                    else data.get("memories", data.get("items", []))
                )

                for entry in entries[:5]:
                    if isinstance(entry, dict):
                        content = entry.get("content", "")[:300]
                        if content:
                            self._preference_learner.record_event(
                                event_type="memory_access",
                                category="memory",
                                action="autopilot_scan",
                                value=content[:200],
                                metadata={
                                    "source": "autopilot",
                                    "cycle": self._cycle_count,
                                },
                            )

                patterns = self._preference_learner.analyze_patterns()
                if patterns:
                    self._stats["patterns_identified"] += len(patterns)
                    log.info(
                        f"[AUTOPILOT] PREFERENCE: {len(patterns)} patterns identified"
                    )
                return {"patterns": len(patterns) if patterns else 0}
            return {"patterns": 0, "preference_learner": "unavailable"}
        except Exception as e:
            log.debug(f"[AUTOPILOT] Preference analysis failed: {e}")
            return {"error": str(e)}

    def _task_mem_health(self):
        self._stats["mem_health_checks"] += 1
        try:
            data = self._api_get("/api/memory/storage/management")
            alerts = data.get("alerts", [])
            stats = self._api_get("/api/memory/stats")

            total = stats.get("total", 0)
            quality_score = 100.0

            if alerts:
                quality_score -= len(alerts) * 5
            if total > 10000:
                quality_score -= 10
            if stats.get("avg_priority", 0.5) < 0.3:
                quality_score -= 10

            quality_score = max(0, min(100, quality_score))
            self._stats["mem_quality_scores"].append(quality_score)
            if len(self._stats["mem_quality_scores"]) > 50:
                self._stats["mem_quality_scores"] = self._stats["mem_quality_scores"][
                    -30:
                ]

            if quality_score < 60:
                log.warning(f"[AUTOPILOT] MEM_HEALTH: score={quality_score:.1f} (LOW)")

            return {
                "quality_score": round(quality_score, 1),
                "alerts": len(alerts),
                "total": total,
            }
        except Exception as e:
            log.debug(f"[AUTOPILOT] Memory health check failed: {e}")
            return {"error": str(e)}

    def _task_predict(self):
        self._stats["prediction_cycles"] += 1
        try:
            if len(self._anomaly_buffer) >= 10:
                values = [e["total"] for e in self._anomaly_buffer[-10:]]
                times = [e["time"] for e in self._anomaly_buffer[-10:]]

                n = len(values)
                if n >= 5:
                    x_mean = sum(range(n)) / n
                    y_mean = sum(values) / n
                    num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
                    den = sum((i - x_mean) ** 2 for i in range(n))

                    if den > 0:
                        slope = num / den
                        next_pred = values[-1] + slope * 3

                        self._stats["predictions_made"] += 1

                        if slope > 0 and next_pred > values[-1] * 1.3:
                            log.warning(
                                f"[AUTOPILOT] PREDICT: growth_rate={slope:.1f}/cycle, forecast={next_pred:.0f}"
                            )
                            return {
                                "prediction": round(next_pred, 0),
                                "trend": "increasing",
                                "growth_rate": round(slope, 1),
                                "alert": True,
                            }

                        return {
                            "prediction": round(next_pred, 0),
                            "trend": "increasing" if slope > 0 else "stable",
                            "growth_rate": round(slope, 1),
                        }

            return {"prediction": None, "reason": "insufficient_data"}
        except Exception as e:
            log.debug(f"[AUTOPILOT] Prediction failed: {e}")
            return {"error": str(e)}

    def _task_rca(self):
        self._stats["rca_analyses"] += 1
        try:
            if (
                self._stats["anomalies_detected"] > 0
                or self._stats["capacity_alerts"] > 0
            ):
                root_causes = []
                if self._stats["capacity_alerts"] > 0:
                    root_causes.append(
                        {
                            "cause": "capacity_over_threshold",
                            "evidence": f"{self._stats['capacity_alerts']} alerts",
                        }
                    )
                if self._stats["anomalies_detected"] > 0:
                    root_causes.append(
                        {
                            "cause": "statistical_anomaly",
                            "evidence": f"z-score={self._stats.get('anomaly_zscore', 0)}",
                        }
                    )
                if self._stats["security_violations"] > 0:
                    root_causes.append(
                        {
                            "cause": "security_violation",
                            "evidence": f"{self._stats['security_violations']} violations",
                        }
                    )

                if root_causes:
                    self._stats["rca_root_causes_found"] += len(root_causes)
                    self._rca_results.append(
                        {
                            "time": time.time(),
                            "causes": root_causes,
                            "cycle": self._cycle_count,
                        }
                    )
                    if len(self._rca_results) > 50:
                        self._rca_results = self._rca_results[-25:]
                    log.warning(
                        f"[AUTOPILOT] RCA: {len(root_causes)} root causes found"
                    )
                    return {"root_causes": root_causes}

            return {"root_causes": [], "no_issues": True}
        except Exception as e:
            log.debug(f"[AUTOPILOT] RCA failed: {e}")
            return {"error": str(e)}

    def _task_resilience(self):
        self._stats["resilience_checks"] += 1
        try:
            if self._circuit_breaker:
                state = self._circuit_breaker.state
                if state != "closed":
                    self._stats["circuit_trips"] += 1
                    log.warning(
                        f"[AUTOPILOT] RESILIENCE: circuit breaker state={state}"
                    )
                return {"circuit_state": state, "trips": self._stats["circuit_trips"]}
            return {"circuit_state": "unavailable"}
        except Exception as e:
            log.debug(f"[AUTOPILOT] Resilience check failed: {e}")
            return {"error": str(e)}

    def _task_scheduler(self):
        self._stats["scheduler_ticks"] += 1
        try:
            if self._scheduler_ref:
                try:
                    scheduler_stats = self._scheduler_ref.get_stats()
                    self._stats["scheduler_tasks_dispatched"] += scheduler_stats.get(
                        "cycles_completed", 0
                    )
                    return {"scheduler": "active", "stats": scheduler_stats}
                except Exception:
                    return {"scheduler": "active", "stats": {}}
            return {"scheduler": "unavailable"}
        except Exception as e:
            log.debug(f"[AUTOPILOT] Scheduler tick failed: {e}")
            return {"error": str(e)}

    def _task_threshold(self):
        self._stats["threshold_adjustments"] += 1
        try:
            if self._quality_gate:
                if hasattr(self._quality_gate, "auto_tune_thresholds"):
                    result = self._quality_gate.auto_tune_thresholds()
                    return {"adjusted": True, "result": str(result)}
                return {"adjusted": False, "reason": "auto_tune not available"}
            if self._dynamic_mgr:
                self._dynamic_mgr.adjust_thresholds()
                return {"adjusted": True, "method": "dynamic_manager"}
            return {"adjusted": False, "reason": "no_threshold_manager"}
        except Exception as e:
            log.debug(f"[AUTOPILOT] Threshold adjustment failed: {e}")
            return {"error": str(e)}

    def _task_correlation(self):
        self._stats["correlation_analyses"] += 1
        try:
            events = {
                "capacity_alerts": self._stats["capacity_alerts"],
                "anomalies": self._stats["anomalies_detected"],
                "security_violations": self._stats["security_violations"],
                "compliance_violations": self._stats["compliance_violations"],
                "circuit_trips": self._stats["circuit_trips"],
                "autoheal_attempts": self._stats["autoheal_attempts"],
            }

            active_issues = sum(1 for v in events.values() if v > 0)
            if active_issues >= 2:
                self._stats["correlation_clusters"] += 1
                self._correlation_graph[str(self._cycle_count)] = events
                if len(self._correlation_graph) > 100:
                    keys = sorted(self._correlation_graph.keys(), key=int)
                    for old_key in keys[:50]:
                        del self._correlation_graph[old_key]
                log.info(f"[AUTOPILOT] CORRELATION: {active_issues} issues correlated")
                return {
                    "active_issues": active_issues,
                    "events": events,
                    "correlated": True,
                }

            return {"active_issues": active_issues, "correlated": False}
        except Exception as e:
            log.debug(f"[AUTOPILOT] Correlation analysis failed: {e}")
            return {"error": str(e)}

    def _task_module_health(self, module_name):
        try:
            import json as _json

            if module_name.startswith("mod_"):
                module_name = module_name[4:]
            try:
                governance_url = (
                    f"http://127.0.0.1:{TIANJI_SERVICE['port']}/api/governance/health"
                )
                req = urllib.request.Request(governance_url)
                resp = urllib.request.urlopen(req, timeout=10)
                raw = resp.read().decode("utf-8")
                data = _json.loads(raw)
                modules_active = data.get("modules_active", 0)
                modules_degraded = data.get("modules_degraded", 0)
                modules_error = data.get("modules_error", 0)
            except Exception:
                modules_active = 0
                modules_degraded = 0
                modules_error = 0

            try:
                container_url = (
                    f"http://127.0.0.1:{TIANJI_SERVICE['port']}/api/container/modules"
                )
                req2 = urllib.request.Request(container_url)
                resp2 = urllib.request.urlopen(req2, timeout=10)
                cdata = _json.loads(resp2.read().decode("utf-8"))
                if isinstance(cdata, list):
                    total_container = len(cdata)
                else:
                    total_container = len(cdata.get("modules", cdata.get("data", [])))
            except Exception:
                total_container = 0

            self._stats["module_patrols"] += 1
            self._stats["modules_healthy"] = modules_active or total_container
            self._stats["modules_degraded"] = modules_degraded
            self._stats["modules_error"] = modules_error
            self._module_health_cache[module_name] = {
                "active": modules_active or total_container,
                "degraded": modules_degraded,
                "error": modules_error,
                "timestamp": time.time(),
            }
            active = modules_active or total_container
            healthy = active > 0 and modules_error == 0
            return {
                "module": module_name,
                "active": active,
                "degraded": modules_degraded,
                "error": modules_error,
                "healthy": healthy,
            }
        except Exception as e:
            return {"module": module_name, "healthy": False, "error": str(e)}

    def _task_daemon_health(self, daemon_name):
        """守护服务健康巡检"""
        try:
            if daemon_name.startswith("daemon_"):
                daemon_name = daemon_name[7:]
            checks = {
                "daemon_main_loop": self._check_daemon_loop,
                "rest_api_server": self._check_rest_api,
                "websocket_server": self._check_websocket,
                "sse_monitor": self._check_sse,
                "chat_pipeline": self._check_chat_pipeline,
                "frontend_dashboard": self._check_frontend,
            }
            checker = checks.get(daemon_name)
            if checker:
                result = checker()
                self._stats["daemon_checks"] += 1
                if result.get("healthy"):
                    self._stats["daemon_healthy"] += 1
                else:
                    self._stats["daemon_degraded"] += 1
                return {"daemon": daemon_name, **result}
            return {"daemon": daemon_name, "status": "no_checker"}
        except Exception as e:
            return {"daemon": daemon_name, "error": str(e)}
