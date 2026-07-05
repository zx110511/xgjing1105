---
name: memory-file-capture
description: "Write/SearchReplace/Bash文件操作后自动捕获生成的文件内容到天机v9.1记忆系统，支持去重和智能分层。"
---

# 文件内容记录 (Memory File Capture) — 天机v9.1

## 目的
解决"对话生成的文件内容未被记录"的核心缺失。在 Write/SearchReplace/Bash 创建或修改文件后，自动将文件关键信息记录到天机v9.1 ICME记忆系统。

## 触发场景
- Write 工具创建新文件后 (自动触发)
- SearchReplace 修改文件后 (自动触发)
- Bash 执行脚本生成文件后 (自动触发)
- 用户明确要求"记录此文件"、"保存文件到记忆"

## 执行步骤

### Step 1: 文件变更检测
1. 拦截 Write/SearchReplace/Bash 操作结果
2. 提取文件元数据:
   - 绝对路径 (file_path)
   - 操作类型 (create/modify)
   - 文件行数 (lines_count)
   - 编程语言 (从扩展名推断: .py→python, .ts→typescript, .md→markdown, etc.)
   - 内容哈希 (SHA256前16位hex, 用于去重)

### Step 2: 去重检查
1. 调用 `memory_recall` 查询同路径+同hash的历史记录
2. 如存在相同hash → 跳过记录, 仅更新 access_count
3. 如存在同路径不同hash → 作为新版本记录, 关联 parent_id

### Step 3: 内容摘要生成
1. 提取前200字作为 content_summary
2. 识别关键模式:
   - Python: class/def/import 声明
   - TypeScript: interface/type/function/import 声明
   - Markdown: # 标题层级
   - JSON/YAML: 顶层 key 列表
3. 生成结构化描述

### Step 4: 智能分层存储

根据文件类型自动选择目标层:

| 文件类型 | 目标层 | 标签 |
|----------|--------|------|
| .py / .ts / .tsx / .js | L3 Episodic | code, {language}, source |
| .json / .yaml / .toml / .env | L4 Semantic | config, settings |
| .md (技能/规则/智能体定义) | L4 Semantic | {type}, definition |
| .md (其他文档) | L3 Episodic | doc, markdown |
| test_*.py | L3 Episodic | test, verification |

### Step 5: 调用 memory_remember

```json
{
  "tool": "memory_remember",
  "arguments": {
    "content": "文件操作记录\n\n路径: {file_path}\n操作: {action}\n语言: {language}\n行数: {lines}\n哈希: {content_hash}\n\n内容摘要:\n{content_summary}\n\n触发消息: {trigger_message}",
    "layer": "{target_layer}",
    "tags": ["file:generated", "{language}", "action:{action}", "session:{id}"],
    "priority": "medium"
  }
}
```

### Step 6: 关联建立
1. 将文件记录与触发消息建立 parent_id 关联
2. 如是修改操作, 关联 previous_version_id
3. 写入 L1 Working 层: `file_count:{session_id}` 计数器

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| file_path | string | 是 | - | 文件绝对路径 |
| action | enum | 是 | - | create / modify |
| content_summary | string | 否 | 自动生成 | 前200字摘要 |
| language | string | 否 | 自动推断 | 编程语言 |
| skip_dedup | boolean | 否 | false | 跳过去重检查 |

## 输出格式
```json
{
  "capture_id": "fc-{timestamp}",
  "file_path": "{绝对路径}",
  "action": "create",
  "entry_id": "{uuid}",
  "layer": "L3 Episodic",
  "dedup_result": "new|duplicate|new_version",
  "parent_message_id": "{触发消息entry_id}",
  "lines": 150,
  "language": "python",
  "content_hash": "a1b2c3d4e5f6g7h8"
}
```

## 绑定Agent
@yiku (主要) | @dongcha (文件分类)

## 协作伙伴
@memory-architect (存储) | @mingjing (审计)

## 去重规则
- 相同 path + 相同 hash → 跳过 (duplicate)
- 相同 path + 不同 hash → 新版本 (new_version, 关联parent_id)
- 不同 path → 正常记录 (new)

## 质量标准
- **文件记录率**: 100% (所有Write/SearchReplace/Bash文件操作)
- **去重准确率**: ≥99%
- **语言识别准确率**: ≥98%
- **最大延迟**: <500ms (异步非阻塞)

---

**版本**: 1.0.0 | **体系**: 天机v9.1 | **维护**: @yiku
