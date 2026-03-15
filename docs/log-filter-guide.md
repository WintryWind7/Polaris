# 日志筛选系统使用指南

## 概述

日志筛选系统提供了灵活的前端筛选机制，支持按日志级别和模块进行多选筛选，类似 VSCode 输出面板的体验。

## 功能特性

### 1. 日志级别筛选
- 支持 5 个级别：DEBUG、INFO、WARNING、ERROR、CRITICAL
- 多选机制，可以同时查看多个级别的日志
- 每个级别有独特的颜色标识

### 2. 模块筛选
- 支持按模块筛选日志（如 Tools、Memory）
- 采用复选框打勾的方式，直观易用
- 可扩展架构，方便添加新模块

## 当前支持的模块

| 模块 ID | 显示名称 | 匹配规则 | 说明 |
|---------|---------|---------|------|
| `tools` | Tools | `agents.tools.*` | 工具系统日志 - 包括工具加载、执行等 |
| `memory` | Memory | `agents.memory*` | 记忆系统日志 - 包括时间线、对话记录等 |

## 如何添加新模块

### 步骤 1: 编辑配置文件

打开 `frontend/src/config/logModules.js`，在 `logModules` 数组中添加新模块：

```javascript
{
  id: 'chat',                                      // 唯一标识符
  label: 'Chat',                                   // 显示名称
  pattern: /^(core\.conversation|api\.routes\.chat)/,  // 匹配规则（正则表达式）
  description: '对话系统日志 - 包括消息处理、会话管理等',  // 描述（用于 tooltip）
  enabled: true                                    // 是否默认启用（可选）
}
```

### 步骤 2: 测试

1. 启动前端开发服务器
2. 打开日志页面
3. 查看新模块是否出现在筛选器中
4. 测试筛选功能是否正常工作

### 示例：添加 LLM 模块

```javascript
{
  id: 'llm',
  label: 'LLM',
  pattern: /^core\.llm/,
  description: 'LLM 调用日志 - 包括 API 请求、响应等',
  enabled: true
}
```

## 模块匹配规则

### 正则表达式语法

- `^` - 匹配字符串开头
- `\.` - 匹配点号（需要转义）
- `.*` - 匹配任意字符（0 个或多个）
- `|` - 或运算符
- `()` - 分组

### 常用模式

```javascript
// 匹配单个模块
/^agents\.tools\./          // 匹配 agents.tools.xxx

// 匹配多个模块
/^(core\.llm|core\.conversation)/  // 匹配 core.llm 或 core.conversation

// 匹配模块及其子模块
/^agents\.memory/           // 匹配 agents.memory 和 agents.memory.xxx

// 匹配特定层级
/^agents\.tools\.[^.]+$/    // 只匹配 agents.tools.xxx，不匹配 agents.tools.xxx.yyy
```

## 筛选逻辑

### 级别筛选
- 只显示选中级别的日志
- 至少需要选中一个级别

### 模块筛选
- **全部选中**：显示所有日志（包括未分类的）
- **部分选中**：只显示匹配选中模块的日志
- **全部未选中**：不显示任何日志

### 组合筛选
日志需要同时满足级别和模块筛选条件才会显示。

## 未来扩展计划

### 短期（重构后）
1. 添加 Chat 模块（对话系统）
2. 添加 LLM 模块（LLM 调用）
3. 添加 Agent 模块（主 Agent 和心跳 Agent）

### 中期
1. 支持模块分组（如 Agent 系统、核心功能、API 层）
2. 支持自定义筛选规则
3. 支持保存筛选配置到本地存储

### 长期
1. 支持搜索和高亮
2. 支持导出日志
3. 支持日志统计和可视化

## 后端日志规范（待完善）

为了更好地支持模块筛选，后端日志应遵循以下规范：

### 模块命名规范

```python
# 推荐：使用 __name__ 自动获取模块名
from backend.logger import get_logger
logger = get_logger(__name__)

# 结果：agents.tools.executor
# 显示：[agents.tools.executor]
```

### 模块层级建议

```
agents/
  ├── main_agent.py          → agents.main_agent
  ├── heartbeat_agent.py     → agents.heartbeat_agent
  ├── tools/
  │   ├── executor.py        → agents.tools.executor
  │   └── loader.py          → agents.tools.loader
  ├── memory/
  │   └── __init__.py        → agents.memory
  └── prompts/
      └── loader.py          → agents.prompts.loader

core/
  ├── llm.py                 → core.llm
  ├── conversation.py        → core.conversation
  └── database.py            → core.database

api/
  ├── server.py              → api.server
  └── routes/
      ├── chat.py            → api.routes.chat
      └── agent.py           → api.routes.agent
```

## 常见问题

### Q: 为什么我的日志没有显示？
A: 检查以下几点：
1. 日志级别是否被选中
2. 日志模块是否匹配任何已选中的模块
3. 如果日志不属于任何已定义的模块，需要全选模块才能显示

### Q: 如何查看所有日志？
A: 选中所有日志级别和所有模块即可。

### Q: 模块筛选的正则表达式不生效？
A: 确保：
1. 正则表达式语法正确
2. 使用 `/` 包裹正则表达式
3. 特殊字符（如 `.`）需要转义

### Q: 如何临时禁用某个模块？
A: 在配置文件中设置 `enabled: false`，或者在前端取消勾选该模块。

## 技术细节

### 架构设计

```
frontend/src/
├── config/
│   └── logModules.js       # 模块配置（集中管理）
└── views/
    └── LogsView.vue        # 日志视图（使用配置）
```

### 数据流

```
WebSocket → logs[] → filteredLogs (computed) → 渲染
                          ↑
                    级别筛选 + 模块筛选
```

### 性能优化

- 使用 `Set` 数据结构进行快速查找
- 使用 `computed` 进行响应式筛选
- 限制内存中的日志数量（最多 2000 条）

## 相关文件

- `frontend/src/config/logModules.js` - 模块配置
- `frontend/src/views/LogsView.vue` - 日志视图
- `backend/logger/logger.py` - 后端日志系统
- `backend/logger/README.md` - 后端日志使用指南
