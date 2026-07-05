"""Container包 — SSS-PhaseB 瘦身后 (core + health + signal_bus + boot_registry)"""
from .core import TianjiContainer
from .module_lifecycle import ModuleState, ModuleDescriptor, ModuleInstance
from .health import ContainerHealthChecker
from .signal_bus import ContainerSignalBus
from .boot_registry import build_container, get_container, set_container
