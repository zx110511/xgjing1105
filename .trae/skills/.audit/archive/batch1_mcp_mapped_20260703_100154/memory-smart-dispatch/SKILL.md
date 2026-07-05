---
name: memory-smart-dispatch
description: "天机v9.1智能记忆调度引擎：对任意内容自动分类、推断目标ICME层、生成标签、判定优先级，取代手动指定layer的低效模式。"
---

# 记忆智能调度 (Memory Smart Dispatch) — 天机v9.1

## 目的
天机v9.1的智能路由核心：对任意待记录内容自动完成分类→层映射→标签生成→优先级推断，实现对ICME六层的精准分发。

## 触发场景
- auto-memory-capture 捕获用户消息后 (自动分类存储)
- memory-file-capture 捕获文件操作后 (自动判定L3/L4)
- 任何Agent调用 memory_remember 前 (推荐先经本Skill分类)
- 工具调用/错误发生后 (自动记录)

## 执行步骤

### Step 1: 内容分类

调用 `tianji_classify` 或本地规则引擎进行分类:

```
分类维度:
├─ 内容来源: user_input / file_output / tool_result / error / decision
├─ 内容性质: conversational / code / config / knowledge / meta
├─ 生命周期: transient(<1会话) / short(<1周) / persistent(永久)
└─ 影响范围: local(单文件) / module(多文件) / system(全局)
```

### Step 2: 层映射决策表

| 内容来源 | 内容性质 | 决策 → 目标层 |
|----------|----------|--------------|
| user_input | conversational | L0 Sensory |
| user_input | command/instruction | L1 Working |
| file_output | code (.py/.ts/.jsx) | L3 Episodic |
| file_output | config (.json/.yaml/.toml) | L4 Semantic |
| file_output | rule/skill/agent-def | L4 Semantic |
| file_output | test code | L3 Episodic |
| tool_result | mcp_call/shell | L1 Working |
| tool_result | performance/profile | L4 Semantic |
| error | exception/crash | L3 Episodic |
| error | timeout/degradation | L3 Episodic |
| decision | architecture/design | L5 Meta |
| decision | strategy/evolution | L5 Meta |

### Step 3: 标签自动生成

规则链:
1. 固定前缀: `src:{来源}` + `nature:{性质}`
2. 内容维度:
   - 代码: `lang:{python|typescript|...}`, `file:{path}`
   - 文档: `doc:{type}`, `section:{heading}`
   - 配置: `config:{domain}`, `env:{production|development}`
3. 会话关联: `session:{id}`, `task:{task_id}`
4. 调用 `tianji_auto_tag` 补充语义标签

### Step 4: 优先级推断

```
优先级决策:
├─ critical → 架构决策 / 安全事件 / 系统级变更
├─ high     → 重要代码生成 / 用户明确要求记住 / 错误异常
├─ medium   → 常规文件操作 / 工具调用 / 一般对话 (默认)
└─ low      → 临时缓存 / 中间结果 / 纯查询
```

### Step 5: 输出调度指令

```json
{
  "dispatch_id": "dsp-{timestamp}",
  "content_class": "{来源}+{性质}",
  "target_layer": "sensory|working|short_term|episodic|semantic|meta",
  "tags": ["src:user_input", "nature:conversational", "session:{id}"],
  "priority": "low|medium|high|critical",
  "confidence": 0.95,
  "reasoning": "用户原始输入 → L0 Sensory, 标签: auto-collected",
  "suggested_tool": "memory_remember",
  "suggested_args": {
    "content": "{original_content}",
    "layer": "{target_layer}",
    "tags": ["{tags}"],
    "priority": "{priority}"
  }
}
```

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| content | string | 是 | - | 待调度的内容原文 |
| source | enum | 否 | auto-detect | user_input/file_output/tool_result/error/decision |
| context_hint | object | 否 | {} | 附加上下文(file_path/language/tool_name) |

## 输出格式
- 标准输出: JSON 调度指令 (dispatch result)
- 精简输出: 仅 target_layer + tags + priority (inline使用)

## 绑定Agent
@dongcha (主要, 内容分类) | @yiku (辅助, 层映射验证)

## 协作伙伴
@tiansuan (分类模型训练数据) | @lingxi (对话上下文)

## 联动Skill
- **auto-memory-capture**: 消息捕获后 → 本Skill分类 → memory_remember 写入
- **memory-file-capture**: 文件操作后 → 本Skill判定L3/L4 → memory_remember 写入
- **memory-remember**: 任意写入前可先经本Skill获取最佳参数

## 优化路径
- 分类准确率通过 L5 Meta 层反馈持续优化
- 新文件类型/内容模式自动学习映射规则
- 错误分类记录到 L3 Episodic 供回顾分析

---

**版本**: 1.0.0 | **体系**: 天机v9.1 | **维护**: @dongcha + @yiku
