---
name: tianji-agent
description: 智能体调度 - 委托任务给指定Agent
category: 天机调度
---

# /tianji-agent - 智能体调度

委托任务给天机智能体执行。

## 输入参数
- `agent` (必填): 目标Agent名称 (如 天枢/明镜/史官等)
- `task` (必填): 任务描述
- `mode` (可选): 串行/并行/流水线

## 执行步骤
1. 调用 `agent_dispatch` 匹配Agent和关键词
2. 调用 `context_extract` 提取任务上下文
3. 如需要多Agent协作，调用 `pipeline_create` 创建流水线
4. 通过 `vap_declare` 声明TVP交接

## 可用Agent
| Agent | 职责 | 层级 |
|-------|------|------|
| @tianshu | 任务编排 | L2 |
| @yiku | 记忆管理 | L1 |
| @mingjing | 质量审计 | L2 |
| @dongcha | 意图感知 | L1 |
| @jingwei | 架构设计 | L2 |
| @kuangshi | 数据处理 | L2 |
| @miaobi | 内容创作 | L2 |
| @shiguan | 版本控制 | L3 |
| @lingxi | 对话守护 | L1 |
| ... | ... | ... |

## TVP声明
[TVP]#system→@tianshu | [OPS]#agent_dispatch
