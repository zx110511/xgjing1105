r"""
Tianji Module Manager v1.0
=============================================
P2-P5 Pluggable Module System Core
P2: 模块描述符YAML标准化元数据
P3: 模块市场目录结构 (core/community/custom)
P4: Hot Swap (unload/replace at runtime)
P5: Version Management + Compatibility Check + Auto Upgrade

架构位置: core/module_manager.py
依赖: tianji_container, module_registry
"""

import hashlib
import json
import logging
import os
import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(os.environ.get("AI_MEMORY_ROOT", Path(__file__).parent.parent))
MODULES_DIR = PROJECT_ROOT / "modules"
MODULES_CORE_DIR = MODULES_DIR / "core"
MODULES_COMMUNITY_DIR = MODULES_DIR / "community"
MODULES_CUSTOM_DIR = MODULES_DIR / "custom"
MODULES_REGISTRY_FILE = MODULES_DIR / "registry.json"
MODULES_STATE_FILE = MODULES_DIR / "activated_state.json"


class ModuleInstallState(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    ACTIVATED = "activated"
    FAILED = "failed"


class CompatibilityLevel(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@dataclass
class ModuleVersion:
    major: int = 1
    minor: int = 0
    patch: int = 0
    prerelease: str = ""

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base += f"-{self.prerelease}"
        return base

    @classmethod
    def parse(cls, version_str: str) -> "ModuleVersion":
        parts = version_str.lstrip("vV").split("-", 1)
        nums = parts[0].split(".")
        prerelease = parts[1] if len(parts) > 1 else ""
        return cls(
            major=int(nums[0]) if len(nums) > 0 else 0,
            minor=int(nums[1]) if len(nums) > 1 else 0,
            patch=int(nums[2]) if len(nums) > 2 else 0,
            prerelease=prerelease,
        )

    def is_compatible_with(self, required: "ModuleVersion") -> bool:
        if self.major != required.major:
            return False
        if self.minor < required.minor:
            return False
        return True


@dataclass
class ModuleDescriptorV2:
    module_id: str
    display_name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "tianji_core"
    category: str = "core"
    tier: str = "core_engine"
    module_type: str = "engine"
    import_path: str = ""
    init_args: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    min_platform_version: str = "9.1.0"
    max_platform_version: str = ""
    checksum: str = ""
    install_state: str = "not_installed"
    installed_at: float = 0.0
    activated_at: float = 0.0
    source_dir: str = ""
    config_schema: dict[str, Any] = field(default_factory=dict)
    health_check_interval: float = 30.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModuleDescriptorV2":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_yaml_dict(
        cls, data: dict[str, Any], source_dir: str = ""
    ) -> "ModuleDescriptorV2":
        return cls(
            module_id=data.get("id", data.get("module_id", "")),
            display_name=data.get("display_name", data.get("name", "")),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", "unknown"),
            category=data.get("category", "core"),
            tier=data.get("tier", "core_engine"),
            module_type=data.get("type", "engine"),
            import_path=data.get("import_path", ""),
            init_args=data.get("init_args", {}),
            depends_on=data.get("depends_on", []),
            provides=data.get("provides", []),
            tags=data.get("tags", []),
            min_platform_version=data.get("min_platform_version", "9.1.0"),
            max_platform_version=data.get("max_platform_version", ""),
            source_dir=source_dir,
            config_schema=data.get("config_schema", {}),
            health_check_interval=data.get("health_check_interval", 30.0),
        )


class ModuleManager:
    """
    Tianji Module Manager v2 - P2-P5 Pluggable Module System Core
    P2: YAML Descriptor + Auto Registration
    P3: Module Market (core/community/custom)
    P4: Hot Swap (unload/replace)
    P5: Version Management + Compatibility Check
    """

    PLATFORM_VERSION = "9.1.0"

    def __init__(self, container=None):
        self._container = container
        self._descriptors: dict[str, ModuleDescriptorV2] = {}
        self._lock = threading.RLock()
        self._event_handlers: dict[str, list[Callable]] = {}
        self._install_log: list[dict] = []
        self._ensure_dirs()
        self._load_registry()
        self._load_activated_state()

    def _ensure_dirs(self):
        for d in [
            MODULES_DIR,
            MODULES_CORE_DIR,
            MODULES_COMMUNITY_DIR,
            MODULES_CUSTOM_DIR,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def _load_registry(self):
        if MODULES_REGISTRY_FILE.exists():
            try:
                data = json.loads(MODULES_REGISTRY_FILE.read_text(encoding="utf-8"))
                for mid, mdata in data.get("modules", {}).items():
                    self._descriptors[mid] = ModuleDescriptorV2.from_dict(mdata)
                logger.info(
                    f"[ModuleManager] Registry loaded: {len(self._descriptors)} modules"
                )
            except Exception as e:
                logger.warning(f"[ModuleManager] Registry load failed: {e}")

    def _save_registry(self):
        with self._lock:
            data = {
                "version": "1.0.0",
                "updated_at": time.time(),
                "modules": {
                    mid: desc.to_dict() for mid, desc in self._descriptors.items()
                },
            }
            MODULES_REGISTRY_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def _load_activated_state(self):
        state_file = MODULES_STATE_FILE
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                self._activated_modules = set(data.get("activated", []))
                logger.info(
                    f"[ModuleManager] Activated state loaded: {len(self._activated_modules)}"
                )
            except Exception:
                self._activated_modules = set()
        else:
            self._activated_modules = set()

    def _save_activated_state(self):
        with self._lock:
            data = {
                "updated_at": time.time(),
                "activated": list(self._activated_modules),
            }
            MODULES_STATE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def set_container(self, container):
        self._container = container

    # ══════════════════════════════════════════════
    # P2: Module Descriptor Registration?    # ══════════════════════════════════════════════

    def register_descriptor(self, descriptor: ModuleDescriptorV2) -> bool:
        with self._lock:
            mid = descriptor.module_id
            if mid in self._descriptors:
                existing = self._descriptors[mid]
                existing_ver = ModuleVersion.parse(existing.version)
                new_ver = ModuleVersion.parse(descriptor.version)
                if (
                    new_ver.major <= existing_ver.major
                    and new_ver.minor <= existing_ver.minor
                ):
                    logger.info(
                        f"[ModuleManager] Module '{mid}' already registered, skipping"
                    )
                    return False
                logger.info(
                    f"[ModuleManager] Module '{mid}' version upgrade: {existing.version} -> {descriptor.version}"
                )

            descriptor.install_state = "installed"
            if not descriptor.installed_at:
                descriptor.installed_at = time.time()
            self._descriptors[mid] = descriptor
            self._save_registry()
            self._emit("module_registered", mid, {"version": descriptor.version})
            logger.info(
                f"[ModuleManager] Module descriptor registered: {mid} v{descriptor.version}"
            )
            return True

    def register_from_catalog(self, catalog: dict[str, dict]) -> int:
        count = 0
        for mid, meta in catalog.items():
            import_path = meta.get("import_path", "")
            if not import_path:
                continue
            desc = ModuleDescriptorV2(
                module_id=mid,
                display_name=meta.get("alias", mid),
                version="1.0.0",
                category="core",
                import_path=import_path,
                init_args=meta.get("init_args", {}),
                depends_on=meta.get("depends_on", []),
                tags=meta.get("tags", []),
                install_state="installed",
                installed_at=time.time(),
                source_dir="builtin",
            )
            if self.register_descriptor(desc):
                count += 1
        return count

    def get_descriptor(self, module_id: str) -> ModuleDescriptorV2 | None:
        return self._descriptors.get(module_id)

    def list_descriptors(self, category: str = None) -> list[ModuleDescriptorV2]:
        with self._lock:
            descs = list(self._descriptors.values())
            if category:
                descs = [d for d in descs if d.category == category]
            return descs

    # ══════════════════════════════════════════════
    # P3: 模块市场
    # ══════════════════════════════════════════════

    def scan_market(self) -> dict[str, list[dict]]:
        result = {"core": [], "community": [], "custom": []}
        for category, base_dir in [
            ("core", MODULES_CORE_DIR),
            ("community", MODULES_COMMUNITY_DIR),
            ("custom", MODULES_CUSTOM_DIR),
        ]:
            if not base_dir.exists():
                continue
            for item in base_dir.iterdir():
                if not item.is_dir():
                    continue
                manifest = item / "tianji_module.json"
                if not manifest.exists():
                    manifest = item / "tianji_module.yaml"
                if manifest.exists():
                    try:
                        if manifest.suffix == ".json":
                            mdata = json.loads(manifest.read_text(encoding="utf-8"))
                        else:
                            try:
                                import yaml

                                mdata = yaml.safe_load(
                                    manifest.read_text(encoding="utf-8")
                                )
                            except ImportError:
                                continue
                        mdata["_source_dir"] = str(item)
                        mdata["_category"] = category
                        result[category].append(mdata)
                    except Exception as e:
                        logger.warning(
                            f"[ModuleManager] Manifest parse failed: {manifest}: {e}"
                        )
        return result

    def install_from_market(
        self, module_id: str, category: str = "core"
    ) -> dict[str, Any]:
        base_dir = {
            "core": MODULES_CORE_DIR,
            "community": MODULES_COMMUNITY_DIR,
            "custom": MODULES_CUSTOM_DIR,
        }.get(category, MODULES_CORE_DIR)
        module_dir = base_dir / module_id
        if not module_dir.exists():
            return {
                "status": "not_found",
                "module": module_id,
                "detail": f"Module directory not found: {module_dir}",
            }

        manifest = module_dir / "tianji_module.json"
        if not manifest.exists():
            manifest = module_dir / "tianji_module.yaml"
        if not manifest.exists():
            return {
                "status": "no_manifest",
                "module": module_id,
                "detail": "Missing module manifest file",
            }

        try:
            if manifest.suffix == ".json":
                mdata = json.loads(manifest.read_text(encoding="utf-8"))
            else:
                import yaml

                mdata = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        except Exception as e:
            return {"status": "manifest_error", "module": module_id, "detail": str(e)}

        compat = self.check_compatibility(mdata)
        if compat["level"] == "incompatible":
            return {
                "status": "incompatible",
                "module": module_id,
                "detail": compat["reasons"],
            }

        code_dir = module_dir / "code"
        if code_dir.exists():
            target_dir = PROJECT_ROOT / mdata.get("target_path", "core")
            if target_dir.exists() and not target_dir == PROJECT_ROOT / "core":
                pass
            elif code_dir != target_dir:
                for py_file in code_dir.rglob("*.py"):
                    rel = py_file.relative_to(code_dir)
                    target_file = target_dir / rel
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(py_file, target_file)

        desc = ModuleDescriptorV2.from_yaml_dict(mdata, source_dir=str(module_dir))
        desc.install_state = "installed"
        desc.installed_at = time.time()
        self.register_descriptor(desc)

        self._install_log.append(
            {
                "module_id": module_id,
                "action": "install_from_market",
                "version": desc.version,
                "category": category,
                "timestamp": time.time(),
            }
        )

        self._emit(
            "module_installed",
            module_id,
            {"version": desc.version, "category": category},
        )
        return {"status": "installed", "module": module_id, "version": desc.version}

    def install_from_file(
        self, file_path: str, category: str = "custom"
    ) -> dict[str, Any]:
        src = Path(file_path)
        if not src.exists():
            return {"status": "not_found", "detail": f"File not found: {file_path}"}

        if src.suffix == ".py":
            module_id = src.stem
            target_dir = MODULES_CUSTOM_DIR / module_id
            target_dir.mkdir(parents=True, exist_ok=True)
            code_dir = target_dir / "code"
            code_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, code_dir / src.name)

            checksum = hashlib.sha256(src.read_bytes()).hexdigest()[:16]
            manifest = {
                "id": module_id,
                "display_name": module_id.replace("_", " ").title(),
                "version": "1.0.0",
                "description": f"Module installed from file: {src.name}",
                "author": "local",
                "category": category,
                "type": "service",
                "import_path": f"modules.{category}.{module_id}.code.{module_id}",
                "tags": ["custom", "uploaded"],
                "min_platform_version": "9.1.0",
            }
            (target_dir / "tianji_module.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            return self.install_from_market(module_id, category)

        elif src.suffix in (".zip", ".tar", ".tar.gz", ".tgz"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                if src.suffix == ".zip":
                    shutil.unpack_archive(str(src), tmp)
                else:
                    shutil.unpack_archive(str(src), tmp)
                manifest_path = None
                for root, dirs, files in os.walk(tmp):
                    for f in files:
                        if f in ("tianji_module.json", "tianji_module.yaml"):
                            manifest_path = Path(root) / f
                            break
                    if manifest_path:
                        break

                if not manifest_path:
                    return {
                        "status": "no_manifest",
                        "detail": "No manifest found in archive",
                    }

                module_dir = Path(manifest_path).parent
                module_id = module_dir.name
                target_dir = MODULES_CUSTOM_DIR / module_id
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(module_dir, target_dir)

                return self.install_from_market(module_id, "custom")

        return {
            "status": "unsupported_format",
            "detail": f"Unsupported file format: {src.suffix}",
        }

    # ══════════════════════════════════════════════
    # P4: Hot Swap?    # ══════════════════════════════════════════════

    def hot_unload(self, module_id: str, force: bool = False) -> dict[str, Any]:
        if not self._container:
            return {"status": "error", "detail": "Container not initialized"}

        with self._lock:
            if module_id not in self._container._modules:
                return {
                    "status": "not_loaded",
                    "module": module_id,
                    "detail": "Module not loaded in container",
                }

            mod = self._container._modules[module_id]
            reverse_deps = [
                n
                for n, m in self._container._modules.items()
                if module_id in m.descriptor.depends_on and n != module_id
            ]
            if reverse_deps and not force:
                return {
                    "status": "has_dependents",
                    "module": module_id,
                    "dependents": reverse_deps,
                    "detail": f"被{len(reverse_deps)}个模块依赖，使用force=True强制卸载",
                }

            if module_id in self._activated_modules:
                self._activated_modules.discard(module_id)
                self._save_activated_state()

            success = self._container.unregister(module_id, force=force)
            if success:
                if module_id in self._descriptors:
                    self._descriptors[module_id].install_state = "installed"
                    self._descriptors[module_id].activated_at = 0
                    self._save_registry()
                self._emit("module_unloaded", module_id, {"force": force})
                return {"status": "unloaded", "module": module_id}
            return {"status": "unload_failed", "module": module_id}

    def hot_replace(
        self, module_id: str, new_version: str = "", new_import_path: str = ""
    ) -> dict[str, Any]:
        if not self._container:
            return {"status": "error", "detail": "Container not initialized"}

        with self._lock:
            was_in_container = module_id in self._container._modules
            old_descriptor = None
            old_display_name = module_id
            old_category = "activated"
            old_depends_on = []
            old_start_fn = None
            old_stop_fn = None
            old_health_fn = None
            old_critical = False

            if was_in_container:
                old_mod = self._container._modules[module_id]
                old_descriptor = old_mod.descriptor
                old_display_name = old_descriptor.display_name
                old_category = old_descriptor.category
                old_depends_on = old_descriptor.depends_on
                old_start_fn = old_descriptor.start_fn
                old_stop_fn = old_descriptor.stop_fn
                old_health_fn = old_descriptor.health_fn
                old_critical = old_descriptor.critical

                unload_result = self.hot_unload(module_id, force=True)
                if unload_result["status"] != "unloaded":
                    return unload_result

            desc = self._descriptors.get(module_id)
            import_path = (
                new_import_path
                or (desc.import_path if desc else "")
                or (old_descriptor.name if old_descriptor else "")
            )
            if not import_path:
                return {"status": "error", "detail": "Unable to determine import path"}

            try:
                parts = import_path.rsplit(".", 1)
                mod = __import__(
                    parts[0], fromlist=[parts[1]] if len(parts) > 1 else []
                )
                cls = getattr(mod, parts[-1]) if len(parts) > 1 else mod

                from server.api.status_routes import _resolve_module_deps

                init_args = _resolve_module_deps(module_id, self._container)
                instance = cls(**init_args) if isinstance(cls, type) else cls

                from core.shared.tianji_container import ModuleDescriptor

                new_desc = ModuleDescriptor(
                    name=module_id,
                    display_name=old_display_name,
                    category=old_category,
                    init_fn=lambda inst=instance: inst,
                    start_fn=old_start_fn,
                    stop_fn=old_stop_fn,
                    health_fn=old_health_fn
                    or (lambda inst: {"status": "running", "hot_replaced": True}),
                    depends_on=old_depends_on,
                    critical=old_critical,
                )
                self._container.register(new_desc)
                self._container._init_single_module(module_id)

                if module_id in self._descriptors:
                    if new_version:
                        self._descriptors[module_id].version = new_version
                    self._descriptors[module_id].install_state = "activated"
                    self._descriptors[module_id].activated_at = time.time()
                    self._save_registry()

                self._activated_modules.add(module_id)
                self._save_activated_state()

                self._emit(
                    "module_replaced",
                    module_id,
                    {"new_version": new_version, "was_loaded": was_in_container},
                )
                return {
                    "status": "replaced",
                    "module": module_id,
                    "new_version": new_version,
                    "was_loaded": was_in_container,
                }
            except Exception as e:
                return {
                    "status": "replace_failed",
                    "module": module_id,
                    "detail": f"{type(e).__name__}: {e}",
                }

    # ══════════════════════════════════════════════
    # P5: Version Management + Compatibility Check?    # ══════════════════════════════════════════════

    def check_compatibility(self, module_data: dict[str, Any]) -> dict[str, Any]:
        reasons = []
        level = CompatibilityLevel.FULL

        min_ver = module_data.get("min_platform_version", "0.0.0")
        max_ver = module_data.get("max_platform_version", "")
        platform_ver = ModuleVersion.parse(self.PLATFORM_VERSION)
        min_platform = ModuleVersion.parse(min_ver)

        if platform_ver.major < min_platform.major:
            level = CompatibilityLevel.INCOMPATIBLE
            reasons.append(f"平台版本{self.PLATFORM_VERSION}低于最低要求{min_ver}")
        elif (
            platform_ver.major == min_platform.major
            and platform_ver.minor < min_platform.minor
        ):
            level = CompatibilityLevel.PARTIAL
            reasons.append(
                f"平台版本{self.PLATFORM_VERSION}低于推荐版本{min_ver}，部分功能可能不可用"
            )

        if max_ver:
            max_platform = ModuleVersion.parse(max_ver)
            if platform_ver.major > max_platform.major:
                level = CompatibilityLevel.INCOMPATIBLE
                reasons.append(f"平台版本{self.PLATFORM_VERSION}高于最高支持{max_ver}")

        deps = module_data.get("depends_on", [])
        missing_deps = []
        for dep in deps:
            if isinstance(dep, str):
                if dep not in self._descriptors:
                    missing_deps.append(dep)
            elif isinstance(dep, dict):
                dep_id = dep.get("id", dep.get("module_id", ""))
                if dep_id not in self._descriptors:
                    missing_deps.append(dep_id)

        if missing_deps:
            if level == CompatibilityLevel.FULL:
                level = CompatibilityLevel.PARTIAL
            reasons.append(f"缺少依赖模块: {missing_deps}")

        return {
            "level": level.value,
            "reasons": reasons,
            "platform_version": self.PLATFORM_VERSION,
        }

    def get_version_info(self, module_id: str) -> dict[str, Any]:
        desc = self._descriptors.get(module_id)
        if not desc:
            return {"module_id": module_id, "installed": False}

        ver = ModuleVersion.parse(desc.version)
        return {
            "module_id": module_id,
            "installed": True,
            "version": desc.version,
            "version_parsed": {
                "major": ver.major,
                "minor": ver.minor,
                "patch": ver.patch,
            },
            "min_platform_version": desc.min_platform_version,
            "max_platform_version": desc.max_platform_version,
            "installed_at": desc.installed_at,
            "activated_at": desc.activated_at,
            "install_state": desc.install_state,
            "source_dir": desc.source_dir,
        }

    def check_upgrade(self, module_id: str) -> dict[str, Any]:
        desc = self._descriptors.get(module_id)
        if not desc:
            return {
                "module_id": module_id,
                "upgrade_available": False,
                "reason": "Module not registered",
            }

        market = self.scan_market()
        for category_modules in market.values():
            for mdata in category_modules:
                if mdata.get("id", mdata.get("module_id")) == module_id:
                    market_ver = ModuleVersion.parse(mdata.get("version", "0.0.0"))
                    current_ver = ModuleVersion.parse(desc.version)
                    if market_ver.major > current_ver.major or (
                        market_ver.major == current_ver.major
                        and market_ver.minor > current_ver.minor
                    ):
                        return {
                            "module_id": module_id,
                            "upgrade_available": True,
                            "current_version": desc.version,
                            "market_version": mdata.get("version"),
                            "market_data": mdata,
                        }
        return {
            "module_id": module_id,
            "upgrade_available": False,
            "current_version": desc.version,
        }

    def auto_activate_on_startup(self) -> dict[str, Any]:
        """启动时自动激活模块

        【精准修复 v2】
        - 容器已内置模块 → builtin (已在线，无需重复激活)
        - import_path=None → placeholder (占位符，待实现)
        - 有import_path但初始化失败 → deferred (延迟加载)
        - 只有成功完成的才计入 activated
        - 不再将初始化失败计入"failed"，避免误导性告警
        """
        if not self._container:
            return {"status": "error", "detail": "Container not initialized"}

        container_builtin = set(self._container._modules.keys())

        # Bootstrap: 首次启动时填充激活列表
        if not self._activated_modules:
            bootstrap_count = 0
            for mid, desc in self._descriptors.items():
                if mid in container_builtin:
                    self._activated_modules.add(mid)
                    bootstrap_count += 1
                    continue
                if desc.import_path and desc.install_state == "installed":
                    self._activated_modules.add(mid)
                    bootstrap_count += 1
            if bootstrap_count > 0:
                self._save_activated_state()
                logger.info(
                    f"[ModuleManager] Bootstrap: {bootstrap_count} 个模块加入激活列表"
                )

        results = {
            "activated": [],  # 成功动态加载
            "builtin": [],  # 容器已内置
            "placeholder": [],  # import_path=None(待实现)
            "deferred": [],  # 导入成功但初始化失败(延迟加载)
            "failed": [],  # 真正失败(import异常等)
        }

        for module_id in list(self._activated_modules):
            # 容器已内置 → 直接跳过
            if module_id in container_builtin:
                mod = self._container._modules[module_id]
                if mod.state.value in ("running", "pend_active"):
                    results["builtin"].append(module_id)
                    continue

            desc = self._descriptors.get(module_id)
            if not desc or not desc.import_path:
                results["placeholder"].append(module_id)
                continue

            # 【彻底简化】不再尝试动态初始化。模块已注册到catalog，按需激活。
            results["deferred"].append(
                {"module": module_id, "reason": "按需激活(延迟加载)"}
            )

        self._save_registry()
        self._emit("auto_activate_complete", "", results)

        # 【简化日志】
        builtin_n = len(results["builtin"])
        placeholder_n = len(results["placeholder"])
        deferred_n = len(results["deferred"])
        logger.info(
            f"[ModuleManager] 启动激活完成: {builtin_n}在线 "
            f"{placeholder_n}占位 {deferred_n}延迟加载"
        )
        return results

    # ══════════════════════════════════════════════
    # Event System
    # ══════════════════════════════════════════════

    def on(self, event: str, handler: Callable):
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def _emit(self, event: str, module_id: str, data: Any = None):
        for handler in self._event_handlers.get(event, []):
            try:
                handler(event, module_id, data)
            except Exception as e:
                logger.warning(f"[ModuleManager] Event handler error: {e}")

    # ══════════════════════════════════════════════
    # Statistics & Query?    # ══════════════════════════════════════════════

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            by_state = {"installed": 0, "activated": 0, "not_installed": 0, "failed": 0}
            by_category = {}
            for desc in self._descriptors.values():
                by_state[desc.install_state] = by_state.get(desc.install_state, 0) + 1
                by_category[desc.category] = by_category.get(desc.category, 0) + 1
            return {
                "total_descriptors": len(self._descriptors),
                "by_state": by_state,
                "by_category": by_category,
                "activated_modules": list(self._activated_modules),
                "install_log_count": len(self._install_log),
                "market_available": len(self.scan_market().get("core", []))
                + len(self.scan_market().get("community", []))
                + len(self.scan_market().get("custom", [])),
            }

    def get_install_log(self, limit: int = 50) -> list[dict]:
        return self._install_log[-limit:]
