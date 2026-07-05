---
name: tianji-remember
description: 向天机记忆系统写入新记忆
category: 天机记忆
---

# /tianji-remember - 天机记忆写入

将内容写入天机ICME六层记忆系统。

## 输入参数
- `content` (必填): 要写入的内容
- `layer` (推荐): 目标层级，自动调用 `tianji_classify` 智能推荐
- `tags` (可选): 标签列表

## 执行步骤
1. 调用 `tianji_classify` 分析内容推荐层级和标签
2. 调用 `tianji_auto_tag` 自动生成标签
3. 调用 `tianji_intercept` 注入上下文
4. 调用 `memory_remember` 写入记忆
5. 返回记忆ID和gate_verdict

## TVP声明
[TVP]#system→@yiku | [OPS]#memory_write
