<script setup>
import { ref, onMounted, nextTick } from 'vue'

const API_BASE = ''  // 使用相对路径，通过 Vite 代理或后端直接提供

// 状态
const messages = ref([
  {
    role: 'assistant',
    content: '你好！我是 Polaris，你的智能助手。有什么可以帮你的吗？',
    timestamp: new Date()
  }
])
const inputMessage = ref('')
const isLoading = ref(false)
const isOnline = ref(false)
const error = ref('')
const chatArea = ref(null)
const sessionId = ref(null)  // 会话 ID

// 检查后端连接
async function checkConnection() {
  try {
    const response = await fetch(`${API_BASE}/api/health`)
    isOnline.value = response.ok
    return response.ok
  } catch (err) {
    isOnline.value = false
    return false
  }
}

// 发送消息
async function sendMessage() {
  const message = inputMessage.value.trim()
  if (!message || isLoading.value) return

  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: message,
    timestamp: new Date()
  })
  inputMessage.value = ''
  isLoading.value = true
  error.value = ''

  // 滚动到底部
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
        session_id: sessionId.value  // 传递 session_id
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()

    // 保存 session_id
    if (data.session_id) {
      sessionId.value = data.session_id
    }

    // 添加助手回复
    messages.value.push({
      role: 'assistant',
      content: data.message,
      timestamp: new Date()
    })

    await nextTick()
    scrollToBottom()

  } catch (err) {
    console.error('Error:', err)
    error.value = '发送失败: ' + err.message
    messages.value.push({
      role: 'assistant',
      content: '抱歉，我遇到了一些问题。请稍后再试。',
      timestamp: new Date()
    })
  } finally {
    isLoading.value = false
  }
}

// 滚动到底部
function scrollToBottom() {
  if (chatArea.value) {
    chatArea.value.scrollTop = chatArea.value.scrollHeight
  }
}

// 格式化时间
function formatTime(date) {
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`

  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 回车发送
function handleKeyPress(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// 初始化
onMounted(() => {
  checkConnection()
  // 定期检查连接
  setInterval(checkConnection, 30000)
})
</script>

<template>
  <div class="container">
    <div class="header">
      <h1>⭐ Polaris</h1>
      <div class="status">
        <span class="status-dot" :class="{ online: isOnline }"></span>
        <span>{{ isOnline ? '在线' : '离线' }}</span>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div ref="chatArea" class="chat-area">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        class="message"
        :class="msg.role"
      >
        <div class="avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
        <div class="message-wrapper">
          <div class="message-content">{{ msg.content }}</div>
          <div class="timestamp">{{ formatTime(msg.timestamp) }}</div>
        </div>
      </div>
    </div>

    <div v-if="isLoading" class="loading">
      <div class="loading-dots">
        <span></span>
        <span></span>
        <span></span>
      </div>
      <span>Polaris 正在思考...</span>
    </div>

    <div class="input-area">
      <input
        v-model="inputMessage"
        type="text"
        placeholder="输入消息..."
        :disabled="isLoading"
        @keypress="handleKeyPress"
      />
      <button @click="sendMessage" :disabled="isLoading || !inputMessage.trim()">
        发送
      </button>
    </div>
  </div>
</template>

<style scoped>
.container {
  width: 90%;
  max-width: 900px;
  height: 80vh;
  background: white;
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin: 0 auto;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
  transition: background 0.3s;
}

.status-dot.online {
  background: #4ade80;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 12px 20px;
  margin: 0;
  font-size: 14px;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f9fafb;
}

.message {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.message.assistant .avatar {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.message-wrapper {
  max-width: 70%;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.5;
  word-wrap: break-word;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.message.user .message-content {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.timestamp {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 4px;
  padding: 0 4px;
}

.loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 14px;
  padding: 12px 20px;
  background: #f9fafb;
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #667eea;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.input-area {
  padding: 20px;
  background: white;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 12px;
}

input {
  flex: 1;
  padding: 12px 16px;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

input:focus {
  border-color: #667eea;
}

input:disabled {
  background: #f3f4f6;
  cursor: not-allowed;
}

button {
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

button:active:not(:disabled) {
  transform: translateY(0);
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 滚动条样式 */
.chat-area::-webkit-scrollbar {
  width: 6px;
}

.chat-area::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.chat-area::-webkit-scrollbar-thumb {
  background: #667eea;
  border-radius: 3px;
}
</style>
