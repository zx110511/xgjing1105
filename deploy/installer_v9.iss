; 天机记忆系统 v9.0-beta1 - Inno Setup安装脚本
; 《天机·星枢运转》— ICME六层记忆 + SSS三链并行 + TVP透明调度
; 日期: 2026-05-30
;
; v9.0-beta1 变更:
;   + 环境全独立化 (所有依赖自包含于 v9.0根目录)
;   + 53个临时文件归档清理
;   + 科研区解散, 文档重组织至 docs/
;   + 8项国际标准100%对齐 (OTel/ISO/OWASP/IETF/MS Agent)
;   + 7链能力100%辐射
;   + P01-P17全栈17任务交付
;   + 专业级Windows ONEDIR编译
;
; 构建步骤:
;   1. 运行 scripts\build_v9.bat 生成 dist\天机.exe
;   2. 用 Inno Setup 6 编译此文件

#define AppName "天机记忆系统"
#define AppNameEn "TianjiMemory"
#define AppVersion "9.0.0-beta1"
#define AppPublisher "元初系统"
#define AppURL "https://github.com/zx110511/yuanchu-system"
#define AppExeName "天机.exe"

[Setup]
AppId={{TIANJI-2026-V9-BETA1-UNIQUE-ID}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName} v9
AllowNoIcons=no
OutputDir=..\output
OutputBaseFilename=天机记忆系统_v9.0.0-beta1_Windows_x64_Setup
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} v{#AppVersion}
DisableProgramGroupPage=yes
DisableWelcomePage=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Messages]
chinesesimplified.WelcomeLabel2=这将安装天机记忆系统 v9.0-beta1 专业版到您的计算机。%n%n天机是一个AI智能记忆平台，自动记录所有对话和操作，提供智能记忆检索。%n%nv9.0新特性：环境全独立化、8项国际标准100%对齐、7链能力完整辐射、专业级Windows ONEDIR。%n%n安装完成后，天机将在后台运行，并在系统托盘显示图标。

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式:"; Flags: checkedonce
Name: "autostart"; Description: "开机自动启动天机"; GroupDescription: "启动选项:"; Flags: checkedonce

[Files]
; 主程序 EXE (PyInstaller打包)
Source: "dist\天机.exe"; DestDir: "{app}"; Flags: ignoreversion

; 核心模块
Source: "..\core\*"; DestDir: "{app}\core"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\agents\*"; DestDir: "{app}\agents"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\enforcement\*"; DestDir: "{app}\enforcement"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\launcher\*"; DestDir: "{app}\launcher"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\daemon\*"; DestDir: "{app}\daemon"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
; 核心模块
Source: "..\active_memory\*"; DestDir: "{app}\active_memory"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\adapters\*"; DestDir: "{app}\adapters"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\mcp\*"; DestDir: "{app}\mcp"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\indexing\*"; DestDir: "{app}\indexing"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,.memory"
Source: "..\web\*"; DestDir: "{app}\web"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,node_modules"
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"

; 脚本工具
Source: "..\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"

; 测试套件
Source: "..\tests\*"; DestDir: "{app}\tests"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"

; 天机服务入口
Source: "..\launcher\tianji_launcher.py"; DestDir: "{app}\launcher"; Flags: ignoreversion

; Python运行时 (自包含)
Source: "..\python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

; 图标资源
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; 配置与依赖
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\.env"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "..\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\.trae\*"; DestDir: "{app}\.trae"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"

; 归档文件 (v9.0-beta1不打包临时文件归档)
; Source: "..\_archive\*"; DestDir: "{app}\_archive"; Flags: skipifsourcedoesntexist recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\data\.memory"; Permissions: everyone-full
Name: "{app}\logs"; Permissions: everyone-full
Name: "{app}\backups"; Permissions: everyone-full
Name: "{app}\.daemon"; Permissions: everyone-full
Name: "{app}\enforcement_cache"; Permissions: everyone-full
Name: "{app}\docs\research"; Permissions: everyone-full
Name: "{app}\docs\instructions"; Permissions: everyone-full
Name: "{app}\tests\reports"; Permissions: everyone-full

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"; Comment: "启动天机记忆系统 v9"
Name: "{group}\管理界面"; Filename: "http://127.0.0.1:8771/"; Comment: "打开天机Web管理界面"
Name: "{group}\API文档"; Filename: "http://127.0.0.1:8771/api/status"; Comment: "查看天机API状态"
Name: "{group}\卸载天机v9"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"; Comment: "天机记忆系统 v9.0-beta1 - AI智能记忆平台"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "立即启动天机记忆系统"; Flags: nowait postinstall skipifsilent unchecked
Filename: "http://127.0.0.1:8771/"; Description: "打开管理界面"; Flags: shellexec postinstall skipifsilent unchecked

[Registry]
Root: HKLM; Subkey: "SOFTWARE\天机记忆系统_v9"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\天机记忆系统_v9"; ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\天机记忆系统_v9"; ValueType: string; ValueName: "InstallDate"; ValueData: "{code:GetCurrentDate}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\天机记忆系统_v9"; ValueType: string; ValueName: "Architecture"; ValueData: "Fusion-v9.0-beta1"; Flags: uninsdeletekey

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\logs"

[Code]
function GetCurrentDate(Param: String): String;
begin
  Result := GetDateTimeString('yyyy-mm-dd', '-', '-');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  AppPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    AppPath := ExpandConstant('{app}');

    if WizardIsTaskSelected('autostart') then
    begin
      Exec('schtasks', '/create /tn "天机记忆系统v9" /tr "' + AppPath + '\天机.exe" /sc onlogon /rl LIMITED /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Exec('taskkill', '/f /im "天机.exe"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    Exec('schtasks', '/delete /tn "天机记忆系统v9" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    if MsgBox('是否删除天机的所有记忆数据？选择"否"将保留数据以便将来恢复。', mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{app}\data'), True, True, True);
    end;
  end;
end;
