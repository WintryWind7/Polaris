<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, ChevronDown, Send } from 'lucide-vue-next'

const API_BASE = '' // Vite proxy handles this in dev

const sessions = ref([])
const currentSessionId = ref(null)
const messages = ref([])
const inputMessage = ref('')
const isLoading = ref(false)
const showHistoryMenu = ref(false)
const chatArea = ref(null)

const route = useRoute()
const router = useRouter()

// Load all sessions
async function loadSessions() {
  try {
    const response = await fetch(`${API_BASE}/api/chat/sessions`)
    if (response.ok) {
      const data = await response.json()
      sessions.value = data.sessions
      
      // 如果没有指定会话，且有历史记录，则自动加载最近一次会话
      if (!currentSessionId.value && sessions.value.length > 0) {
        // 如果 URL 中有指定 session_id，则加载 URL 中的
        const urlSessionId = route.query.session
        if (urlSessionId) {
            loadSession(urlSessionId)
        } else {
            // 否则加载最近的第一个历史会话
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
      // format to match expected structure if needed
      messages.value = data.messages
      currentSessionId.value = sessionId
      showHistoryMenu.value = false
      
      // 更新 URL 参数
      if (route.query.session !== sessionId) {
        router.replace({ query: { ...route.query, session: sessionId } })
      }
      
      await nextTick()
      scrollToBottom()
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
  // 移除 URL 中的 session 参数
  if (route.query.session) {
    router.replace({ query: { ...route.query, session: undefined } })
  }
}

// Send message
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

  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message,
        session_id: currentSessionId.value
      })
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()

    if (data.session_id && currentSessionId.value !== data.session_id) {
      currentSessionId.value = data.session_id
      
      // 更新 URL
      router.replace({ query: { ...route.query, session: data.session_id } })
      
      loadSessions() // Refresh history list
    }

    messages.value.push({
      role: 'assistant',
      content: data.message,
      timestamp: data.timestamp || new Date().toISOString()
    })

  } catch (err) {
    console.error('Error:', err)
    messages.value.push({
      role: 'assistant',
      content: '抱歉，发送失败，请稍后再试。',
      timestamp: new Date().toISOString()
    })
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
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
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

// Format time nicely
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
        <div class="chat-title-group" @click="toggleHistoryMenu">
            <span class="chat-title">{{ currentTitle }}</span>
            <ChevronDown class="chevron-down" :size="16" />
            
            <!-- History Dropdown -->
            <div v-if="showHistoryMenu" class="history-dropdown" @click.stop>
              <div class="dropdown-header">会话历史</div>
              <div class="dropdown-list" v-if="sessions.length > 0">
                <div 
                  v-for="session in sessions" 
                  :key="session.id" 
                  class="history-item"
                  :class="{ active: currentSessionId === session.id }"
                  @click="loadSession(session.id)"
                >
                  <div class="history-item-content">
                    <div class="history-item-title">{{ session.title }}</div>
                    <div class="history-item-time">{{ formatRelativeTime(session.updated_at) }}</div>
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
                  <div class="message-bubble">
                      {{ msg.content }}
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
    word-break: break-all;
    white-space: pre-wrap;
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
</style>
