# 天机v9.1 发布包同步脚本
# 将最新源码同步到 release/天机v9.1-全量发布包 目录
$ErrorActionPreference = "Stop"
$srcRoot = "D:\元初系统\天机v9.1"
$dstRoot = "$srcRoot\release\天机v9.1-全量发布包"

Write-Output "=== 天机v9.1 发布包同步 ==="
Write-Output "源: $srcRoot"
Write-Output "目标: $dstRoot"
Write-Output ""

# 1. 同步核心代码目录 (robocopy /MIR 镜像同步)
$codeDirs = @(
    @{Src="core"; Dst="core"; Exclude=@("__pycache__","*.pyc","*.pyo")},
    @{Src="server"; Dst="server"; Exclude=@("__pycache__","*.pyc","*.pyo")},
    @{Src="indexing"; Dst="indexing"; Exclude=@("__pycache__","*.pyc","*.pyo")},
    @{Src="active_memory"; Dst="active_memory"; Exclude=@("__pycache__","*.pyc","*.pyo")},
    @{Src="agents"; Dst="agents"; Exclude=@("__pycache__","*.pyc","*.pyo")},
    @{Src="adapters"; Dst="adapters"; Exclude=@("__pycache__","*.pyc","*.pyo")}
)

foreach ($dir in $codeDirs) {
    $src = Join-Path $srcRoot $dir.Src
    $dst = Join-Path $dstRoot $dir.Dst
    if (Test-Path $src) {
        Write-Output "同步: $($dir.Src) -> $($dir.Dst)"
        robocopy $src $dst /MIR /XD __pycache__ .git node_modules /XF *.pyc *.pyo .gitignore /NFL /NDL /NJH /NJS /NP | Out-Null
    }
}

# 2. 同步Python运行时 (只同步Lib和DLL，不复制整个python目录)
Write-Output "同步: python (运行时)"
$pySrc = Join-Path $srcRoot "python"
$pyDst = Join-Path $dstRoot "python"
if (Test-Path $pySrc) {
    # 同步python.exe和关键DLL
    robocopy $pySrc $pyDst python.exe python3*.dll python*.dll vcruntime*.dll /XF *.pdb /NFL /NDL /NJH /NJS /NP | Out-Null
    # 同步Lib目录
    robocopy "$pySrc\Lib" "$pyDst\Lib" /MIR /XD __pycache__ test tests idlelib tkinter turtledemo /XF *.pyc *.pyo *.pdb /NFL /NDL /NJH /NJS /NP | Out-Null
    # 同步DLLs目录
    robocopy "$pySrc\DLLs" "$pyDst\DLLs" /MIR /XF *.pdb /NFL /NDL /NJH /NJS /NP | Out-Null
    # 同步Scripts目录 (pip等)
    if (Test-Path "$pySrc\Scripts") {
        robocopy "$pySrc\Scripts" "$pyDst\Scripts" /MIR /XD __pycache__ /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NP | Out-Null
    }
}

# 3. 同步site-packages (关键依赖)
Write-Output "同步: site-packages"
$spSrc = "$pySrc\Lib\site-packages"
$spDst = "$pyDst\Lib\site-packages"
if (Test-Path $spSrc) {
    # 关键依赖包列表
    $criticalPkgs = @(
        "fastapi", "uvicorn", "pydantic", "pydantic_core",
        "starlette", "anyio", "httpcore", "httpx", "h11",
        "aiofiles", "sklearn", "scikit-learn", "numpy", "scipy",
        "joblib", "threadpoolctl", "sympy", "mpmath",
        "typing_extensions", "annotated_types", "click", "sniffio",
        "idna", "certifi", "h2", "hpack", "hyperframe",
        "dotenv", "python_dotenv", "python-multipart",
        "sse_starlette", "websockets", "watchfiles"
    )
    # 先同步所有包，排除大型无关包
    $excludeDirs = @("test", "tests", "__pycache__", "docs", "doc", "examples", ".dist-info")
    $excludeFiles = @("*.pyc", "*.pyo", "*.pdb", "*.exe", "*.whl")

    # 直接镜像整个site-packages，排除无关目录
    robocopy $spSrc $spDst /MIR /XD test tests __pycache__ docs doc examples .dist-info .git /XF *.pyc *.pyo *.pdb /NFL /NDL /NJH /NJS /NP | Out-Null
}

# 4. 同步数据目录 (排除临时文件)
Write-Output "同步: data"
$dataSrc = Join-Path $srcRoot "data"
$dataDst = Join-Path $dstRoot "data"
if (Test-Path $dataSrc) {
    robocopy $dataSrc $dataDst /MIR /XD __pycache__ .git /XF *.pyc *.pyo *.log /NFL /NDL /NJH /NJS /NP | Out-Null
}

# 5. 同步.trae配置目录
Write-Output "同步: .trae"
$traeSrc = Join-Path $srcRoot ".trae"
$traeDst = Join-Path $dstRoot ".trae"
if (Test-Path $traeSrc) {
    robocopy $traeSrc $traeDst /MIR /XD __pycache__ .git /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NP | Out-Null
}

# 6. 同步web构建产物 (只同步dist和Tauri exe)
Write-Output "同步: web构建产物"
$webDst = Join-Path $dstRoot "web"
# dist目录
$distSrc = Join-Path $srcRoot "web\dist"
$distDst = Join-Path $webDst "dist"
if (Test-Path $distSrc) {
    robocopy $distSrc $distDst /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
}
# Tauri exe
$tauriSrc = Join-Path $srcRoot "web\src-tauri\target\release\tianji.exe"
$tauriDst = Join-Path $webDst "tianji.exe"
if (Test-Path $tauriSrc) {
    if (-not (Test-Path $webDst)) { New-Item -ItemType Directory -Path $webDst -Force | Out-Null }
    Copy-Item $tauriSrc $tauriDst -Force
    Write-Output "  复制: tianji.exe"
}
# NSIS安装程序
$nsisSrc = Join-Path $srcRoot "web\src-tauri\target\release\bundle\nsis"
$nsisDst = Join-Path $webDst "bundle\nsis"
if (Test-Path $nsisSrc) {
    robocopy $nsisSrc $nsisDst /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
}

# 7. 同步顶层文件
Write-Output "同步: 顶层文件"
$topFiles = @(
    "functional_audit.py",
    "requirements.txt",
    "mcp_servers.py",
    "tianji_mcp_server.py"
)
foreach ($f in $topFiles) {
    $src = Join-Path $srcRoot $f
    $dst = Join-Path $dstRoot $f
    if (Test-Path $src) {
        Copy-Item $src $dst -Force
    }
}

# 8. 创建启动脚本 (如果不存在)
$launchVbs = Join-Path $dstRoot "启动天机.vbs"
if (-not (Test-Path $launchVbs)) {
    $vbsContent = @'
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
installDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonExe = installDir & "\python\python.exe"

' 设置环境变量
WshShell.Environment("Process").Item("AI_MEMORY_ROOT") = installDir
WshShell.Environment("Process").Item("AI_MEMORY_PORT") = "8778"
WshShell.Environment("Process").Item("PYTHONIOENCODING") = "gbk"

' 启动后端服务(无窗口)
WshShell.Run """" & pythonExe & """ -m uvicorn server.main:app --host 127.0.0.1 --port 8778 --log-level warning", 0, False

' 等待服务启动
WScript.Sleep 5000

' 启动桌面应用(如果存在)
tauriExe = installDir & "\web\tianji.exe"
If fso.FileExists(tauriExe) Then
    WshShell.Run """" & tauriExe & """", 1, False
Else
    ' 打开浏览器
    WshShell.Run "http://127.0.0.1:8778", 1, False
End If
'@
    Set-Content -Path $launchVbs -Value $vbsContent -Encoding ASCII
    Write-Output "  创建: 启动天机.vbs"
}

# 创建安装说明
$installTxt = Join-Path $dstRoot "安装说明.txt"
$txtContent = @"
天机v9.1 · AI智能记忆平台 - 安装说明
========================================
版本: 9.1.0
系统要求: Windows 10/11 (64位), 无需预装任何软件

【快速启动】
  1. 将整个文件夹复制到目标电脑 (如 D:\天机v9.1)
  2. 双击 "启动天机.vbs"
  3. 等待5秒后浏览器自动打开 http://127.0.0.1:8778
  4. 如有桌面应用(tianji.exe)会自动启动

【端口说明】
  后端API服务: http://127.0.0.1:8778
  健康检查: http://127.0.0.1:8778/api/health
  API文档: http://127.0.0.1:8778/docs

【MCP接入】
  在Trae IDE或Cursor的MCP配置中添加:
  {
    "mcpServers": {
      "tianji-native": {
        "command": "python/python.exe",
        "args": ["mcp_servers.py"],
        "cwd": "D:/天机v9.1"
      }
    }
  }

【停止服务】
  在任务管理器中结束 python.exe 进程
  或访问 http://127.0.0.1:8778/api/shutdown

【目录结构】
  python/       - Python 3.12运行时(内置)
  core/         - 天机核心引擎
  server/       - FastAPI后端服务
  data/         - 记忆数据存储
  .trae/        - 配置和规则
  web/          - 前端和桌面应用
  indexing/     - 检索索引引擎
  active_memory/ - 主动记忆系统
  agents/       - 智能体定义
  adapters/     - AI平台适配器
"@
    Set-Content -Path $installTxt -Value $txtContent -Encoding UTF8
    Write-Output "  创建: 安装说明.txt"

# 9. 统计最终大小
$totalSize = (Get-ChildItem $dstRoot -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
$totalFiles = (Get-ChildItem $dstRoot -Recurse -File -ErrorAction SilentlyContinue).Count
Write-Output ""
Write-Output "=== 同步完成 ==="
Write-Output "总文件数: $totalFiles"
Write-Output "总大小: $([math]::Round($totalSize,1))MB"
