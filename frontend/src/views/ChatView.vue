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

const expandedSteps = reactive({})

function toggleStep(key) { expandedSteps[key] = !expandedSteps[key] }

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
      status: resultData.success ? 'completed' : 'error',
      children: [],
      _expanded: false,
      _conversation: resultData.conversation || []
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

function renderSubText(content) { return content ? marked.parse(content) : '' }

// ---- Stream event handling ----
let _inSubagent = false

function _findSubagentStep(assistantMsg) {
  for (let i = assistantMsg.blocks.length - 1; i >= 0; i--) {
    const block = assistantMsg.blocks[i]
    if (block.type === 'tools') {
      for (let j = block.steps.length - 1; j >= 0; j--) {
        if (block.steps[j].tool_name === 'subagent') return block.steps[j]
      }
    }
  }
  return null
}

function handleStreamEvent(event, assistantMsg) {
  if (event.type === 'tool_call' && event.tool_name === 'subagent') _inSubagent = true

  if (_inSubagent && event.tool_name !== 'subagent') {
    const subStep = _findSubagentStep(assistantMsg)
    if (subStep) {
      if (!subStep._conversation) subStep._conversation = []
      const conv = subStep._conversation
      if ((event.type === 'text' || event.type === 'reasoning') && conv.length > 0) {
        const last = conv[conv.length - 1]
        if (last.type === event.type) {
          last.content = (last.content || '') + (event.content || '')
          subStep._expanded = true
          return
        }
      }
      conv.push({ ...event })
      subStep._expanded = true
    }
    return
  }

  if (event.type === 'tool_result' && event.tool_name === 'subagent') {
    _inSubagent = false
    const subStep = _findSubagentStep(assistantMsg)
    if (subStep) {
      subStep._complete = true
      setTimeout(() => { subStep._expanded = false; subStep._collapsing = false }, 1000)
      subStep._collapsing = true
    }
  }

  if (event.type === 'tool_call' && assistantMsg) {
    const newStep = {
      tool_name: event.tool_name, arguments: event.arguments,
      result: '', status: 'running', children: [],
      ...(event.tool_name === 'subagent' ? { _expanded: true } : {})
    }
    const lastBlock = assistantMsg.blocks[assistantMsg.blocks.length - 1]
    if (lastBlock?.type === 'tools') {
      if (event.tool_name === 'subagent') {
        lastBlock.steps.push(newStep)
      } else {
        const lastStep = lastBlock.steps[lastBlock.steps.length - 1]
        if (lastStep?.tool_name === 'subagent') {
          lastStep.children.push(newStep)
        } else { lastBlock.steps.push(newStep) }
      }
    } else {
      assistantMsg.blocks.push({ type: 'tools', steps: [newStep] })
    }
  } else if (event.type === 'tool_result' && assistantMsg) {
    let lastToolsBlock = null
    for (let i = assistantMsg.blocks.length - 1; i >= 0; i--) {
      if (assistantMsg.blocks[i].type === 'tools') { lastToolsBlock = assistantMsg.blocks[i]; break }
    }
    if (lastToolsBlock) {
      const steps = lastToolsBlock.steps
      const lastStep = steps[steps.length - 1]
      let found = false
      if (lastStep?.tool_name === 'subagent') {
        for (let i = lastStep.children.length - 1; i >= 0; i--) {
          const c = lastStep.children[i]
          if (c.tool_name === event.tool_name && c.status === 'running') {
            c.result = event.result; c.status = event.status; found = true; break
          }
        }
      }
      if (!found) {
        for (let i = steps.length - 1; i >= 0; i--) {
          const s = steps[i]
          if (s.tool_name === event.tool_name && s.status === 'running') {
            s.result = event.result; s.status = event.status; break
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
    for (const block of assistantMsg.blocks) {
      if (block.type === 'reasoning' && block._expanded && !block._complete) {
        block._complete = true
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

  messages.value.push({ role: 'user', content: message, timestamp: new Date().toISOString() })
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
    const resp = await fetch(`${API_BASE}/api/chat/history`)
    if (resp.ok) {
      const data = await resp.json()
      if (data.messages?.length) {
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
                  <span class="reasoning-label">{{ block._complete ? '思考完成' : '思考过程' }}</span>
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
                <template v-for="(step, si) in block.steps" :key="si">
                  <div v-if="step.tool_name === 'subagent'" class="tool-group">
                    <div class="tool-group-header" @click="step._expanded = step._expanded === false ? true : false; step._collapsing = false">
                      <span class="tool-group-icon">{{ step.arguments?.agent_type === 'coding' ? '\u{1F527}' : step.arguments?.agent_type === 'web' ? '\u{1F310}' : '\u{1F9E0}' }}</span>
                      <span class="tool-group-name">{{ formatAgentStep(step) }}</span>
                      <span v-if="step.arguments?.task" class="tool-group-task">{{ step.arguments.task }}</span>
                      <span class="tool-status" :class="step.status">
                        <template v-if="step.status === 'running'">⏳</template>
                        <template v-else-if="step.status === 'completed'">✓</template>
                        <template v-else>✗</template>
                      </span>
                      <span class="tool-group-toggle">{{ step._expanded !== false ? '收起' : (step._collapsing ? '收起中…' : '展开') }}</span>
                      <ChevronRight :size="14" class="tool-expand-icon" :class="{ expanded: step._expanded !== false }" />
                    </div>
                    <Transition name="reasoning-collapse">
                      <div v-if="step._expanded !== false" class="tool-group-body">
                        <div v-if="step._conversation?.length" class="sub-conversation">
                          <div v-for="(entry, ei) in step._conversation" :key="ei">
                            <div v-if="entry.type === 'reasoning' && entry.content" class="sub-reasoning">
                              <div class="sub-reasoning-header"><span>💭 思考</span></div>
                              <div class="sub-reasoning-content">{{ entry.content }}</div>
                            </div>
                            <div v-else-if="entry.type === 'tool_call'" class="sub-tool-call">
                              <span class="sub-tool-icon">🔧</span>
                              <span class="sub-tool-name">{{ formatToolName(entry) }}</span>
                              <span class="sub-tool-status running">⏳</span>
                            </div>
                            <div v-else-if="entry.type === 'tool_result'" class="sub-tool-result">
                              <span class="sub-tool-icon">📋</span>
                              <span class="sub-tool-name">{{ formatToolName(entry) }}</span>
                              <span class="sub-tool-status" :class="entry.status">{{ entry.status === 'completed' ? '✓' : '✗' }}</span>
                              <div v-if="entry.result" class="sub-tool-result-text"><pre>{{ formatToolResult(entry.result) }}</pre></div>
                            </div>
                            <div v-else-if="entry.type === 'text' && entry.content" class="sub-text" v-html="renderSubText(entry.content)"></div>
                          </div>
                        </div>
                        <div v-if="step.result" class="tool-group-body-result">
                          <pre>{{ formatToolResult(step.result) }}</pre>
                        </div>
                      </div>
                    </Transition>
                  </div>
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
            <div v-if="msg.isStreaming && !getBlocks(msg).length" class="thinking-bubble">
              <div class="loading-dots"><span></span><span></span><span></span></div>
            </div>
          </div>
        </div>
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
  display: flex; flex-direction: column; height: 100%; width: 100%;
  background: #ffffff;
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
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
  width: 100%; max-width: 800px;
  display: flex; flex-direction: column; gap: 28px;
  padding: 0 24px 80px; box-sizing: border-box;
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
  pointer-events: auto; width: 100%; max-width: 800px;
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
.tool-group { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; }
.tool-group-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  cursor: pointer; transition: background 0.15s; user-select: none; background: #f1f5f9;
}
.tool-group-header:hover { background: #e8eef5; }
.tool-group-icon { font-size: 16px; flex-shrink: 0; }
.tool-group-name { font-size: 13px; font-weight: 700; color: #1e293b; flex: 1; }
.tool-group-task { font-size: 12px; color: #64748b; max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tool-group-body { border-top: 1px solid #e2e8f0; }
.tool-group-body-result { padding: 10px 14px; font-size: 13px; border-top: 1px solid #e2e8f0; }
.tool-group-body-result pre {
  margin: 0; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto;
  font-family: monospace; font-size: 12px; background: #1e293b; color: #e2e8f0; padding: 10px 14px; border-radius: 6px;
}
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
.reasoning-label { font-weight: 600; }
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

.tool-group-toggle { font-size: 11px; color: #94a3b8; margin-right: 4px; }

/* Sub-agent conversation */
.sub-conversation { display: flex; flex-direction: column; gap: 4px; padding: 8px 12px; }
.sub-reasoning { background: #faf5ff; border: 1px solid #f3e8ff; border-radius: 8px; overflow: hidden; font-size: 12px; }
.sub-reasoning-header { padding: 6px 10px; color: #a855f7; font-weight: 600; }
.sub-reasoning-content { padding: 6px 10px 10px; color: #7c3aed; white-space: pre-wrap; line-height: 1.5; max-height: 200px; overflow-y: auto; border-top: 1px solid #f3e8ff; }
.sub-tool-call, .sub-tool-result {
  display: flex; align-items: flex-start; gap: 6px; padding: 5px 10px;
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 12px;
}
.sub-tool-icon { flex-shrink: 0; font-size: 12px; }
.sub-tool-name { flex: 1; color: #475569; font-weight: 500; }
.sub-tool-status { flex-shrink: 0; font-size: 11px; }
.sub-tool-status.running { color: #f59e0b; }
.sub-tool-status.completed { color: #22c55e; }
.sub-tool-result { flex-wrap: wrap; }
.sub-tool-result-text { width: 100%; margin-top: 4px; }
.sub-tool-result-text pre { font-size: 11px; color: #64748b; white-space: pre-wrap; max-height: 120px; overflow-y: auto; background: #f1f5f9; padding: 6px 10px; border-radius: 4px; margin: 0; }
.sub-text { font-size: 13px; line-height: 1.6; color: #334155; padding: 4px 0; }
.sub-text :deep(p) { margin: 4px 0; }
</style>
