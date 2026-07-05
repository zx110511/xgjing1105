# 章节创作 (novel/chapter-create)

## 目的
基于世界观设定和前文内容，创作指定章节的完整正文。

## 触发场景
- 用户要求"创作第X章"、"写章节正文"、"生成章节内容"
- @writer Agent被调度执行创作任务时
- 进入工业化生产流水线的"创作"阶段

## 执行步骤

### Step 1: 准备工作 (必须完成)
1. 调用 `memory_recall` 查询:
   - `{chapter_number}章相关内容`
   - `前文章节摘要`
   - `最近创作记录`
2. 调用 `memory_recall` 加载:
   - `世界观设定` + `力量体系`
   - `{character_names} 人物设定`

### Step 2: 内容创作
1. 确认章节编号和标题（如未提供则自动生成）
2. 遵循写作风格指南（默认: 科幻悬疑）
3. 应用叙事视角（默认: 第三人称有限）
4. 控制字数在目标范围内（默认: 5000字）

### Step 3: 质量检查
1. 自检: 与前文衔接是否自然
2. 自检: 人物行为是否符合角色卡设定
3. 自检: 世界观元素是否一致

### Step 4: 记忆存储
1. 调用 `memory_remember` 存储新章节到 episodic 层
2. 更新章节摘要到 semantic 层
3. 标记版本信息

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| chapter_number | integer | ✅ | - | 章节编号 |
| chapter_title | string | ❌ | 自动生成 | 章节标题 |
| word_count | integer | ❌ | 5000 | 目标字数 |
| style | enum | ❌ | 科幻悬疑 | 写作风格 |
| pov | enum | ❌ | 第三人称有限 | 叙事视角 |
| characters | array | ❌ | 自动检测 | 出场人物列表 |

## 输出格式
```markdown
# 第{chapter_number}章 {chapter_title}

[正文内容...]

---
*本章字数: {actual_word_count} | 版本: v{version} | 创作时间: {timestamp}*
```

## 绑定Agent
@writer (写手)

## 协作伙伴
@planner (大纲参考) | @reviewer (审校) | @memory-architect (存储)
