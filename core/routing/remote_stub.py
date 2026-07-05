# -*- coding: utf-8-sig -*-
"""远程路由策略 stub — 代理至 core.shared.remote_stub [SSS-PhaseA]"""

from core.shared.remote_stub import RemoteRoutingStrategy  # noqa: F401
from core.shared.remote_stub import RemoteStubFactory  # noqa: F401

PLUGIN_INFO = RemoteStubFactory.create_plugin_info(
    name="remote_routing",
    category="route",
    protocols=["ITaskRouter"],
    description="灵境远程路由策略 (gRPC stub)",
)

__all__ = ["RemoteRoutingStrategy", "PLUGIN_INFO"]
