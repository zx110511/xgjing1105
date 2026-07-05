# -*- coding: utf-8-sig -*-
"""main_static.py — 静态文件+SPA路由 (SSS-PhaseB拆分+PhaseE修复)

从 main.py 拆分，补充缺失的WEB_DIST/_MIME_TYPES定义。
app通过 from server.main import app 获取。
"""

import os
import sys
import time
from pathlib import Path

from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from server.main import app  # noqa: E402 — app在main.py中先创建

# ── 路径定义 ──
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent
AI_MEMORY_ROOT = Path(os.environ.get("AI_MEMORY_ROOT", str(_DEFAULT_ROOT)))
TIANJI_EDITION = os.environ.get("TIANJI_EDITION", "source-v9.1")
_EDITION_LABEL = {
    "compiled-exe": "编译版 (天机v9.1.exe)",
    "source-v8.0": "源码版 v8.0 (平台化研究)",
    "source-v9.0": "源码版 v9.0 (统一架构)",
    "source-v9.1": "源码版 v9.1 (SSS精炼)",
}.get(TIANJI_EDITION, TIANJI_EDITION)

WEB_DIST = AI_MEMORY_ROOT / "web" / "dist"

_MIME_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".eot": "application/vnd.ms-fontobject",
    ".webp": "image/webp",
    ".webm": "video/webm",
    ".mp4": "video/mp4",
    ".wasm": "application/wasm",
}

_HASHED_EXTENSIONS = {".js", ".mjs", ".css", ".wasm"}


def _get_mime_type(path: Path) -> str:
    return _MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")


def _is_hashed_filename(filename: str) -> bool:
    name = filename.rsplit(".", 1)[0] if "." in filename else filename
    parts = name.split("-")
    if len(parts) >= 2:
        last_part = parts[-1]
        if len(last_part) >= 8 and all(
            c in "0123456789abcdefABCDEF" for c in last_part
        ):
            return True
    return False


_FAVICON_PATH = WEB_DIST.parent / "public" / "vite.svg"

if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST / "assets")), name="static")

    @app.get("/assets/{file_path:path}")
    def serve_assets(file_path: str):
        full_path = WEB_DIST / "assets" / file_path
        if not full_path.exists():
            return Response(status_code=404)
        mime = _get_mime_type(full_path)
        headers: dict[str, str] = {"Content-Type": mime}
        if _is_hashed_filename(full_path.name):
            headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            headers["Cache-Control"] = "public, max-age=3600"
        return FileResponse(str(full_path), media_type=mime, headers=headers)


@app.get("/vite.svg")
def favicon():
    if _FAVICON_PATH and _FAVICON_PATH.exists():
        return FileResponse(
            str(_FAVICON_PATH),
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    return Response(content="", media_type="image/svg+xml")


@app.get("/")
def root():
    if (WEB_DIST / "index.html").exists():
        return FileResponse(
            str(WEB_DIST / "index.html"),
            media_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return {
        "service": "天机v9.1",
        "version": "9.1.0-sss",
        "edition": TIANJI_EDITION,
        "edition_label": _EDITION_LABEL,
        "engine": "ICME v9.1",
        "status": "healthy",
        "docs": "/docs",
    }


def _serve_spa():
    if (WEB_DIST / "index.html").exists():
        return FileResponse(
            str(WEB_DIST / "index.html"),
            media_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return {"error": "Frontend not built"}


@app.get("/dashboard")
@app.get("/memory")
@app.get("/knowledge-graph")
@app.get("/config")
@app.get("/monitor")
@app.get("/monitoring")
@app.get("/chat")
@app.get("/settings")
@app.get("/operations")
@app.get("/agents")
@app.get("/governance")
@app.get("/search")
@app.get("/mcp-tools")
@app.get("/standards")
@app.get("/sss-audit")
@app.get("/audit")
@app.get("/orchestrator")
@app.get("/deepseek")
def spa_routes():
    return _serve_spa()


@app.get("/api/health")
def health_check():
    from server.deps import engine
    from server.main import _START_TIME, _PROTOCOL_MODE_ACTIVE, _EVENT_WIRING_ACTIVE
    try:
        capacity = engine.get_layer_capacity_info()
    except Exception:
        capacity = {}
    return {
        "status": "healthy",
        "version": "9.1.0-sss",
        "edition": TIANJI_EDITION,
        "engine_ready": engine is not None,
        "layers": capacity,
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "protocol_mode": _PROTOCOL_MODE_ACTIVE,
        "event_wiring": _EVENT_WIRING_ACTIVE,
    }
