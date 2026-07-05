# 天机记忆系统 - 科学目录管理计划 v1.0
# =========================================
# 日期: 2026-05-10
# 执行: 立即

# ═══════════════════════════════════════════════════════════════
# Phase 1: 天机/ 根目录清理 - 归类散乱文件
# ═══════════════════════════════════════════════════════════════

# --- 启动/停止脚本归入 scripts/ ---
# 移动: 天机\启动天机.bat   → 天机\scripts\start_tianji.bat
# 移动: 天机\停止天机.bat   → 天机\scripts\stop_tianji.bat  
# 移动: 天机\查看状态.bat   → 天机\scripts\status_tianji.bat
# 移动: 天机\tianji.bat      → 天机\scripts\cli.bat
# 移动: 天机\tianji.ps1     → 天机\scripts\cli.ps1
# 移动: 天机\restart_tianji.bat → 天机\scripts\restart.bat
# 移动: 天机\kill_tianji.bat → 天机\scripts\kill.bat
# 移动: 天机\quick_restart.bat → 天机\scripts\quick_restart.bat
# 移动: 天机\force_restart.bat → 天机\scripts\force_restart.bat
# 移动: 天机\start_daemon.bat → 天机\scripts\daemon_start.bat
# 移动: 天机\start_server.bat → 天机\scripts\server_start.bat
# 移动: 天机\stop_tianji.bat → 天机\scripts\stop.bat

# --- 构建/部署工具归入 deploy/ ---
# 移动: 天机\build_installer.bat    → 天机\deploy\build.bat
# 移动: 天机\create_shortcut.ps1    → 天机\deploy\create_shortcut.ps1
# 移动: 天机\创建桌面图标.vbs       → 天机\deploy\create_shortcut.vbs
# 移动: 天机\generate_icon.py       → 天机\deploy\generate_icon.py
# 移动: 天机\tianji_service.spec    → 天机\deploy\tianji.spec
# 移动: 天机\天机.spec              → 天机\deploy\ (删除，合并到tianji.spec)

# --- 测试文件整理 ---
# 重命名: 天机\tests\_t1.py → _t9.py  → tests/legacy/ (归档)
# 重命名: 天机\tests\_run_t1.py → _run_t9.py → tests/legacy/
# 保留核心测试：

# --- 文档归入 docs/ ---
# 移动: 天机\大模型集成状态.md   → 天机\docs\LLM-INTEGRATION-STATUS.md
# 移动: 天机\智能体调度计划_TVP.md → 天机\docs\TVP-SCHEDULING-PLAN.md
# 移动: 天机\测试全部通过         → 删除(空文件)
# 移动: 天机\验证存储纯净性.ps1   → 天机\scripts\verify_storage.ps1

# --- 服务核心入口保持根目录 ---
# 保留: 天机\tianji_service.py     (主服务入口)
# 保留: 天机\tianji_launcher.py    (EXE打包入口)
# 保留: 天机\tianji.py             (原始入口)
# 保留: 天机\start_server.py       (独立服务器启动)
# 保留: 天机\verify_refactoring.py  (验证脚本)
# 保留: 天机\requirements.txt       (依赖声明)

# ═══════════════════════════════════════════════════════════════
# Phase 2: 项目根目录清理
# ═══════════════════════════════════════════════════════════════

# --- 临时目录归档 ---
# 归档: A_root_oneoff_scripts → _archive/ (一次性脚本)
# 归档: B_root_stale_reports  → _archive/ (过时报告)
# 归档: C_root_stale_docs_scripts → _archive/
# 归档: E_tianji_fix_verify_build → _archive/
# 归档: F_tianji_build_artifacts → _archive/
# 归档: F_tianji_stale_reports → _archive/
# 归档: G_pycache → 删除(python自动生成)
# 归档: H_novel_fix_scripts → _archive/
# 归档: Z_cleanup_scripts → _archive/

# --- 重复目录合并 ---
# 合并: 4个 scripts/ 目录 → D:\元初系统\scripts\
# 合并: 4个 data/ 目录 → 统一到天机/data/
# 合并: 4个 tests/ 目录 → 统一策略
# 合并: 4个 logs/ 目录 → 统一到天机/logs/

# --- node_modules清理 ---
# 删除: D:\元初系统\node_modules\ (应在天机/web/node_modules/)

# ═══════════════════════════════════════════════════════════════
# Phase 3: 科学目录标准
# ═══════════════════════════════════════════════════════════════

# 天机/
# ├── tianji_service.py      # ★ 主服务入口
# ├── tianji_launcher.py     # ★ EXE打包入口
# ├── requirements.txt        # 依赖声明
# ├── core/                   # 核心引擎
# │   ├── engine.py           # ICME记忆引擎
# │   ├── sqlite_store.py     # SQLite存储
# │   ├── deepseek_driver.py  # DeepSeek驾驶者
# │   ├── enforcement_hook.py # 强制执行钩子
# │   ├── intelligent_scheduler.py # 智能调度器
# │   └── tvp_bridge.py       # TVP桥接器
# ├── server/                 # 服务层
# │   ├── main.py             # FastAPI入口
# │   ├── deps.py             # 依赖注入
# │   └── api/                # API路由
# ├── mcp/                    # MCP服务器
# ├── indexing/               # 认知处理
# ├── adapters/               # 平台适配器
# ├── llm_integration/        # LLM集成
# ├── config/                 # 配置
# ├── agents/                 # Agent定义
# ├── web/                    # Web前端
# ├── daemon/                 # 守护进程
# ├── tools/                  # 工具集
# ├── active_memory/          # 主动记忆协议
# ├── tests/                  # 测试
# │   └── legacy/             # 归档旧测试
# ├── docs/                   # 文档
# ├── deploy/                 # 部署
# │   ├── build.bat           # 构建脚本
# │   ├── installer_v7.iss    # Inno Setup
# │   ├── generate_icon.py    # 图标生成
# │   └── scripts/            # 部署脚本
# ├── scripts/                # 运维脚本
# │   ├── start.bat           # 启动
# │   ├── stop.bat            # 停止
# │   ├── status.bat          # 状态
# │   └── restart.bat         # 重启
# ├── assets/                 # 静态资源
# ├── data/                   # 数据
# ├── logs/                   # 日志
# ├── backups/                # 备份
# └── output/                 # 构建产物
