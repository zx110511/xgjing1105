# 任务分发 (agent/dispatch)

## 目的
根据任务特征智能选择最优Agent，执行TVP透明调度。

## 触发场景
- 用户提交复杂任务需要多Agent协作
- @tianshu 需要进行子任务分解与分配
- 系统自动化流水线需要Agent路由

## 执行步骤

### Step 1: 任务解析
1. 使用 `context_extract` 分析用户意图
2. 评估复杂度 (low/medium/high/critical)
3. 识别所需能力维度

### Step 2: Agent匹配
1. 查询 AMIM Agent能力矩阵
2. 计算匹配得分：keyword_match(40) + intent_match(30) + domain_priority(15) + context_relevance(20) + complexity_fit(10)
3. 排除不可用Agent（健康检查失败/并发满载）

### Step 3: TVP声明与执行
1. 输出 `[TVP] @tianshu → @{target}` 声明
2. 传递上下文摘要（≤50字）+ 任务类型 + 优先级
3. 监控执行状态，超时自动降级到fallback_agent

### Step 4: 结果聚合
1. 收集子Agent执行结果
2. 去重、冲突检测、优先级合并
3. 生成综合报告并记录到L3 Episodic

## 降级策略
- 主Agent不可用 → 按fallback_chain顺序尝试
- 全部不可用 → 降级为本地规则处理 + 记录异常

## 绑定Agent
@tianshu (主要)

## 强制规则
- 每次切换必须TVP声明
- 禁止越级调用（参考权限矩阵）
- 复杂任务必须经过6步决策流水线
