# 运维部署 (Ops Deploy) — @gongzao

## 触发条件

- 部署请求
- 服务健康检查
- 配置变更

## 执行流程

1. **部署前检查**：deploy_check（依赖/配置/环境）
2. **健康检查**：health_check（所有服务端点）
3. **资源监控**：resource_monitor（CPU/内存/磁盘）
4. **日志追踪**：log_tail（关键日志）
5. **备份配置**：backup_config（变更前备份）
6. **服务重启**：restart_service（灰度重启）

## MCP 工具

- `ops-engine`: deploy_check, health_check, resource_monitor, log_tail, restart_service, backup_config
- `command-executor`: execute_command, list_processes, system_info

## 部署检查清单

```yaml
pre_deploy:
  - 天机8771: healthy ✓
  - ICME六层: all_ready ✓
  - MCP服务器: 6/6 online ✓
  - 磁盘空间: >1GB ✓
  - 备份完成: config+database ✓
```

## 联动 Agent

- @qianli (运维) — 服务状态监控
- @zhuiguang (性能) — 部署后性能基线
- @zhenshan (安全) — 部署安全扫描
