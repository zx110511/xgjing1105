# -*- coding: utf-8-sig -*-
"""tianji_daemon_TianjiDaemon — 从 tianji_daemon.py 拆分 (SSS-PhaseB)

源文件: tianji_daemon.py
"""

import os
import sys
from typing import Any, Dict, List, Optional
from .tianji_daemon_watchdog import Watchdog
from .tianji_daemon_autobackup import AutoBackup
from .tianji_daemon_autorepair import AutoRepair
from .tianji_daemon_integritychecker import IntegrityChecker


from typing import Optional

class TianjiDaemon:
    SYSTEM_NAME = "天机"
    SYSTEM_TAG = "【天机·智能驾驶v3.0】"
    SYSTEM_VERSION = "9.1.0"

    def __init__(
        self, recorder: Optional[Any] = None, learning_engine: Optional[Any] = None
    ):
        self.watchdog = Watchdog()
        self.backup = AutoBackup()
        self.repair = AutoRepair()
        self.integrity = IntegrityChecker()
        self.memory_automation = TianjiAutopilot()
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._running = False
        self._errors = 0
        self._loop_iterations = 0
        self._server_restart_count = 0
        self._backup_count = 0

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="tianji_daemon",
                    effectiveness_fn=self._calc_daemon_effectiveness,
                    learn_fn=self._learn_from_daemon,
                    evolve_fn=self._evolve_daemon_config,
                    mutable_config={
                        "watchdog_interval": WATCHDOG_INTERVAL,
                        "backup_interval": BACKUP_INTERVAL,
                        "full_backup_interval": FULL_BACKUP_INTERVAL,
                        "integrity_check_interval": INTEGRITY_CHECK_INTERVAL,
                        "max_restart_attempts": MAX_RESTART_ATTEMPTS,
                        "restart_cooldown": RESTART_COOLDOWN,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception:
                pass

    def run(self):
        existing_pid = _read_pid(PID_FILE)
        if existing_pid and _is_port_listening(TIANJI_SERVICE["port"]):
            print(f"[TIANJI] Daemon already running (PID {existing_pid})")
            return

        _write_pid(PID_FILE, os.getpid())
        STOP_FILE.unlink(missing_ok=True)
        self._running = True

        log.info(f"TIANJI Daemon v{self.SYSTEM_VERSION} starting...")
        print(f"[{self.SYSTEM_TAG}] Daemon v{self.SYSTEM_VERSION} starting...")

        server_ok = _start_server()
        if not server_ok:
            log.warning("Initial server start failed, will retry via watchdog")

        log.info("Entering main daemon loop...")

        while self._running and not STOP_FILE.exists():
            try:
                watchdog_result = self.watchdog.check()
                self._loop_iterations += 1

                if not all(watchdog_result.values()):
                    repairs = self.repair.diagnose_and_repair(watchdog_result)
                    if repairs:
                        log.info(f"Auto-repair results: {repairs}")
                        self._server_restart_count += 1

                self.backup.incremental()
                self.backup.full()
                self.backup.cleanup_old()
                self._backup_count += 1 if self._loop_iterations % 10 == 0 else 0

                integrity_result = self.integrity.check()
                if integrity_result.get("checks"):
                    log.info(f"Integrity check: {integrity_result['checks']}")

                memory_auto_result = self.memory_automation.run_cycle()
                if memory_auto_result:
                    for task_name, task_result in memory_auto_result.items():
                        if isinstance(task_result, dict) and "error" not in task_result:
                            log.info(f"[AUTOPILOT] {task_name}: {task_result}")
                        elif isinstance(task_result, dict) and "error" in task_result:
                            log.debug(
                                f"[AUTOPILOT] {task_name} error: {task_result.get('error', 'unknown')}"
                            )

                if self._evo_loop is not None:
                    try:
                        self._evo_loop.record_action(
                            action="daemon_loop",
                            state_before={},
                            state_after={
                                "iteration": self._loop_iterations,
                                "server_healthy": all(watchdog_result.values()),
                                "repairs_applied": bool(
                                    not all(watchdog_result.values())
                                ),
                                "backup_count": self._backup_count,
                                "restart_count": self._server_restart_count,
                            },
                        )
                    except Exception:
                        pass

                time.sleep(WATCHDOG_INTERVAL)

            except KeyboardInterrupt:
                log.info("Daemon interrupted by keyboard")
                break
            except Exception as e:
                log.exception(f"Daemon loop error: {e}")
                time.sleep(10)

        self._cleanup()
        log.info("TIANJI Daemon stopped")

    def stop(self):
        STOP_FILE.touch()
        self._running = False
        pid = _read_pid(PID_FILE)
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"[TIANJI] Stop signal sent to PID {pid}")
            except ProcessLookupError:
                print("[TIANJI] Daemon process not found")
        else:
            print("[TIANJI] No daemon PID file found")
        _stop_server()

    def status(self):
        pid = _read_pid(PID_FILE)
        running = pid is not None and _is_port_listening(TIANJI_SERVICE["port"])
        healthy = _check_health(TIANJI_SERVICE["health_url"]) if running else False

        print(f"\n{'=' * 55}")
        print("  TIANJI Memory Engine - Daemon Status")
        print(f"  {self.SYSTEM_TAG}")
        print(f"{'=' * 55}")
        print(f"  Daemon PID:     {pid or 'N/A'}")
        print(f"  Daemon Running: {'YES' if pid else 'NO'}")
        print(
            f"  Server :8771:   {'HEALTHY' if healthy else 'UNHEALTHY' if running else 'STOPPED'}"
        )
        print(f"  Data Dir:       {DATA_DIR}")
        print(f"  Backup Dir:     {BACKUP_DIR}")
        print(f"  Log Dir:        {LOG_DIR}")

        db_path = DATA_DIR / "icme.db"
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            print(f"  Database:       {size_mb:.1f} MB")

        auto_stats = self.memory_automation.get_stats()
        auto_status = self.memory_automation.get_status()
        modules_ok = auto_status.get("modules_initialized", False)
        print(
            f"  --- TianjiAutopilot v2.0 (Modules: {'OK' if modules_ok else 'INIT'}): {auto_status.get('cycle_count', 0)} cycles ---"
        )
        print(
            f"  Capacity:       {auto_status.get('capacity_state', 'N/A')} | C:{auto_stats.get('consolidations', 0)} E:{auto_stats.get('evictions', 0)} A:{auto_stats.get('capacity_alerts', 0)}"
        )
        print(
            f"  Evolution:      {auto_stats.get('evolution_ticks', 0)} ticks | CausalPairs: {auto_stats.get('causal_pairs_recorded', 0)}"
        )
        print(
            f"  DeepLearn:      {auto_stats.get('deep_learning_reflections', 0)} reflections | K:{auto_stats.get('knowledge_extracted', 0)}"
        )
        print(
            f"  KG Build:       {auto_stats.get('kg_builds', 0)} builds | Triples: {auto_stats.get('kg_triples_added', 0)}"
        )
        print(
            f"  Agent Dispatch: {auto_stats.get('agent_dispatches', 0)} | Scheduler: {auto_stats.get('scheduler_tasks_dispatched', 0)}"
        )
        print(
            f"  Security:       {auto_stats.get('security_scans', 0)} scans | V:{auto_stats.get('security_violations', 0)}"
        )
        print(
            f"  Compliance:     {auto_stats.get('compliance_checks', 0)} checks | V:{auto_stats.get('compliance_violations', 0)}"
        )
        print(
            f"  Extract:        {auto_stats.get('extract_tasks', 0)} tasks | API:{auto_stats.get('extract_success', 0)} Local:{auto_stats.get('extract_fallback', 0)}"
        )
        print(
            f"  Anomaly:        {auto_stats.get('anomaly_checks', 0)} checks | Detected:{auto_stats.get('anomalies_detected', 0)}"
        )
        print(
            f"  AutoHeal:       {auto_stats.get('autoheal_attempts', 0)} attempts | OK:{auto_stats.get('autoheal_successes', 0)}"
        )
        print(
            f"  SkillLearn:     {auto_stats.get('skill_learn_cycles', 0)} cycles | Created:{auto_stats.get('skills_created', 0)} Verified:{auto_stats.get('skills_verified', 0)}"
        )
        print(
            f"  Preference:     {auto_stats.get('preference_analyses', 0)} analyses | Patterns:{auto_stats.get('patterns_identified', 0)}"
        )
        print(
            f"  MemHealth:      {auto_stats.get('mem_health_checks', 0)} checks | AvgQuality:{auto_stats.get('mem_avg_quality', 'N/A')}"
        )
        print(
            f"  Predict:        {auto_stats.get('prediction_cycles', 0)} cycles | Forecasts:{auto_stats.get('predictions_made', 0)}"
        )
        print(
            f"  RCA:            {auto_stats.get('rca_analyses', 0)} analyses | Causes:{auto_stats.get('rca_root_causes_found', 0)}"
        )
        print(
            f"  Resilience:     {auto_stats.get('resilience_checks', 0)} checks | Trips:{auto_stats.get('circuit_trips', 0)}"
        )
        print(
            f"  Threshold:      {auto_stats.get('threshold_adjustments', 0)} adjustments"
        )
        print(
            f"  Correlation:    {auto_stats.get('correlation_analyses', 0)} analyses | Clusters:{auto_stats.get('correlation_clusters', 0)}"
        )
        print(f"{'=' * 55}\n")

    def health(self) -> Dict[str, Any]:
        return {
            "status": "running" if self._running else "stopped",
            "version": "9.1.0",
            "pid": _read_pid(PID_FILE),
            "server_healthy": _check_health(TIANJI_SERVICE["health_url"]),
            "server_port_listening": _is_port_listening(TIANJI_SERVICE["port"]),
            "loop_iterations": self._loop_iterations,
            "server_restart_count": self._server_restart_count,
            "backup_count": self._backup_count,
            "errors": self._errors,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
            "memory_automation": self.memory_automation.get_stats(),
            "autopilot_status": self.memory_automation.get_status(),
        }

    def get_stats(self) -> Dict:
        return {
            "health": self.health(),
            "version": "9.1.0",
            "loop_iterations": self._loop_iterations,
            "server_restart_count": self._server_restart_count,
            "backup_count": self._backup_count,
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
        }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_daemon_effectiveness(
        self, action: str, state_before: Dict[str, Any], state_after: Dict[str, Any]
    ) -> float:
        if action == "daemon_loop":
            if state_after.get("server_healthy", False):
                return 0.9
            if state_after.get("repairs_applied", False):
                return 0.5
            return 0.1
        return 0.0

    def _learn_from_daemon(
        self, causal_pairs: List[Any], effectiveness_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        uptime_ratio = max(self._loop_iterations - self._server_restart_count, 0) / max(
            self._loop_iterations, 1
        )
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "loop_iterations": self._loop_iterations,
            "server_restart_count": self._server_restart_count,
            "backup_count": self._backup_count,
            "uptime_ratio": round(uptime_ratio, 4),
        }

    def _evolve_daemon_config(
        self, learn_result: Dict[str, Any], mutable_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        changes = {}
        uptime = learn_result.get("uptime_ratio", 1.0)
        restarts = learn_result.get("server_restart_count", 0)

        if uptime < 0.95 or restarts > 3:
            changes["watchdog_interval"] = max(
                10, mutable_config.get("watchdog_interval", 30) // 2
            )
            changes["max_restart_attempts"] = min(
                10, mutable_config.get("max_restart_attempts", 5) + 1
            )
        else:
            changes["watchdog_interval"] = 30
            changes["max_restart_attempts"] = 5

        if restarts > 5:
            changes["restart_cooldown"] = min(
                300, mutable_config.get("restart_cooldown", 60) * 2
            )

        return {"rules_modified": changes, "skills_created": []}

    def _cleanup(self):
        STOP_FILE.unlink(missing_ok=True)
        PID_FILE.unlink(missing_ok=True)
        _stop_server()


__all__ = ["TianjiDaemon"]
