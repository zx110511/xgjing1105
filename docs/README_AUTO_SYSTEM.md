# README自动化守护系统使用指南

## 📖 概述

**README自动化守护系统** 是天机v9.1的完全自动化README索引维护机制，实现：
- ✅ 文件系统实时监控
- ✅ 自动触发README更新
- ✅ 防抖+批处理优化
- ✅ 与天机记忆系统集成
- ✅ 配置化管理
- ✅ 守护进程模式

---

## 🚀 快速启动

### 方法1: 独立守护进程

```bash
# 启动README自动化守护进程
python scripts/start_readme_auto.py

# 按 Ctrl+C 停止
```

### 方法2: 集成到天机服务

```bash
# 1. 运行集成脚本
python scripts/integrate_readme_to_service.py

# 2. 重启天机服务
python tianji_service.py restart

# 3. 通过托盘菜单控制
# - 查看状态: "📝 README自动化"
# - 暂停: "⏸ 暂停README自动化"
# - 恢复: "▶ 恢复README自动化"
# - 手动更新: "🔄 立即更新README"
```

---

## ⚙️ 配置文件

**位置**: `config/readme_auto_config.json`

```json
{
  "watch_dirs": [
    "D:\\元初系统\\天机v9.1\\core",
    "D:\\元初系统\\天机v9.1\\indexing",
    "D:\\元初系统\\天机v9.1\\server",
    "D:\\元初系统\\天机v9.1\\agents",
    "D:\\元初系统\\天机v9.1\\mcp"
  ],
  "trigger_config": {
    "enabled": true,
    "debounce_seconds": 2.0,
    "batch_size": 10,
    "batch_timeout": 5.0,
    "exclude_patterns": [
      "*.pyc", "*.pyo", "__pycache__", ".git", "node_modules"
    ],
    "include_patterns": ["*"]
  },
  "auto_commit": false,
  "auto_push": false,
  "store_to_tianji": true,
  "notify_on_update": true,
  "max_depth": 2,
  "update_interval": 300.0
}
```

### 配置项说明

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `watch_dirs` | List[str] | 监控目录列表 | [] |
| `trigger_config.enabled` | bool | 是否启用自动触发 | true |
| `trigger_config.debounce_seconds` | float | 防抖时间(秒) | 2.0 |
| `trigger_config.batch_size` | int | 批处理大小 | 10 |
| `trigger_config.batch_timeout` | float | 批处理超时(秒) | 5.0 |
| `trigger_config.exclude_patterns` | List[str] | 排除模式 | ["*.pyc", ...] |
| `trigger_config.include_patterns` | List[str] | 包含模式 | ["*"] |
| `auto_commit` | bool | 自动提交到git | false |
| `auto_push` | bool | 自动推送 | false |
| `store_to_tianji` | bool | 存储到天机 | true |
| `notify_on_update` | bool | 更新通知 | true |
| `max_depth` | int | 最大扫描深度 | 2 |
| `update_interval` | float | 周期更新间隔(秒) | 300.0 |

---

## 🔧 核心组件

### 1. READMEAutoSystem (核心类)

```python
from core.readme_auto_system import READMEAutoSystem, create_default_config

# 创建配置
config = create_default_config("/path/to/project")

# 创建自动化系统
auto_system = READMEAutoSystem(engine=engine, config=config)

# 初始化
auto_system.initialize("/path/to/config.json")

# 触发更新
auto_system.trigger_update("/path/to/dir", AutoTriggerType.MANUAL)

# 获取统计
stats = auto_system.get_stats()

# 关闭
auto_system.shutdown()
```

### 2. DebouncedTrigger (防抖触发器)

```python
from core.readme_auto_system import DebouncedTrigger

trigger = DebouncedTrigger(callback, debounce_seconds=2.0)
trigger.trigger("/path/to/dir", AutoTriggerType.FILE_MODIFY)
```

### 3. BatchProcessor (批量处理器)

```python
from core.readme_auto_system import BatchProcessor

processor = BatchProcessor(callback, batch_size=10, batch_timeout=5.0)
processor.add("/path/to/dir", AutoTriggerType.FILE_CREATE)
```

### 4. READMEFileSystemHandler (文件监控)

```python
from core.readme_auto_system import READMEAutoSystem
# 自动集成watchdog，无需手动使用
```

---

## 📊 触发类型

| 类型 | 说明 | 触发时机 |
|------|------|----------|
| `FILE_CREATE` | 文件创建 | 创建新文件时 |
| `FILE_DELETE` | 文件删除 | 删除文件时 |
| `FILE_MODIFY` | 文件修改 | 修改文件时 |
| `DIR_CREATE` | 目录创建 | 创建新目录时 |
| `DIR_DELETE` | 目录删除 | 删除目录时 |
| `PERIODIC` | 周期更新 | 定时触发 |
| `MANUAL` | 手动触发 | 用户手动触发 |

---

## 🔄 自动化流程

```
文件系统事件
    ↓
READMEFileSystemHandler (文件监控)
    ↓
DebouncedTrigger (防抖)
    ↓
BatchProcessor (批处理)
    ↓
TianjiREADMEIntegrator (生成README)
    ↓
AIHookExecutor (执行钩子)
    ↓
天机L3 Episodic层 (存储记录)
    ↓
README.md更新完成
```

---

## 📈 性能优化

### 1. 防抖机制
- 避免频繁触发更新
- 默认防抖时间: 2秒
- 可配置: `trigger_config.debounce_seconds`

### 2. 批处理机制
- 合并多个触发事件
- 默认批大小: 10
- 默认超时: 5秒
- 可配置: `trigger_config.batch_size`, `trigger_config.batch_timeout`

### 3. 排除模式
- 排除临时文件、缓存文件等
- 默认排除: `*.pyc`, `__pycache__`, `.git`, `node_modules`
- 可配置: `trigger_config.exclude_patterns`

### 4. 深度限制
- 限制扫描深度，避免过深递归
- 默认深度: 2
- 可配置: `max_depth`

---

## 🎯 使用场景

### 场景1: 开发时实时更新

```bash
# 启动守护进程
python scripts/start_readme_auto.py

# 修改任意监控目录下的文件
# README.md自动更新
```

### 场景2: 定期批量更新

```json
{
  "update_interval": 300.0  // 每5分钟更新一次
}
```

### 场景3: CI/CD集成

```bash
# 在CI/CD中触发更新
python -c "
from core.readme_auto_system import READMEAutoSystem, AutoTriggerType
auto = READMEAutoSystem()
auto.initialize()
auto.trigger_update('/path/to/project', AutoTriggerType.MANUAL)
auto.shutdown()
"
```

### 场景4: Git集成

```json
{
  "auto_commit": true,
  "auto_push": true
}
```

---

## 🐛 故障排查

### 问题1: watchdog不可用

```bash
# 安装watchdog
pip install watchdog
```

### 问题2: 更新未触发

检查配置:
```json
{
  "trigger_config": {
    "enabled": true  // 确保为true
  }
}
```

### 问题3: 更新过于频繁

调整防抖时间:
```json
{
  "trigger_config": {
    "debounce_seconds": 5.0  // 增加防抖时间
  }
}
```

### 问题4: 内存占用高

减少监控目录或深度:
```json
{
  "watch_dirs": ["core"],  // 只监控core目录
  "max_depth": 1  // 减少扫描深度
}
```

---

## 📝 日志示例

```
[READMEAutoSystem] 初始化完成
  监控目录: 5
  防抖时间: 2.0s
  批量大小: 10
  周期间隔: 300.0s
[READMEAutoSystem] 文件监控启动成功
  监控: D:\元初系统\天机v9.1\core
  监控: D:\元初系统\天机v9.1\indexing
  ...
[READMEAutoSystem] 更新成功: D:\元初系统\天机v9.1\core (file_modify)
[READMEAutoSystem] 更新成功: D:\元初系统\天机v9.1\indexing (file_create)
```

---

## 🔗 相关文件

- **核心模块**: [core/readme_auto_system.py](../core/readme_auto_system.py)
- **启动脚本**: [scripts/start_readme_auto.py](../scripts/start_readme_auto.py)
- **集成脚本**: [scripts/integrate_readme_to_service.py](../scripts/integrate_readme_to_service.py)
- **配置文件**: [config/readme_auto_config.json](../config/readme_auto_config.json)
- **基础模块**: [core/directory_index.py](../core/directory_index.py)

---

**版本**: v1.0.0 | **更新**: 2026-06-04 | **维护**: @tianshu