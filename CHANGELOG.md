# Changelog

本文件记录天机记忆系统 (Tianji Memory Engine) 的所有重要变更。

格式遵循 [Keep a Changelog](https://keepachangelog.com/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [10.0.1] - 2026-06-05 (预发布)

> 演进式架构升级：在保持 v9.1 全部 API 100% 向后兼容的前提下，完成 Phase 0~4 的模块化重构。

### 架构演进 (Phase 0~4)

#### Phase 0: 共享内核建立

- 新建 `core/shared/` 子包 (protocols.py / events.py / exceptions.py / plugin_interface.py / plugin_manager.py)
- 38 个 Protocol 接口定义 (IStorageEngine / ISearchStrategy / ICacheStrategy 等)
- LocalEventBus 事件总线 + DomainEvent 基类

#### Phase 1: 巨型基点拆分

- `engine.py` → `core/memory/` (writer / promoter / archiver / indexer)
- `deepseek_driver.py` → `core/driver/` (perceiver / thinker / actor / reflector)
- `hybrid_engine.py` → `core/storage/` (backend / migration / tiered)
- `agent_orchestrator.py` → `core/orchestration/` (dispatcher / dag / planner / monitor)
- `intelligent_scheduler.py` → `core/scheduling/` (priority / round_robin)
- 9 个兼容层保持 v9.1 API 不变

#### Phase 2: 策略插件化

- 8 个策略域插件化 (搜索 / 门禁 / 路由 / 缓存 / 调度 / LLM / 适配器 / 序列化)
- 每域: Protocol + LocalXxx 实现 + RemoteXxx stub
- PluginManager 动态加载 + 生命周期管理

#### Phase 3: 事件驱动改造

- EventBus 事件驱动通信
- ACL 防腐层 (AnticorruptionLayer)
- 7 域事件接线 (engine / driver / gate / orchestration / scheduling / search / evolution)
- 事件 Schema + EventContract + 优先级映射

#### Phase 4: Memory Core 模块化

- ICME 六层 → 6 个独立 MemoryCore 实例
- 4 个存储后端 (SQLite / JSON / Tiered / Remote) + StorageEngineFactory
- CoreConfig + CoreConfigRegistry (per-layer 配置)
- AssetBindingService (L-Asset 三重绑定统一)

### 新增功能

- `[v10-ready]` 标记体系 (累计 964 个)
- 分布式预留接口 (Remote stubs)
- 配置热 Override 机制
- 三重绑定验证 + 自动修复

### 技术指标

- Protocol 接口: 38+ 个
- 核心子包: 22 个
- 代码行数: 76,606 行 (core/)
- 测试覆盖: 30 个测试文件

---

## [9.0.0] - 2026-05-31 — SSS 级审计修复版

- 🔴 **修复**: 三图标问题（单实例保护 + DETACHED 进程分离）
- 🔴 **修复**: trigger_manual 方法不存在 → 改用 trigger_deep_think / trigger_evolution
- 🔴 **修复**: Dashboard 假数据 → 真实 API 数据驱动
- 🔴 **修复**: Monitoring 空壳 → 三栏式实时监控（调度 / 录入 / 会话）
- 🟠 **增强**: API 端点从 20 个扩展到 71 个（完整覆盖所有模块）
- 🟠 **增强**: api.config.ts 补全 orchestrator / active / deepseek / mcp 端点
- 🟢 **新增**: Web 界面自动刷新（Dashboard 10s / Monitoring 8s）
- 🟢 **新增**: 调度轨迹 Timeline 可视化
- 🟢 **新增**: 对话录入痕迹表格（拦截 / 提取 / 存储全流程）
- 天机原生 + Trae IDE 融合
- 多智能体协同架构

---

## [8.0.0] - 2026-05-20 — Orchestrator 架构重构

- 新增智能体调度中心 (agent_orchestrator.py)
- 新增 DeepSeek 驾驶者大脑 (deepseek_driver.py)
- 新增强制记录系统 (enforcement_hook.py)
- 新增 Web 管理界面 (React + Ant Design)
- Agent 编排器升级

---

## [3.1.0] - 2026-05-03 — AI 记忆系统集成

- ICME 六层记忆架构初版
- SQLite + FTS5 高性能存储
- 15 个 MCP 工具
- Docker 容器化部署
