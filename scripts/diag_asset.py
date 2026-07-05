"""诊断引擎内部_asset_registry状态"""
import sys
sys.path.insert(0, ".")

from core.shared.config import ICMEConfig
from core.memory.hybrid_engine import ICMEStorageEngine

config = ICMEConfig()
engine = ICMEStorageEngine(config)

print(f"_asset_registry type: {type(engine._asset_registry)}")
print(f"_asset_registry is None: {engine._asset_registry is None}")
print(f"_snapshot_mgr type: {type(engine._snapshot_mgr)}")
print(f"_snapshot_mgr is None: {engine._snapshot_mgr is None}")

if engine._asset_registry:
    print(f"AssetRegistry db_path: {engine._asset_registry._db_path}")
    print(f"AssetRegistry _snapshot_mgr: {engine._asset_registry._snapshot_mgr}")

# 尝试写入
result = engine.remember("诊断测试-检查asset_id", layer="working", tags=["debug"])
print(f"\nremember result:")
print(f"  id: {result.get('id')}")
print(f"  asset_id: {result.get('asset_id')}")
print(f"  status: {result.get('status')}")
