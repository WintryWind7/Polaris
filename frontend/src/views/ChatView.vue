<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, ChevronDown, Send, ChevronRight, Wrench } from 'lucide-vue-next'
import { marked } from 'marked'
import workspaceApi from '../services/workspaceApi'

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

const API_BASE = '' // Vite proxy handles this in dev
// SSE 直连后端（Vite 代理会缓冲流式响应）
const SSE_BASE = import.meta.env.DEV ? 'http://127.0.0.1:6547' : ''

const sessions = ref([])
const currentSessionId = ref(null)
const messages = ref([])
const inputMessage = ref('')
const isLoading = ref(false)
const showHistoryMenu = ref(false)
const chatArea = ref(null)
const workspaceInfo = ref(null)
const workspaceMap = ref({})  // workspace_id → name

// 会话多选
const selectedSessions = reactive(new Set())

function toggleSelect(sessionId) {
  if (selectedSessions.has(sessionId)) {
    selectedSessions.delete(sessionId)
  } else {
    selectedSessions.add(sessionId)
  }
}

function selectAll() {
  if (selectedSessions.size === sessions.value.length) {
    selectedSessions.clear()
  } else {
    for (const s of sessions.value) {
      selectedSessions.add(s.id)
    }
  }
}

async function deleteSelected() {
  if (selectedSessions.size === 0) return
  if (!confirm(`确定要删除 ${selectedSessions.size} 个会话吗？`)) return
  try {
    const ids = [...selectedSessions]
    const response = await fetch(`${API_BASE}/api/chat/sessions/batch-delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_ids: ids })
    })
    if (response.ok) {
      sessions.value = sessions.value.filter(s => !selectedSessions.has(s.id))
      if (selectedSessions.has(currentSessionId.value)) {
        startNewChat()
      }
      selectedSessions.clear()
    }
  } catch (err) {
    console.error('Failed to batch delete:', err)
  }
}

// 工具调用步骤展开状态
const expandedSteps = reactive({})

function toggleStep(key) {
  expandedSteps[key] = !expandedSteps[key]
}

// 从历史消息的 tool_calls + tool_results 解析为 steps 格式
function parseToolSteps(msg) {
  if (!msg.tool_calls?.length) return []
  const steps = msg.tool_calls.map((tc, i) => {
    const args = JSON.parse(tc.function?.arguments || '{}')
    const tr = msg.tool_results?.[i]
    let resultData = {}
    try { resultData = JSON.parse(tr?.content || '{}') } catch {}
    const step = {
      tool_name: tc.function?.name || '',
      arguments: args,
      result: resultData.response || resultData.error || '',
      status: resultData.success ? 'completed' : 'error',
      children: []
    }
    return step
  })
  return steps
}

// 工具名称友好显示
const TOOL_DISPLAY = {
  list_directory: '列出目录',
  read_file: '读取文件',
  write_file: '写入文件',
  web_search: '网络搜索',
  web_fetch: '抓取网页',
  search_memory: '检索记忆',
  ask_main_agent: '询问主 Agent',
}

const AGENT_DISPLAY = {
  filesystem: '文件系统',
  web: '网络搜索',
  memory: '记忆检索',
}

function formatToolName(step) {
  return TOOL_DISPLAY[step.tool_name] || step.tool_name
}

function formatAgentStep(step) {
  if (step.tool_name !== 'subagent') return ''
  const type = step.arguments?.agent_type || ''
  return AGENT_DISPLAY[type] || type
}

// Markdown 渲染
function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text)
}

// 将消息转换为有序内容块（兼容历史消息格式）
function getBlocks(msg) {
  if (msg.blocks?.length) return msg.blocks
  const blocks = []
  let contentUsedAsTools = false

  // 有 tool_calls（标准格式）→ 工具块
  if (msg.tool_calls?.length) {
    blocks.push({ type: 'tools', steps: msg.steps?.length ? msg.steps : parseToolSteps(msg) })
  }
  // content 是原始 tool_calls JSON（旧存储格式）→ 也解析为工具块
  if (!msg.tool_calls?.length && msg.content) {
    try {
      const parsed = JSON.parse(msg.content)
      if (Array.isArray(parsed) && parsed[0]?.function) {
        blocks.push({ type: 'tools', steps: parseToolSteps({ tool_calls: parsed, tool_results: [] }) })
        contentUsedAsTools = true
      }
    } catch {}
  }
  // 文本内容
  if (msg.content && !contentUsedAsTools) {
    blocks.push({ type: 'text', content: msg.content })
  }
  // 思维链内容（历史消息）
  if (msg.reasoning_content) {
    blocks.unshift({ type: 'reasoning', content: msg.reasoning_content, _expanded: false })
  }
  return blocks
}

// 渲染文本块内容（含打字光标）
function renderBlockContent(block, showCursor) {
  if (!block.content) return ''
  const html = renderMarkdown(block.content)
  if (showCursor) return html + '<span class="typing-cursor">|</span>'
  return html
}

// 格式化工具结果（尝试美化 JSON）
function formatToolResult(result) {
  if (!result) return ''
  try {
    const parsed = JSON.parse(result)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return result
  }
}

// 判断消息是否有可见的文本内容
function hasTextContent(msg) {
  const blocks = getBlocks(msg)
  return blocks.some(b => b.type === 'text' && b.content)
}

const route = useRoute()
const router = useRouter()

const workspaceId = computed(() => route.query.workspace)

// Load all sessions (始终加载全部，按 workspace 过滤通过左上角 badge 进入)
async function loadSessions() {
  try {
    // 并行拉取会话列表和工作空间列表
    const [sessionsRes, wsData] = await Promise.all([
      fetch(`${API_BASE}/api/chat/sessions`),
      workspaceApi.getWorkspaces().catch(() => ({ workspaces: [] }))
    ])
    // 建立 workspace 名称映射
    for (const ws of (wsData.workspaces || [])) {
      workspaceMap.value[ws.id] = ws.name
    }
    if (sessionsRes.ok) {
      const data = await sessionsRes.json()
      sessions.value = data.sessions
      
      // 如果没有指定会话，且有历史记录，则自动加载最近一次会话
      if (!currentSessionId.value && sessions.value.length > 0) {
        const urlSessionId = route.query.session
        if (urlSessionId) {
            loadSession(urlSessionId)
        } else if (workspaceId.value) {
            // 从工作空间进入，保持新对话（不自动加载旧会话）
            startNewChat()
        } else {
            loadSession(sessions.value[0].id)
        }
      } else if (!currentSessionId.value) {
        startNewChat()
      }
    }
  } catch (err) {
    console.error('Failed to load sessions:', err)
  }
}

// Load specific session
async function loadSession(sessionId) {
  try {
    const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`)
    if (response.ok) {
      const data = await response.json()
      messages.value = data.messages
      currentSessionId.value = sessionId
      showHistoryMenu.value = false

      // 以 session 自身的 workspace_id 为准，同步工作空间和 URL
      const sessionWid = data.session?.workspace_id
      const query = { ...route.query, session: sessionId }
      if (sessionWid) {
        query.workspace = sessionWid
        if (!workspaceInfo.value || workspaceInfo.value.id !== sessionWid) {
          await loadWorkspaceInfo(sessionWid)
        }
      } else {
        delete query.workspace
        workspaceInfo.value = null
      }
      router.replace({ query })

      await nextTick()
      scrollToBottom()

      // 检查是否有正在进行的流式生成，尝试恢复
      resumeStream(sessionId)
    }
  } catch (err) {
    console.error('Failed to load session:', err)
  }
}

// Delete session
async function deleteSession(sessionId, event) {
  if (event) {
    event.stopPropagation()
  }
  
  if (!confirm('确定要删除这个对话吗？')) return
  
  try {
    const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, {
      method: 'DELETE'
    })
    
    if (response.ok) {
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      if (currentSessionId.value === sessionId) {
        startNewChat()
      }
    }
  } catch (err) {
    console.error('Failed to delete session:', err)
  }
}

// Start new chat
function startNewChat() {
  currentSessionId.value = null
  messages.value = [
    {
      role: 'assistant',
      content: '你好！我是 Polaris，你的智能助手。开始新的对话吧。',
      timestamp: new Date().toISOString()
    }
  ]
  showHistoryMenu.value = false
  // 保留 workspace 参数，只移除 session
  const query = { ...route.query }
  delete query.session
  router.replace({ query })
}

// 处理单个流式事件（tool_call/tool_result/reasoning/text/done）
function handleStreamEvent(event, assistantMsg) {
  if (event.type === 'tool_call' && assistantMsg) {
    const newStep = {
      tool_name: event.tool_name,
      arguments: event.arguments,
      result: '',
      status: 'running',
      children: []
    }
    const lastBlock = assistantMsg.blocks[assistantMsg.blocks.length - 1]
    if (lastBlock?.type === 'tools') {
      if (event.tool_name === 'subagent') {
        lastBlock.steps.push(newStep)
      } else {
        const lastStep = lastBlock.steps[lastBlock.steps.length - 1]
        if (lastStep?.tool_name === 'subagent') {
          lastStep.children.push(newStep)
        } else {
          lastBlock.steps.push(newStep)
        }
      }
    } else {
      const toolsBlock = { type: 'tools', steps: [newStep] }
      assistantMsg.blocks.push(toolsBlock)
    }
  } else if (event.type === 'tool_result' && assistantMsg) {
    let lastToolsBlock = null
    for (let i = assistantMsg.blocks.length - 1; i >= 0; i--) {
      if (assistantMsg.blocks[i].type === 'tools') {
        lastToolsBlock = assistantMsg.blocks[i]
        break
      }
    }
    if (lastToolsBlock) {
      const steps = lastToolsBlock.steps
      const lastStep = steps[steps.length - 1]
      let found = false
      if (lastStep?.tool_name === 'subagent') {
        for (let i = lastStep.children.length - 1; i >= 0; i--) {
          const c = lastStep.children[i]
          if (c.tool_name === event.tool_name && c.status === 'running') {
            c.result = event.result
            c.status = event.status
            found = true
            break
          }
        }
      }
      if (!found) {
        for (let i = steps.length - 1; i >= 0; i--) {
          const s = steps[i]
          if (s.tool_name === event.tool_name && s.status === 'running') {
            s.result = event.result
            s.status = event.status
            break
          }
        }
      }
    }
  } else if (event.type === 'reasoning' && assistantMsg) {
    const lastBlock = assistantMsg.blocks[assistantMsg.blocks.length - 1]
    if (lastBlock?.type === 'reasoning') {
      lastBlock.content += event.content
    } else {
      assistantMsg.blocks.push({ type: 'reasoning', content: event.content, _expanded: true })
    }
  } else if (event.type === 'text' && assistantMsg) {
    // 正式输出开始，标记思考完成，延迟平滑收起
    for (const block of assistantMsg.blocks) {
      if (block.type === 'reasoning' && block._expanded && !block._complete) {
        block._complete = true
        setTimeout(() => {
          block._expanded = false
          block._collapsing = false
        }, 1000)
        block._collapsing = true
      }
    }
    const lastBlock = assistantMsg.blocks[assistantMsg.blocks.length - 1]
    if (lastBlock?.type === 'text') {
      lastBlock.content += event.content
    } else {
      assistantMsg.blocks.push({ type: 'text', content: event.content })
    }
  } else if (event.type === 'done' && assistantMsg) {
    assistantMsg.isStreaming = false
    assistantMsg.timestamp = new Date().toISOString()
  }
}

// 从 ReadableStream 读取 SSE 事件并回调
async function readSSEStream(reader, onEvent) {
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    while (buffer.includes('\n\n')) {
      const eventEnd = buffer.indexOf('\n\n')
      const eventStr = buffer.slice(0, eventEnd)
      buffer = buffer.slice(eventEnd + 2)

      const lines = eventStr.split('\n').filter(l => l.startsWith('data: '))
      for (const line of lines) {
        const data = line.slice(6).trim()
        if (data === '[DONE]') continue
        try {
          onEvent(JSON.parse(data))
        } catch (parseErr) {
          console.error('解析 SSE 事件失败:', parseErr)
        }
      }

      await new Promise(r => requestAnimationFrame(r))
      scrollToBottom()
    }
  }
}

// Send message (streaming)
async function sendMessage() {
  const message = inputMessage.value.trim()
  if (!message || isLoading.value) return

  messages.value.push({
    role: 'user',
    content: message,
    timestamp: new Date().toISOString()
  })
  inputMessage.value = ''
  isLoading.value = true

  await nextTick()
  scrollToBottom()

  let assistantMsg = null

  try {
    const response = await fetch(`${SSE_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: currentSessionId.value,
        workspace_id: workspaceId.value || undefined
      })
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body.getReader()

    await readSSEStream(reader, (event) => {
      if (event.type === 'session') {
        isLoading.value = false
        messages.value.push({
          role: 'assistant',
          blocks: [],
          timestamp: null,
          isStreaming: true
        })
        assistantMsg = messages.value[messages.value.length - 1]

        if (event.session_id && currentSessionId.value !== event.session_id) {
          currentSessionId.value = event.session_id
          router.replace({ query: { ...route.query, session: event.session_id } })
          loadSessions()
        }
      } else if (event.type === 'error') {
        if (!assistantMsg) {
          isLoading.value = false
          assistantMsg = {
            role: 'assistant',
            blocks: [],
            timestamp: new Date().toISOString(),
            isStreaming: false
          }
          messages.value.push(assistantMsg)
        }
        const lastBlock = assistantMsg.blocks[assistantMsg.blocks.length - 1]
        if (lastBlock?.type === 'text') {
          lastBlock.content += `\n\n错误: ${event.message}`
        } else {
          assistantMsg.blocks.push({ type: 'text', content: `错误: ${event.message}` })
        }
        assistantMsg.isStreaming = false
      } else {
        handleStreamEvent(event, assistantMsg)
      }
    })

    if (assistantMsg) {
      assistantMsg.isStreaming = false
      if (!assistantMsg.timestamp) assistantMsg.timestamp = new Date().toISOString()
    }

  } catch (err) {
    console.error('Error:', err)
    isLoading.value = false
    messages.value.push({
      role: 'assistant',
      blocks: [{ type: 'text', content: '抱歉，发送失败，请稍后再试。' }],
      timestamp: new Date().toISOString()
    })
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

// 恢复中断的流式对话
async function resumeStream(sessionId) {
  try {
    const statusResp = await fetch(`${API_BASE}/api/chat/stream/status/${sessionId}`)
    if (!statusResp.ok) return
    const { streaming } = await statusResp.json()
    if (!streaming) return

    // 移除最后一条不完整的 assistant 消息（DB 快照）
    const last = messages.value[messages.value.length - 1]
    if (last?.role === 'assistant') {
      messages.value.pop()
    }

    // 创建新的 assistant 消息接收恢复的事件
    messages.value.push({
      role: 'assistant',
      blocks: [],
      timestamp: null,
      isStreaming: true
    })
    const assistantMsg = messages.value[messages.value.length - 1]

    const response = await fetch(`${SSE_BASE}/api/chat/stream/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId })
    })

    if (!response.ok) return

    // 竞态：status 查到 streaming 但 resume 时流已结束，重新加载会话
    const ct = response.headers.get('Content-Type') || ''
    if (!ct.includes('text/event-stream')) {
      const sessionResp = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`)
      if (sessionResp.ok) {
        const data = await sessionResp.json()
        messages.value = data.messages
        await nextTick()
        scrollToBottom()
      }
      return
    }

    const reader = response.body.getReader()

    await readSSEStream(reader, (event) => {
      if (event.type === 'session') {
        // 恢复模式下忽略 session 事件
        return
      } else if (event.type === 'error') {
        const lastBlock = assistantMsg.blocks[assistantMsg.blocks.length - 1]
        if (lastBlock?.type === 'text') {
          lastBlock.content += `\n\n错误: ${event.message}`
        } else {
          assistantMsg.blocks.push({ type: 'text', content: `错误: ${event.message}` })
        }
        assistantMsg.isStreaming = false
      } else {
        handleStreamEvent(event, assistantMsg)
      }
    })

    assistantMsg.isStreaming = false
    if (!assistantMsg.timestamp) assistantMsg.timestamp = new Date().toISOString()
  } catch (err) {
    console.error('恢复流式对话失败:', err)
  }
}

function scrollToBottom() {
  if (chatArea.value) {
    chatArea.value.scrollTop = chatArea.value.scrollHeight
  }
}

function handleKeyPress(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const currentTitle = computed(() => {
  if (!currentSessionId.value) return '新对话'
  const session = sessions.value.find(s => s.id === currentSessionId.value)
  return session ? session.title : '对话中...'
})

// 加载 workspace 信息
async function loadWorkspaceInfo(wid) {
  const effectiveId = wid ?? workspaceId.value
  if (!effectiveId) {
    workspaceInfo.value = null
    return
  }
  try {
    workspaceInfo.value = await workspaceApi.getWorkspace(effectiveId)
  } catch (err) {
    console.error('加载工作空间信息失败:', err)
  }
}

// Close dropdown when clicking outside
function handleClickOutside(event) {
    const dropdown = document.querySelector('.history-dropdown');
    const titleGroup = document.querySelector('.chat-title-group');
    if (titleGroup && titleGroup.contains(event.target)) {
        return; // Title group click is handled by toggle
    }
    if (dropdown && !dropdown.contains(event.target)) {
        showHistoryMenu.value = false;
    }
}

function toggleHistoryMenu() {
  showHistoryMenu.value = !showHistoryMenu.value
}

onMounted(() => {
  loadSessions()
  loadWorkspaceInfo()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

// Format time nicely
function getWorkspaceName(session) {
  if (session.workspace_id && workspaceMap.value[session.workspace_id]) {
    return workspaceMap.value[session.workspace_id]
  }
  return '通用'
}

function formatRelativeTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now - date
  
  if (diffMs < 60000) return '刚刚'
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)} 分钟前`
  if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)} 小时前`
  if (diffMs < 172800000) return '昨天'
  
  return `${date.getMonth() + 1}月${date.getDate()}日`
}
</script>

<template>
  <div class="chat-view">
    <!-- Top Navigation Bar -->
    <div class="chat-topbar">
        <div v-if="workspaceInfo" class="workspace-badge" @click="$router.push({ path: '/workspaces', query: { workspace: workspaceId } })">
          📁 {{ workspaceInfo.name }}
        </div>
        <div v-else class="workspace-badge default">
          🌐 通用
        </div>
        <div class="chat-title-group" @click="toggleHistoryMenu">
            <span class="chat-title">{{ currentTitle }}</span>
            <ChevronDown class="chevron-down" :size="16" />
            
            <!-- History Dropdown -->
            <div v-if="showHistoryMenu" class="history-dropdown" @click.stop>
              <div class="dropdown-header">
                <span>会话历史</span>
                <div class="header-actions">
                  <label class="select-all-label" @click.stop>
                    <input type="checkbox" :checked="selectedSessions.size === sessions.length && sessions.length > 0" @change="selectAll" />
                    <span>全选</span>
                  </label>
                  <button v-if="selectedSessions.size > 0" class="batch-delete-btn" @click.stop="deleteSelected">
                    删除 ({{ selectedSessions.size }})
                  </button>
                </div>
              </div>
              <div class="dropdown-list" v-if="sessions.length > 0">
                <div
                  v-for="session in sessions"
                  :key="session.id"
                  class="history-item"
                  :class="{ active: currentSessionId === session.id }"
                >
                  <input type="checkbox" class="select-checkbox" :checked="selectedSessions.has(session.id)" @click.stop @change="toggleSelect(session.id)" />
                  <div class="history-item-content" @click="loadSession(session.id)">
                    <div class="history-item-title">{{ session.title }}</div>
                    <div class="history-item-meta">
                      <span class="history-item-time">{{ formatRelativeTime(session.updated_at) }}</span>
                      <span class="history-item-workspace" :class="{ default: !session.workspace_id }">{{ getWorkspaceName(session) }}</span>
                    </div>
                  </div>
                  <button class="delete-btn" @click="(e) => deleteSession(session.id, e)" title="删除">x</button>
                </div>
              </div>
              <div v-else class="empty-history">
                暂无历史记录
              </div>
            </div>
        </div>
        <button class="new-chat-btn" @click="startNewChat">
            <Plus :size="16" />
            新对话
        </button>
    </div>

    <!-- Centered Chat Area -->
    <div class="chat-container" ref="chatArea">
        <div class="chat-messages">
            <div class="message-row" v-for="(msg, index) in messages" :key="index" :class="msg.role">
                <div class="avatar">{{ msg.role === 'user' ? 'U' : '✨' }}</div>
                <div class="message-content-wrapper">
                  <template v-for="(block, bi) in getBlocks(msg)" :key="bi">
                    <!-- 思维链块 -->
                    <div v-if="block.type === 'reasoning' && block.content" class="reasoning-block">
                      <div class="reasoning-header" @click="if (block._expanded) { block._expanded = false; block._collapsing = false } else { block._expanded = true; block._collapsing = false }">
                        <span class="reasoning-icon">{{ block._complete ? '💡' : '💭' }}</span>
                        <span class="reasoning-label">{{ block._complete ? '思考完成' : '思考过程' }}</span>
                        <span class="reasoning-toggle">{{ block._expanded ? '收起' : (block._collapsing ? '收起中…' : '展开') }}</span>
                      </div>
                      <Transition name="reasoning-collapse">
                        <div v-if="block._expanded" class="reasoning-content">{{ block.content }}</div>
                      </Transition>
                    </div>
                    <!-- 文本块 -->
                    <div v-if="block.type === 'text' && block.content" class="message-bubble markdown-body"
                         v-html="renderBlockContent(block, msg.isStreaming && bi === getBlocks(msg).length - 1)">
                    </div>
                    <!-- 工具块 -->
                    <div v-if="block.type === 'tools' && block.steps?.length" class="tool-steps">
                      <template v-for="(step, si) in block.steps" :key="si">
                        <!-- 子 Agent 分组卡片 -->
                        <div v-if="step.tool_name === 'subagent'" class="tool-group">
                          <div class="tool-group-header" @click="toggleStep(`${index}-${bi}-${si}`)">
                            <span class="tool-group-icon">{{ step.arguments?.agent_type === 'filesystem' ? '📁' : step.arguments?.agent_type === 'web' ? '🌐' : '🧠' }}</span>
                            <span class="tool-group-name">{{ formatAgentStep(step) }}</span>
                            <span v-if="step.arguments?.task" class="tool-group-task">{{ step.arguments.task }}</span>
                            <span class="tool-status" :class="step.status">
                              <template v-if="step.status === 'running'">⏳</template>
                              <template v-else-if="step.status === 'completed'">✓</template>
                              <template v-else>✗</template>
                            </span>
                            <ChevronRight :size="14" class="tool-expand-icon" :class="{ expanded: expandedSteps[`${index}-${bi}-${si}`] }" />
                          </div>
                          <!-- 展开内容 -->
                          <div v-if="expandedSteps[`${index}-${bi}-${si}`]" class="tool-group-body">
                            <div v-if="step.children?.length" class="tool-group-children">
                              <div v-for="(child, ci) in step.children" :key="ci" class="tool-step">
                                <div class="tool-step-header" @click="toggleStep(`${index}-${bi}-${si}-${ci}`)">
                                  <Wrench :size="14" class="tool-icon-lucide" />
                                  <span class="tool-name">{{ formatToolName(child) }}</span>
                                  <span class="tool-status" :class="child.status">
                                    <template v-if="child.status === 'running'">⏳</template>
                                    <template v-else-if="child.status === 'completed'">✓</template>
                                    <template v-else>✗</template>
                                  </span>
                                  <ChevronRight :size="14" class="tool-expand-icon" :class="{ expanded: expandedSteps[`${index}-${bi}-${si}-${ci}`] }" />
                                </div>
                                <div v-if="expandedSteps[`${index}-${bi}-${si}-${ci}`] && child.result" class="tool-step-detail">
                                  <div class="tool-result"><pre>{{ formatToolResult(child.result) }}</pre></div>
                                </div>
                              </div>
                            </div>
                            <div v-if="!step.children?.length && step.result" class="tool-group-body-result">
                              <pre>{{ formatToolResult(step.result) }}</pre>
                            </div>
                          </div>
                        </div>
                        <!-- 普通工具步骤（非 subagent） -->
                        <div v-else class="tool-step">
                          <div class="tool-step-header" @click="toggleStep(`${index}-${bi}-${si}`)">
                            <Wrench :size="14" class="tool-icon-lucide" />
                            <span class="tool-name">{{ formatToolName(step) }}</span>
                            <span class="tool-status" :class="step.status">
                              <template v-if="step.status === 'running'">⏳</template>
                              <template v-else-if="step.status === 'completed'">✓</template>
                              <template v-else>✗</template>
                            </span>
                            <ChevronRight :size="14" class="tool-expand-icon" :class="{ expanded: expandedSteps[`${index}-${bi}-${si}`] }" />
                          </div>
                          <div v-if="expandedSteps[`${index}-${bi}-${si}`] && step.result" class="tool-step-detail">
                            <div class="tool-result"><pre>{{ formatToolResult(step.result) }}</pre></div>
                          </div>
                        </div>
                      </template>
                    </div>
                  </template>
                  <!-- 思考中 -->
                  <div v-if="msg.isStreaming && !getBlocks(msg).length" class="thinking-bubble">
                    <div class="loading-dots"><span></span><span></span><span></span></div>
                  </div>
                </div>
            </div>
            
            <div v-if="isLoading" class="message-row assistant">
                <div class="avatar">✨</div>
                <div class="message-content-wrapper">
                  <div class="loading-bubble">
                    <div class="loading-dots">
                      <span></span><span></span><span></span>
                    </div>
                  </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Input Area -->
    <div class="chat-input-wrapper">
        <div class="chat-input-container">
            <textarea 
              class="chat-input" 
              v-model="inputMessage"
              placeholder="输入问题，按回车键发送..."
              @keydown="handleKeyPress"
              :disabled="isLoading"
              rows="1"
            ></textarea>
            <button class="send-btn" @click="sendMessage" :disabled="isLoading || !inputMessage.trim()">
                <Send class="send-icon" :size="16" />
            </button>
        </div>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
    background: #ffffff;
    position: relative;
    /* Ensure it acts perfectly inside main-content */
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
}

/* Variables from Polaris project theme */
:root {
    --primary-blue: #3b82f6;
    --sidebar-bg: #f1f5f9;
    --border-color: #e2e8f0;
    --text-dark: #1e293b;
    --text-light: #64748b;
}

/* Top Navigation Bar */
.chat-topbar {
    height: 70px;
    padding: 0 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid rgba(226, 232, 240, 0.6);
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(8px);
    z-index: 20;
    flex-shrink: 0;
}

.chat-title-group {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s;
    position: relative;
    user-select: none;
}

.chat-title-group:hover {
    background: #f1f5f9;
}

.chat-title {
    font-size: 16px;
    font-weight: 600;
    color: #1e293b;
}

.chevron-down {
    color: #64748b;
}

.workspace-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    color: #2563eb;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
}

.workspace-badge:hover {
    background: #dbeafe;
}

.workspace-badge.default {
    background: #f8fafc;
    border-color: #e2e8f0;
    color: #64748b;
    cursor: default;
}

.workspace-badge.default:hover {
    background: #f8fafc;
}

.history-dropdown {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    width: 320px;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
    z-index: 50;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    max-height: 400px;
}

.dropdown-header {
    padding: 12px 16px;
    font-size: 13px;
    font-weight: 600;
    color: #64748b;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
}

.select-all-label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    color: #94a3b8;
}

.select-all-label input {
    width: 13px;
    height: 13px;
    accent-color: #3b82f6;
    cursor: pointer;
}

.batch-delete-btn {
    font-size: 11px;
    padding: 3px 8px;
    border: 1px solid #fecaca;
    border-radius: 4px;
    background: #fef2f2;
    color: #dc2626;
    cursor: pointer;
}

.batch-delete-btn:hover {
    background: #fee2e2;
}

.select-checkbox {
    width: 15px;
    height: 15px;
    accent-color: #3b82f6;
    cursor: pointer;
    flex-shrink: 0;
    margin-right: 8px;
}

.dropdown-list {
    overflow-y: auto;
    flex: 1;
}

.history-item {
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #f1f5f9;
    cursor: pointer;
    transition: background-color 0.2s;
}

.history-item:hover {
    background-color: #f8fafc;
}

.history-item.active {
    background-color: #eff6ff;
}

.history-item-content {
    flex: 1;
    overflow: hidden;
}

.history-item-title {
    font-size: 14px;
    font-weight: 500;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 4px;
}

.history-item.active .history-item-title {
    color: #3b82f6;
}

.history-item-meta {
    display: flex;
    align-items: center;
    gap: 8px;
}

.history-item-workspace {
    font-size: 11px;
    font-weight: 500;
    padding: 1px 6px;
    border-radius: 4px;
    background: #eff6ff;
    color: #2563eb;
    white-space: nowrap;
}

.history-item-workspace.default {
    background: #f1f5f9;
    color: #94a3b8;
}

.history-item-time {
    font-size: 12px;
    color: #94a3b8;
}

.delete-btn {
    background: transparent;
    border: none;
    color: #cbd5e1;
    font-size: 14px;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    cursor: pointer;
    opacity: 0;
    transition: all 0.2s;
}

.history-item:hover .delete-btn {
    opacity: 1;
}

.delete-btn:hover {
    background: #fee2e2;
    color: #ef4444;
}

.empty-history {
    padding: 32px;
    text-align: center;
    color: #94a3b8;
    font-size: 14px;
}

.new-chat-btn {
    background: #3b82f6;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-weight: 500;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
    transition: all 0.2s;
}

.new-chat-btn:hover {
    background: #2563eb;
    box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3);
}

/* Centered Chat Layout */
.chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    overflow-y: auto;
    padding: 32px 0;
    scroll-behavior: smooth;
}

.chat-messages {
    width: 100%;
    max-width: 800px;
    display: flex;
    flex-direction: column;
    gap: 28px;
    padding: 0 24px 60px; /* Extra padding at bottom for input area */
    box-sizing: border-box;
}

.message-row {
    display: flex;
    gap: 16px;
    width: 100%;
    animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.message-row.user {
    flex-direction: row-reverse;
}

.avatar {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 18px;
    flex-shrink: 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.user .avatar {
    background-color: #1e293b;
    color: white;
}

.assistant .avatar {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
}

.message-content-wrapper {
    display: flex;
    flex-direction: column;
    max-width: 80%;
}

.message-bubble {
    padding: 14px 20px;
    border-radius: 12px;
    font-size: 15px;
    line-height: 1.6;
    word-break: break-word;
}

/* Markdown 渲染样式 */
.markdown-body :deep(p) {
    margin: 0 0 8px;
}

.markdown-body :deep(p:last-child) {
    margin-bottom: 0;
}

.markdown-body :deep(strong) {
    font-weight: 700;
    color: #1e293b;
}

.markdown-body :deep(em) {
    font-style: italic;
}

.markdown-body :deep(code) {
    background: #f1f5f9;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
}

.markdown-body :deep(pre) {
    background: #1e293b;
    color: #e2e8f0;
    padding: 12px 16px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 8px 0;
    font-size: 13px;
    line-height: 1.5;
}

.markdown-body :deep(pre code) {
    background: none;
    padding: 0;
    color: inherit;
    font-size: inherit;
}

.markdown-body :deep(ul), .markdown-body :deep(ol) {
    padding-left: 20px;
    margin: 4px 0;
}

.markdown-body :deep(li) {
    margin: 2px 0;
}

.markdown-body :deep(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 8px 0;
    font-size: 14px;
}

.markdown-body :deep(th), .markdown-body :deep(td) {
    border: 1px solid #e2e8f0;
    padding: 6px 12px;
    text-align: left;
}

.markdown-body :deep(th) {
    background: #f1f5f9;
    font-weight: 600;
}

.markdown-body :deep(blockquote) {
    border-left: 3px solid #3b82f6;
    padding-left: 12px;
    margin: 8px 0;
    color: #64748b;
}

.markdown-body :deep(h1), .markdown-body :deep(h2), .markdown-body :deep(h3) {
    margin: 12px 0 6px;
    font-weight: 700;
    color: #1e293b;
}

.markdown-body :deep(h1) { font-size: 18px; }
.markdown-body :deep(h2) { font-size: 16px; }
.markdown-body :deep(h3) { font-size: 15px; }

.markdown-body :deep(a) {
    color: #3b82f6;
    text-decoration: none;
}

.markdown-body :deep(a:hover) {
    text-decoration: underline;
}

.markdown-body :deep(hr) {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 12px 0;
}

.assistant .message-bubble {
    background-color: #f8fafc;
    color: #1e293b;
    border: 1px solid #e2e8f0;
    border-top-left-radius: 4px;
}

.user .message-bubble {
    background-color: #f1f5f9;
    color: #1e293b;
    border: 1px solid #e2e8f0;
    border-top-right-radius: 4px;
}

/* Loading state */
.loading-bubble {
    padding: 16px 24px;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    border-top-left-radius: 4px;
    display: inline-block;
}

.loading-dots {
  display: flex;
  gap: 5px;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  opacity: 0.6;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* Input Area */
.chat-input-wrapper {
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    display: flex;
    justify-content: center;
    padding: 24px;
    box-sizing: border-box;
    background: linear-gradient(to bottom, rgba(255,255,255,0) 0%, rgba(255,255,255,0.9) 30%, rgba(255,255,255,1) 100%);
    pointer-events: none; /* Let clicks pass through background */
}

.chat-input-container {
    pointer-events: auto; /* Re-enable clicks for input */
    width: 100%;
    max-width: 800px;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 16px;
    padding: 12px 16px;
    display: flex;
    align-items: flex-end;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
    transition: border-color 0.2s, box-shadow 0.2s;
}

.chat-input-container:focus-within {
    border-color: #3b82f6;
    box-shadow: 0 4px 20px rgba(59, 130, 246, 0.15);
}

.chat-input {
    flex: 1;
    border: none;
    outline: none;
    resize: none;
    min-height: 24px;
    max-height: 120px;
    font-size: 15px;
    font-family: inherit;
    color: #1e293b;
    padding: 4px 0;
    line-height: 1.5;
    background: transparent;
}

.chat-input::placeholder {
    color: #94a3b8;
}

.send-btn {
    background: #3b82f6;
    color: white;
    border: none;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    margin-left: 12px;
    flex-shrink: 0;
    transition: background 0.2s, transform 0.1s;
}

.send-btn:hover:not(:disabled) {
    background: #2563eb;
}

.send-btn:active:not(:disabled) {
    transform: scale(0.95);
}

.send-btn:disabled {
    background: #cbd5e1;
    cursor: not-allowed;
}

.send-icon {
    width: 16px;
    height: 16px;
}

/* 工具调用卡片 */
.tool-steps {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 8px;
}

/* 子 Agent 分组 */
.tool-group {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}

.tool-group-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    cursor: pointer;
    transition: background 0.15s;
    user-select: none;
    background: #f1f5f9;
}

.tool-group-header:hover {
    background: #e8eef5;
}

.tool-group-icon {
    font-size: 16px;
    flex-shrink: 0;
}

.tool-group-name {
    font-size: 13px;
    font-weight: 700;
    color: #1e293b;
    flex: 1;
}

.tool-group-task {
    font-size: 12px;
    color: #64748b;
    max-width: 300px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.tool-group-body {
    border-top: 1px solid #e2e8f0;
}

.tool-group-body-result {
    padding: 10px 14px;
    font-size: 13px;
    color: #1e293b;
    line-height: 1.5;
    border-top: 1px solid #e2e8f0;
}

.tool-group-body-result pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 300px;
    overflow-y: auto;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12px;
    background: #1e293b;
    color: #e2e8f0;
    padding: 10px 14px;
    border-radius: 6px;
}

.tool-group-children {
    padding: 4px 8px 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.tool-group-children .tool-step {
    border-left: 2px solid #93c5fd;
    background: #ffffff;
}

.tool-step {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #3b82f6;
    border-radius: 8px;
    overflow: hidden;
}

.tool-step-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    cursor: pointer;
    transition: background 0.15s;
    user-select: none;
}

.tool-step-header:hover {
    background: #f1f5f9;
}

.tool-icon-lucide {
    color: #3b82f6;
    flex-shrink: 0;
}

.tool-name {
    font-size: 13px;
    font-weight: 600;
    color: #1e293b;
    flex: 1;
}

.tool-status {
    font-size: 12px;
    font-weight: 700;
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
}

.tool-status.completed {
    color: #22c55e;
}

.tool-status.error {
    color: #ef4444;
}

.tool-expand-icon {
    color: #cbd5e1;
    transition: transform 0.2s;
    flex-shrink: 0;
}

.tool-expand-icon.expanded {
    transform: rotate(90deg);
}

.tool-step-detail {
    padding: 10px 14px;
    border-top: 1px solid #f1f5f9;
    background: #ffffff;
}

.tool-task {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 6px;
}

.tool-task::before {
    content: '任务: ';
    font-weight: 600;
    color: #94a3b8;
}

.tool-result {
    font-size: 13px;
    color: #1e293b;
    line-height: 1.5;
}

.tool-result pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 300px;
    overflow-y: auto;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12px;
    background: #1e293b;
    color: #e2e8f0;
    padding: 10px 14px;
    border-radius: 6px;
}

.tool-result::before {
    content: '结果: ';
    font-weight: 600;
    color: #94a3b8;
    display: block;
    margin-bottom: 6px;
}

/* 思考中气泡 */
.thinking-bubble {
    padding: 16px 24px;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    border-top-left-radius: 4px;
    display: inline-block;
}

/* 打字光标 */
.typing-cursor {
    animation: cursor-blink 1s infinite;
    color: #3b82f6;
    font-weight: bold;
}

@keyframes cursor-blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}

/* 思维链块 */
.reasoning-block {
    margin: 6px 0;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    overflow: hidden;
    background: #f8fafc;
}

.reasoning-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    cursor: pointer;
    user-select: none;
    font-size: 12px;
    color: #94a3b8;
    transition: background 0.2s;
}

.reasoning-header:hover {
    background: #f1f5f9;
}

.reasoning-icon {
    font-size: 13px;
}

.reasoning-label {
    font-weight: 600;
    letter-spacing: 0.03em;
}

.reasoning-toggle {
    margin-left: auto;
    font-size: 11px;
    color: #cbd5e1;
}

.reasoning-content {
    padding: 10px 14px;
    font-size: 13px;
    line-height: 1.6;
    color: #64748b;
    white-space: pre-wrap;
    border-top: 1px solid #f1f5f9;
    max-height: 300px;
    overflow-y: auto;
}

/* 思维链收起动画 */
.reasoning-collapse-enter-active,
.reasoning-collapse-leave-active {
    transition: max-height 0.35s ease, padding 0.35s ease, opacity 0.25s ease;
    overflow: hidden;
}
.reasoning-collapse-enter-from,
.reasoning-collapse-leave-to {
    max-height: 0;
    padding-top: 0;
    padding-bottom: 0;
    opacity: 0;
}
.reasoning-collapse-enter-to,
.reasoning-collapse-leave-from {
    max-height: 300px;
    padding-top: 10px;
    padding-bottom: 10px;
    opacity: 1;
}
</style>
