# 天机v10.0.1 架构总览

> 本文档描述天机记忆引擎 v10.0.1 的分层架构、Phase 演进、数据流与配置体系。
> 架构基线与 `core/` 实际子包结构一致。编码 UTF-8-SIG。

---

## 分层架构图

```
┌─────────────────────────────────────────────────┐
│                REST API Layer (71端点)            │
│   memory/search/orchestrator/llm/mcp/governance   │
├─────────────────────────────────────────────────┤
│           Event-Driven Communication             │
│    (LocalEventBus + 7域Wiring + ACL防腐层)        │
├─────────────────────────────────────────────────┤
│         MemoryCore Layer (6独立实例)             │
│  [Sensory][Working][ShortTerm][Episodic]         │
│  [Semantic][Meta]  + CoreConfigRegistry          │
├─────────────────────────────────────────────────┤
│         Strategy Plugin Layer                    │
│  Search|Gate|Route|Cache|LLM|Schedule|Validation │
├─────────────────────────────────────────────────┤
│         Storage Backend Layer                    │
│  [SQLite] [JSON] [Tiered] [Remote stub]          │
│         + StorageEngineFactory                    │
├─────────────────────────────────────────────────┤
│         Shared Kernel (Ω基点)                    │
│  38 Protocols | CoreConfigRegistry | Events      │
│  Exceptions | Types | Constants | ACL            │
└─────────────────────────────────────────────────┘

         治理/工程化扩展 (横切各层)
  container(DI) · enforcement(合规) · law(律令) · sla(SLA) · lingxi(探针)
```

设计要点:
- **依赖倒置**: 上层仅依赖 `core/shared` 的 38 个 Protocol 契约，不依赖具体实现。
- **本地/远程双实现**: 每个 Protocol 均提供 `LocalXxx`(单进程默认) 与 `RemoteXxx`(灵境分布式 stub)，经工厂/容器按运行模式切换。
- **事件驱动过渡**: `core/event_wiring` 在不改动既有领域实现的前提下叠加 EventBus，将跨域直接耦合渐进式转换为事件通信。

---

## Phase 演进路径

```
P0 共享内核   → core/shared (38 Protocol/Events/Exceptions/ACL) Ω基点
P1 核心拆分   → core/memory, core/driver, core/storage,
                core/orchestration, core/scheduling
P2 策略插件化 → core/search, core/gate, core/routing, core/cache,
                core/llm, core/validation, core/scheduling(优先级策略)
P3 事件接线   → core/event_wiring (核心域 #38 / 次要域 #39 / 进化治理域 #40)
P4 六层实例化 → core/memory_core (6层实例+配置),
                core/storage/backends (后端策略化),
                core/asset_binding (L-Asset三重绑定)
P5 工程化     → 文档体系(本目录) + container/enforcement/law/lingxi/sla 扩展
```

演进策略遵循「**演进优于重构**」: 每个 Phase 拆分时保留原模块为兼容路由层，
旧版 import 路径全部继续可用，确保 v9.1 单进程运行不受影响。

---

## 数据流

### 写入链路 (remember)
```
用户输入
  → [拦截层 IInterceptLayer] 捕获 (sensory L0)
  → [路由 ITaskRouter] 内容→层级判定
  → [门禁 IGateStrategy] 三问推演 (PASS/DOWNGRADE/REJECT/CONFLICT/PENDING)
  → [MemoryCore.write] 写入目标层
  → [存储 IStorageEngine.insert] 落地 (SQLite/JSON/Tiered)
  → [资产绑定 AssetBindingService] L-Asset 三重绑定
  → [事件 LocalEventBus.publish] memory.stored 广播
```

### 检索链路 (recall)
```
查询文本
  → [查询扩展 IQueryExpander] 语义改写
  → [融合检索 IFusionRetriever] 编排四通道:
       FTS5(快) + Tag(准) + Semantic(深) + KG(全)
  → [RRF 加权融合] (CHANNEL_WEIGHTS / RRF_K)
  → [重排 IReranker] top_k 重排
  → SearchResult(entries/total_count/search_time_ms/strategy_used)
```

### 晋升链路 (consolidate)
```
固结调度 IConsolidationScheduler (按层 interval 触发)
  → [晋升门禁 IPromotionGate] 评分判定 can_promote
  → [晋升策略 IConsolidationStrategy] select_candidates → promote
  → 流向: sensory → working → short_term → episodic → semantic → meta
  → [事件] memory.consolidated 广播
```

---

## 配置体系

层级配置由 `core/memory_core/config.py` 统一管理：

| 层 | layer_index | max_size | max_entries | 阈值 | 固结间隔 | priority |
|---|---|---|---|---|---|---|
| sensory (L0) | 0 | 10MB | 2000 | 0.85 | 30s | low |
| working (L1) | 1 | 50MB | 1000 | 0.80 | 60s | medium |
| short_term (L2) | 2 | 200MB | 5000 | 0.75 | 120s | medium |
| episodic (L3) | 3 | 500MB | 5000 | 0.80 | 300s | high |
| semantic (L4) | 4 | 2GB | 10000 | 0.85 | 600s | high |
| meta (L5) | 5 | 500MB | 100000 | 0.90 | 900s | critical |

- **CoreConfig**: 单层独立配置数据类，支持运行时 `override`/`reset`、`validate`、序列化。
- **CoreConfigRegistry**: 6 层配置注册表，线程安全；`create_default()` 装配默认配置，
  `from_icme_config()` 从旧版 `ICMEConfig` 平滑迁移。
- **配置树同步**: `export_config_tree()`/`import_config_tree()` 提供跨节点序列化通道，灵境侧据此同步各节点层级配置。

---

## 分布式预留 (v10.0 灵境)

天机 v10.0.1 在单进程(v9.1)基础上为分布式演进预留完整切换点：

```
单进程模式 (v9.1 默认)              分布式模式 (v10.0 灵境)
─────────────────────              ─────────────────────
LocalSQLiteEngine          ←工厂→   RemoteStorageEngine (gRPC)
LocalGateStrategy          ←切换→   RemoteGateStrategy
FusionRetrievalStrategy    ←切换→   RemoteSearchStrategy
DeepSeekLLMStrategy        ←切换→   RemoteLLMStrategy
MemoryCacheStrategy        ←切换→   RemoteCacheStrategy
PriorityBasedScheduler     ←切换→   RemoteSchedulerStrategy
LocalEventBus              ←切换→   RemoteEventBus (消息队列)
AssetBindingService        ←切换→   RemoteAssetBinding
```

- 每个策略子包均含 `remote_stub.py`，预留远程实现骨架与降级逻辑。
- 上层代码仅依赖 Protocol，无需感知实现切换，从而保证 v9.1 不受影响、v10.0 平滑接入。
- 服务端口: 天机 8771 / 灵境 8772。

---

## 关键约束

- **编码**: 全链路 UTF-8-SIG (BOM)，MCP 层强制。
- **类型**: Python 类型注解 ≥80%，圈复杂度 ≤10。
- **依赖方向**: 严格自上而下，禁止反向依赖 `core/shared`(Ω基点零依赖)。
- **接口稳定**: 拆分不改变对外公开符号，兼容层保证旧路径可用。

---

**版本**: v10.0.1 | **维护**: @jingwei + @tianshu | 关联文档: [MODULE_INDEX.md](./MODULE_INDEX.md) · [API_REFERENCE.md](./API_REFERENCE.md)
