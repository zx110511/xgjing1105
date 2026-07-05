# 天机v9.1 Code Wiki

> 本文档是天机记忆系统 v9.1 的结构化代码百科，覆盖项目整体架构、主要模块职责、关键类与函数、依赖关系以及独立运行方式。编码：UTF-8-SIG。
> 生成日期：2026-07-05 | 项目根目录：`D:\元初系统\天机v9.1` | 服务端口：8771

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [目录结构](#3-目录结构)
4. [核心模块职责](#4-核心模块职责)
5. [关键类与函数](#5-关键类与函数)
6. [依赖关系](#6-依赖关系)
7. [运行方式](#7-运行方式)
8. [启动链路详解](#8-启动链路详解)
9. [配置说明](#9-配置说明)
10. [常见问题](#10-常见问题)

---

## 1. 项目概述

**天机记忆系统 v9.1 (Orchestrator 专业版)** 是元初系统的核心记忆服务，定位为在 `D:\元初系统\天机v9.1` 目录内完全独立运行的后台智能体平台。系统集成了：

- **ICME 六层记忆架构**（L0 Sensory → L5 Meta）
- **23+ 智能体调度中心**（天枢、忆库、铁卫等）
- **FastAPI REST 服务**（71+ API 端点）
- **MCP 协议服务**（6 个 MCP Server，约 39-71 个工具）
- **强制记录系统**（对话捕获、ICME 分层存储）
- **Web 管理界面**（实时仪表盘、调度追踪）
- **系统托盘**（pystray + PIL，单实例保护）

**设计目标**：通过唯一桌面启动器 `C:\Users\Administrator\Desktop\天机v9.1.lnk` 启动后，系统在电脑后台全功率、全功能运行，不依赖外部 IDE 或手动命令行。

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     入口层 (Launcher / Tray)                  │
│  start_tianji.bat → tianji_v91_launcher.py → tianji_tray.py  │
├─────────────────────────────────────────────────────────────┤
│                    REST API 层 (server/)                      │
│  71+ HTTP 端点：memory / search / orchestrator / llm / mcp    │
├─────────────────────────────────────────────────────────────┤
│                    MCP 服务层 (mcp/)                          │
│  6 个 MCP Server：memory-engine / agent-framework / ops /     │
│  command-executor / security-scanner / performance-profiler   │
├─────────────────────────────────────────────────────────────┤
│                    Agent 调度层 (agents/ + core/orchestration) │
│  23 个 Agent + Dispatcher + Registry + Pipeline + Tracker     │
├─────────────────────────────────────────────────────────────┤
│                    记忆引擎层 (core/memory)                    │
│  ICMEEngine + SQLiteMemoryStore + HybridEngine + MemoryCore   │
├─────────────────────────────────────────────────────────────┤
│                    共享内核层 (core/shared)                    │
│  Protocols / Events / Types / Config / ModuleManager / Models │
├─────────────────────────────────────────────────────────────┤
│                    存储持久层 (data/.memory)                   │
│  SQLite (icme.db) + WAL + JSON 文件 + 分层目录                │
└─────────────────────────────────────────────────────────────┘
```

### 架构设计要点

- **分层清晰**：入口 → API → MCP → Agent → Memory → Shared → Storage，逐层向下依赖。
- **协议优先**：上层代码依赖 `core/shared/protocols*.py` 中定义的契约，便于后续 v10.0 分布式切换。
- **事件驱动**：`core/event_wiring` 在不改动既有领域实现的前提下叠加 EventBus。
- **兼容降级**：v9.1 Protocol 模式优先使用 MemoryCore，失败时静默降级到旧 SQLite/JSON 路径。

---

## 3. 目录结构

| 目录 | 说明 |
|------|------|
| `agents/` | 23 个天机 Agent 实现（tianshu、yiku、mingjing 等） |
| `core/` | 系统内核，含 memory、orchestration、shared、enforcement、law 等 |
| `server/` | FastAPI 服务入口与 API 路由 |
| `mcp/` | MCP Server 实现与工具注册 |
| `launcher/` | 统一启动器、托盘、启动脚本 |
| `daemon/` | 后台守护进程、看门狗、自动修复 |
| `adapters/` | 多平台适配器（Trae / VSCode / CherryClaw / 通用） |
| `active_memory/` | 强制记录系统（对话捕获、LayerRouter 分发） |
| `config/` | 配置包与路径定义 |
| `data/.memory/` | 记忆持久化目录（SQLite + JSON） |
| `web/` | 前端 Web UI（React + Vite + Tauri） |
| `tests/` | 测试套件与报告 |
| `scripts/` | 运维、审计、修复脚本 |
| `docs/` | 设计文档与百科 |
| `.trae/` | Trae IDE 规则、Agent 注册表、技能定义 |
| `python/` | 项目内置 Python 3.12 虚拟环境 |

---

## 4. 核心模块职责

### 4.1 启动与运维层

#### `launcher/start_tianji.bat`
- Windows 桌面快捷方式指向的批处理文件。
- 设置 UTF-8 编码（`chcp 65001`），切换工作目录到 `D:\元初系统\天机v9.1`。
- 检查 PID 文件与端口 8771 占用，避免重复启动。
- 调用内置 `python\pythonw.exe` 以无窗口方式启动 `launcher.tianji_v91_launcher --tray`。

#### `launcher/tianji_v91_launcher.py`
- **TianjiLauncher 类**：统一启动器。
- 职责：端口检测与释放、PID 文件管理、子进程启动、全链健康验证（10 个关键端点）。
- 支持三种模式：命令行前台、系统托盘 `--tray`、后台守护 `--daemon`。

#### `launcher/tianji_tray.py`
- 系统托盘控制面板，基于 `pystray + PIL`。
- 右键菜单：打开 Web UI / Dashboard / API 文档 / 健康检查 / 全链验证 / 重启 / 停止。
- 动态生成图标（“天”字），根据状态变色。

#### `daemon/`
- `tianji_daemon.py`：兼容入口，聚合各子模块。
- `tianji_daemon_tianjidaemon.py`：`TianjiDaemon` 核心实现（PID 管理、服务上下文）。
- `tianji_daemon_watchdog.py`：`Watchdog` 异常重启与系统自愈。
- `tianji_daemon_autorepair.py`：`AutoRepair` 自动修复。
- `tianji_daemon_autobackup.py`：`AutoBackup` 自动备份。
- `supervisor.py`：模块注册、生命周期管理、健康检查。

### 4.2 REST API 层

#### `server/main.py`
- FastAPI 应用主入口，创建 `app` 实例，注册 CORS、GZip 中间件。
- 导入并注册全部路由模块（memory、search、orchestrator、llm、mcp、active 等）。
- 定义核心变量：`_START_TIME`、`_SHUTDOWN_EVENT`、`_PROTOCOL_MODE_ACTIVE`。

#### `server/api/memory_routes.py`
- 记忆 CRUD REST API：列表、统计、层级信息、导出、存储管理、整合。
- 依赖 `server.deps.engine`（ICMEEngine 单例）。

#### `server/api/orchestrator_routes.py` / `orchestrator_v10.py`
- Agent 调度 API：状态、Agent 列表、流水线、并行分发、追踪。

#### `server/api/active_routes.py`
- 强制记录 API：拦截输入/回复、平台列表、会话详情、子 Agent 执行。

#### `server/api/llm_routes.py`
- DeepSeek 大脑 API：状态、分类、价值分析、存储决策、知识提取、摘要。

#### `server/api/mcp_routes_searchperspectivememoriesrequest.py`
- MCP 工具 REST 路由：15 个 MCP 相关端点，提供工具清单与 Schema。

### 4.3 MCP 服务层

#### `mcp/tianji_mcp_server.py`
- 天机记忆引擎 MCP Server 主入口。
- 定义 39 个工具：BASIC_TOOLS（memory_remember/recall/forget/stats 等）+ ADVANCED_TOOLS（tianji_classify/auto_tag/summarize 等）。
- 通过 HTTP 调用本地 127.0.0.1:8771 REST API 实现工具功能。

#### `mcp/server/agent_framework.py`
- Agent 调度框架，提供 `agent_dispatch` 等工具。

#### `mcp/server/command_executor.py`
- 命令执行器，支持本地系统命令与脚本执行。

#### `mcp/server/ops_engine.py`
- DevOps 运维引擎：部署、服务管理、资源伸缩。

#### `mcp/server/security_scanner.py`
- 安全扫描器：漏洞扫描、合规检查、权限检查。

#### `mcp/server/performance_profiler.py`
- 性能剖析器：CPU/内存/瓶颈分析。

### 4.4 Agent 调度层

#### `core/orchestration/registry.py`
- **AGENT_CAPABILITY_MATRIX**：Agent 能力矩阵单一数据源。
- 从 `.trae/agents/_AGENT_REGISTRY.json` 动态加载 31 个 Agent 元数据。
- 提供 `_build_unified_matrix()`、`_fill_defaults()`、CapabilityRegistry。

#### `core/orchestration/dispatcher.py`
- **ParallelDispatcher**：并行任务精准 Agent 分配。
- `dispatch(parallel_tasks)`：按任务关键词选择 Agent，输出 TVP 调度日志。

#### `core/orchestration/task_planner.py`
- 任务规划与决策，确定执行顺序和调度策略。

#### `core/orchestration/pipeline.py`
- 流水线管理，支持多阶段任务执行。

#### `core/orchestration/tracker.py`
- 任务与 Agent 执行状态跟踪。

#### `core/orchestration/tvp_bridge.py`
- TVP 透明调度协议桥接，协议转换与兼容性处理。

#### `agents/tianshu.py`
- **TianshuAgent**：L2 总指挥 Agent。
- `handle(task)` → `evaluate_decision()` → `dispatch_agent()` 决策链路。
- 根据任务关键词委派给 miaobi、mingjing、jingwei 等 Agent。

#### `agents/yiku.py`
- L1 记忆架构师 Agent，负责 ICME 六层管理、语义检索、容量监控。

#### `agents/miaobi.py` / `mingjing.py` / `tiewei.py`
- 创作、审校、质量守护 Agent。

### 4.5 记忆引擎层

#### `core/memory/engine.py`
- **ICMEEngine**：通过 8 个 Mixin 组合的记忆引擎主类。
- Mixin：Init / Evo / Event / Remember / Recall / Consolidate / Forget / Capacity / Stats。

#### `core/memory/engine_init.py`
- **ICMEEngineInitMixin**：初始化六层数据结构、SQLiteStore、进化闭环、MemoryCore。

#### `core/memory/engine_remember.py`
- **ICMEEngineRememberMixin**：`remember()` 写入入口，Protocol 模式优先写入 MemoryCore，降级时写入 JSON/SQLite。

#### `core/memory/engine_recall.py`
- **ICMEEngineRecallMixin**：`recall()` 检索入口，融合 FTS5 + Tag + Semantic + KG 多通道。

#### `core/memory/sqlite_store.py`
- **SQLiteMemoryStore**：多 Mixin 组合的 SQLite 持久化存储（CRUD / Search / Stats / Cache / Evo）。

#### `core/memory/hybrid_engine.py`
- **ICMEStorageEngine**：混合存储引擎，组合 Init / Remember / Recall / Consolidate / Stats。

#### `core/memory/storage/`
- 存储后端抽象：`backend.py`（基类）、`local_sqlite.py`、`local_json.py`、`tiered_engine.py`、`factory.py`。

#### `core/memory_core/`
- v9.1 Protocol 模式六层独立实例：`base.py`、`core_sensory.py`、`core_working.py`、`core_short_term.py`、`core_episodic.py`、`core_semantic.py`、`core_meta.py`、`config.py`。

### 4.6 共享内核层

#### `core/shared/`
- `models.py`：核心数据模型（MemoryEntry、MemoryLayer 等）。
- `types.py`：共享类型系统。
- `events.py`：事件总线与事件类型。
- `config.py` / `config_manager.py`：全局配置与配置管理。
- `module_manager.py`：`ModuleManager`，模块注册、生命周期、热插拔。
- `protocols*.py`：38+ 协议契约，实现本地/远程双实现切换。
- `utils.py`：通用工具函数。
- `platform_adapter.py`：平台适配核心。

### 4.7 适配器与强制记录

#### `adapters/trae_adapter.py`
- **TraeAdapter**：Trae IDE 标准化接入接口。
- 事件处理：message_received、agent_switch、file_changed、session_start/end。
- 所有事件最终通过 `remember()` 写入 ICME 对应层级。

#### `active_memory/trae_capture.py`
- **TraeConversationCapture**：Trae 对话全量捕获。
- `capture_conversation_turn()`：生成 L0 Sensory 快照，经 LayerRouter 分发到 L1-L5。

---

## 5. 关键类与函数

### 5.1 启动链路

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `launcher/start_tianji.bat` | 批处理主流程 | 桌面启动入口，防重复启动 |
| `launcher/tianji_v91_launcher.py` | `TianjiLauncher` | 统一启动器，端口/PID/全链验证 |
| `launcher/tianji_v91_launcher.py` | `_wait_basic_health()` | 等待基础服务就绪 |
| `launcher/tianji_v91_launcher.py` | `_verify_chain()` | 验证 10 个关键端点 |
| `launcher/tianji_tray.py` | `create_tray_image()` | 动态托盘图标 |
| `launcher/tianji_tray.py` | `on_full_check()` | 全链验证菜单动作 |
| `launcher/tianji_tray.py` | `on_restart()` / `on_stop()` | 服务重启/停止 |

### 5.2 FastAPI 服务

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `server/main.py` | `app` | FastAPI 应用实例 |
| `server/main.py` | `api_config_all()` | 获取系统全部配置 |
| `server/main.py` | `api_mcp_servers()` | MCP 服务器列表 |
| `server/api/memory_routes.py` | `list_memories()` | 记忆列表 |
| `server/api/memory_routes.py` | `memory_stats()` | 记忆统计 |
| `server/api/memory_routes.py` | `layer_capacity()` | 层级容量信息 |
| `server/deps.py` | `engine` | ICMEEngine 单例依赖 |

### 5.3 MCP 工具

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `mcp/tianji_mcp_server.py` | `BASIC_TOOLS` | 9 个基础记忆工具 |
| `mcp/tianji_mcp_server.py` | `ADVANCED_TOOLS` | 30 个高级工具 |
| `mcp/tianji_mcp_server.py` | `TianjiMCPServer` | MCP Server 主类 |
| `mcp/server/agent_framework.py` | Agent 调度工具 | agent_dispatch / system_status 等 |
| `mcp/server/command_executor.py` | 命令执行工具 | execute_command / run_script 等 |

### 5.4 Agent 调度

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `core/orchestration/registry.py` | `AGENT_CAPABILITY_MATRIX` | 能力矩阵字典 |
| `core/orchestration/registry.py` | `_load_from_registry()` | 从 _AGENT_REGISTRY.json 加载 |
| `core/orchestration/registry.py` | `_build_unified_matrix()` | 构建统一矩阵 |
| `core/orchestration/dispatcher.py` | `ParallelDispatcher` | 并行调度器 |
| `core/orchestration/dispatcher.py` | `dispatch()` | 并行任务分发 |
| `agents/tianshu.py` | `TianshuAgent` | 总指挥 Agent |
| `agents/tianshu.py` | `evaluate_decision()` | 任务决策评估 |
| `agents/tianshu.py` | `dispatch_agent()` | Agent 委派 |

### 5.5 记忆引擎

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `core/memory/engine.py` | `ICMEEngine` | 记忆引擎主类 |
| `core/memory/engine_init.py` | `ICMEEngineInitMixin.__init__()` | 引擎初始化 |
| `core/memory/engine_remember.py` | `ICMEEngineRememberMixin.remember()` | 写入记忆 |
| `core/memory/engine_recall.py` | `ICMEEngineRecallMixin.recall()` | 检索记忆 |
| `core/memory/sqlite_store.py` | `SQLiteMemoryStore` | SQLite 存储 |
| `core/memory/hybrid_engine.py` | `ICMEStorageEngine` | 混合存储引擎 |
| `core/memory_core/config.py` | `CoreConfig` / `CoreConfigRegistry` | 六层配置 |

### 5.6 共享内核

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `core/shared/module_manager.py` | `ModuleManager` | 模块管理器 |
| `core/shared/module_manager.py` | `_load_registry()` | 加载模块注册表 |
| `core/shared/config_manager.py` | `ConfigManager` | 配置管理器 |
| `core/shared/models.py` | `MemoryEntry` | 记忆条目模型 |
| `core/shared/events.py` | `EventBus` | 事件总线 |
| `config/paths.py` | `TIANJI_ROOT` / `DATA_DIR` / `DATABASE_PATH` | 路径常量 |

---

## 6. 依赖关系

### 6.1 顶层依赖方向

```
launcher/ ──► server/ ──► mcp/ ──► agents/ ──► core/orchestration ──► core/memory ──► core/shared ──► config/
                 │           │                                                  │
                 ▼           ▼                                                  ▼
            active_memory  adapters                                    data/.memory (SQLite/JSON)
```

### 6.2 关键导入链

1. **启动时**：
   - `start_tianji.bat` → `python -m launcher.tianji_v91_launcher --tray`
   - `tianji_v91_launcher.py` 启动 `server.main_ops` 子进程（Uvicorn 运行 `server.main:app`）

2. **服务启动时**：
   - `server/main.py` 导入 `server.deps.engine`，创建 `ICMEEngine` 单例
   - `ICMEEngine` 初始化 `SQLiteMemoryStore`、`MemoryWriter`、`PromotionEngine`、`ArchiveManager`、`MemoryIndex`
   - 若 `TIANJI_V91_PROTOCOL_MODE` 开启，初始化 `core/memory_core` 六层实例

3. **API 请求时**：
   - 路由函数从 `server.deps` 获取 `engine`
   - 调用 `engine.remember()` / `engine.recall()` / `engine.stats()`
   - 引擎内部委托给 `MemoryWriter` / `MemoryIndex` / `SQLiteMemoryStore`

4. **MCP 调用时**：
   - MCP Server 作为独立进程，通过 HTTP 调用 127.0.0.1:8771 REST API
   - 或直接与 `core/orchestration` 交互（agent-framework-global）

### 6.3 外部 Python 依赖

主要依赖（完整清单见 `requirements.txt`）：

| 类别 | 关键库 |
|------|--------|
| Web 框架 | `fastapi>=0.109.0`, `uvicorn[standard]>=0.27.0`, `starlette>=0.36.0`, `websockets>=12.0` |
| 数据验证 | `pydantic>=2.5.0`, `PyYAML>=6.0.1`, `python-dotenv>=1.0.0` |
| 数据库 | `aiosqlite>=0.19.0` |
| 异步 | `aiofiles>=23.2.0`, `aiohttp>=3.9.0` |
| LLM | `httpx>=0.27.0`, `openai>=1.12.0` |
| 计算 | `numpy>=1.26.0` |
| 托盘 | `pystray>=0.19.0`, `Pillow>=10.0.0` |
| 日志 | `loguru>=0.7.2` |
| 测试 | `pytest>=8.0.0`, `pytest-cov>=4.1.0`, `pytest-asyncio>=0.23.0` |
| 质量 | `ruff>=0.3.0`, `mypy>=1.8.0`, `bandit>=1.7.0` |

---

## 7. 运行方式

### 7.1 推荐方式：桌面快捷方式启动

1. 确保快捷方式 `C:\Users\Administrator\Desktop\天机v9.1.lnk` 指向 `D:\元初系统\天机v9.1\launcher\start_tianji.bat`。
2. 双击快捷方式。
3. 系统托盘出现“天”字图标，表示后台服务已启动。
4. 访问 `http://127.0.0.1:8771/` 打开 Web UI。

### 7.2 命令行启动

```powershell
# 切换到项目根目录
cd "D:\元初系统\天机v9.1"

# 系统托盘模式（后台）
python\pythonw.exe -X utf8 -m launcher.tianji_v91_launcher --tray

# 前台调试模式
python\python.exe -m launcher.tianji_v91_launcher

# 后台守护模式
python\python.exe -m launcher.tianji_v91_launcher --daemon

# 直接启动 FastAPI 服务（开发者）
python\python.exe -m server.main_ops
# 或
uvicorn server.main:app --host 0.0.0.0 --port 8771
```

### 7.3 健康检查

```bash
curl http://127.0.0.1:8771/api/health
```

预期返回包含 `engine_ready: true`。

### 7.4 停止服务

- 托盘右键 → **停止服务**。
- 或终止 PID 文件 `.daemon/tianji.pid` 对应的进程。

---

## 8. 启动链路详解

### 8.1 完整启动流程

```
用户双击桌面快捷方式
    │
    ▼
C:\Users\Administrator\Desktop\天机v9.1.lnk
    │
    ▼
D:\元初系统\天机v9.1\launcher\start_tianji.bat
    │
    ├─ chcp 65001（UTF-8）
    ├─ cd /d "D:\元初系统\天机v9.1"
    ├─ 检查 .daemon\tianji.pid 是否存在且进程存活
    ├─ HTTP GET http://127.0.0.1:8771/api/health（单实例保护）
    └─ 若未运行：
        start /B python\pythonw.exe -X utf8 -m launcher.tianji_v91_launcher --tray
    │
    ▼
launcher/tianji_v91_launcher.py — TianjiLauncher
    │
    ├─ _ensure_dirs()：创建 logs/、.daemon/
    ├─ _check_port()：检测 8771 端口
    ├─ _free_port()：释放被占用端口（必要时 kill 旧进程）
    ├─ _cleanup_old_pid()：清理旧 PID 及子进程
    ├─ 启动子进程：python -m server.main_ops（Uvicorn 运行 server.main:app）
    ├─ _wait_basic_health()：等待 /api/health 返回 200
    ├─ _wait_container_ready()：等待容器模块初始化
    ├─ _verify_chain()：验证 10 个关键端点
    └─ 若 --tray：启动 tianji_tray.py 托盘图标
    │
    ▼
server/main.py — FastAPI 应用初始化
    │
    ├─ 创建 FastAPI app 实例
    ├─ 注册 CORS、GZip 中间件
    ├─ 导入 server.deps.engine（初始化 ICMEEngine 单例）
    ├─ 注册所有 APIRouter
    └─ Uvicorn 监听 0.0.0.0:8771
    │
    ▼
ICMEEngine 初始化（core/memory/engine_init.py）
    │
    ├─ 创建六层内存结构 _layers
    ├─ 初始化 SQLiteMemoryStore（data/.memory/icme.db）
    ├─ 初始化 MemoryWriter / PromotionEngine / ArchiveManager / MemoryIndex
    ├─ 若 Protocol 模式开启：创建 MemoryCore 六层实例
    ├─ _load_memory_data()：加载持久化数据
    └─ _start_consolidation_daemon()：启动整合守护线程
    │
    ▼
后台全功能运行
    ├─ REST API 监听 8771
    ├─ MCP Server 就绪
    ├─ Agent 调度器就绪
    ├─ 强制记录系统就绪
    └─ Web UI 可访问
```

### 8.2 单实例保护机制

1. **PID 文件**：`.daemon/tianji.pid` 记录当前服务进程 ID。
2. **健康检查**：启动前请求 `http://127.0.0.1:8771/api/health`。
3. **端口占用清理**：若旧进程孤儿化，PowerShell 强制终止占用 8771 端口的进程。

### 8.3 全链验证端点

`launcher/tianji_v91_launcher.py` 中 `_CHAIN_ENDPOINTS` 定义的 10 个关键端点：

| 端点 | 用途 |
|------|------|
| `/api/health` | 健康检查 |
| `/` | Web 前端 UI |
| `/docs` | API 文档（Swagger） |
| `/api/mcp/tools` | MCP 工具清单 |
| `/api/orchestrator/agents` | Agent 调度器 |
| `/api/kg/stats` | 知识图谱 |
| `/api/search` | 搜索功能 |
| `/api/deepseek/models` | DeepSeek 大脑 |
| `/api/status/system/stats` | 完整系统状态 |
| `/api/conversation/health` | 对话归档器 |

---

## 9. 配置说明

### 9.1 关键配置文件

| 文件 | 说明 |
|------|------|
| `config/paths.py` | 定义 TIANJI_ROOT、DATA_DIR、DATABASE_PATH 等路径 |
| `config/user_config.json` | 用户个性化配置 |
| `config/platform_adapter.json` | 平台适配器配置 |
| `.trae/config/launcher.json` | Trae 启动配置 |
| `.trae/config/routing-engine.json` | 路由引擎配置 |
| `.trae/agents/_AGENT_REGISTRY.json` | 31 个 Agent 能力矩阵 |
| `modules/registry.json` | 模块注册表 |
| `modules/activated_state.json` | 模块激活状态 |

### 9.2 环境变量

| 变量 | 说明 |
|------|------|
| `AI_MEMORY_ROOT` / `TIANJI_ROOT` | 项目根目录覆盖 |
| `TIANJI_EDITION` | 版本标识，默认 `source-v9.1` |
| `PYTHONIOENCODING` | 强制 UTF-8（Windows） |
| `TIANJI_V91_PROTOCOL_MODE` | 是否启用 MemoryCore Protocol 模式 |

### 9.3 ICME 六层配置

| 层级 | 索引 | 容量 | 条目上限 | 固结间隔 | 优先级 |
|------|------|------|---------|---------|--------|
| L0 Sensory | 0 | 10 MB | 2000 | 30s | low |
| L1 Working | 1 | 50 MB | 1000 | 60s | medium |
| L2 Short-Term | 2 | 200 MB | 5000 | 120s | medium |
| L3 Episodic | 3 | 500 MB | 5000 | 300s | high |
| L4 Semantic | 4 | 2 GB | 10000 | 600s | high |
| L5 Meta | 5 | 500 MB | 100000 | 900s | critical |

---

## 10. 常见问题

### Q1: 双击桌面快捷方式无反应？
- 检查快捷方式是否指向 `launcher/start_tianji.bat`。
- 检查 `D:\元初系统\天机v9.1` 目录是否存在。
- 查看 `logs/tianji-launcher.log` 与 `logs/tianji-server.err.log`。

### Q2: 端口 8771 被占用？
- 启动器会自动检测并清理占用进程。
- 若失败，可手动运行 `scripts/tools/stop-tianji.ps1` 后重试。

### Q3: 如何确认所有功能已启动？
- 托盘右键 → **全链验证**。
- 或访问 `http://127.0.0.1:8771/api/health`、`/api/mcp/tools`、`/api/orchestrator/agents`。

### Q4: MCP 工具调用超时？
- `mcp/tianji_mcp_server.py` 启动时会清空代理环境变量，确保直连 127.0.0.1:8771。
- 确认服务已完全启动（`engine_ready=true`）。

### Q5: 数据存储在哪里？
- 主数据库：`data/.memory/icme.db`
- 工作层文件：`data/.memory/working/*.json`
- 对话记录：`data/conversations/*.json`
- 日志：`logs/`
- PID：`.daemon/tianji.pid`

---

**维护者**：@tianshu + @jingwei + @yiku
**关联文档**：[ARCHITECTURE.md](./ARCHITECTURE.md) · [API_REFERENCE.md](./API_REFERENCE.md) · [MODULE_INDEX.md](./MODULE_INDEX.md) · [AGENTS.md](./AGENTS.md)
