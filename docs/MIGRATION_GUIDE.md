# v9.1 → v10.0.1 迁移指南

## 概述

v10.0.1 是 v9.1 的**演进版本**，保持 **100% 向后兼容**。所有 v9.1 API 通过兼容层继续可用，无需修改任何现有代码即可平滑升级。

升级核心理念：**演进优于重构**。Phase 0~4 的模块化重构全部在内部完成，对外 API 表面保持稳定。

---

## 兼容层映射

下表列出 9 个兼容层，所有旧导入路径自动转发到新实现：

| v9.1 导入路径                                     | v10.0.1 实际实现                                             | 状态    |
| ------------------------------------------------- | ------------------------------------------------------------ | ------- |
| `core.engine.ICMEEngine`                          | `core/memory/` (writer + promoter + archiver + indexer)      | ✅ 兼容 |
| `core.deepseek_driver.DeepSeekDriver`             | `core/driver/` (perceiver + thinker + actor + reflector)     | ✅ 兼容 |
| `core.hybrid_engine.HybridEngine`                 | `core/storage/` (backend + migration + tiered)               | ✅ 兼容 |
| `core.agent_orchestrator.AgentOrchestrator`       | `core/orchestration/` (dispatcher + dag + planner + monitor) | ✅ 兼容 |
| `core.intelligent_scheduler.IntelligentScheduler` | `core/scheduling/` (priority + round_robin)                  | ✅ 兼容 |
| `core.quality_gate.QualityGate`                   | `core/shared/` + 门禁策略插件                                | ✅ 兼容 |
| `core.sqlite_store.SQLiteStore`                   | `core/storage/backend` (SQLite 后端)                         | ✅ 兼容 |
| `core.config.ICMEConfig`                          | `core/config` + CoreConfigRegistry                           | ✅ 兼容 |
| `core.models`                                     | `core/shared/protocols` + 数据模型                           | ✅ 兼容 |

> 说明：兼容层是薄转发层，仅做导入重定向与签名适配，运行时行为与 v9.1 一致。

---

## 新 API 使用

以下为 v10.0.1 推荐的新 API，可在不破坏旧代码的前提下逐步采用。

### MemoryCore (推荐)

ICME 六层各拥有独立的 `MemoryCore` 实例，支持 per-layer 配置与存储后端：

```python
from core.memory import MemoryCore
from core.config import CoreConfigRegistry

core = MemoryCore(layer="episodic", config=CoreConfigRegistry.get("episodic"))
core.write(content="...", tags=["decision"])
```

### StorageEngineFactory

通过工厂创建 4 种存储后端 (SQLite / JSON / Tiered / Remote)：

```python
from core.storage import StorageEngineFactory

engine = StorageEngineFactory.create(backend="sqlite")
```

### CoreConfigRegistry

集中管理 per-layer 配置，支持热 Override：

```python
from core.config import CoreConfigRegistry

CoreConfigRegistry.override("working", {"capacity_mb": 80})
```

### AssetBindingService

统一处理 L-Asset 三重绑定的验证与自动修复：

```python
from core.asset import AssetBindingService

AssetBindingService().bind_and_verify(asset_id="...")
```

---

## 迁移步骤

1. **确认运行环境**：Python 3.12+
2. **无需修改现有代码**：兼容层自动转发所有 v9.1 API
3. **可选 — 逐步切换到新 API**：
   - 新模块优先使用 `MemoryCore` / `StorageEngineFactory`
   - 逐步以 `CoreConfigRegistry` 替换全局配置读取
   - 验证每步迁移后运行全量回归测试
4. **验证**：运行 9 个兼容层回归测试，确认行为一致

---

## 常见问题

- **Q: 旧代码会失效吗？** 不会。9 个兼容层保证 v9.1 API 全部可用。
- **Q: 必须迁移到新 API 吗？** 不必须。新 API 为推荐项，旧 API 长期保留。
- **Q: 性能是否受影响？** 兼容层为薄转发层，性能退化 < 5%。
