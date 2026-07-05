# Fix Desktop Shortcut Script
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Tianji v9.1.lnk")

# Fix incorrect pythonw.exe path
$Shortcut.TargetPath = "D:\元初系统\天机v9.1\python\Scripts\pythonw.exe"
$Shortcut.Arguments = "-m launcher.tianji_v91_launcher --daemon --tray"
$Shortcut.WorkingDirectory = "D:\元初系统\天机v9.1"
$Shortcut.Description = "Tianji v9.1 - Memory Agent System (Port 8771)"
$Shortcut.IconLocation = "D:\元初系统\天机v9.1\assets\icon.ico,0"

$Shortcut.Save()

Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "TargetPath: $($Shortcut.TargetPath)" -ForegroundColor Cyan
Write-Host "Arguments: $($Shortcut.Arguments)" -ForegroundColor Cyan
