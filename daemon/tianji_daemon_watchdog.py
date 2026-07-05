# -*- coding: utf-8-sig -*-
"""tianji_daemon_Watchdog — 从 tianji_daemon.py 拆分 (SSS-PhaseB)

源文件: tianji_daemon.py
"""

import os
import sys



from typing import Optional

class Watchdog:
    def __init__(self):
        self.restart_count = 0
        self.last_restart_time = 0.0

    def check(self) -> dict[str, bool]:
        results = {}
        healthy = _check_health(TIANJI_SERVICE["health_url"])
        port_ok = _is_port_listening(TIANJI_SERVICE["port"])
        results["server_health"] = healthy
        results["server_port"] = port_ok

        if not healthy or not port_ok:
            now = time.time()
            if now - self.last_restart_time < RESTART_COOLDOWN:
                self.restart_count += 1
            else:
                self.restart_count = 1

            if self.restart_count > MAX_RESTART_ATTEMPTS:
                log.critical(
                    f"Max restart attempts ({MAX_RESTART_ATTEMPTS}) reached. "
                    f"Manual intervention required."
                )
                return results

            log.warning(
                f"Server unhealthy (health={healthy}, port={port_ok}), "
                f"restarting (attempt {self.restart_count}/{MAX_RESTART_ATTEMPTS})..."
            )
            _start_server()
            self.last_restart_time = now
        else:
            if self.restart_count > 0:
                log.info("Server recovered, resetting restart counter")
            self.restart_count = 0

        return results


__all__ = ["Watchdog"]
