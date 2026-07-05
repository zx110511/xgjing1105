# -*- coding: utf-8-sig -*-
"""远程资产绑定 stub — 代理至 core.shared.remote_stub [SSS-PhaseA]"""

from core.shared.remote_stub import RemoteAssetBinding  # noqa: F401
from core.shared.remote_stub import RemoteStubFactory  # noqa: F401

PLUGIN_INFO = RemoteStubFactory.create_plugin_info(
    name="remote_asset_binding",
    category="asset_binding",
    protocols=["IAssetBinding"],
    description="远程资产绑定 (gRPC stub)",
)

__all__ = ["RemoteAssetBinding", "PLUGIN_INFO"]
