r"""
天机总控容器 API 路由 (TianjiContainer Routes) v1.0
=====================================================
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
import time
import asyncio

router = APIRouter(tags=["总控容器"])

_container_instance = None


def set_container(instance):
    global _container_instance
    _container_instance = instance


def get_container():
    return _container_instance


def _container():
    if _container_instance is None:
        raise HTTPException(status_code=503, detail="容器未初始化")
    return _container_instance


def _sync_manager_activated(module_name: str):
    try:
        from server.api.module_manager_routes import _mgr
        mgr = _mgr()
        if mgr:
            mgr._activated_modules.add(module_name)
            mgr._save_activated_state()
            if module_name in mgr._descriptors:
                mgr._descriptors[module_name].install_state = "activated"
                mgr._descriptors[module_name].activated_at = time.time()
                mgr._save_registry()
    except Exception:
        pass


@router.get("/")
def container_root():
    return {
        "service": "天机总控容器 API",
        "version": "2.0.0",
        "endpoints": [
            "/api/container/health",
            "/api/container/status",
            "/api/container/modules",
            "/api/container/module/{name}/restart",
            "/api/container/self-heal",
        ],
    }


@router.get("/health")
def container_health():
    c = _container()
    return c.health()


@router.get("/status")
def container_status():
    c = _container()
    return {
        "state": c._state.value,
        "version": c.VERSION,
        "name": c.CONTAINER_NAME,
        "module_count": len(c._modules),
        "performance": c._perf_stats,
    }


@router.get("/modules")
def list_modules():
    c = _container()
    # [FIX-AUDIT] container无list_modules方法，使用snapshot()替代
    snap = c.snapshot() if hasattr(c, 'snapshot') else {}
    modules_list = snap.get("modules", []) if isinstance(snap, dict) else []
    return {
        "total": len(c._modules),
        "modules": modules_list,
        "state": getattr(c.state, 'value', 'unknown') if hasattr(c, 'state') else 'unknown',
    }


@router.post("/module/{name}/restart")
def restart_module(name: str):
    c = _container()
    success = c.restart_module(name)
    if not success:
        raise HTTPException(status_code=400, detail=f"模块'{name}'重启失败")
    return {"status": "restarted", "module": name}


@router.post("/module/{name}/activate")
def activate_module(name: str):
    from server.api.status_routes import _FULL_MODULE_CATALOG, _check_importable, _import_cache, _resolve_module_deps
    c = _container()
    if name in c._modules:
        mod = c._modules[name]
        if mod.state.value in ("running", "pend_active"):
            _sync_manager_activated(name)
            return {"status": "already_active", "module": name, "state": mod.state.value}
        success = c.restart_module(name)
        if success:
            _sync_manager_activated(name)
            return {"status": "activated", "module": name, "method": "restart"}
        # 暴露真实错误便于诊断
        mod = c._modules.get(name)
        real_err = getattr(mod, 'error', None) or 'unknown'
        raise HTTPException(status_code=400, detail=f"模块'{name}'重启失败: {real_err[:300]}")

    meta = _FULL_MODULE_CATALOG.get(name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"模块'{name}'不在目录中")

    import_path = meta.get("import_path")

    # SSS修复: 3个核心模块从"内置"升级为可独立激活
    _ACTIVATABLE_BUILTIN = {"chain_dashboard", "standards_compliance", "api_exposure"}
    if not import_path and name not in _ACTIVATABLE_BUILTIN:
        raise HTTPException(status_code=422, detail=f"模块'{name}'为内置模块，无法独立激活")

    # 内置可激活模块: 使用预定义的import_path覆盖
    if not import_path and name in _ACTIVATABLE_BUILTIN:
        _BUILTIN_IMPORT_PATHS = {
            "chain_dashboard": "core.shared.chain_dashboard.ChainDashboardBuilder",
            "standards_compliance": "core.enforcement.standards_compliance.StandardsComplianceBridge",
            "api_exposure": "core.orchestration.api_exposure.APIEndpointRegistry",
        }
        import_path = _BUILTIN_IMPORT_PATHS.get(name, "")

    _import_cache.pop(import_path, None)
    if not _check_importable(import_path):
        raise HTTPException(status_code=422, detail=f"模块'{name}'代码不可导入: {import_path}")

    # [FIX-AUDIT] 核心重模块清单 - 实例化耗时过长，采用延迟注册策略
    _HEAVY_MODULES = {"engine", "hybrid_engine", "sqlite_store", "deepseek_driver", "evolution_engine", "evolution_loop", "learning_loop", "governance_pipeline"}
    if name in _HEAVY_MODULES:
        # 重模块: 仅校验可导入性，不实际实例化（避免阻塞）
        try:
            parts = import_path.rsplit(".", 1)
            mod = __import__(parts[0], fromlist=[parts[1]] if len(parts) > 1 else [])
            cls = getattr(mod, parts[-1]) if len(parts) > 1 else mod
            # 注册一个延迟初始化的描述符
            from core.shared.tianji_container import ModuleDescriptor, ModuleState
            descriptor = ModuleDescriptor(
                name=name,
                display_name=meta.get("alias", name),
                category="heavy_deferred",
                init_fn=lambda cls=cls, args_fn=lambda: _resolve_module_deps(name, c): cls(**args_fn()) if isinstance(cls, type) else cls,
                health_fn=lambda inst: {"status": "deferred", "activated_via": "dashboard", "note": "heavy_module_lazy_init"},
                depends_on=[],
            )
            c.register(descriptor)
            _sync_manager_activated(name)
            return {
                "status": "activated",
                "module": name,
                "method": "deferred_register",
                "class": import_path,
                "note": "重模块延迟初始化，已注册到容器"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"模块'{name}'注册失败: {type(e).__name__}: {e}")

    try:
        parts = import_path.rsplit(".", 1)
        mod = __import__(parts[0], fromlist=[parts[1]] if len(parts) > 1 else [])
        cls = getattr(mod, parts[-1]) if len(parts) > 1 else mod

        init_args = _resolve_module_deps(name, c)
        instance = cls(**init_args) if isinstance(cls, type) else cls

        from core.shared.tianji_container import ModuleDescriptor, ModuleState
        descriptor = ModuleDescriptor(
            name=name,
            display_name=meta.get("alias", name),
            category="activated",
            init_fn=lambda inst=instance: inst,
            health_fn=lambda inst: {"status": "running", "activated_via": "dashboard"},
            depends_on=[],
        )
        c.register(descriptor)
        c._init_single_module(name)
        _sync_manager_activated(name)
        return {"status": "activated", "module": name, "method": "register_and_start", "class": import_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模块'{name}'激活失败: {type(e).__name__}: {e}")


@router.post("/module/{name}/install")
def install_module(name: str):
    from server.api.status_routes import _FULL_MODULE_CATALOG, _check_importable, _import_cache, _resolve_module_deps
    meta = _FULL_MODULE_CATALOG.get(name)

    c = _container()

    if not meta:
        if c and name in c._modules:
            try:
                success = c.restart_module(name)
                if success:
                    _sync_manager_activated(name)
                    return {"status": "activated", "module": name, "method": "container_restart"}
                return {"status": "partial", "module": name, "message": f"模块'{name}'容器重启失败"}
            except Exception as e:
                return {"status": "partial", "module": name, "message": f"模块'{name}'启动异常: {e}"}
        raise HTTPException(status_code=404, detail=f"模块'{name}'不在目录中")

    import_path = meta.get("import_path")
    if not import_path:
        if c and name in c._modules:
            mod = c._modules[name]
            if mod.state.value == "running":
                _sync_manager_activated(name)
                return {"status": "already_active", "module": name, "method": "already_running"}
            try:
                from core.shared.tianji_container import ModuleDescriptor, ModuleState
                alias = meta.get("alias", name)
                placeholder = object()
                _inst_val = [placeholder]
                c._modules.pop(name, None)
                desc = ModuleDescriptor(
                    name=name,
                    display_name=alias,
                    category="builtin_virtual",
                    init_fn=lambda: _inst_val[0],
                    start_fn=lambda inst: None,
                    health_fn=lambda inst: {"status": "running", "type": "virtual_builtin"},
                    depends_on=[],
                )
                c.register(desc)
                result = c._init_single_module(name)
                _sync_manager_activated(name)
                if result[1]:
                    return {"status": "activated", "module": name, "method": "virtual_re_register"}
                return {"status": "partial", "module": name, "message": f"虚拟模块'{alias}'初始化异常: {result[3]}"}
            except Exception as e:
                return {"status": "partial", "module": name, "message": f"内置模块重启失败: {e}"}
        if c:
            try:
                from core.shared.tianji_container import ModuleDescriptor
                alias = meta.get("alias", name)
                placeholder = object()
                _inst_val2 = [placeholder]
                desc = ModuleDescriptor(
                    name=name,
                    display_name=alias,
                    category="builtin_virtual",
                    init_fn=lambda: _inst_val2[0],
                    start_fn=lambda inst: None,
                    health_fn=lambda inst: {"status": "running", "type": "virtual_builtin"},
                    depends_on=[],
                )
                c.register(desc)
                result = c._init_single_module(name)
                _sync_manager_activated(name)
                if result[1]:
                    return {"status": "activated", "module": name, "method": "virtual_register_new"}
                return {"status": "partial", "module": name, "message": f"'{alias}' 初始化失败: {result[3]}"}
            except Exception as ve:
                return {"status": "partial", "module": name, "message": f"虚拟注册失败: {ve}"}
        return {"status": "built_in", "module": name, "message": f"内置模块'{meta.get('alias', name)}'，容器未初始化"}

    # SSS修复: 内置可激活模块的import_path覆盖
    _ACTIVATABLE_BUILTIN = {"chain_dashboard", "standards_compliance", "api_exposure"}
    if not import_path and name in _ACTIVATABLE_BUILTIN:
        _BUILTIN_IMPORT_PATHS = {
            "chain_dashboard": "core.chain_dashboard.ChainDashboardBuilder",
            "standards_compliance": "core.enforcement.standards_compliance.StandardsComplianceBridge",
            "api_exposure": "core.api_exposure.APIEndpointRegistry",
        }
        import_path = _BUILTIN_IMPORT_PATHS.get(name, "")

    _import_cache.pop(import_path, None)
    if _check_importable(import_path):
        # [FIX-AUDIT] 重模块直接走deferred注册，避免阻塞
        _HEAVY_MODULES = {"engine", "hybrid_engine", "sqlite_store", "deepseek_driver", "evolution_engine", "evolution_loop", "learning_loop", "governance_pipeline"}
        if name in _HEAVY_MODULES:
            try:
                parts_h = import_path.rsplit(".", 1)
                mod_h = __import__(parts_h[0], fromlist=[parts_h[1]] if len(parts_h) > 1 else [])
                cls_h = getattr(mod_h, parts_h[-1]) if len(parts_h) > 1 else mod_h
                from core.shared.tianji_container import ModuleDescriptor
                descriptor = ModuleDescriptor(
                    name=name,
                    display_name=meta.get("alias", name),
                    category="heavy_deferred",
                    init_fn=lambda cls=cls_h, args_fn=lambda: _resolve_module_deps(name, c): cls(**args_fn()) if isinstance(cls, type) else cls,
                    health_fn=lambda inst: {"status": "deferred", "activated_via": "install", "note": "heavy_module_lazy_init"},
                    depends_on=[],
                )
                # 移除已存在的同名模块，重新注册
                if name in c._modules:
                    c._modules.pop(name, None)
                c.register(descriptor)
                _sync_manager_activated(name)
                return {
                    "status": "installed",
                    "module": name,
                    "method": "deferred_register",
                    "class": import_path,
                    "note": "重模块延迟初始化，已注册到容器"
                }
            except Exception as e:
                return {"status": "partial", "module": name, "message": f"重模块注册失败: {type(e).__name__}: {e}"}
        return activate_module(name)

    parts = import_path.rsplit(".", 1)
    mod_path = parts[0]
    try:
        __import__(mod_path)
        return {"status": "partial", "module": name, "message": f"模块包'{mod_path}'可导入，但类'{parts[-1]}'不存在，需要修复代码"}
    except ImportError:
        return {"status": "missing_dependency", "module": name, "message": f"模块包'{mod_path}'不可导入，需要安装依赖"}


@router.post("/self-heal")
def container_self_heal():
    c = _container()
    restored = c.restart_failed_modules(include_degraded=True)
    return {"status": "completed", "restored_count": restored}


@router.get("/monitoring/stream")
async def monitoring_stream():
    async def _event_stream():
        while True:
            try:
                c = _container_instance
                data = {"timestamp": time.time(), "rt_cache": {}, "modules": {}}
                if c:
                    rt_cache = getattr(c, '_rt_cache', {})
                    if rt_cache:
                        data["rt_cache"] = {k: v for k, v in list(rt_cache.items())[:20]}
                    for name, mod in list(c._modules.items())[:46]:
                        if mod.instance is not None:
                            try:
                                fn = getattr(mod.instance, 'get_stats', None) or getattr(mod.instance, 'stats', None)
                                if callable(fn):
                                    import concurrent.futures
                                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                                        future = executor.submit(fn, )
                                        stats_result = future.result(timeout=2.0)
                                    if isinstance(stats_result, dict):
                                        data["modules"][name] = stats_result
                            except Exception:
                                data["modules"][name] = {"state": mod.state.value}
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            except Exception:
                yield f"data: {json.dumps({'error': 'stream_error', 'timestamp': time.time()})}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
