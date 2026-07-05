# -*- coding: utf-8-sig -*-
"""main_config.py — config功能组 (SSS-PhaseB拆分+PhaseE修复)

从 main.py 拆分，补充缺失的app/engine导入。
"""

import json
import os
import sys
from pathlib import Path

from server.main import app

_DEFAULT_ROOT = Path(__file__).resolve().parent.parent
AI_MEMORY_ROOT = Path(os.environ.get("AI_MEMORY_ROOT", str(_DEFAULT_ROOT)))
TIANJI_EDITION = os.environ.get("TIANJI_EDITION", "source-v9.1")


def api_config():
    import json

    try:
        from core.shared.config import MEMORY_DATA_PATH

        data_path = str(MEMORY_DATA_PATH)
    except Exception:
        data_path = str(AI_MEMORY_ROOT / "data" / ".memory")

    config_file = AI_MEMORY_ROOT / "config" / "user_config.json"
    user_config = {}
    if config_file.exists():
        try:
            with open(config_file, encoding="utf-8") as f:
                user_config = json.load(f)
        except Exception:
            pass

    base_config = {
        "version": "9.1.0",
        "edition": TIANJI_EDITION,
        "port": int(os.environ.get("AI_MEMORY_PORT", "8771")),
        "host": os.environ.get("AI_MEMORY_HOST", "0.0.0.0"),
        "data_path": data_path,
        "working_max_entries": 500,
        "short_term_max_entries": 300,
        "llm_provider": "deepseek-chat",
        "embedding_provider": "sklearn-tfidf",
        "modules": {
            "memory": True,
            "search": True,
            "governance": True,
            "ops": True,
            "llm": True,
            "mcp": True,
            "orchestrator": True,
            "active": True,
            "platform": True,
            "summary": True,
            "websocket": True,
        },
        "features": [
            "六层ICME记忆",
            "语义搜索",
            "Agent调度",
            "治理审计",
            "自动运维",
            "WebSocket实时推送",
        ],
    }
    base_config.update(user_config)
    return base_config


@app.post("/api/config")
def api_config_save(body: dict):
    import json
    from datetime import datetime

    config_dir = AI_MEMORY_ROOT / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "user_config.json"
    backup_file = (
        config_dir
        / f"user_config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    try:
        if config_file.exists():
            import shutil

            shutil.copy2(config_file, backup_file)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)

        llm_cfg = body.get("llm", {})
        api_key = llm_cfg.get("api_key") if isinstance(llm_cfg, dict) else None
        base_url = llm_cfg.get("base_url") if isinstance(llm_cfg, dict) else None
        if api_key:
            env_file = AI_MEMORY_ROOT / ".env"
            env_lines = []
            if env_file.exists():
                with open(env_file, encoding="utf-8") as f:
                    env_lines = f.readlines()
            key_written = False
            url_written = False
            new_lines = []
            for line in env_lines:
                stripped = line.strip()
                if stripped.startswith("DEEPSEEK_API_KEY="):
                    new_lines.append(f"DEEPSEEK_API_KEY={api_key}\n")
                    key_written = True
                elif stripped.startswith("DEEPSEEK_BASE_URL=") and base_url:
                    new_lines.append(f"DEEPSEEK_BASE_URL={base_url}\n")
                    url_written = True
                else:
                    new_lines.append(line)
            if not key_written:
                new_lines.append(f"DEEPSEEK_API_KEY={api_key}\n")
            if not url_written and base_url:
                new_lines.append(f"DEEPSEEK_BASE_URL={base_url}\n")
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            os.environ["DEEPSEEK_API_KEY"] = api_key
            if base_url:
                os.environ["DEEPSEEK_BASE_URL"] = base_url
                os.environ["DEEPSEEK_API_URL"] = base_url

        return {
            "status": "ok",
            "saved_to": str(config_file),
            "keys_saved": list(body.keys()),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
