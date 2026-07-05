"""
pytest配置文件 - 天机v9.1测试框架配置
"""
import pytest
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def project_root_path():
    """项目根目录路径"""
    return project_root


@pytest.fixture(scope="session")
def core_module_path():
    """core模块路径"""
    return project_root / "core"


@pytest.fixture(scope="session")
def data_path():
    """数据目录路径"""
    return project_root / "data"


@pytest.fixture(scope="function")
def temp_db_path(tmp_path):
    """临时数据库路径"""
    return tmp_path / "test_icme.db"


@pytest.fixture(scope="function")
def clean_engine(temp_db_path):
    """干净的ICME引擎实例"""
    from core.memory.engine import ICMEEngine
    from core.shared.config import DEFAULT_CONFIG
    
    config = DEFAULT_CONFIG
    config.db_path = str(temp_db_path)
    
    engine = ICMEEngine(config)
    yield engine
    
    engine.clear_all()


@pytest.fixture(scope="function")
def sample_memory_entry():
    """示例记忆条目"""
    from core.shared.models import MemoryEntry
    import time
    
    return MemoryEntry(
        id="test_entry_001",
        content="这是一条测试记忆内容",
        layer="working",
        tags=["test", "sample"],
        priority="medium",
        created_at=time.time(),
        last_accessed=time.time(),
        access_count=1,
        effectiveness_score=0.8,
        related_ids=[],
        metadata={"source": "conftest"}
    )


@pytest.fixture(scope="function")
def sample_entries():
    """多个示例记忆条目"""
    from core.shared.models import MemoryEntry
    import time
    
    entries = []
    for i in range(10):
        entry = MemoryEntry(
            id=f"test_entry_{i:03d}",
            content=f"测试记忆内容 #{i}",
            layer="working",
            tags=["test", f"batch_{i//3}"],
            priority=["low", "medium", "high"][i % 3],
            created_at=time.time() - i * 100,
            last_accessed=time.time() - i * 50,
            access_count=i + 1,
            effectiveness_score=0.5 + i * 0.05,
            related_ids=[],
            metadata={"batch_index": i}
        )
        entries.append(entry)
    
    return entries


def pytest_configure(config):
    """pytest配置钩子"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "sss: mark test as SSS级关键测试"
    )


def pytest_collection_modifyitems(config, items):
    """pytest收集修改钩子"""
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="需要--runslow选项运行"))
