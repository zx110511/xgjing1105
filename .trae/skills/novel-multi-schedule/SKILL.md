# 多小说并行调度 (novel/multi-schedule)

## 目的
协调多个小说项目的并行创作进度，管理资源分配与优先级冲突。

## 触发场景
- 用户同时推进多部小说作品
- 需要跨项目统一世界观或角色设定
- 资源（时间、Agent算力）冲突需要仲裁

## 执行步骤

### Step 1: 项目扫描
1. 检索天机 L4 中所有 `novel:project:*` 标签的记忆
2. 汇总各项目当前进度、最近更新、阻塞项

### Step 2: 优先级评估
1. 根据用户设定的截止日期计算紧急度
2. 根据项目规模计算所需Agent资源
3. 识别跨项目依赖（共享世界观、角色联动）

### Step 3: 调度编排
1. 为每个项目分配创作时间窗口
2. 协调共享资源（如世界观设定需先由@jingwei完成）
3. 生成周/日级别的创作计划

## 输出格式
```json
{
  "schedule_id": "sch-{timestamp}",
  "projects": [
    {
      "project_id": "proj-001",
      "name": "小说A",
      "priority": 1,
      "assigned_slots": ["周一上午", "周三全天"],
      "next_milestone": "第15章完稿",
      "blocking": null
    }
  ],
  "shared_resources": [
    {"resource": "世界观设定V3", "owner": "proj-001", "consumers": ["proj-002"]}
  ]
}
```

## 绑定Agent
@tianshu (主要) | @wenzong (进度统筹)

## 协作伙伴
@jingwei (架构) | @miaobi (创作) | @shiguan (版本)
