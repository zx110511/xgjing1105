# GovernanceOrchestrator 集成经验

> 来源：Phase2治理组件集成到 tianji_launcher.py
> 日期：2026-05-24

---

## 集成架构

```
tianji_launcher.py
├── TianjiTray (托盘管理)
│   ├── 菜单项：查看状态、打开管理界面
│   ├── 菜单项：治理健康检查 → on_gov_audit()
│   ├── 菜单项：生成审计报告 → on_gov_report()
│   ├── 菜单项：导出模块清单 → on_gov_manifest()
│   └── 菜单项：重启服务+治理审计 → on_restart()
│
├── GovernanceOrchestrator (治理引导器)
│   ├── bootstrap()
│   │   ├── Phase 2a: _run_registration_phase()
│   │   ├── Phase 2b: _run_analysis_phase()
│   │   ├── Phase 2c: _run_pipeline_phase()
│   │   └── Phase 2d: _generate_audit_report()
│   │
│   ├── run_health_check() → 实时健康检查
│   ├── run_reaudit() → 全量重新审计
│   └── export_manifest() → 模块清单导出
│
└── 启动流程
    └── start_tray() → governor.bootstrap() → 启动成功
```

---

## 集成关键决策

### 1. 治理引导器作为独立类
- **决策**: 在 `tianji_launcher.py` 内定义 `GovernanceOrchestrator` 类
- **理由**: 保持单文件部署，避免循环导入，方便审计脚本直接导入
- **代价**: 启动器文件较大（~800行），但模块化程度清晰

### 2. 组件导入放在方法内部
- **决策**: `from core.module_registry import ...` 放在 `bootstrap()` 方法内部
- **理由**: 延迟导入，避免模块级导入失败导致启动器完全不可用
- **经验**: 导入失败时只降级治理功能，不影响托盘基础功能

### 3. 状态管理线程安全
- **决策**: 使用 `threading.Lock()` 保护 `_status` 字典
- **理由**: 托盘菜单可能在任何时候调用健康检查/重新审计

### 4. 渐进式容错
- **决策**: 导入失败→返回False但托盘正常启动；阶段失败→记录日志但不崩溃
- **理由**: 治理功能应该是增强而非必须，不能阻止系统启动

---

## 集成测试教训

### 关键教训1: 私有API不可假设
在 `_run_analysis_phase` 最初实现中，直接调用了 `self._analyzer._create_import_visitor()` 等私有方法，这些方法不存在。
**解决**: 使用公共API `self._analyzer.analyze(str(self._core_dir))` 替代。

### 关键教训2: 代码生成需对照源文件
几乎所有Bug都是因为假设了dataclass/枚举的结构而不验证。
**解决**: 在开发新集成的 GovernanceOrchestrator 时必须随时对照 `core/*.py` 源文件。

### 关键教训3: SSS审计先行
先编写审计脚本再修复Bug，比逐个手动检查更高效。
本次采用"审计→修复→审计→修复→100%"的迭代模式，总共8轮修复达到100%。

---

## 托盘菜单集成模式

```python
# 治理菜单项最佳实践
def on_gov_audit(_):
    result = _gov_orchestrator.run_reaudit()
    messagebox.showinfo("治理审计完成",
        f"模块: {result['modules_registered']}\n"
        f"分析发现: {result['analysis_findings']}\n"
        f"状态: {'通过' if result['success'] else '失败'}")

def on_gov_report(_):
    report = _gov_orchestrator._last_audit_report
    if report:
        report_path = APP_DIR / "logs" / "audit_reports" / f"audit_{datetime.now():%Y%m%d_%H%M%S}.json"
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        messagebox.showinfo("审计报告", f"已保存到: {report_path}")

def on_gov_manifest(_):
    manifest = _gov_orchestrator.export_manifest()
    manifest_path = APP_DIR / "logs" / f"module_manifest_{datetime.now():%Y%m%d_%H%M%S}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    messagebox.showinfo("模块清单", f"已保存到: {manifest_path}")
```

---

## 启动流程最佳实践

```python
def start_tray():
    # 1. 先初始化治理系统（不阻塞托盘启动）
    global _gov_orchestrator
    _gov_orchestrator = GovernanceOrchestrator()
    _gov_orchestrator.bootstrap()  # 失败不影响后续

    # 2. 启动托盘（永远可用）
    tray = TianjiTray()

    # 3. 后台启动天机服务
    # ...

    # 4. 日志记录治理状态
    if _gov_orchestrator.governance_available:
        _log("治理系统已启用")
    else:
        _log("治理系统未启用（非关键）")
```

---

## 集成状态检查清单

- [x] 治理组件导入成功
- [x] ModuleRegistry 实例化
- [x] StaticAnalyzer 实例化
- [x] GovernancePipeline 实例化
- [x] 注册阶段完成（25个模块）
- [x] 分析阶段完成（26个模块，35条依赖）
- [x] 流水线阶段完成（25条记录）
- [x] 审计报告生成
- [x] 数据闭环验证通过
- [x] 健康检查可用
- [x] 托盘菜单集成完成
- [x] SSS审计100%通过
> 🔄 自动更新于 2026-05-24 09:51:13（源文件变更触发）