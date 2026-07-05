# trae_conversation_capture 核心短板诊断报告

**诊断时间**: 2026-06-04
**问题**: trae_conversation_capture captured=0
**严重程度**: P0 - 核心功能缺失

---

## 一、问题现象

### 1.1 用户期望

- Trae IDE 每轮对话结束时自动触发捕获
- 对话内容自动写入 L0 Sensory 层
- 通过 LayerRouter 自动分发到 L1-L5
- 实现全量对话内容捕获，无需手动调用

### 1.2 实际情况

```
L0 Sensory 层状态:
- entry_count: 1648
- accumulated_entries: 1
- accumulation_ratio: 0.0003 (极低!)

最近L0条目:
- 全部为测试数据 "test fix-verification 2026"
- 无本次对话内容
- captured = 0
```

**结论**: trae_conversation_capture **未工作**，captured=0

---

## 二、根因分析

### 2.1 模块注册状态

**文件**: `modules/registry.json`

```json
"trae_conversation_capture": {
  "module_id": "trae_conversation_capture",
  "display_name": "Trae对话捕获",
  "version": "1.0.0",
  "import_path": "active_memory.trae_capture.TraeConversationCapture",
  "install_state": "installed",  // ✅ 已安装
  "activated_at": 0.0,           // ❌ 未激活！
}
```

**关键发现**:
- ✅ 模块已注册
- ✅ 模块已安装
- ❌ **模块未激活** (activated_at = 0.0)

### 2.2 模块实现检查

**文件**: `active_memory/trae_capture.py`

```python
class TraeConversationCapture:
    """
    Trae对话全量捕获器

    职责:
    1. 捕获完整对话内容（不限长度）
    2. 提取涉及文件的摘要（保留≥40%内容）
    3. 写入L0 Sensory层（原始快照）
    4. 通过LayerRouter分发到L1-L5
    """

    def capture_conversation_turn(
        self,
        user_input: str,
        ai_response: str,
        session_id: str,
        ...
    ) -> Dict[str, Any]:
        """捕获一轮对话 — 核心入口"""
```

**检查结果**:
- ✅ 类实现完整
- ✅ 核心方法存在
- ✅ 导入路径正确

### 2.3 API调用链路检查

**文件**: `server/api/active_routes.py`

```python
# 第194-203行
container = get_container()
if container:
    cap_mod = container._modules.get("trae_conversation_capture")
    if cap_mod and cap_mod.instance:
        cap_mod.instance.capture_now(
            {
                "content": request.user_input,
                "agent": request.agent_id,
                "role": "user",
                "conversation_id": request.conversation_id,
            }
        )
```

**问题**:
- ❌ `cap_mod` 为 None (模块未激活)
- ❌ `cap_mod.instance` 不存在
- ❌ `capture_now()` 未被调用

---

## 三、根本原因

### 3.1 激活失败原因推测

**可能原因**:

1. **容器启动时未激活模块**
   - 容器启动时只激活了部分核心模块
   - trae_conversation_capture 未在激活列表中

2. **模块依赖未满足**
   - 可能依赖 engine 或 layer_router
   - 依赖未注入导致激活失败

3. **激活逻辑缺失**
   - registry.json 中 install_state="installed"
   - 但没有自动激活逻辑

### 3.2 对比其他模块

**已激活模块** (activated_at > 0):
```json
"engine": {
  "install_state": "activated",
  "activated_at": 1780581239.2620497  // ✅ 已激活
}

"intelligent_scheduler": {
  "install_state": "activated",
  "activated_at": 1780581238.9469903  // ✅ 已激活
}

"learning_loop": {
  "install_state": "activated",
  "activated_at": 1780581238.948649  // ✅ 已激活
}
```

**未激活模块** (activated_at = 0):
```json
"trae_conversation_capture": {
  "install_state": "installed",  // 仅安装
  "activated_at": 0.0  // ❌ 未激活
}

"enforcement_hook": {
  "install_state": "installed",
  "activated_at": 0.0  // ❌ 未激活
}

"tvp_bridge": {
  "install_state": "installed",
  "activated_at": 0.0  // ❌ 未激活
}
```

**结论**: 容器启动时**选择性激活**模块，trae_conversation_capture 未被选中

---

## 四、解决方案

### 4.1 方案A: 修改 registry.json (推荐)

**步骤**:

1. 修改 `modules/registry.json`:

```json
"trae_conversation_capture": {
  "install_state": "activated",  // 改为 activated
  "activated_at": 1780581240.0   // 设置激活时间
}
```

2. 重启天机服务

**优点**: 简单直接，立即生效
**缺点**: 需要重启服务

### 4.2 方案B: 运行时激活

**步骤**:

```python
# 通过 API 或脚本激活模块
container = get_container()
container.activate_module("trae_conversation_capture")
```

**优点**: 无需重启
**缺点**: 需要实现激活API

### 4.3 方案C: 修改容器启动逻辑

**步骤**:

1. 修改容器启动代码，自动激活所有 "installed" 模块

```python
# core/container/core.py
def start(self):
    # 激活所有已安装模块
    for module_id, module in self._modules.items():
        if module.install_state == "installed":
            self.activate_module(module_id)
```

**优点**: 一劳永逸，所有模块自动激活
**缺点**: 可能激活不必要的模块

### 4.4 方案D: 实现自动激活装饰器

**步骤**:

```python
# active_memory/trae_capture.py
@auto_activate  # 自动激活装饰器
class TraeConversationCapture:
    ...
```

**优点**: 模块自声明激活需求
**缺点**: 需要实现装饰器机制

---

## 五、推荐方案

**推荐**: **方案A + 方案C 组合**

1. **立即修复**: 修改 registry.json，设置 install_state="activated"
2. **长期修复**: 修改容器启动逻辑，自动激活核心模块

**实施步骤**:

```bash
# 1. 修改 registry.json
# 将 trae_conversation_capture 的 install_state 改为 "activated"
# 将 activated_at 改为当前时间戳

# 2. 重启天机服务
python tianji_service.py restart

# 3. 验证激活状态
curl http://127.0.0.1:8771/api/health
# 检查 trae_conversation_capture 是否激活

# 4. 测试捕获功能
# 发起一次对话，检查 L0 Sensory 层是否有新条目
```

---

## 六、验证清单

### 6.1 激活验证

- [ ] registry.json 中 install_state = "activated"
- [ ] registry.json 中 activated_at > 0
- [ ] 容器 _modules 中存在 trae_conversation_capture
- [ ] cap_mod.instance 不为 None
- [ ] cap_mod.instance.capture_now 方法可调用

### 6.2 功能验证

- [ ] 发起对话后 L0 Sensory 层有新条目
- [ ] 条目内容包含对话全文
- [ ] 条目 metadata 包含 session_id, agent_id
- [ ] accumulated_entries 增加
- [ ] accumulation_ratio 提升

### 6.3 性能验证

- [ ] 捕获延迟 < 100ms
- [ ] 不影响对话响应速度
- [ ] 内存占用正常
- [ ] 无错误日志

---

## 七、影响评估

### 7.1 当前影响

- ❌ 所有 Trae 对话未自动捕获
- ❌ L0 Sensory 层数据缺失
- ❌ 记忆完整性受损
- ❌ 无法追溯对话历史

### 7.2 修复后收益

- ✅ 100% 对话自动捕获
- ✅ L0 Sensory 层数据完整
- ✅ 记忆完整性提升
- ✅ 可追溯所有对话历史
- ✅ 支持对话回放、分析、挖掘

---

## 八、相关模块

### 8.1 同样未激活的模块

| 模块 | 说明 | 影响 |
|------|------|------|
| trae_conversation_capture | Trae对话捕获 | P0 |
| enforcement_hook | 强制记录钩子 | P1 |
| tvp_bridge | TVP协议桥接 | P1 |
| workflow_engine | 工作流引擎 | P2 |
| message_gateway | 消息网关 | P2 |
| evolution_engine | 进化引擎 | P2 |

**建议**: 一并激活所有核心模块

### 8.2 依赖关系

```
trae_conversation_capture
├── engine (ICME核心引擎) - 已激活 ✅
├── layer_router (层级路由器) - 未激活 ❌
└── quality_gate (质量门禁) - 未激活 ❌
```

**建议**: 激活 trae_conversation_capture 前，先激活其依赖

---

## 九、总结

**问题**: trae_conversation_capture 模块未激活，导致所有 Trae 对话未自动捕获

**根因**: 容器启动时选择性激活模块，trae_conversation_capture 未在激活列表中

**解决**: 修改 registry.json 设置 install_state="activated"，重启服务

**优先级**: P0 - 核心功能缺失，影响记忆完整性

**预计修复时间**: 5分钟 (修改配置 + 重启)

---

**诊断人**: @鉴衡
**诊断时间**: 2026-06-04