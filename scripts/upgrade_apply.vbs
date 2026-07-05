' 天机v9.1 - 一键升级
' 用户端使用: 解压升级包后双击此脚本
' 自动: 停止服务 -> 备份数据 -> 覆盖文件 -> 启动服务

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' 升级包目录(脚本所在目录)
upgradeDir = fso.GetParentFolderName(WScript.ScriptFullName)
manifestFile = upgradeDir & "\upgrade_manifest.json"
versionFile = upgradeDir & "\version.json"

' ========== Step 1: 读取升级清单 ==========
If Not fso.FileExists(manifestFile) Then
    MsgBox "未找到升级清单文件!" & vbCrLf & "请确认这是完整的天机升级包", vbCritical, "天机v9.1 升级"
    WScript.Quit 1
End If

' 读取版本信息
Set verFile = fso.OpenTextFile(versionFile, 1, False)
verContent = verFile.ReadAll
verFile.Close

' 简单解析JSON中的版本号
toVersion = ExtractValue(verContent, """version""")
fromVersion = ExtractValue(verContent, """min_upgrade_from""")

' ========== Step 2: 定位天机安装目录 ==========
' 优先: 升级包放在天机目录内
installDir = ""
If fso.FileExists(upgradeDir & "\..\python\python.exe") Then
    installDir = fso.GetParentFolderName(upgradeDir)
' 备选: 升级包放在天机目录同级
ElseIf fso.FileExists(upgradeDir & "\python\python.exe") Then
    installDir = upgradeDir
Else
    ' 让用户选择
    installDir = BrowseForFolder("请选择天机v9.1的安装目录:")
    If installDir = "" Then
        MsgBox "未选择安装目录, 升级取消", vbInformation, "天机v9.1 升级"
        WScript.Quit 0
    End If
    If Not fso.FileExists(installDir & "\python\python.exe") Then
        MsgBox "所选目录不是有效的天机安装目录!", vbCritical, "天机v9.1 升级"
        WScript.Quit 1
    End If
End If

' ========== Step 3: 版本检查 ==========
currentVer = "未知"
If fso.FileExists(installDir & "\version.json") Then
    Set curVerFile = fso.OpenTextFile(installDir & "\version.json", 1, False)
    curVerContent = curVerFile.ReadAll
    curVerFile.Close
    currentVer = ExtractValue(curVerContent, """version""")
End If

' 确认升级
msg = "天机v9.1 升级确认" & vbCrLf & vbCrLf
msg = msg & "当前版本: " & currentVer & vbCrLf
msg = msg & "升级到:   " & toVersion & vbCrLf
msg = msg & "安装目录: " & installDir & vbCrLf & vbCrLf
msg = msg & "升级过程中服务将暂时停止" & vbCrLf
msg = msg & "用户数据(data/)将被保留" & vbCrLf & vbCrLf
msg = msg & "是否继续?"

result = MsgBox(msg, vbQuestion + vbYesNo, "天机v9.1 升级")
If result <> vbYes Then
    WScript.Quit 0
End If

' ========== Step 4: 停止天机服务 ==========
On Error Resume Next
Set http = CreateObject("MSXML2.XMLHTTP.6.0")
http.Open "GET", "http://127.0.0.1:8778/api/shutdown", False
http.Send
On Error GoTo 0
WScript.Sleep 3000

' ========== Step 5: 备份当前版本信息 ==========
backupDir = installDir & "\_upgrade_backup_" & currentVer
If Not fso.FolderExists(backupDir) Then
    fso.CreateFolder(backupDir)
End If

' 备份version.json
If fso.FileExists(installDir & "\version.json") Then
    fso.CopyFile installDir & "\version.json", backupDir & "\version.json", True
End If

' ========== Step 6: 执行文件升级 ==========
' 读取清单中的文件列表
Set manFile = fso.OpenTextFile(manifestFile, 1, False)
manContent = manFile.ReadAll
manFile.Close

' 解析需要保留的目录
preserveDirs = Array("data", "logs", "_upgrade_backup_")

' 复制升级文件(覆盖安装目录中的对应文件)
Set upgradeFolder = fso.GetFolder(upgradeDir)
copiedCount = 0
CopyFolderContents upgradeDir, installDir, copiedCount

' 删除清单中标记为删除的文件
removedCount = 0
removedSection = ExtractValue(manContent, """removed_files""")
If Len(removedSection) > 0 Then
    ' 简单解析删除列表
    arr = Split(removedSection, ",")
    For Each item In arr
        filePath = Replace(Replace(item, """", ""), "[", "")
        filePath = Replace(Replace(filePath, "]", ""), " ", "")
        If Len(filePath) > 0 Then
            fullPath = installDir & "\" & filePath
            If fso.FileExists(fullPath) Then
                fso.DeleteFile fullPath, True
                removedCount = removedCount + 1
            End If
        End If
    Next
End If

' ========== Step 7: 启动服务 ==========
pythonExe = installDir & "\python\python.exe"
WshShell.Environment("Process").Item("AI_MEMORY_ROOT") = installDir
WshShell.Environment("Process").Item("AI_MEMORY_PORT") = "8778"
WshShell.Environment("Process").Item("PYTHONIOENCODING") = "gbk"
WshShell.Environment("Process").Item("PYTHONPATH") = installDir

WshShell.Run """" & pythonExe & """ -m uvicorn server.main:app --host 127.0.0.1 --port 8778 --log-level warning", 0, False
WScript.Sleep 6000

' ========== Step 8: 验证升级 ==========
upgradeOk = False
On Error Resume Next
Set http2 = CreateObject("MSXML2.XMLHTTP.6.0")
http2.Open "GET", "http://127.0.0.1:8778/api/health", False
http2.Send
If http2.Status = 200 Then
    upgradeOk = True
End If
On Error GoTo 0

If upgradeOk Then
    MsgBox "升级成功!" & vbCrLf & vbCrLf & _
           "版本: " & currentVer & " -> " & toVersion & vbCrLf & _
           "更新文件: " & copiedCount & "个" & vbCrLf & _
           "删除文件: " & removedCount & "个" & vbCrLf & vbCrLf & _
           "备份位置: " & backupDir, vbInformation, "天机v9.1 升级"
Else
    MsgBox "升级完成, 但服务启动失败!" & vbCrLf & _
           "请手动运行 启动天机.vbs", vbExclamation, "天机v9.1 升级"
End If

' ========== 辅助函数 ==========

Sub CopyFolderContents(src, dst, ByRef count)
    Set folder = fso.GetFolder(src)
    ' 复制文件
    For Each file In folder.Files
        fname = file.Name
        ' 跳过升级脚本和清单
        If fname <> "一键升级.vbs" And fname <> "upgrade_manifest.json" Then
            fso.CopyFile file.Path, dst & "\" & fname, True
            count = count + 1
        End If
    Next
    ' 递归复制子目录
    For Each subFolder In folder.SubFolders
        subName = subFolder.Name
        ' 跳过保留目录
        skip = False
        For Each pDir In preserveDirs
            If LCase(subName) = LCase(pDir) Then skip = True
        Next
        If Not skip And subName <> "_upgrade_backup_" Then
            targetPath = dst & "\" & subName
            If Not fso.FolderExists(targetPath) Then
                fso.CreateFolder(targetPath)
            End If
            CopyFolderContents subFolder.Path, targetPath, count
        End If
    Next
End Sub

Function ExtractValue(jsonStr, key)
    ' 简单JSON值提取
    pos = InStr(jsonStr, key)
    If pos = 0 Then
        ExtractValue = ""
        Exit Function
    End If
    ' 找到冒号后的值
    colonPos = InStr(pos, jsonStr, ":")
    If colonPos = 0 Then
        ExtractValue = ""
        Exit Function
    End If
    ' 提取冒号后的内容
    rest = Mid(jsonStr, colonPos + 1)
    ' 去掉前导空白和引号
    rest = LTrim(rest)
    If Left(rest, 1) = """" Then
        rest = Mid(rest, 2)
        endPos = InStr(rest, """")
        If endPos > 0 Then
            ExtractValue = Left(rest, endPos - 1)
        Else
            ExtractValue = rest
        End If
    Else
        ' 非字符串值
        endPos = InStr(rest, ",")
        If endPos = 0 Then endPos = InStr(rest, "}")
        If endPos = 0 Then endPos = InStr(rest, "]")
        If endPos > 0 Then
            ExtractValue = Trim(Left(rest, endPos - 1))
        Else
            ExtractValue = Trim(rest)
        End If
    End If
End Function

Function BrowseForFolder(prompt)
    Set shell = CreateObject("Shell.Application")
    Set folder = shell.BrowseForFolder(0, prompt, 0)
    If folder Is Nothing Then
        BrowseForFolder = ""
    Else
        BrowseForFolder = folder.Self.Path
    End If
End Function
