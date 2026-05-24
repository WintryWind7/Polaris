# 日志筛选系统实现总结

## 已完成的工作

### 1. 前端筛选框架 ✅

#### 文件变更
- **frontend/src/views/LogsView.vue** - 添加模块筛选功能
  - 新增模块筛选 UI（复选框样式）
  - 实现多选筛选逻辑
  - 支持级别 + 模块组合筛选

- **frontend/src/config/logModules.js** - 模块配置文件（新建）
  - 集中管理所有可筛选模块
  - 提供可扩展的配置结构
  - 包含详细的扩展示例和注释

- **docs/log-filter-guide.md** - 使用和扩展指南（新建）
  - 完整的使用说明
  - 添加新模块的步骤
  - 后端日志规范建议
  - 常见问题解答

### 2. 当前支持的模块

| 模块 | 匹配规则 | 说明 |
|------|---------|------|
| Tools | `agents.tools.*` | 工具系统日志 |
| Memory | `agents.memory*` | 记忆系统日志 |

### 3. 架构特点

#### 可扩展性
- 配置与视图分离
- 添加新模块只需修改配置文件
- 支持正则表达式匹配

#### 用户体验
- 类似 VSCode 输出面板的筛选体验
- 复选框打勾方式，直观易用
- 支持多选组合筛选
- 实时筛选，无需刷新

#### 性能优化
- 使用 Set 数据结构快速查找
- 使用 computed 响应式筛选
- 限制内存中日志数量（2000 条）

## 筛选逻辑说明

### 模块筛选规则

```javascript
// 全部选中 → 显示所有日志（包括未分类的）
if (activeModules.size === moduleFilters.length) {
  return true
}

// 全部未选中 → 不显示任何日志
if (activeModules.size === 0) {
  return false
}

// 部分选中 → 只显示匹配的日志
for (const filter of moduleFilters) {
  if (activeModules.has(filter.id) && filter.pattern.test(logName)) {
    return true
  }
}

// 未匹配任何模块 → 不显示
return false
```

### 组合筛选

日志需要同时满足：
1. 日志级别在选中的级别中
2. 日志模块匹配选中的模块

```javascript
filteredLogs = logs.filter(log =>
  activeLevels.has(log.level) && matchesModuleFilter(log.name)
)
```

## 下一步工作

### 1. 重构后端日志结构（优先）

需要规范化日志模块命名，建议的模块结构：

```
agents/
  ├── main_agent.py          # 主 Agent 核心逻辑
  ├── heartbeat_agent.py     # 心跳 Agent
  ├── chat/                  # 对话处理（新建）
  │   ├── handler.py
  │   └── session.py
  ├── tools/                 # 工具系统 ✅
  │   ├── executor.py
  │   └── loader.py
  ├── memory/                # 记忆系统 ✅
  │   └── __init__.py
  └── prompts/
      └── loader.py

core/
  ├── llm/                   # LLM 适配层
  ├── conversation.py        # 对话管理
  └── database.py            # 数据库

api/
  ├── server.py
  └── routes/
      ├── chat.py            # 聊天路由
      └── agent.py
```

### 2. 添加更多模块（重构后）

在 `frontend/src/config/logModules.js` 中添加：

```javascript
// Chat 模块
{
  id: 'chat',
  label: 'Chat',
  pattern: /^(agents\.chat|core\.conversation|api\.routes\.chat)/,
  description: '对话系统日志 - 包括消息处理、会话管理等',
  enabled: true
}

// LLM 模块
{
  id: 'llm',
  label: 'LLM',
  pattern: /^core\.llm/,
  description: 'LLM 调用日志 - 包括 API 请求、响应等',
  enabled: true
}

// Agent 模块
{
  id: 'agent',
  label: 'Agent',
  pattern: /^agents\.(main_agent|heartbeat_agent)/,
  description: 'Agent 核心日志 - 主 Agent 和心跳 Agent',
  enabled: true
}
```

### 3. 未来增强功能

- [ ] 模块分组（如 Agent 系统、核心功能、API 层）
- [ ] 搜索和高亮功能
- [ ] 导出日志功能
- [ ] 保存筛选配置到本地存储
- [ ] 日志统计和可视化
- [ ] 支持自定义筛选规则

## 测试建议

### 手动测试步骤

1. 启动项目
   ```bash
   $env:POLARIS_RELOAD="1"; $env:POLARIS_DEV="1"; python -m backend.api.server
   ```

2. 打开日志页面
   - 访问 http://127.0.0.1:6546
   - 进入"日志"页面

3. 测试筛选功能
   - 测试日志级别筛选（DEBUG、INFO、WARNING、ERROR、CRITICAL）
   - 测试模块筛选（Tools、Memory）
   - 测试组合筛选
   - 测试全选/全不选

4. 验证日志显示
   - 执行一些操作触发 tools 日志（如调用工具）
   - 执行一些操作触发 memory 日志（如发送消息）
   - 观察筛选是否正常工作

### 验证点

- [ ] 模块筛选按钮显示正常
- [ ] 复选框状态切换正常
- [ ] 筛选逻辑正确（只显示匹配的日志）
- [ ] 组合筛选正常工作
- [ ] 未分类日志的处理正确
- [ ] 性能良好（大量日志时）

## 相关文件清单

### 新建文件
- `frontend/src/config/logModules.js` - 模块配置
- `docs/log-filter-guide.md` - 使用指南

### 修改文件
- `frontend/src/views/LogsView.vue` - 日志视图

### 相关文件（未修改）
- `backend/logger/logger.py` - 后端日志系统
- `backend/logger/router.py` - WebSocket 路由
- `backend/logger/README.md` - 后端日志文档

## 技术栈

- **前端框架**: Vue 3 Composition API
- **状态管理**: ref + computed
- **数据结构**: Set（快速查找）
- **通信**: WebSocket
- **样式**: Scoped CSS

## 注意事项

1. **正则表达式性能**: 当前使用简单的正则匹配，如果模块数量很多，可能需要优化
2. **未分类日志**: 当前设计是全选时显示未分类日志，部分选中时不显示
3. **配置持久化**: 当前筛选配置不会保存，刷新页面会重置
4. **后端依赖**: 依赖后端日志的 `name` 字段格式正确

## 总结

已成功搭建了一个灵活、可扩展的日志筛选框架。当前实现了 Tools 和 Memory 两个模块的筛选，为后续添加更多模块打下了良好的基础。下一步需要重构后端日志结构，规范化模块命名，然后再完善更多的筛选模块。
