# 深度设定一致性检查 (novel/setting-consistency-deep)

## 目的
对小说世界观、角色、时间线进行深度跨卷一致性检查，识别隐形矛盾。

## 触发场景
- 长篇小说跨越50章以上
- 世界观设定复杂（多势力、多时间线）
- 发现疑似矛盾需要根因定位

## 执行步骤

### Step 1: 设定萃取
1. 从天机 L4 Semantic 层提取所有 `worldbuilding:*` 和 `character:*` 标签
2. 按类别归类：地理、历史、势力、角色能力、时间线

### Step 2: 关系图谱构建
1. 构建设定项之间的依赖关系图
2. 标记"高影响设定"（修改会连锁影响多处）

### Step 3: 矛盾检测
1. 时间线冲突：同一角色在同一时间出现在两个地点
2. 能力冲突：角色能力描述前后不一致
3. 规则冲突：世界观规则被违反
4. 情感冲突：角色关系跳跃缺乏过渡

### Step 4: 影响评估
1. 对每个矛盾标记修复难度
2. 生成最小化修改建议（改一处解决多处）

## 输出报告
```json
{
  "check_id": "csd-{timestamp}",
  "novel_id": "novel-001",
  "consistency_score": 87,
  "issues": [
    {
      "severity": "high",
      "type": "timeline_conflict",
      "location": "第32章 vs 第45章",
      "description": "角色林远同时在京城和江南",
      "suggested_fix": "将第45章事件延后3天"
    }
  ]
}
```

## 绑定Agent
@mingjing (主要) | @dongcha (上下文分析)

## 协作伙伴
@yiku (记忆检索) | @tiansuan (数据统计)
