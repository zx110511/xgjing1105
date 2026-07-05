---
name: tianji-deploy
description: 天机部署流水线 - 一键部署/回滚/验证
category: 天机运维
argument-hint: "<service | all>"
---

# /tianji-deploy - 天机部署流水线

执行服务部署或回滚操作。

## 执行步骤
1. 调用 `get_resource_usage` 检查当前资源
2. 调用 `deploy_service` 执行部署
3. 调用 `check_deployment` 验证健康状态
4. 失败自动触发回滚

## 支持操作
- `deploy <service>`: 部署指定服务
- `rollback <service>`: 回滚到上一版本
- `scale <service> <N>`: 扩容/缩容

## TVP声明
[TVP]#system→@gongzao | [OPS]#deploy
