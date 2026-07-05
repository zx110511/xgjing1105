# 天机对话捕获集成指南 (Trae + Qoder)

**版本**: v1.0.0
**日期**: 2026-06-05
**作者**: @灵犀
**目标**: 实现Trae/Qoder IDE对话自动捕获，确保100%对话录入天机记忆系统

---

## 一、集成概述

### 1.1 目标

将天机对话捕获钩子集成到Trae/Qoder IDE，实现：
- ✅ 每次对话结束自动触发捕获
- ✅ 用户输入、AI回复、MCP调用、文件操作全量记录
- ✅ 三层存储：L0 Sensory + L1 Working + L3 Episodic
- ✅ 平台标识区分：trae/qoder
- ✅ 失败容错：不影响IDE正常使用

### 1.2 集成架构

```
┌─────────────────────────────────────────────────────────┐
│                   IDE集成架构                            │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Trae IDE                    Qoder IDE                    │
│      │                           │                        │
│      │  用户发送消息              │  用户发送消息           │
│      │       ↓                   │       ↓                │
│      │  AI生成回复                │  AI生成回复             │
│      │       ↓                   │       ↓                │
│      │  对话结束事件              │  对话结束事件           │
│      │       ↓                   │       ↓                │
│      └───┬───────────────────────┘                       │
│          │                                               │
│          ▼                                               │
│   on_conversation_end()                                  │
│          │                                               │
│          ├─ 收集对话数据                                  │
│          │  - user_input                                 │
│          │  - ai_response                                │
│          │  - mcp_calls                                  │
│          │  - file_operations                            │
│          │                                               │
│          ├─ 调用天机API                                   │
│          │  POST /api/active/capture_conversation        │
│          │                                               │
│          └─ 返回结果                                      │
│             success: true/false                          │
│             turn_id: xxx                                 │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## 二、Trae IDE集成方案

### 2.1 集成位置

**推荐集成点**: Trae IDE的对话完成处理函数

**可能的位置**:
- `src/conversation/ConversationManager.ts` (TypeScript)
- `src/chat/ChatService.ts` (TypeScript)
- `src/ai/AIResponseHandler.ts` (TypeScript)

### 2.2 集成代码 (TypeScript)

```typescript
// src/integration/TianjiCapture.ts

import axios from 'axios';

/**
 * 天机对话捕获集成
 */
export class TianjiCapture {
  private apiBaseUrl: string;
  private platform: string = 'trae';
  private enabled: boolean = true;

  constructor(apiBaseUrl: string = 'http://127.0.0.1:8771') {
    this.apiBaseUrl = apiBaseUrl;
  }

  /**
   * 对话结束钩子 — 在每次对话完成时调用
   */
  async onConversationEnd(context: ConversationContext): Promise<CaptureResult> {
    if (!this.enabled) {
      return { success: false, reason: 'disabled' };
    }

    try {
      // 1. 构造捕获请求
      const payload = {
        user_input: context.userInput,
        ai_response: context.aiResponse,
        agent_id: context.agentId || 'lingxi',
        conversation_id: context.conversationId,
        session_id: context.sessionId,
        platform: this.platform,
        mcp_calls: this.extractMcpCalls(context),
        file_operations: this.extractFileOperations(context),
        tags: ['auto-capture', 'trae', ...context.tags],
      };

      // 2. 调用天机API
      const response = await axios.post(
        `${this.apiBaseUrl}/api/active/capture_conversation`,
        payload,
        { timeout: 5000 }
      );

      // 3. 处理响应
      if (response.data.success) {
        console.log(`[天机] ✅ 对话已捕获: turn_id=${response.data.turn_id}`);
        return {
          success: true,
          turn_id: response.data.turn_id,
          captured_layers: response.data.captured_layers,
        };
      } else {
        console.error('[天机] ❌ 捕获失败:', response.data);
        return { success: false, reason: 'api_error' };
      }

    } catch (error) {
      // 4. 容错处理 — 不影响IDE正常使用
      console.error('[天机] ❌ 捕获异常:', error);
      return { success: false, reason: 'exception', error: error.message };
    }
  }

  /**
   * 提取MCP调用记录
   */
  private extractMcpCalls(context: ConversationContext): McpCall[] {
    const mcpCalls: McpCall[] = [];

    // 从上下文中提取MCP调用
    if (context.toolCalls && Array.isArray(context.toolCalls)) {
      for (const call of context.toolCalls) {
        mcpCalls.push({
          tool_name: call.name || call.toolName,
          arguments: call.arguments || call.args,
          result: call.result,
          timestamp: call.timestamp || Date.now(),
        });
      }
    }

    return mcpCalls;
  }

  /**
   * 提取文件操作记录
   */
  private extractFileOperations(context: ConversationContext): FileOperation[] {
    const fileOps: FileOperation[] = [];

    // 从上下文中提取文件操作
    if (context.fileOperations && Array.isArray(context.fileOperations)) {
      for (const op of context.fileOperations) {
        fileOps.push({
          operation: op.type || op.operation, // read/write/edit/delete
          path: op.path || op.filePath,
          content_preview: op.content ? op.content.substring(0, 200) : undefined,
          timestamp: op.timestamp || Date.now(),
        });
      }
    }

    return fileOps;
  }

  /**
   * 启用/禁用捕获
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    console.log(`[天机] 捕获${enabled ? '已启用' : '已禁用'}`);
  }

  /**
   * 健康检查
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await axios.get(
        `${this.apiBaseUrl}/api/active/capture_health`,
        { timeout: 3000 }
      );
      return response.data.status === 'healthy';
    } catch (error) {
      return false;
    }
  }
}

// 类型定义
interface ConversationContext {
  userInput: string;
  aiResponse: string;
  agentId?: string;
  conversationId?: string;
  sessionId: string;
  tags?: string[];
  toolCalls?: any[];
  fileOperations?: any[];
}

interface McpCall {
  tool_name: string;
  arguments?: any;
  result?: any;
  timestamp: number;
}

interface FileOperation {
  operation: string;
  path: string;
  content_preview?: string;
  timestamp: number;
}

interface CaptureResult {
  success: boolean;
  turn_id?: string;
  captured_layers?: string[];
  reason?: string;
  error?: string;
}
```

### 2.3 集成到Trae对话流程

```typescript
// src/conversation/ConversationManager.ts

import { TianjiCapture } from '../integration/TianjiCapture';

export class ConversationManager {
  private tianjiCapture: TianjiCapture;

  constructor() {
    // 初始化天机捕获
    this.tianjiCapture = new TianjiCapture('http://127.0.0.1:8771');
  }

  /**
   * 处理用户消息
   */
  async handleUserMessage(userInput: string): Promise<string> {
    // 1. 生成AI回复
    const aiResponse = await this.generateAIResponse(userInput);

    // 2. 对话结束 — 触发天机捕获
    await this.onConversationComplete(userInput, aiResponse);

    // 3. 返回回复
    return aiResponse;
  }

  /**
   * 对话完成处理
   */
  private async onConversationComplete(
    userInput: string,
    aiResponse: string
  ): Promise<void> {
    // 构造对话上下文
    const context = {
      userInput,
      aiResponse,
      sessionId: this.currentSessionId,
      conversationId: this.currentConversationId,
      agentId: this.currentAgentId,
      toolCalls: this.getToolCallHistory(),
      fileOperations: this.getFileOperationHistory(),
      tags: [],
    };

    // 触发天机捕获（异步，不阻塞）
    this.tianjiCapture.onConversationEnd(context)
      .catch(err => {
        // 容错：捕获失败不影响IDE使用
        console.error('[Trae] 天机捕获失败:', err);
      });
  }

  // 其他方法...
}
```

### 2.4 配置选项

```typescript
// src/config/tianji.config.ts

export const tianjiConfig = {
  // API地址
  apiBaseUrl: 'http://127.0.0.1:8771',

  // 平台标识
  platform: 'trae',

  // 是否启用捕获
  enabled: true,

  // 捕获选项
  captureOptions: {
    // 最大内容长度
    maxContentLength: 10000,

    // 是否包含MCP调用
    includeMcpCalls: true,

    // 是否包含文件操作
    includeFileOps: true,

    // 超时时间(ms)
    timeout: 5000,
  },

  // 容错选项
  fallbackOptions: {
    // 失败时是否重试
    retryOnFailure: true,

    // 重试次数
    maxRetries: 2,

    // 重试间隔(ms)
    retryInterval: 1000,
  },
};
```

---

## 三、Qoder IDE集成方案

### 3.1 集成位置

**推荐集成点**: Qoder IDE的对话完成处理函数

**可能的位置**:
- `src/dialog/DialogManager.ts` (TypeScript)
- `src/chat/ChatHandler.ts` (TypeScript)
- `src/agent/AgentResponseHandler.ts` (TypeScript)

### 3.2 集成代码 (TypeScript)

```typescript
// src/integration/TianjiCapture.ts (Qoder版本)

import axios from 'axios';

export class TianjiCapture {
  private apiBaseUrl: string;
  private platform: string = 'qoder';  // Qoder平台标识
  private enabled: boolean = true;

  constructor(apiBaseUrl: string = 'http://127.0.0.1:8771') {
    this.apiBaseUrl = apiBaseUrl;
  }

  /**
   * 对话结束钩子
   */
  async onConversationEnd(context: DialogContext): Promise<CaptureResult> {
    if (!this.enabled) {
      return { success: false, reason: 'disabled' };
    }

    try {
      const payload = {
        user_input: context.userMessage,
        ai_response: context.agentResponse,
        agent_id: context.agentId || 'tianshu',  // Qoder默认使用@tianshu
        conversation_id: context.dialogId,
        session_id: context.sessionId,
        platform: this.platform,
        mcp_calls: this.collectMcpCalls(context),
        file_operations: this.collectFileOps(context),
        tags: ['auto-capture', 'qoder', ...context.tags],
      };

      const response = await axios.post(
        `${this.apiBaseUrl}/api/active/capture_conversation`,
        payload,
        { timeout: 5000 }
      );

      if (response.data.success) {
        console.log(`[天机] ✅ Qoder对话已捕获: turn_id=${response.data.turn_id}`);
        return {
          success: true,
          turn_id: response.data.turn_id,
          captured_layers: response.data.captured_layers,
        };
      } else {
        return { success: false, reason: 'api_error' };
      }

    } catch (error) {
      console.error('[天机] ❌ Qoder捕获异常:', error);
      return { success: false, reason: 'exception', error: error.message };
    }
  }

  // 其他方法与Trae版本类似...
}

// Qoder特定的上下文类型
interface DialogContext {
  userMessage: string;
  agentResponse: string;
  agentId?: string;
  dialogId?: string;
  sessionId: string;
  tags?: string[];
  toolInvocations?: any[];
  fileChanges?: any[];
}
```

### 3.3 集成到Qoder对话流程

```typescript
// src/dialog/DialogManager.ts

import { TianjiCapture } from '../integration/TianjiCapture';

export class DialogManager {
  private tianjiCapture: TianjiCapture;

  constructor() {
    this.tianjiCapture = new TianjiCapture('http://127.0.0.1:8771');
  }

  /**
   * 处理用户消息
   */
  async processUserMessage(message: string): Promise<string> {
    // 1. Agent生成响应
    const response = await this.agent.generateResponse(message);

    // 2. 对话完成 — 触发天机捕获
    await this.onDialogComplete(message, response);

    // 3. 返回响应
    return response;
  }

  /**
   * 对话完成处理
   */
  private async onDialogComplete(
    userMessage: string,
    agentResponse: string
  ): Promise<void> {
    const context = {
      userMessage,
      agentResponse,
      sessionId: this.session.id,
      dialogId: this.dialog?.id,
      agentId: this.agent.id,
      toolInvocations: this.getToolInvocations(),
      fileChanges: this.getFileChanges(),
      tags: [],
    };

    // 异步触发捕获
    this.tianjiCapture.onConversationEnd(context)
      .catch(err => console.error('[Qoder] 天机捕获失败:', err));
  }
}
```

---

## 四、测试验证

### 4.1 本地测试脚本

```python
# test_ide_integration.py

import requests
import time

def test_capture_conversation():
    """测试对话捕获API"""

    payload = {
        "user_input": "这是一条测试消息，来自IDE集成测试",
        "ai_response": "这是AI的测试回复，验证集成是否正常",
        "agent_id": "lingxi",
        "session_id": "test-session-ide-001",
        "platform": "trae",
        "mcp_calls": [
            {
                "tool_name": "memory_recall",
                "arguments": {"query": "测试"},
                "result": "找到3条记录",
                "timestamp": time.time()
            }
        ],
        "file_operations": [
            {
                "operation": "write",
                "path": "/test/file.txt",
                "content_preview": "测试内容",
                "timestamp": time.time()
            }
        ],
        "tags": ["test", "ide-integration"]
    }

    response = requests.post(
        "http://127.0.0.1:8771/api/active/capture_conversation",
        json=payload,
        timeout=5
    )

    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")

    if response.json().get("success"):
        print("✅ 对话捕获成功")
    else:
        print("❌ 对话捕获失败")

def test_capture_stats():
    """测试捕获统计API"""

    response = requests.get(
        "http://127.0.0.1:8771/api/active/capture_stats",
        timeout=5
    )

    print(f"捕获统计: {response.json()}")

def test_capture_health():
    """测试捕获健康检查API"""

    response = requests.get(
        "http://127.0.0.1:8771/api/active/capture_health",
        timeout=5
    )

    print(f"健康检查: {response.json()}")

if __name__ == "__main__":
    print("=" * 60)
    print("测试1: 对话捕获")
    print("=" * 60)
    test_capture_conversation()

    print("\n" + "=" * 60)
    print("测试2: 捕获统计")
    print("=" * 60)
    test_capture_stats()

    print("\n" + "=" * 60)
    print("测试3: 健康检查")
    print("=" * 60)
    test_capture_health()
```

### 4.2 验证步骤

**步骤1**: 启动天机服务
```bash
cd D:\元初系统\天机v9.1
python server/main.py
```

**步骤2**: 运行测试脚本
```bash
python test_ide_integration.py
```

**步骤3**: 检查数据库
```bash
python scripts/check_actual_db.py
```

**步骤4**: 验证监控端点
```bash
curl http://127.0.0.1:8771/api/active/capture_stats
curl http://127.0.0.1:8771/api/active/capture_health
```

---

## 五、监控与运维

### 5.1 监控端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/active/capture_stats` | GET | 捕获统计（总数、按平台、按层级） |
| `/api/active/capture_health` | GET | 健康检查（钩子、存储、最近捕获） |
| `/api/active/capture_conversation` | POST | 对话捕获（主入口） |

### 5.2 监控指标

```json
{
  "total_captured": 1250,
  "by_platform": {
    "trae": 800,
    "qoder": 450
  },
  "by_layer": {
    "sensory": 1250,
    "working": 1250,
    "episodic": 1250
  },
  "capture_rate": 0.95,
  "recent_captures": [...]
}
```

### 5.3 告警规则

- **捕获率 < 0.8**: 警告 — 部分对话未捕获
- **捕获率 < 0.5**: 严重 — 捕获系统异常
- **最近1小时无捕获**: 警告 — 可能IDE未集成或服务异常

---

## 六、故障排查

### 6.1 常见问题

**问题1**: 对话未捕获

**排查**:
1. 检查天机服务是否运行: `curl http://127.0.0.1:8771/api/health`
2. 检查IDE集成是否启用: 查看IDE配置
3. 检查钩子是否注册: `curl http://127.0.0.1:8771/api/active/capture_health`
4. 检查日志: `tail -f logs/server.log | grep capture`

**问题2**: 捕获失败但不报错

**排查**:
1. 检查API响应: 查看IDE控制台日志
2. 检查网络连接: ping 127.0.0.1
3. 检查超时设置: 增加timeout值

**问题3**: 数据库无记录

**排查**:
1. 检查数据库路径: `D:\元初系统\天机v9.1\data\.memory\icme.db`
2. 检查表结构: `sqlite3 icme.db ".schema memories"`
3. 检查存储引擎: 查看server.log中的存储日志

### 6.2 日志查看

```bash
# 查看捕获日志
grep "capture_conversation" logs/server.log

# 查看错误日志
grep "ERROR" logs/server.log | grep "capture"

# 查看最近捕获
tail -100 logs/server.log | grep "turn_id"
```

---

## 七、性能优化

### 7.1 异步捕获

**推荐**: 使用异步方式触发捕获，不阻塞IDE主流程

```typescript
// 异步触发（推荐）
this.tianjiCapture.onConversationEnd(context)
  .catch(err => console.error(err));

// 同步等待（不推荐）
await this.tianjiCapture.onConversationEnd(context);
```

### 7.2 批量捕获

**场景**: 大量对话需要捕获时

```typescript
// 批量捕获
const conversations = [...]; // 多个对话
await this.tianjiCapture.batchCapture(conversations);
```

### 7.3 内容压缩

**场景**: 内容过长时自动压缩

```typescript
// 自动截断
const maxLen = this.config.maxContentLength;
const compressed = content.substring(0, maxLen);
```

---

## 八、安全考虑

### 8.1 敏感信息过滤

```typescript
// 过滤敏感信息
function sanitizeContent(content: string): string {
  // 过滤密码
  content = content.replace(/password["\s:=]+["']?[^"'\s]+/gi, 'password=***');

  // 过滤token
  content = content.replace(/token["\s:=]+["']?[^"'\s]+/gi, 'token=***');

  // 过滤API密钥
  content = content.replace(/api[_-]?key["\s:=]+["']?[^"'\s]+/gi, 'api_key=***');

  return content;
}
```

### 8.2 访问控制

```typescript
// 检查权限
if (!this.hasCapturePermission()) {
  return { success: false, reason: 'unauthorized' };
}
```

---

## 九、总结

### 9.1 集成清单

- [x] 创建天机捕获类 (TianjiCapture.ts)
- [x] 集成到对话结束事件
- [x] 配置平台标识 (trae/qoder)
- [x] 实现容错机制
- [x] 添加监控端点
- [x] 编写测试脚本
- [x] 编写故障排查指南

### 9.2 下一步

1. **Trae开发团队**: 将TianjiCapture集成到Trae IDE对话流程
2. **Qoder开发团队**: 将TianjiCapture集成到Qoder IDE对话流程
3. **测试验证**: 运行测试脚本验证集成效果
4. **监控上线**: 启用监控端点，持续观察捕获率

---

**文档版本**: v1.0.0
**最后更新**: 2026-06-05
**维护者**: @灵犀
