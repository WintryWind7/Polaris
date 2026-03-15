/**
 * 日志模块筛选配置
 *
 * 这个文件定义了所有可筛选的日志模块。
 * 每个模块包含：
 * - id: 唯一标识符
 * - label: 显示名称
 * - pattern: 正则表达式，用于匹配日志的 name 字段
 * - description: 模块描述（用于 tooltip）
 * - enabled: 是否默认启用（可选，默认 true）
 *
 * 未来扩展指南：
 * 1. 添加新模块时，只需在 modules 数组中添加新配置
 * 2. pattern 支持正则表达式，可以匹配多个模块名
 * 3. 可以使用 category 字段对模块进行分组（未来功能）
 */

export const logModules = [
  {
    id: 'tools',
    label: 'Tools',
    pattern: /^agents\.tools\./,
    description: '工具系统日志 - 包括工具加载、执行等',
    enabled: true
  },
  {
    id: 'memory',
    label: 'Memory',
    pattern: /^agents\.memory/,
    description: '记忆系统日志 - 包括时间线、对话记录等',
    enabled: true
  }

  // ===== 未来可添加的模块示例 =====

  // {
  //   id: 'chat',
  //   label: 'Chat',
  //   pattern: /^(core\.conversation|api\.routes\.chat)/,
  //   description: '对话系统日志 - 包括消息处理、会话管理等',
  //   enabled: true
  // },

  // {
  //   id: 'llm',
  //   label: 'LLM',
  //   pattern: /^core\.llm/,
  //   description: 'LLM 调用日志 - 包括 API 请求、响应等',
  //   enabled: true
  // },

  // {
  //   id: 'agent',
  //   label: 'Agent',
  //   pattern: /^agents\.main_agent|^agents\.heartbeat_agent/,
  //   description: 'Agent 核心日志 - 主 Agent 和心跳 Agent',
  //   enabled: true
  // },

  // {
  //   id: 'prompts',
  //   label: 'Prompts',
  //   pattern: /^agents\.prompts\./,
  //   description: '提示词系统日志 - 包括加载、构建等',
  //   enabled: true
  // },

  // {
  //   id: 'hooks',
  //   label: 'Hooks',
  //   pattern: /^agents\.hooks\./,
  //   description: '钩子系统日志 - 包括系统提示词钩子等',
  //   enabled: true
  // },

  // {
  //   id: 'api',
  //   label: 'API',
  //   pattern: /^api\./,
  //   description: 'API 层日志 - 包括路由、服务器等',
  //   enabled: true
  // },

  // {
  //   id: 'database',
  //   label: 'Database',
  //   pattern: /^core\.database/,
  //   description: '数据库日志 - 包括查询、连接等',
  //   enabled: true
  // }
]

/**
 * 获取默认启用的模块 ID 列表
 */
export function getDefaultEnabledModules() {
  return logModules
    .filter(m => m.enabled !== false)
    .map(m => m.id)
}

/**
 * 根据日志名称匹配对应的模块
 * @param {string} logName - 日志的 name 字段
 * @returns {string|null} - 匹配的模块 ID，如果没有匹配则返回 null
 */
export function matchLogModule(logName) {
  for (const module of logModules) {
    if (module.pattern.test(logName)) {
      return module.id
    }
  }
  return null
}
