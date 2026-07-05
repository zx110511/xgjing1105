# 天机v9.1 安全审计脚本 (简化版)
# 执行代码/配置/资源审计，确保发布质量

param(
    [string]$ProjectRoot = $PSScriptRoot,
    [string]$OutputPath = ".\audit-report.json"
)

$ErrorActionPreference = "Continue"
$AuditResults = @()
$CriticalIssues = @()
$Warnings = @()

function Write-AuditHeader($title) {
    Write-Host "`n" + "=" * 70 -ForegroundColor Cyan
    Write-Host "  $title" -ForegroundColor Yellow
    Write-Host "=" * 70 -ForegroundColor Cyan
}

function Add-AuditResult($category, $item, $passed, $severity, $detail) {
    if (-not $detail) { $detail = "" }

    $script:AuditResults += [PSCustomObject]@{
        Category = $category
        Item = $item
        Passed = $passed
        Severity = $severity
        Detail = $detail
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }

    $status = if ($passed) { "[OK]" } else { "[FAIL]" }
    $color = if ($passed) { "Green" } else {
        if ($severity -eq "Critical") { "Red" } else { "Yellow" }
    }
    Write-Host "  $status [$severity] $item" -ForegroundColor $color
    if ($detail) {
        Write-Host "      $detail" -ForegroundColor Gray
    }

    if (-not $passed) {
        if ($severity -eq "Critical") {
            $script:CriticalIssues += "$category - $item"
        } else {
            $script:Warnings += "$category - $item"
        }
    }
}

# ============================================
# 1. 代码审计
# ============================================

function Audit-Code {
    Write-AuditHeader "1. 代码审计"

    # 1.1 硬编码密钥检测
    $codeFiles = Get-ChildItem -Path $ProjectRoot -Include "*.py", "*.ts", "*.js" -Recurse -ErrorAction SilentlyContinue |
                 Where-Object { $_.FullName -notmatch "node_modules|\.git|__pycache__|dist|target" }

    $foundSecrets = $false
    foreach ($file in $codeFiles) {
        try {
            $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
            if ($content -match 'sk-[a-zA-Z0-9]{20,}' -or
                $content -match 'password\s*=\s*[''"][^''"]{5,}[''"]') {
                $foundSecrets = $true
                Add-AuditResult "代码" "硬编码密钥检测" $false "Critical" "文件: $($file.Name)"
                break
            }
        } catch {}
    }
    if (-not $foundSecrets) {
        Add-AuditResult "代码" "硬编码密钥检测" $true "Critical" ""
    }

    # 1.2 bare except检测
    $bareExceptCount = 0
    foreach ($file in ($codeFiles | Where-Object { $_.Extension -eq ".py" })) {
        try {
            $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
            if ($content -match 'except\s*:') {
                $bareExceptCount++
            }
        } catch {}
    }
    Add-AuditResult "代码" "无bare except" ($bareExceptCount -eq 0) "Warning" "文件数: $bareExceptCount"

    # 1.3 TODO/FIXME检测
    $todoCount = 0
    foreach ($file in $codeFiles) {
        try {
            $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
            $matches = ([regex]::Matches($content, 'TODO:|FIXME:')).Count
            $todoCount += $matches
        } catch {}
    }
    Add-AuditResult "代码" "无技术债务" ($todoCount -lt 20) "Warning" "TODO/FIXME数: $todoCount"

    # 1.4 SQL注入检测
    $sqlInjectionFound = $false
    foreach ($file in ($codeFiles | Where-Object { $_.Extension -eq ".py" })) {
        try {
            $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
            if ($content -match 'execute\s*\(' -and $content -match '\+') {
                $sqlInjectionFound = $true
                break
            }
        } catch {}
    }
    Add-AuditResult "代码" "无SQL注入风险" (-not $sqlInjectionFound) "Critical" ""
}

# ============================================
# 2. 配置审计
# ============================================

function Audit-Configuration {
    Write-AuditHeader "2. 配置审计"

    # 2.1 tauri.conf.json
    $tauriConf = Join-Path $ProjectRoot "web\src-tauri\tauri.conf.json"
    if (Test-Path $tauriConf) {
        try {
            $conf = Get-Content $tauriConf -Raw | ConvertFrom-Json
            $hasProductName = $conf.productName -and $conf.productName -ne "app"
            Add-AuditResult "配置" "tauri.conf.json productName正确" $hasProductName "Critical" "值: $($conf.productName)"

            $hasIdentifier = $conf.identifier -and $conf.identifier -ne "com.tauri.dev"
            Add-AuditResult "配置" "tauri.conf.json identifier正确" $hasIdentifier "Critical" "值: $($conf.identifier)"
        } catch {
            Add-AuditResult "配置" "tauri.conf.json解析" $false "Critical" "解析失败"
        }
    } else {
        Add-AuditResult "配置" "tauri.conf.json存在" $false "Critical" ""
    }

    # 2.2 Cargo.toml
    $cargoToml = Join-Path $ProjectRoot "web\src-tauri\Cargo.toml"
    if (Test-Path $cargoToml) {
        $content = Get-Content $cargoToml -Raw
        $hasVersion = $content -match 'version\s*=\s*[''"][\d.]+[''"]'
        Add-AuditResult "配置" "Cargo.toml版本正确" $hasVersion "Warning" ""
    } else {
        Add-AuditResult "配置" "Cargo.toml存在" $false "Critical" ""
    }

    # 2.3 环境变量
    $envFiles = Get-ChildItem -Path $ProjectRoot -Include ".env", ".env.local" -Recurse -ErrorAction SilentlyContinue
    $hasHardcodedEnv = $false
    foreach ($file in $envFiles) {
        try {
            $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
            if ($content -match 'sk-[a-zA-Z0-9]{20,}') {
                $hasHardcodedEnv = $true
                break
            }
        } catch {}
    }
    Add-AuditResult "配置" "环境变量无硬编码" (-not $hasHardcodedEnv) "Critical" ""
}

# ============================================
# 3. 资源审计
# ============================================

function Audit-Resources {
    Write-AuditHeader "3. 资源审计"

    # 3.1 图标文件
    $iconPath = Join-Path $ProjectRoot "web\src-tauri\icons"
    $iconIco = Join-Path $iconPath "icon.ico"
    $iconPng = Join-Path $iconPath "icon.png"
    $iconsExist = (Test-Path $iconIco) -and (Test-Path $iconPng)
    Add-AuditResult "资源" "图标文件完整" $iconsExist "Warning" ""

    # 3.2 静态资源
    $staticDir = Join-Path $ProjectRoot "web\dist"
    $staticExists = Test-Path $staticDir
    Add-AuditResult "资源" "前端构建产物存在" $staticExists "Critical" ""

    # 3.3 数据目录
    $dataDir = Join-Path $ProjectRoot "data"
    $dataExists = Test-Path $dataDir
    Add-AuditResult "资源" "数据目录存在" $dataExists "Warning" ""

    # 3.4 数据库文件
    $dbPath = Join-Path $ProjectRoot "data\.memory\tianji_memory.db"
    $dbExists = Test-Path $dbPath
    Add-AuditResult "资源" "数据库文件存在" $dbExists "Warning" ""
}

# ============================================
# 4. 文档审计
# ============================================

function Audit-Documentation {
    Write-AuditHeader "4. 文档审计"

    # 4.1 README
    $readme = Join-Path $ProjectRoot "README.md"
    $readmeExists = Test-Path $readme
    Add-AuditResult "文档" "README.md存在" $readmeExists "Warning" ""

    # 4.2 验收标准文档
    $acceptance = Join-Path $ProjectRoot "ACCEPTANCE-CRITERIA-V2.md"
    $acceptanceExists = Test-Path $acceptance
    Add-AuditResult "文档" "验收标准文档存在" $acceptanceExists "Warning" ""

    # 4.3 构建脚本
    $buildScript = Join-Path $ProjectRoot "build-desktop.ps1"
    $buildExists = Test-Path $buildScript
    Add-AuditResult "文档" "构建脚本存在" $buildExists "Warning" ""

    # 4.4 测试脚本
    $testScript = Join-Path $ProjectRoot "test-acceptance-v2.ps1"
    $testExists = Test-Path $testScript
    Add-AuditResult "文档" "测试脚本存在" $testExists "Warning" ""
}

# ============================================
# 生成报告
# ============================================

function Generate-AuditReport {
    Write-AuditHeader "审计报告摘要"

    $totalItems = $AuditResults.Count
    $passedItems = ($AuditResults | Where-Object { $_.Passed }).Count
    $criticalCount = $CriticalIssues.Count
    $warningCount = $Warnings.Count

    $report = [PSCustomObject]@{
        AuditDate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        ProjectRoot = $ProjectRoot
        Summary = [PSCustomObject]@{
            TotalItems = $totalItems
            PassedItems = $passedItems
            FailedItems = $totalItems - $passedItems
            CriticalIssues = $criticalCount
            Warnings = $warningCount
            PassRate = [math]::Round(($passedItems / $totalItems) * 100, 1)
        }
        CriticalIssues = $CriticalIssues
        Warnings = $Warnings
        Results = $AuditResults
    }

    $report | ConvertTo-Json -Depth 4 | Out-File $OutputPath -Encoding UTF8

    Write-Host "`n  总审计项: $totalItems" -ForegroundColor White
    Write-Host "  通过项: $passedItems" -ForegroundColor Green
    Write-Host "  严重问题: $criticalCount" -ForegroundColor $(if ($criticalCount -gt 0) { "Red" } else { "Green" })
    Write-Host "  警告问题: $warningCount" -ForegroundColor $(if ($warningCount -gt 0) { "Yellow" } else { "Green" })

    if ($criticalCount -eq 0 -and $warningCount -eq 0) {
        Write-Host "`n  [OK] 审计通过！" -ForegroundColor Green
    } elseif ($criticalCount -eq 0) {
        Write-Host "`n  [WARN] 审计通过，但有 $warningCount 个警告" -ForegroundColor Yellow
    } else {
        Write-Host "`n  [FAIL] 审计未通过！发现 $criticalCount 个严重问题" -ForegroundColor Red
        foreach ($issue in $CriticalIssues) {
            Write-Host "     - $issue" -ForegroundColor Red
        }
    }

    Write-Host "`n  报告已保存: $OutputPath"
}

# ============================================
# 主流程
# ============================================

Write-Host "`n  天机v9.1 安全审计脚本" -ForegroundColor Cyan
Write-Host "  执行代码/配置/资源/文档审计" -ForegroundColor Cyan

Audit-Code
Audit-Configuration
Audit-Resources
Audit-Documentation
Generate-AuditReport
