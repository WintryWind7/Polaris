<script setup>
import { ref, onMounted, onUnmounted, nextTick, reactive } from 'vue'
import { Send, ChevronRight, Wrench } from 'lucide-vue-next'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const API_BASE = ''
const SSE_BASE = import.meta.env.DEV ? 'http://127.0.0.1:6547' : ''

const messages = ref([])
const inputMessage = ref('')
const isLoading = ref(false)
const chatArea = ref(null)
const tokenStats = ref({ prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 })

const expandedSteps = reactive({})
const expandedGroups = reactive({})

function toggleStep(key) { expandedSteps[key] = !expandedSteps[key] }
function toggleGroup(key) { expandedGroups[key] = !expandedGroups[key] }

function parseToolSteps(msg) {
  if (!msg.tool_calls?.length) return []
  return msg.tool_calls.map((tc, i) => {
    const args = JSON.parse(tc.function?.arguments || '{}')
    const tr = msg.tool_results?.[i]
    let resultData = {}
    try { resultData = JSON.parse(tr?.content || '{}') } catch {}
    return {
      tool_name: tc.function?.name || '',
      arguments: args,
      result: resultData.response || resultData.error || '',
      status: resultData.success ? 'completed' : 'error'
    }
  })
}

const TOOL_DISPLAY = {
  list_directory: '列出目录', read_file: '读取文件', write_file: '写入文件',
  search_files: '搜索文件', search_content: '搜索内容',
  web_search: '网络搜索', web_fetch: '抓取网页',
  search_memory: '检索记忆', ask_main_agent: '询问主 Agent',
}

const AGENT_DISPLAY = { coding: '编码助手', web: '网络搜索', memory: '记忆检索' }

function formatToolName(step) { return TOOL_DISPLAY[step.tool_name] || step.tool_name }
function formatAgentStep(step) {
  if (step.tool_name !== 'subagent') return ''
  return AGENT_DISPLAY[step.arguments?.agent_type] || step.arguments?.agent_type || ''
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function groupConsecutiveSteps(steps) {
  // 将连续相同 instance_id 的 subagent step 合并为组
  // 非 subagent step 保持独立
  const groups = []
  let i = 0
  while (i < steps.length) {
    const step = steps[i]
    if (step.tool_name === 'subagent') {
      const instanceId = step.arguments?.instance_id || ''
      const agentType = step.arguments?.agent_type || ''
      const turns = []
      while (i < steps.length &&
             steps[i].tool_name === 'subagent' &&
             (steps[i].arguments?.instance_id || '') === instanceId) {
        turns.push(steps[i])
        i++
      }
      groups.push({ type: 'subagent_group', instanceId, agentType, turns })
    } else {
      groups.push({ type: 'tool_step', step })
      i++
    }
  }
  return groups
}

function renderMarkdown(text) { return text ? marked.parse(text) : '' }

function getBlocks(msg) {
  if (msg.blocks?.length) return msg.blocks
  const blocks = []
  let contentUsedAsTools = false
  if (msg.tool_calls?.length) {
    blocks.push({ type: 'tools', steps: msg.steps?.length ? msg.steps : parseToolSteps(msg) })
  }
  if (!msg.tool_calls?.length && msg.content) {
    try {
      const parsed = JSON.parse(msg.content)
      if (Array.isArray(parsed) && parsed[0]?.function) {
        blocks.push({ type: 'tools', steps: parseToolSteps({ tool_calls: parsed, tool_results: [] }) })
        contentUsedAsTools = true
      }
    } catch {}
  }
  if (msg.content && !contentUsedAsTools) {
    blocks.push({ type: 'text', content: msg.content })
  }
  if (msg.reasoning_content) {
    blocks.unshift({ type: 'reasoning', content: msg.reasoning_content, _expanded: false })
  }
  return blocks
}

function renderBlockContent(block, showCursor) {
  if (!block.content) return ''
  const html = renderMarkdown(block.content)
  return showCursor ? html + '<span class="typing-cursor">|</span>' : html
}

function formatToolResult(result) {
  if (!result) return ''
  try { return JSON.stringify(JSON.parse(result), null, 2) } catch { return result }
}

// ---- Stream event handling ----

function handleStreamEvent(event, assistantMsg) {
  if (event.type === 'tool_call' && assistantMsg) {
    const newStep = {
      tool_name: event.tool_name, arguments: event.arguments,
      result: '', status: 'running',
      _createdAt: new Date().toISOString()
    }
    const lastBlock = assistantMsg.blocks[assistantMsg.blocks.length - 1]
    if (lastBlock?.type === 'tools') {
      lastBlock.steps.push(newStep)
    } else {
      assistantMsg.blocks.push({ type: 'tools', steps: [newStep] })
    }
    // 子 Agent 调用自动展开：新 instance_id 时展开卡片
    if (event.tool_name === 'subagent') {
      const bi = assistantMsg.blocks.length - 1
      const steps = assistantMsg.blocks[bi].steps
      const msgIdx = messages.value.indexOf(assistantMsg)
      const instanceId = event.arguments?.instance_id || ''
      // 检查是否和上一个 step 属于同一组（同一个 instance_id）
      const prevStep = steps.length > 1 ? steps[steps.length - 2] : null
      const prevId = prevStep?.arguments?.instance_id
      if (prevId !== instanceId) {
        expandedGroups[`${msgIdx}-${bi}-${instanceId}`] = true
      }
    }
  } else if (event.type === 'tool_result' && assistantMsg) {
    let lastToolsBlock = null
    for (let i = assistantMsg.blocks.length - 1; i >= 0; i--) {
      if (assistantMsg.blocks[i].type === 'tools') { lastToolsBlock = assistantMsg.blocks[i]; break }
    }
    if (lastToolsBlock) {
      for (let i = lastToolsBlock.steps.length - 1; i >= 0; i--) {
        const s = lastToolsBlock.steps[i]
        if (s.tool_name === event.tool_name && s.status === 'running') {
          s.result = event.result; s.status = event.status; break
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
    for (const block of assistantMsg.blocks) {
      if (block.type === 'reasoning' && block._expanded && !block._complete) {
        block._complete = true
        block._showDone = true
        setTimeout(() => { block._showDone = false }, 2000)
        setTimeout(() => { block._expanded = false; block._collapsing = false }, 1000)
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
  } else if (event.type === 'usage') {
    tokenStats.value = event.usage || {}
  }
}

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
        try { onEvent(JSON.parse(data)) } catch (parseErr) { console.error('SSE parse error:', parseErr) }
      }
      await new Promise(r => requestAnimationFrame(r))
      scrollToBottom()
    }
  }
}

async function sendMessage() {
  const message = inputMessage.value.trim()
  if (!message || isLoading.value) return

  const userMsg = { role: 'user', content: message, timestamp: new Date().toISOString() }
  userMsg.blocks = getBlocks(userMsg)
  messages.value.push(userMsg)
  inputMessage.value = ''
  isLoading.value = true
  await nextTick()
  scrollToBottom()

  let assistantMsg = null
  try {
    const response = await fetch(`${SSE_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body.getReader()
    await readSSEStream(reader, (event) => {
      if (event.type === 'session') {
        isLoading.value = false
        messages.value.push({
          role: 'assistant', blocks: [], timestamp: null, isStreaming: true
        })
        assistantMsg = messages.value[messages.value.length - 1]
      } else if (event.type === 'error') {
        if (!assistantMsg) {
          isLoading.value = false
          assistantMsg = { role: 'assistant', blocks: [], timestamp: new Date().toISOString(), isStreaming: false }
          messages.value.push(assistantMsg)
        }
        const lastBlock = assistantMsg.blocks[assistantMsg.blocks.length - 1]
        if (lastBlock?.type === 'text') {
          lastBlock.content += `\n\n错误: ${event.message}`
        } else {
          assistantMsg.blocks.push({ type: 'text', content: `错误: ${event.message}` })
        }
        assistantMsg.isStreaming = false
      } else if (event.type === 'usage') {
        tokenStats.value = event.usage || {}
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

async function loadHistory() {
  try {
    const [histResp, tokenResp] = await Promise.all([
      fetch(`${API_BASE}/api/chat/history`),
      fetch(`${API_BASE}/api/token-usage`)
    ])
    if (tokenResp.ok) {
      tokenStats.value = await tokenResp.json()
    }
    if (histResp.ok) {
      const data = await histResp.json()
      if (data.messages?.length) {
        // 在赋值给响应式 messages 之前预先计算并固化 blocks，避免渲染期间触发连锁更新
        for (const msg of data.messages) {
          msg.blocks = getBlocks(msg)
        }
        messages.value = data.messages
        await nextTick()
        scrollToBottom()
      }
    }
  } catch (err) { console.error('Failed to load history:', err) }
}

function scrollToBottom() {
  if (chatArea.value) chatArea.value.scrollTop = chatArea.value.scrollHeight
}

function handleKeyPress(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

onMounted(loadHistory)
</script>

<template>
  <div class="chat-view">
    <div class="chat-main">
      <div class="chat-topbar">
        <span class="chat-title">Polaris</span>
      </div>

      <div class="chat-container" ref="chatArea">
      <div class="chat-messages">
        <div class="message-row" v-for="(msg, index) in messages" :key="index" :class="msg.role">
          <div class="avatar">{{ msg.role === 'user' ? 'U' : '✨' }}</div>
          <div class="message-content-wrapper">
            <template v-for="(block, bi) in getBlocks(msg)" :key="bi">
              <div v-if="block.type === 'reasoning' && block.content" class="reasoning-block">
                <div class="reasoning-header" @click="block._expanded = !block._expanded; block._collapsing = false">
                  <span class="reasoning-icon">{{ block._complete ? '💡' : '💭' }}</span>
                  <span class="reasoning-label">
                    <span class="label-text" :class="{ hide: block._showDone }">思考过程</span>
                    <span class="label-done" :class="{ show: block._showDone }">思考完成</span>
                  </span>
                  <span class="reasoning-toggle">{{ block._expanded ? '收起' : (block._collapsing ? '收起中…' : '展开') }}</span>
                </div>
                <Transition name="reasoning-collapse">
                  <div v-if="block._expanded" class="reasoning-content">{{ block.content }}</div>
                </Transition>
              </div>
              <div v-if="block.type === 'text' && block.content" class="message-bubble markdown-body"
                   v-html="renderBlockContent(block, msg.isStreaming && bi === getBlocks(msg).length - 1)">
              </div>
              <div v-if="block.type === 'tools' && block.steps?.length" class="tool-steps">
                <template v-for="(group, gi) in groupConsecutiveSteps(block.steps)" :key="gi">
                  <!-- 子 Agent 对话卡片（按 instance_id 合并多轮） -->
                  <div v-if="group.type === 'subagent_group'" class="subagent-card">
                    <div class="subagent-header" @click="toggleGroup(`${index}-${bi}-${group.instanceId}`)">
                      <span class="subagent-icon">{{ group.agentType === 'coding' ? '\u{1F527}' : group.agentType === 'web' ? '\u{1F310}' : '\u{1F9E0}' }}</span>
                      <span class="subagent-name">{{ AGENT_DISPLAY[group.agentType] || group.agentType }}</span>
                      <span class="subagent-status" :class="group.turns[group.turns.length - 1].status">
                        <template v-if="group.turns[group.turns.length - 1].status === 'running'">⏳</template>
                        <template v-else-if="group.turns[group.turns.length - 1].status === 'completed'">✓</template>
                        <template v-else>✗</template>
                      </span>
                      <ChevronRight :size="14" class="tool-expand-icon" :class="{ expanded: expandedGroups[`${index}-${bi}-${group.instanceId}`] }" />
                    </div>
                    <Transition name="reasoning-collapse">
                      <div v-if="expandedGroups[`${index}-${bi}-${group.instanceId}`]" class="subagent-body">
                        <div class="subagent-meta">
                          <span class="meta-label">新建</span>
                          <span class="meta-sep">·</span>
                          <span class="meta-id">{{ group.instanceId }}</span>
                          <span class="meta-sep">·</span>
                          <span class="meta-time">{{ formatTime(group.turns[0]._createdAt) }}</span>
                        </div>
                        <template v-for="(turn, ti) in group.turns" :key="ti">
                          <div v-if="ti > 0" class="turn-separator"></div>
                          <div class="conv-msg-main">
                            <div class="conv-role">主Agent</div>
                            <div class="conv-content">{{ turn.arguments?.message || turn.arguments?.task || '' }}</div>
                          </div>
                          <div v-if="turn.result" class="conv-msg-sub">
                            <div class="conv-role">子Agent</div>
                            <div class="conv-content markdown-body" v-html="renderMarkdown(turn.result)"></div>
                          </div>
                          <div v-else class="conv-waiting">
                            <div class="loading-dots"><span></span><span></span><span></span></div>
                          </div>
                        </template>
                      </div>
                    </Transition>
                  </div>
                  <!-- 普通工具调用 -->
                  <div v-else class="tool-step">
                    <div class="tool-step-header" @click="toggleStep(`${index}-${bi}-${gi}`)">
                      <Wrench :size="14" class="tool-icon-lucide" />
                      <span class="tool-name">{{ formatToolName(group.step) }}</span>
                      <span class="tool-status" :class="group.step.status">
                        <template v-if="group.step.status === 'running'">⏳</template>
                        <template v-else-if="group.step.status === 'completed'">✓</template>
                        <template v-else>✗</template>
                      </span>
                      <ChevronRight :size="14" class="tool-expand-icon" :class="{ expanded: expandedSteps[`${index}-${bi}-${gi}`] }" />
                    </div>
                    <div v-if="expandedSteps[`${index}-${bi}-${gi}`] && group.step.result" class="tool-step-detail">
                      <div class="tool-result"><pre>{{ formatToolResult(group.step.result) }}</pre></div>
                    </div>
                  </div>
                </template>
              </div>
            </template>
            <div v-if="msg.isStreaming && !getBlocks(msg).length" class="thinking-bubble">
              <div class="loading-dots"><span></span><span></span><span></span></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    </div><!-- /.chat-main -->

    <!-- 右侧监控侧边栏 -->
    <div class="monitor-sidebar">
      <div class="sidebar-title">📊 监控台</div>
      <div class="stat-row">
        <span class="stat-label">Prompt</span>
        <span class="stat-value">{{ tokenStats.prompt_tokens.toLocaleString() }}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Completion</span>
        <span class="stat-value">{{ tokenStats.completion_tokens.toLocaleString() }}</span>
      </div>
      <div class="stat-row total">
        <span class="stat-label">Total</span>
        <span class="stat-value">{{ tokenStats.total_tokens.toLocaleString() }}</span>
      </div>
      <div class="context-bar">
        <div class="context-bar-label">
          <span>上下文用量</span>
          <span>{{ (tokenStats.prompt_tokens / 1000000 * 100).toFixed(2) }}%</span>
        </div>
        <div class="context-bar-track">
          <div class="context-bar-fill" :style="{ width: Math.min(tokenStats.prompt_tokens / 1000000 * 100, 100) + '%' }"></div>
        </div>
        <div class="context-bar-limit">{{ tokenStats.prompt_tokens.toLocaleString() }} / 1,000,000</div>
      </div>
    </div>

    <div class="chat-input-wrapper">
      <div class="chat-input-container">
        <textarea class="chat-input" v-model="inputMessage" placeholder="输入问题，按回车键发送..."
                  @keydown="handleKeyPress" :disabled="isLoading" rows="1"></textarea>
        <button class="send-btn" @click="sendMessage" :disabled="isLoading || !inputMessage.trim()">
          <Send class="send-icon" :size="16" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex; height: 100%; width: 100%;
  background: #ffffff;
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
}
.chat-main {
  flex: 1; display: flex; flex-direction: column; min-width: 0;
}

.chat-topbar {
  height: 56px; padding: 0 32px;
  display: flex; align-items: center;
  border-bottom: 1px solid #e2e8f0;
  background: #ffffff; z-index: 20; flex-shrink: 0;
}

.chat-title {
  font-size: 16px; font-weight: 700; color: #1e293b;
}

.chat-container {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  overflow-y: auto; padding: 32px 0; scroll-behavior: smooth;
}

.chat-messages {
  width: 100%; max-width: 700px;
  display: flex; flex-direction: column; gap: 28px;
  padding: 0 24px 80px 24px; box-sizing: border-box;
}

.message-row { display: flex; gap: 16px; width: 100%; animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.message-row.user { flex-direction: row-reverse; }

.avatar {
  width: 38px; height: 38px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-weight: bold; font-size: 18px; flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.user .avatar { background-color: #1e293b; color: white; }
.assistant .avatar { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; }

.message-content-wrapper { display: flex; flex-direction: column; max-width: 80%; }

.message-bubble {
  padding: 14px 20px; border-radius: 12px; font-size: 15px;
  line-height: 1.6; word-break: break-word;
}
.assistant .message-bubble { background-color: #f8fafc; color: #1e293b; border: 1px solid #e2e8f0; border-top-left-radius: 4px; }
.user .message-bubble { background-color: #f1f5f9; color: #1e293b; border: 1px solid #e2e8f0; border-top-right-radius: 4px; }

/* Markdown */
.markdown-body :deep(p) { margin: 0 0 8px; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(strong) { font-weight: 700; color: #1e293b; }
.markdown-body :deep(code) { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px; font-family: monospace; }
.markdown-body :deep(pre) { background: #1e293b; color: #e2e8f0; padding: 12px 16px; border-radius: 8px; overflow-x: auto; margin: 8px 0; font-size: 13px; }
.markdown-body :deep(pre code) { background: none; padding: 0; color: inherit; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; margin: 4px 0; }
.markdown-body :deep(blockquote) { border-left: 3px solid #3b82f6; padding-left: 12px; margin: 8px 0; color: #64748b; }
.markdown-body :deep(h1), .markdown-body :deep(h2), .markdown-body :deep(h3) { margin: 12px 0 6px; font-weight: 700; }
.markdown-body :deep(h1) { font-size: 18px; }
.markdown-body :deep(h2) { font-size: 16px; }
.markdown-body :deep(a) { color: #3b82f6; }

.thinking-bubble { padding: 16px 24px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; border-top-left-radius: 4px; display: inline-block; }

.loading-dots { display: flex; gap: 5px; }
.loading-dots span { width: 6px; height: 6px; border-radius: 50%; background: #3b82f6; opacity: 0.6; animation: bounce 1.4s infinite ease-in-out both; }
.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }

.typing-cursor { animation: cursor-blink 1s infinite; color: #3b82f6; font-weight: bold; }
@keyframes cursor-blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }

/* Input */
.chat-input-wrapper {
  position: absolute; bottom: 0; left: 0; width: 100%;
  display: flex; justify-content: center; padding: 24px; box-sizing: border-box;
  background: linear-gradient(to bottom, rgba(255,255,255,0) 0%, rgba(255,255,255,0.9) 30%, rgba(255,255,255,1) 100%);
  pointer-events: none;
}
.chat-input-container {
  pointer-events: auto; width: 100%; max-width: 700px;
  background: #ffffff; border: 1px solid #cbd5e1; border-radius: 16px;
  padding: 12px 16px; display: flex; align-items: flex-end;
  box-shadow: 0 4px 20px rgba(0,0,0,0.05); transition: border-color 0.2s, box-shadow 0.2s;
}
.chat-input-container:focus-within { border-color: #3b82f6; box-shadow: 0 4px 20px rgba(59,130,246,0.15); }
.chat-input {
  flex: 1; border: none; outline: none; resize: none;
  min-height: 24px; max-height: 120px; font-size: 15px; font-family: inherit;
  color: #1e293b; padding: 4px 0; line-height: 1.5; background: transparent;
}
.chat-input::placeholder { color: #94a3b8; }
.send-btn {
  background: #3b82f6; color: white; border: none;
  width: 36px; height: 36px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; margin-left: 12px; flex-shrink: 0;
  transition: background 0.2s, transform 0.1s;
}
.send-btn:hover:not(:disabled) { background: #2563eb; }
.send-btn:active:not(:disabled) { transform: scale(0.95); }
.send-btn:disabled { background: #cbd5e1; cursor: not-allowed; }

/* Tool cards */
.tool-steps { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px; }

/* Sub-agent conversation card */
.subagent-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.subagent-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  cursor: pointer; transition: background 0.15s; user-select: none;
}
.subagent-header:hover { background: #f1f5f9; }
.subagent-icon { font-size: 16px; flex-shrink: 0; }
.subagent-name { font-size: 13px; font-weight: 700; color: #1e293b; flex: 1; }
.subagent-status { font-size: 12px; font-weight: 700; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; border-radius: 50%; flex-shrink: 0; }
.subagent-status.completed { color: #22c55e; }
.subagent-status.error { color: #ef4444; }
.subagent-body { border-top: 1px solid #e2e8f0; background: #ffffff; }

/* Metadata row */
.subagent-meta {
  padding: 6px 14px; font-size: 11px; color: #94a3b8;
  display: flex; align-items: center; gap: 4px;
  background: #fafafa; border-bottom: 1px solid #f1f5f9;
}
.meta-label { color: #22c55e; font-weight: 600; }
.meta-sep { color: #cbd5e1; }
.meta-id { font-family: monospace; }
.meta-time { color: #94a3b8; }

/* Turn separator */
.turn-separator {
  height: 1px; background: #f1f5f9;
  margin: 0 14px;
}
/* Conversation turns */
.conv-msg-main, .conv-msg-sub { padding: 10px 14px; }
.conv-msg-main { padding-bottom: 6px; }
.conv-msg-sub { padding-top: 6px; }
.conv-role { font-size: 11px; font-weight: 700; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
.conv-msg-main .conv-role { color: #3b82f6; }
.conv-msg-sub .conv-role { color: #8b5cf6; }
.conv-msg-main .conv-content { font-size: 13px; color: #475569; line-height: 1.6; white-space: pre-wrap; }
.conv-msg-sub .conv-content { font-size: 13px; line-height: 1.6; }
.conv-waiting { padding: 14px; display: flex; align-items: center; justify-content: center; }

.tool-step { background: #f8fafc; border: 1px solid #e2e8f0; border-left: 3px solid #3b82f6; border-radius: 8px; overflow: hidden; }
.tool-step-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  cursor: pointer; transition: background 0.15s; user-select: none;
}
.tool-step-header:hover { background: #f1f5f9; }
.tool-icon-lucide { color: #3b82f6; flex-shrink: 0; }
.tool-name { font-size: 13px; font-weight: 600; color: #1e293b; flex: 1; }
.tool-status { font-size: 12px; font-weight: 700; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; border-radius: 50%; }
.tool-status.completed { color: #22c55e; }
.tool-status.error { color: #ef4444; }
.tool-expand-icon { color: #cbd5e1; transition: transform 0.2s; flex-shrink: 0; }
.tool-expand-icon.expanded { transform: rotate(90deg); }
.tool-step-detail { padding: 10px 14px; border-top: 1px solid #f1f5f9; background: #ffffff; }
.tool-result pre {
  margin: 0; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto;
  font-family: monospace; font-size: 12px; background: #1e293b; color: #e2e8f0; padding: 10px 14px; border-radius: 6px;
}

/* Reasoning */
.reasoning-block { margin: 6px 0; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; background: #f8fafc; }
.reasoning-header {
  display: flex; align-items: center; gap: 6px; padding: 8px 14px;
  cursor: pointer; user-select: none; font-size: 12px; color: #94a3b8; transition: background 0.2s;
}
.reasoning-header:hover { background: #f1f5f9; }
.reasoning-icon { font-size: 13px; }
.reasoning-label { font-weight: 600; position: relative; display: inline-block; }
.label-text, .label-done { transition: opacity 0.5s ease; }
.label-text.hide { opacity: 0; }
.label-done { position: absolute; left: 0; top: 0; opacity: 0; color: #22c55e; }
.label-done.show { opacity: 1; }
.reasoning-toggle { margin-left: auto; font-size: 11px; color: #cbd5e1; }
.reasoning-content {
  padding: 10px 14px; font-size: 13px; line-height: 1.6; color: #64748b;
  white-space: pre-wrap; border-top: 1px solid #f1f5f9; max-height: 300px; overflow-y: auto;
}
.reasoning-collapse-enter-active, .reasoning-collapse-leave-active {
  transition: max-height 0.35s ease, padding 0.35s ease, opacity 0.25s ease; overflow: hidden;
}
.reasoning-collapse-enter-from, .reasoning-collapse-leave-to { max-height: 0; padding-top: 0; padding-bottom: 0; opacity: 0; }
.reasoning-collapse-enter-to, .reasoning-collapse-leave-from { max-height: 300px; padding-top: 10px; padding-bottom: 10px; opacity: 1; }

/* 右侧监控侧边栏 */
.monitor-sidebar {
  width: 240px; padding: 20px 16px;
  border-left: 1px solid #e2e8f0;
  background: #f8fafc;
  overflow-y: auto; flex-shrink: 0;
}
.sidebar-title { font-size: 14px; font-weight: 700; color: #1e293b; margin-bottom: 16px; }
.stat-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid #f1f5f9; }
.stat-row.total { border-bottom: none; margin-top: 2px; border-top: 1px solid #e2e8f0; padding-top: 10px; }
.stat-label { font-size: 11px; color: #94a3b8; font-weight: 500; }
.stat-value { font-size: 13px; color: #1e293b; font-weight: 600; font-variant-numeric: tabular-nums; }
.stat-row.total .stat-label { color: #64748b; }
.stat-row.total .stat-value { color: #3b82f6; font-size: 15px; }
.context-bar { margin-top: 12px; }
.context-bar-label { display: flex; justify-content: space-between; font-size: 10px; color: #94a3b8; margin-bottom: 4px; }
.context-bar-track { height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; }
.context-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #22c55e); border-radius: 3px; transition: width 0.5s ease; min-width: 2px; }
.context-bar-limit { font-size: 9px; color: #cbd5e1; text-align: right; margin-top: 2px; }
</style>
