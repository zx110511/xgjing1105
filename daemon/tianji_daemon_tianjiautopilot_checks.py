# -*- coding: utf-8-sig -*-
"""tianji_daemon_tianjiautopilot_checks.py — TianjiAutopilotChecksMixin (SSS-PhaseB)

从 tianji_daemon_tianjiautopilot.py 拆分的方法组: checks
源文件: tianji_daemon_tianjiautopilot.py
"""

import os
import sys
from typing import Optional


from typing import Optional

class TianjiAutopilotChecksMixin:
    """checks方法组Mixin"""

    def _check_daemon_loop(self):
        try:
            pid_file = DAEMON_DIR / "tianji.pid"
            if pid_file.exists():
                return {"healthy": True, "pid_file": str(pid_file)}
            return {"healthy": False, "reason": "no_pid_file"}
        except Exception:
            return {"healthy": False, "reason": "check_error"}

    def _check_rest_api(self):
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{TIANJI_SERVICE['port']}/api/health"
            )
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read().decode("utf-8"))
            return {"healthy": data.get("status") == "healthy", "api": data}
        except Exception as e:
            return {"healthy": False, "reason": str(e)}

    def _check_websocket(self):
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{TIANJI_SERVICE['port']}/api/health"
            )
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read().decode("utf-8"))
            ws_ok = "ws" in str(data).lower() or data.get("status") == "healthy"
            return {"healthy": ws_ok, "detail": "ws_implied_by_api_health"}
        except Exception as e:
            return {"healthy": False, "reason": str(e)}

    def _check_sse(self):
        return {"healthy": True, "detail": "sse_implied_by_api_health"}

    def _check_chat_pipeline(self):
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{TIANJI_SERVICE['port']}/api/memory/stats"
            )
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "healthy": data.get("total_entries", 0) > 0,
                "entries": data.get("total_entries", 0),
            }
        except Exception as e:
            return {"healthy": False, "reason": str(e)}

    def _check_frontend(self):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{TIANJI_SERVICE['port']}/")
            resp = urllib.request.urlopen(req, timeout=5)
            return {"healthy": resp.status == 200, "status_code": resp.status}
        except Exception as e:
            return {"healthy": False, "reason": str(e)}
