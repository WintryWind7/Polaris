# Hook 系统使用指南

## 概述

Hook 系统提供了一种声明式的方式来扩展 system prompt，允许你在运行时动态注入额外的上下文信息。通过装饰器语法，你可以轻松注册自定义 hooks，并根据条件控制它们的启用。

当前支持的 hook 类型：
- **System Prompt Hook**：向 system prompt 追加内容

适用场景：
- 根据用户偏好动态添加技能描述
- 根据会话状态添加上下文信息
- 注入用户配置或偏好设置

## System Prompt Hook

### 基本用法

使用 `@system_prompt_hook` 装饰器注册一个 hook 函数：

```python
from backend.agents.hooks import system_prompt_hook
from typing import Dict

@system_prompt_hook()
def my_hook(context: Dict) -> Dict:
    return {
        "hook_type": "system_prompt",
        "content": "\n\n## 自定义信息\n这是一个示例"
    }
```

**函数签名**：
- 接收参数：`context: Dict` - 包含运行时数据的字典
- 返回格式：`Dict` - 必须包含 `hook_type` 和 `content` 字段

**返回格式要求**：
```python
{
    "hook_type": "system_prompt",  # 必须是 "system_prompt"
    "content": "要追加的内容"        # 字符串，会追加到 system prompt 末尾
}
```

### 装饰器参数

| 参数 | 类型 | 默认值 | 说明 | 示例 |
|------|------|--------|------|------|
| `priority` | int | 50 | 执行优先级（数字越小越先执行）| `priority=10` |
| `enabled_by` | Callable[[Dict], bool] | None | 启用条件函数，接收 context，返回 bool | `enabled_by=lambda ctx: ctx.get("enable_xxx")` |

### 完整示例

#### 1. 简单示例：无条件 hook

这个 hook 总是会执行，不需要任何条件：

```python
from backend.agents.hooks import system_prompt_hook
from typing import Dict

@system_prompt_hook(priority=100)
def add_custom_info(context: Dict) -> Dict:
    """添加自定义信息到 system prompt"""
    return {
        "hook_type": "system_prompt",
        "content": "\n\n## 自定义信息\n这是一个示例"
    }
```

#### 2. 条件启用示例：使用 enabled_by

只有当 context 中的开关为 True 时才执行：

```python
@system_prompt_hook(
    priority=50,
    enabled_by=lambda ctx: ctx.get("enable_custom_feature", False)
)
def add_feature_info(context: Dict) -> Dict:
    """当自定义特性启用时，添加相关信息"""
    return {
        "hook_type": "system_prompt",
        "content": "\n\n## 特性已启用\n自定义特性正在运行中..."
    }
```

#### 3. 依赖数据示例：从 context 获取数据

从 context 中读取数据，动态生成内容：

```python
@system_prompt_hook(
    priority=20,
    enabled_by=lambda ctx: ctx.get("enable_user_profile", False)
)
def inject_user_profile(context: Dict) -> Dict:
    """注入用户信息到 system prompt"""
    user_name = context.get("user_name", "未知用户")
    user_prefs = context.get("user_preferences", [])

    content = f"\n\n## 用户信息\n用户名：{user_name}\n"
    if user_prefs:
        content += "偏好：" + ", ".join(user_prefs)

    return {"hook_type": "system_prompt", "content": content}
```

### 启用 Hook

在 `MainAgent` 中配置 `hooks_context` 来控制 hooks 的启用和传递依赖数据：

```python
# 在 MainAgent._handle_chat 方法中
hooks_context = {
    # Hook 开关（默认禁用，按需启用）
    "enable_skills": False,
    "enable_user_profile": False,  # 自定义开关

    # Hook 依赖数据
    "session_id": session_id,
    "skills": ["搜索网络", "执行代码", "读写文件"],
    "user_name": "张三",  # 自定义数据
    "user_preferences": ["简洁回答", "技术细节"],  # 自定义数据
}

# 构建 messages 时传入 context
messages = self.prompt_builder.build_messages(
    user_message=user_message,
    history=history,
    context=hooks_context,
    max_history=20
)
```

**启用自定义 hook 的步骤**：

1. 在 `hooks_context` 中添加启用开关（如 `enable_user_profile: True`）
2. 添加 hook 需要的依赖数据（如 `user_name`, `user_preferences`）
3. Hook 会在 `build_messages` 时自动执行

### 内置 Hooks 参考

系统提供了一个内置 hook，位于 `backend/agents/hooks/builtin_hooks.py`：

| Hook 名称 | Priority | 启用条件 | 依赖数据 | 功能说明 |
|----------|----------|---------|---------|---------|
| `inject_skills` | 10 | `enable_skills` | `skills` (List[str]) | 添加技能描述到 system prompt |

**使用示例**：

```python
# 启用技能描述 hook
hooks_context = {
    "enable_skills": True,
    "skills": ["搜索网络", "执行代码", "读写文件"]
}
```

### 注意事项

1. **返回格式必须严格遵守**：必须返回包含 `hook_type` 和 `content` 的字典，否则 hook 会被忽略
2. **Priority 数字越小越先执行**：内置 hooks 使用 10-30，建议自定义 hooks 使用 50 以上
3. **Hook 执行失败会被捕获**：单个 hook 失败不会中断主流程，错误会被记录到日志
4. **Context 数据需要提前准备**：hook 依赖的数据必须在调用 `build_messages` 前添加到 context 中
5. **Hook name 会自动生成**：格式为 `模块名.函数名`，例如 `backend.agents.hooks.builtin_hooks.inject_capabilities`
6. **Hook 注册是全局的**：装饰器在模块加载时自动注册，无需手动调用

### 测试 Hook

#### 编写测试

使用 `clear_registry` fixture 清空注册表，避免测试间干扰：

```python
import pytest
from backend.agents.hooks import system_prompt_hook, SystemPromptRegistry

@pytest.fixture
def clear_registry():
    """清空注册表并重新加载 builtin hooks"""
    import importlib
    import backend.agents.hooks.builtin_hooks

    registry = SystemPromptRegistry.get_instance()
    registry.clear()

    # 重新加载 builtin_hooks 模块以重新注册装饰器
    importlib.reload(backend.agents.hooks.builtin_hooks)

    yield registry

def test_my_hook(clear_registry):
    """测试自定义 hook"""
    from backend.core.prompt_builder import PromptBuilder

    @system_prompt_hook(priority=10)
    def my_test_hook(context):
        return {"hook_type": "system_prompt", "content": "\nTest"}

    builder = PromptBuilder()
    messages = builder.build_messages("你好", [], {})

    system_prompt = messages[0]["content"]
    assert "Test" in system_prompt
```

#### 常见测试场景

1. **测试启用/禁用**：验证 `enabled_by` 条件是否正确工作
2. **测试优先级**：验证多个 hooks 按 priority 顺序执行
3. **测试错误隔离**：验证单个 hook 失败不影响其他 hooks
4. **测试返回格式校验**：验证错误的返回格式会被忽略

参考 `tests/unit/agents/test_hooks.py` 获取更多测试示例。

## 常见问题

**Q: 如何调试 hook？**

A: Hook 执行信息会被记录到日志中。查看日志可以看到：
- Hook 注册信息（`注册 hook: xxx (priority=xx)`）
- Hook 执行信息（`[Hook] 添加能力描述: 3 项`）
- Hook 错误信息（`Hook 'xxx' 执行失败: ...`）

**Q: 如何查看已注册的 hooks？**

A: 使用注册表的 `get_hooks()` 方法：

```python
from backend.agents.hooks import SystemPromptRegistry

registry = SystemPromptRegistry.get_instance()
hooks = registry.get_hooks()

for hook in hooks:
    print(f"Name: {hook.name}, Priority: {hook.priority}")
```

**Q: Hook 执行顺序如何确定？**

A: Hooks 按 `priority` 升序执行（数字越小越先执行）。如果多个 hooks 有相同的 priority，执行顺序不确定。

**Q: 可以在运行时动态注册 hook 吗？**

A: 可以，但不推荐。装饰器在模块加载时自动注册，这是推荐的方式。如果需要动态注册，可以手动调用 `registry.register()`，但需要注意线程安全。

**Q: Hook 可以修改 context 吗？**

A: 不建议。Hook 应该是只读的，只根据 context 生成内容。如果需要修改状态，应该在调用 `build_messages` 之前完成。

**Q: 如何禁用内置 hooks？**

A: 在 `hooks_context` 中将对应的开关设置为 `False`（默认就是 `False`）：

```python
hooks_context = {
    "enable_skills": False,  # 禁用技能描述 hook
}
```
