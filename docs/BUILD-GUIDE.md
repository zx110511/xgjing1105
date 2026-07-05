# 天机v9.1 桌面版构建指南

## 当前状态

| 步骤 | 状态 | 说明 |
|------|------|------|
| 前端构建 | ✅ 完成 | 2.1 MB, 25秒 |
| Python后端 | ✅ 就绪 | 使用Python解释器 |
| Tauri编译 | ❌ 阻塞 | Windows安全策略 |
| 安装包生成 | ⏳ 待执行 | 依赖Tauri编译 |
| 安全审计 | ✅ 完成 | 11/16通过 |
| 验收测试 | ✅ 完成 | 后端运行正常 |

---

## 手动完成构建（管理员PowerShell）

### 方法1: 使用自动化脚本

```powershell
# 1. 右键PowerShell → 以管理员身份运行

# 2. 设置执行策略
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3. 进入项目目录
cd D:\元初系统\天机v9.1

# 4. 运行自动化脚本
.\auto-build.ps1
```

### 方法2: 手动分步执行

```powershell
# Step 1: 创建Junction（解决中文路径）
if (-not (Test-Path "C:\tianji-build")) {
    New-Item -ItemType Junction -Path "C:\tianji-build" -Target "D:\元初系统\天机v9.1"
}

# Step 2: 清理旧构建
Remove-Item -Recurse -Force "C:\tianji-build\web\src-tauri\target" -ErrorAction SilentlyContinue

# Step 3: 设置Rust工具链
& "$env:USERPROFILE\.cargo\bin\rustup.exe" default stable-x86_64-pc-windows-msvc

# Step 4: 编译Tauri（预计3-5分钟）
cd C:\tianji-build\web\src-tauri
& "$env:USERPROFILE\.cargo\bin\rustup.exe" run stable-x86_64-pc-windows-msvc cargo build --release

# Step 5: 验证编译结果
Test-Path "C:\tianji-build\web\src-tauri\target\release\tianji.exe"

# Step 6: 生成安装包
cd D:\元初系统\天机v9.1\web
npm run tauri:build

# Step 7: 查找安装包
Get-ChildItem -Path "web\src-tauri\target\release\bundle" -Include "*.msi","*.exe" -Recurse
```

---

## 预期产物

| 产物 | 路径 | 预期大小 |
|------|------|---------|
| Tauri应用 | C:\tianji-build\web\src-tauri\target\release\tianji.exe | ~5-8 MB |
| 安装包 | web\src-tauri\target\release\bundle\*.msi | ~50-80 MB |

---

## 验收结果

### 天机后端状态

- **运行状态**: ✅ 正常运行
- **访问地址**: http://127.0.0.1:8778
- **健康状态**: healthy
- **运行时间**: 4.7小时
- **总记忆数**: 74,839条

### ICME六层记忆

| 层级 | 条目数 | 使用率 |
|------|--------|--------|
| Sensory | 1,597 | 5.6% |
| Working | 648 | 1.0% |
| Short-Term | 2,599 | 0.8% |
| Episodic | 2,682 | 0.2% |
| Semantic | 8,436 | 0.1% |
| Meta | 58,477 | 2.9% |

---

## 故障排除

### 问题1: PowerShell闪退

**原因**: 执行策略限制或脚本错误

**解决**:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 问题2: Rust编译失败 (os error 4551)

**原因**: Windows安全策略阻止build script执行

**解决**: 必须以管理员权限运行PowerShell

### 问题3: 中文路径问题

**原因**: Rust不支持中文路径

**解决**: 使用Junction链接到ASCII路径
```powershell
New-Item -ItemType Junction -Path "C:\tianji-build" -Target "D:\元初系统\天机v9.1"
```

### 问题4: MSVC工具链缺失

**原因**: 未安装VS Build Tools

**解决**:
```powershell
# 下载并安装
winget install Microsoft.VisualStudio.2022.BuildTools
```

---

## 下一步

1. ✅ 前端已构建完成
2. ✅ 后端运行正常
3. ⏳ 完成Tauri编译（需管理员权限）
4. ⏳ 生成安装包
5. ⏳ 最终验收测试

**建议**: 使用方法1的自动化脚本，在管理员PowerShell中一键完成。
