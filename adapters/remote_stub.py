# -*- coding: utf-8-sig -*-
"""远程适配器策略 stub — 代理至 core.shared.remote_stub [SSS-PhaseA]"""

from core.shared.remote_stub import RemoteAdapterStrategy  # noqa: F401
from core.shared.remote_stub import RemoteStubFactory  # noqa: F401

PLUGIN_INFO = RemoteStubFactory.create_plugin_info(
    name="remote_adapter",
    category="adapter",
    protocols=["IAdapterStrategy"],
    description="远程平台适配策略 (灵境跨平台网关 stub)",
)

__all__ = ["RemoteAdapterStrategy", "PLUGIN_INFO"]
