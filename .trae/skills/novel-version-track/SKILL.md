# 版本追踪 (novel/version-track)

## 目的
追踪和管理小说设定的版本变更，确保设定一致性和可追溯性。

## 触发场景
- 设定发生修改/扩展时
- @version-keeper Agent被调度时
- 需要回溯某个时间点的设定状态时

## 追踪对象

### 1. 世界观设定基线
- 力量体系规则变更
- 世界架构调整
- 历史/传说修订

### 2. 人物角色卡
- 新增人物
- 人物属性修改
- 人物关系变化

### 3. 力量体系细节
- 能力等级定义更新
- 技能/招式增删
- 限制条件调整

### 4. 章节内容变更
- 正文修改记录
- 情节走向调整
- 删除/重写标记

## 执行流程

### Step 1: 变更检测
1. 对比当前版本与上一版本
2. 识别差异点 (diff)
3. 分类变更类型:
   - 🆕 **新增** (Addition)
   - ✏️ **修改** (Modification)
   - ❌ **删除** (Deletion)
   - 🔀 **重构** (Restructure)

### Step 2: 变更记录
```json
{
  "version_id": "v{major}.{minor}.{patch}",
  "timestamp": "ISO8601",
  "author_agent": "@{agent_name}",
  "change_category": "worldbuilding|character|power_system|chapter",
  "changes": [
    {
      "type": "modification",
      "target": "{具体设定项}",
      "old_value": "...",
      "new_value": "...",
      "reason": "{变更原因}",
      "impact_assessment": {
        "affected_chapters": ["第X章", "第Y章"],
        "affected_agents": ["@writer", "@reviewer"],
        "consistency_risk": "low|medium|high"
      }
    }
  ],
  "baseline_checksum": "hash_value"
}
```

### Step 3: 影响分析
1. 识别受影响的章节和情节
2. 评估一致性风险等级
3. 生成需通知的Agent列表
4. 标记需要回溯修改的内容

### Step 4: 存储与通知
1. 调用 `memory_remember` 存储到 episodic 层
2. 更新semantic层的基线引用
3. 向相关Agent发送变更通知
4. 更新版本索引

## 版本号规范
- **主版本 (Major)**: 重大架构变更/推翻重写
- **次版本 (Minor)**: 重要功能新增/重要设定修改
- **修订版 (Patch)**: 小修正/错别字/表述优化

示例: v2.1.3 → 第2大版, 第1次重要更新, 第3次小修复

## 回溯能力
支持查询任意历史版本的设定状态:
```
memory_recall(query="设定基线 version:v2.0.0")
→ 返回v2.0.0时刻的完整快照
```

## 绑定Agent
@version-keeper (主要) | @memory-architect (存储)

## 协作伙伴
@planner (发起变更) | @reviewer (一致性检查) | @writer (应用新设定)

## 安全机制
- ⚠️ 高风险变更(high consistency_risk)需@editor确认
- ⚠️ 已被多章节引用的设定修改需特别谨慎
- ✅ 所有变更可回溯，支持rollback到任意版本
- ✅ 自动生成变更日志供审计
