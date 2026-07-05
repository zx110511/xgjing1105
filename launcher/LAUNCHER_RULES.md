# 天机v9.1 启动规则 (Tianji Launcher Rules)

## 1. 端口强制规则
- **端口**: 8771 (宪法强制，不可更改)
- **健康检查**: http://127.0.0.1:8771/api/health
- **API文档**: http://127.0.0.1:8771/docs

## 2. 启动方式规则
| 模式 | 命令 | 说明 |
|------|------|------|
| 前台 | `python -m launcher.tianji_v91_launcher` | 可见窗口，Ctrl+C停止 |
| 后台 | `python -m launcher.tianji_v91_launcher --daemon` | 无窗口后台运行 |
| 托盘 | `pythonw -m launcher.tianji_v91_launcher --tray` | 系统托盘图标 |

## 3. 启动文件位置规则
- **唯一启动入口**: `launcher/tianji_v91_launcher.py`
- **配置文件**: `config/tianji.conf`
- **Trae配置**: `.trae/config/launcher.json`
- **PID文件**: `.daemon/tianji.pid`
- **日志目录**: `logs/`

## 4. 启动顺序规则
1. 检查端口8771是否可用
2. 清理旧进程(PID文件)
3. 设置环境变量(AI_MEMORY_ROOT, PYTHONIOENCODING)
4. 启动uvicorn服务
5. 健康检查(最长等待120秒)

## 5. 禁止事项
- ❌ 禁止使用端口8778 (违反宪法)
- ❌ 禁止硬编码API密钥 (违反宪法第1条)
- ❌ 禁止引用不存在的launcher/tianji_launcher.py
- ❌ 禁止使用v8.1路径配置

## 6. 必须事项
- ✅ 必须使用UTF-8编码
- ✅ 必须使用端口8771
- ✅ 必须使用v9.1路径配置
- ✅ 必须通过launcher.tianji_v91_launcher启动

## 7. 修复对齐检查清单
- [ ] config/tianji.conf → 检查project_root是否为v9.1
- [ ] .trae/config/launcher.json → 检查command是否正确
- [ ] scripts/tools/start-tianji.ps1 → 检查端口是否为8771
- [ ] launcher/tianji_v91_launcher.py → 检查是否存在
- [ ] .env → 检查是否硬编码密钥(应使用环境变量)

## 8. 版本历史
| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-25 | 初始创建，统一启动规则 |