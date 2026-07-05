"""直接模拟服务初始化路径，诊断_asset_registry状态"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

# 模拟 deps.py 的初始化方式
from core.shared.config import DEFAULT_CONFIG
from core.memory.hybrid_engine import ICMEStorageEngine

print("1. 创建 ICMEStorageEngine...")
engine = ICMEStorageEngine(config=DEFAULT_CONFIG, use_sqlite=True)

print(f"2. _asset_registry = {engine._asset_registry}")
print(f"   type = {type(engine._asset_registry)}")

if engine._asset_registry:
    print("3. 测试 asset 注册...")
    result = engine.remember(
        content="直接引擎测试-检查asset_id",
        layer="working",
        tags=["诊断"],
    )
    print(f"   result keys: {list(result.keys())}")
    print(f"   asset_id: {result.get('asset_id')}")
    print(f"   id: {result.get('id')}")
else:
    print("3. _asset_registry is None! 尝试手动初始化...")
    engine._init_asset_registry()
    print(f"   after init: _asset_registry = {engine._asset_registry}")
