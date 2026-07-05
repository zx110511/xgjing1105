# dataclass字段验证规范

> 来源：Phase2集成审计中发现的"影子字段"Bug模式
> 日期：2026-05-24

---

## 问题背景

在Phase2集成开发过程中，多次出现以下模式：
```python
# 生成代码假设字段名
MethodSignature(
    name="foo",
    return_type="Any",  # ❌ 实际是 returns
    is_async=False,      # ❌ 不存在
    is_public=True,      # ❌ 不存在
    doc="说明"           # ❌ 实际是 description
)
```

这类Bug的根因是：**在未对照源文件的情况下，凭经验假设dataclass的字段名。**

---

## 规范1: 构造前必验证

### 步骤
1. 打开目标dataclass所在的源文件
2. 查看 `@dataclass` 下方所有字段定义
3. 逐一对照构造代码中的字段名
4. 特别关注：命名风格差异（camelCase vs snake_case，简写 vs 全写）

### 示例：TianjiModuleDefinition

```python
# 源文件定义
@dataclass
class TianjiModuleDefinition:
    module_id: str
    module_name: str
    display_name: str = ""
    module_version: str = "1.0.0"          # ✅ 是 module_version
    tier: ModuleTier = ModuleTier.CORE_ENGINE
    module_type: ModuleType = ModuleType.ENGINE
    domain: str = ""
    responsibility: str = ""                # ✅ 是 responsibility（单数），不是 description
    capabilities: List[str] = field(...)    # ✅ 是 capabilities，不是 responsibilities
    anti_responsibilities: List[str] = ...
    dependencies: List[ModuleDependency] = ...  # ✅ 对象列表，不是字符串列表
    public_api: List[MethodSignature] = ...
    events_published: List[EventDef] = ...  # ✅ 是 events_published
    events_subscribed: List[EventDef] = ...
    lifecycle_state: ModuleLifecycleState = ...
    # ... 还有更多字段
```

---

## 规范2: 枚举值必确认

### 步骤
1. 找到枚举类定义
2. 运行 `print([e.name for e in EnumClass])` 或直接查看类体
3. 确认每个枚举成员的确切名称
4. 不要凭英文语义猜测（如：`SELF_EVOLUTION` → `LEARNING_EVOLUTION`）

### 已知枚举陷阱

| 常见猜测 | 实际值 | 来源 |
|---------|--------|------|
| SELF_EVOLUTION | LEARNING_EVOLUTION | ModuleTier |
| DATA_PERSISTENCE | INFRASTRUCTURE_FOUNDATION | ModuleTier |
| EVOLUTION_LOOP | LOOP | ModuleType |
| STORAGE | REGISTRY | ModuleType |
| SERVICE | ORCHESTRATOR | ModuleType |

---

## 规范3: 私有API禁止假设

### 步骤
1. 查看类的公共方法列表：`[m for m in dir(obj) if not m.startswith('_')]`
2. 阅读公共方法的文档和签名
3. 通过公共API完成目标，不调用 `_` 开头的方法

### 已知陷阱
- ~~`StaticDependencyAnalyzer._create_import_visitor()`~~ → 不存在，使用 `analyze()` 公共方法
- ~~`StaticDependencyAnalyzer._build_dependency_graph()`~~ → 存在但内部方法，使用 `analyze()` 统一入口
- ~~`StaticDependencyAnalyzer._detect_circular_deps()`~~ → 不存在
- ~~`StaticDependencyAnalyzer._resolve_dep_layers()`~~ → 不存在

---

## 规范4: 审计脚本自动检测

在SSS审计脚本中应加入以下自动化检查：

```python
def validate_dataclass_fields(obj, expected_class):
    valid_fields = {f.name for f in fields(expected_class)}
    for key in obj.__dict__:
        if key not in valid_fields:
            raise AuditError(f"字段 '{key}' 在 {expected_class.__name__} 中不存在")

def validate_enum_values(value, expected_enum):
    valid_values = {e.name for e in expected_enum}
    if value.name not in valid_values:
        raise AuditError(f"枚举值 '{value.name}' 不在 {expected_enum.__name__} 中")
```

---

## 防御检查清单

在提交涉及dataclass构造的代码前：
- [ ] 已打开dataclass源文件确认所有字段名
- [ ] 所有枚举值已确认存在于枚举类中
- [ ] 没有调用任何未验证的 `_` 前缀私有方法
- [ ] `dependencies` 使用了对象列表（非字符串列表）
- [ ] 没有使用不存在的字段名
- [ ] 字段命名风格与源文件一致