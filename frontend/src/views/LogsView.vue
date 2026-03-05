<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'

const logs = ref([])
const ws = ref(null)
const logContainer = ref(null)
const autoScroll = ref(true)

// Configurable log levels. Using Set for quick lookup.
const logLevels = [
  { value: 'DEBUG', label: 'DEBUG', color: '#64748b' },
  { value: 'INFO', label: 'INFO', color: '#10b981' },
  { value: 'WARNING', label: 'WARN', color: '#eab308' },
  { value: 'ERROR', label: 'ERROR', color: '#ef4444' },
  { value: 'CRITICAL', label: 'CRIT', color: '#a855f7' }
]

const activeLevels = ref(new Set(['INFO', 'WARNING', 'ERROR', 'CRITICAL']))

const toggleLevel = (level) => {
  if (activeLevels.value.has(level)) {
    activeLevels.value.delete(level)
  } else {
    activeLevels.value.add(level)
  }
}

const filteredLogs = computed(() => {
  return logs.value.filter(log => activeLevels.value.has(log.level))
})

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  // Since the frontend runs on a dev server (e.g., 6546) and backend on 6547 in dev,
  // we'll need to construct the URL based on the backend API port.
  // Assuming a standard setup where the backend API is at a known port or same host.
  // For Polaris, we usually proxy or know the backend port. Let's assume 6547.
  const host = window.location.hostname
  const wsUrl = `${protocol}//${host}:6547/api/ws/logs`

  console.log('Connecting to WebSocket logs at:', wsUrl)
  ws.value = new WebSocket(wsUrl)

  ws.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      logs.value.push(data)
      // Limit buffer size to prevent memory issues in browser
      if (logs.value.length > 2000) {
        logs.value.shift()
      }
      if (autoScroll.value) {
        scrollToBottom()
      }
    } catch (e) {
      console.error('Failed to parse log message:', e)
    }
  }

  ws.value.onclose = () => {
    console.log('WebSocket disconnected. Attempting reconnect in 3s...')
    setTimeout(connectWebSocket, 3000)
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

const handleScroll = () => {
  if (!logContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = logContainer.value
  // If we are within 50px of the bottom, keep auto-scrolling on. Otherwise turn it off.
  autoScroll.value = scrollHeight - scrollTop - clientHeight < 50
}

onMounted(() => {
  connectWebSocket()
})

onUnmounted(() => {
  if (ws.value) {
    ws.value.onclose = null // Prevent auto-reconnect on deliberate unmount
    ws.value.close()
  }
})

// Helper for row colors
const getLevelColor = (level) => {
  const mapping = {
    'DEBUG': '#94a3b8',
    'INFO': '#10b981',
    'WARNING': '#eab308',
    'ERROR': '#ef4444',
    'CRITICAL': '#a855f7'
  }
  return mapping[level] || '#ffffff'
}

</script>

<template>
  <div class="logs-view">
    <div class="logs-header">
      <h2>系统运行日志</h2>
      <div class="filters">
        <button
          v-for="level in logLevels"
          :key="level.value"
          class="filter-btn"
          :class="{ active: activeLevels.has(level.value) }"
          @click="toggleLevel(level.value)"
        >
          <span class="indicator" :style="{ backgroundColor: level.color }"></span>
          {{ level.label }}
        </button>
      </div>
    </div>

    <!-- Terminal Container -->
    <div class="terminal-container" ref="logContainer" @scroll="handleScroll">
      <div class="log-lines">
        <div class="log-line" v-for="(log, idx) in filteredLogs" :key="idx">
          <span class="ts">[{{ log.timestamp }}]</span>
          <span class="module">[{{ log.name }}]</span>
          <span class="level" :style="{ color: getLevelColor(log.level) }">[{{ log.level }}]</span>
          <span class="msg">{{ log.message }}</span>
        </div>
        <div v-if="filteredLogs.length === 0" class="empty-state">
          等待日志数据...
        </div>
      </div>
      <!-- Auto-scroll indicator -->
      <div v-if="!autoScroll" class="scroll-resume" @click="() => { autoScroll = true; scrollToBottom(); }">
        ↓ 继续滚动
      </div>
    </div>
  </div>
</template>

<style scoped>
.logs-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  min-height: 0;
  padding: 24px;
  box-sizing: border-box;
  background-color: #f8fafc;
}

.logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.logs-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
}

.filters {
  display: flex;
  gap: 10px;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: white;
  border: 1px solid #e2e8f0;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-btn:hover {
  background: #f1f5f9;
}

.filter-btn.active {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #1e293b;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
}

.filter-btn .indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  opacity: 0.3;
  transition: opacity 0.2s;
}

.filter-btn.active .indicator {
  opacity: 1;
}

/* Terminal Styles */
.terminal-container {
  flex-grow: 1;
  background-color: #1e1e2e;
  border-radius: 12px;
  padding: 16px;
  overflow-y: auto;
  position: relative;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, Monaco, monospace;
}

/* Scrollbar specifically for terminal */
.terminal-container::-webkit-scrollbar {
  width: 10px;
}
.terminal-container::-webkit-scrollbar-track {
  background: #1e1e2e;
  border-radius: 0 12px 12px 0;
}
.terminal-container::-webkit-scrollbar-thumb {
  background: #3f3f5a;
  border-radius: 5px;
  border: 2px solid #1e1e2e; /* adds padding effect */
}
.terminal-container::-webkit-scrollbar-thumb:hover {
  background: #5a5a7b;
}

.log-lines {
  display: flex;
  flex-direction: column;
}

.log-line {
  font-size: 13px;
  line-height: 1.6;
  color: #cdd6f4;
  word-break: break-all;
  white-space: pre-wrap;
  margin-bottom: 4px;
}

.log-line:hover {
  background-color: rgba(255, 255, 255, 0.03);
}

.ts {
  color: #89b4fa; /* Cyan/Blue */
  margin-right: 8px;
}

.module {
  color: #cba6f7; /* Purple */
  margin-right: 8px;
}

.level {
  font-weight: 600;
  margin-right: 8px;
  display: inline-block;
  min-width: 60px; /* Aligns messages roughly */
}

.msg {
  color: #cdd6f4; /* Light gray */
}

.empty-state {
  color: #6c7086;
  text-align: center;
  padding: 40px;
  font-style: italic;
}

.scroll-resume {
  position: sticky;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(59, 130, 246, 0.9);
  color: white;
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 6px rgba(0,0,0,0.3);
  backdrop-filter: blur(4px);
  z-index: 10;
  display: inline-block;
  width: fit-content;
  margin: 0 auto;
}
.scroll-resume:hover {
  background: #3b82f6;
}
</style>
