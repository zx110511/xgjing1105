r"""
天机模块管理 API 路由 (Module Manager Routes) v1.0
====================================================
P2: 模块描述符YAML + 自动注册
P3: 模块市场 (core/community/custom)
P4: 热插拔 (卸载/替换)
P5: 版本管理 + 兼容性检查
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import Dict, Any, Optional
import os
import time
import json
import shutil
from pathlib import Path

router = APIRouter(tags=["模块管理"])

_manager_instance = None


def set_manager(manager):
    global _manager_instance
    _manager_instance = manager


def _mgr():
    if _manager_instance is None:
        raise HTTPException(status_code=503, detail="模块管理器未初始化")
    return _manager_instance


@router.get("/")
def manager_root():
    return {
        "service": "天机模块管理器 API",
        "version": "1.0.0",
        "phases": {
            "P2": "模块描述符YAML + 自动注册",
            "P3": "模块市场 (core/community/custom)",
            "P4": "热插拔 (卸载/替换)",
            "P5": "版本管理 + 兼容性检查",
        },
        "endpoints": [
            "GET  /module-manager/descriptors",
            "GET  /module-manager/descriptor/{module_id}",
            "POST /module-manager/descriptor",
            "GET  /module-manager/market",
            "POST /module-manager/market/{module_id}/install",
            "POST /module-manager/upload",
            "POST /module-manager/hot-unload/{module_id}",
            "POST /module-manager/hot-replace/{module_id}",
            "GET  /module-manager/version/{module_id}",
            "GET  /module-manager/compatibility-check",
            "GET  /module-manager/upgrade-check/{module_id}",
            "POST /module-manager/auto-activate",
            "GET  /module-manager/stats",
            "GET  /module-manager/install-log",
        ],
    }


# ══════════════════════════════════════════════
# P2: 模块描述符
# ══════════════════════════════════════════════

@router.get("/descriptors")
def list_descriptors(category: Optional[str] = Query(None)):
    mgr = _mgr()
    descs = mgr.list_descriptors(category=category)
    return {"total": len(descs), "descriptors": [d.to_dict() for d in descs]}


@router.get("/descriptor/{module_id}")
def get_descriptor(module_id: str):
    mgr = _mgr()
    desc = mgr.get_descriptor(module_id)
    if not desc:
        raise HTTPException(status_code=404, detail=f"模块'{module_id}'描述符不存在")
    return desc.to_dict()


@router.post("/descriptor")
def register_descriptor(descriptor: Dict[str, Any]):
    from core.shared.module_manager import ModuleDescriptorV2
    mgr = _mgr()
    desc = ModuleDescriptorV2.from_dict(descriptor)
    if not desc.module_id:
        raise HTTPException(status_code=422, detail="module_id不能为空")
    success = mgr.register_descriptor(desc)
    return {"status": "registered" if success else "skipped", "module_id": desc.module_id}


@router.post("/register-catalog")
def register_from_catalog():
    from server.api.status_routes import _FULL_MODULE_CATALOG
    mgr = _mgr()
    count = mgr.register_from_catalog(_FULL_MODULE_CATALOG)
    return {"status": "ok", "registered_count": count}


# ══════════════════════════════════════════════
# P3: 模块市场
# ══════════════════════════════════════════════

@router.get("/market")
def scan_market():
    mgr = _mgr()
    market = mgr.scan_market()
    total = sum(len(v) for v in market.values())
    return {"total": total, "market": market}


@router.post("/market/{module_id}/install")
def install_from_market(module_id: str, category: str = Query("core")):
    mgr = _mgr()
    result = mgr.install_from_market(module_id, category=category)
    if result["status"] not in ("installed", "ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/upload")
async def upload_module(file: UploadFile = File(...), category: str = Query("custom")):
    mgr = _mgr()
    upload_dir = Path(os.environ.get("AI_MEMORY_ROOT", ".")) / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    result = mgr.install_from_file(str(file_path), category=category)
    try:
        file_path.unlink(missing_ok=True)
    except Exception:
        pass
    if result["status"] not in ("installed", "ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


# ══════════════════════════════════════════════
# P4: 热插拔
# ══════════════════════════════════════════════

@router.post("/hot-unload/{module_id}")
def hot_unload(module_id: str, force: bool = Query(False)):
    mgr = _mgr()
    result = mgr.hot_unload(module_id, force=force)
    if result["status"] == "error":
        raise HTTPException(status_code=503, detail=result)
    if result["status"] == "has_dependents" and not force:
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post("/hot-replace/{module_id}")
def hot_replace(module_id: str, new_version: str = Query(""), new_import_path: str = Query("")):
    mgr = _mgr()
    result = mgr.hot_replace(module_id, new_version=new_version, new_import_path=new_import_path)
    if result["status"] not in ("replaced", "ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


# ══════════════════════════════════════════════
# P5: 版本管理 + 兼容性检查
# ══════════════════════════════════════════════

@router.get("/version/{module_id}")
def get_version_info(module_id: str):
    mgr = _mgr()
    return mgr.get_version_info(module_id)


@router.post("/compatibility-check")
def check_compatibility(module_data: Dict[str, Any]):
    mgr = _mgr()
    return mgr.check_compatibility(module_data)


@router.get("/upgrade-check/{module_id}")
def check_upgrade(module_id: str):
    mgr = _mgr()
    return mgr.check_upgrade(module_id)


# ══════════════════════════════════════════════
# 自动激活
# ══════════════════════════════════════════════

@router.post("/auto-activate")
def auto_activate():
    mgr = _mgr()
    result = mgr.auto_activate_on_startup()
    return {"status": "completed", "results": result}


# ══════════════════════════════════════════════
# 统计与日志
# ══════════════════════════════════════════════

@router.get("/stats")
def get_stats():
    mgr = _mgr()
    return mgr.get_stats()


@router.get("/install-log")
def get_install_log(limit: int = Query(50)):
    mgr = _mgr()
    return {"log": mgr.get_install_log(limit=limit)}
