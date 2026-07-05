# 透明调度可视化 (agent/transparent-dispatch)

## 目的
将多Agent协作过程以TVP协议可视化呈现，确保调度100%透明可追溯。

## 触发场景
- 复杂任务涉及3个以上Agent协作
- 需要向用户展示决策过程与Agent分工
- 事后审计与复盘

## 执行步骤

### Step 1: 调度计划生成
1. 解析任务依赖图（哪些步骤必须顺序，哪些可并行）
2. 生成甘特图式调度计划
3. 标记关键路径与风险点

### Step 2: 实时追踪
1. 每个Agent开始/完成时输出TVP事件
2. 收集执行耗时、工具调用次数、记忆读写次数
3. 检测异常（超时、错误、重复调用）

### Step 3: 可视化输出
```
[TVP-Timeline] 任务: proj-001
06:14:23 🎯@天枢(tianshu)  START  plan
06:14:25 🔎@洞察(dongcha)  SWITCH 意图分析 (45ms)
06:14:28 🎯@天枢(tianshu)  SWITCH 方案评估 (12ms)
06:14:30 ✍️@妙笔(miaobi)   SWITCH 内容创作 (2.3s)
06:14:33 🔍@明镜(mingjing) SWITCH 质量审校 (1.1s)
06:14:35 🎯@天枢(tianshu)  END    总耗时 12s
```

### Step 4: 归档
1. 完整调度记录存入天机 L3 Episodic
2. 生成调度效率报告（Agent利用率、等待时间、瓶颈识别）

## 绑定Agent
@tianshu (主要) | @qianli (监控数据)

## 规范要求
- TVP格式：`[TVP] {emoji}@{name}({id}) → {action} | {detail}`
- 时间戳精确到毫秒
- 必须包含：Agent标识、动作类型、耗时、状态
- 违规标记：未声明切换高亮为 🔴
