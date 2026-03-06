<script setup>
import { ref, onMounted } from 'vue'
import { Server, Monitor, Save, CheckCircle, AlertCircle, RefreshCw } from 'lucide-vue-next'

const backendPort = ref(6547)
const frontendPort = ref(6546)
const isSaving = ref(false)
const toast = ref(null) // { type: 'success'|'error'|'restarting', message: string }
const countdown = ref(0)   // 重启倒计时秒数
let toastTimer = null
let countdownTimer = null

// 从后端读取当前配置
async function loadConfig() {
  try {
    const res = await fetch('/api/config')
    if (res.ok) {
      const data = await res.json()
      backendPort.value = data?.server?.port ?? 6547
      frontendPort.value = data?.server?.frontend_port ?? 6546
    }
  } catch (e) {
    console.error('加载配置失败', e)
  }
}

// 仅保存，不重启
async function savePorts() {
  isSaving.value = true
  try {
    const res = await fetch('/api/config/ports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        backend_port: backendPort.value,
        frontend_port: frontendPort.value
      })
    })
    const data = await res.json()
    if (res.ok) {
      showToast('success', data.message || '端口配置已保存，重启后生效')
    } else {
      showToast('error', data.detail || '保存失败，请检查输入')
    }
  } catch (e) {
    showToast('error', '网络错误，请稍后重试')
  } finally {
    isSaving.value = false
  }
}

// 保存并重启（调用 /api/config/restart，触发 main.py 自重启）
async function saveAndRestart() {
  isSaving.value = true
  const newFrontendPort = frontendPort.value

  try {
    const res = await fetch('/api/config/restart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        backend_port: backendPort.value,
        frontend_port: newFrontendPort
      })
    })
    const data = await res.json()
    if (res.ok) {
      startRestartCountdown(newFrontendPort)
    } else {
      showToast('error', data.detail || '重启失败，请检查配置')
      isSaving.value = false
    }
  } catch (e) {
    // 后端已开始重启，连接断开属于正常现象
    startRestartCountdown(newFrontendPort)
  }
}

// 重启倒计时，结束后跳转到新前端端口
function startRestartCountdown(newFrontendPort) {
  countdown.value = 4
  const currentPort = window.location.port || '80'
  const portChanged = String(newFrontendPort) !== String(currentPort)

  showToast('restarting', portChanged
    ? `服务正在重启，${countdown.value}秒后跳转到新端口 ${newFrontendPort}...`
    : `服务正在重启，${countdown.value}秒后刷新页面...`
  )

  countdownTimer = setInterval(() => {
    countdown.value--
    toast.value = {
      type: 'restarting',
      message: portChanged
        ? `服务正在重启，${countdown.value}秒后跳转到新端口 ${newFrontendPort}...`
        : `服务正在重启，${countdown.value}秒后刷新页面...`
    }
    if (countdown.value <= 0) {
      clearInterval(countdownTimer)
      if (portChanged) {
        window.location.href = `http://${window.location.hostname}:${newFrontendPort}`
      } else {
        window.location.reload()
      }
    }
  }, 1000)
}

function showToast(type, message) {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { type, message }
  if (type !== 'restarting') {
    toastTimer = setTimeout(() => { toast.value = null }, 3500)
  }
}

onMounted(loadConfig)
</script>

<template>
  <div class="system-settings">
    <!-- Toast 提示 -->
    <Transition name="toast">
      <div v-if="toast" class="toast" :class="toast.type">
        <component :is="toast.type === 'success' ? CheckCircle : toast.type === 'restarting' ? RefreshCw : AlertCircle" :size="16" :class="{ spin: toast.type === 'restarting' }" />
        <span>{{ toast.message }}</span>
      </div>
    </Transition>

    <!-- 页头 -->
    <div class="page-header">
      <h2 class="page-title">系统设置</h2>
      <p class="page-desc">配置系统运行参数，端口修改后可选择「仅保存」或「保存并重启」</p>
    </div>

    <!-- 端口配置卡片 -->
    <div class="settings-card">
      <div class="card-header">
        <Server :size="18" class="card-icon" />
        <span class="card-title">端口配置</span>
      </div>

      <div class="setting-row">
        <div class="setting-label">
          <Monitor :size="15" class="row-icon" />
          <div>
            <div class="label-main">后端端口</div>
            <div class="label-sub">FastAPI 服务监听端口</div>
          </div>
        </div>
        <div class="input-wrap">
          <input
            v-model.number="backendPort"
            type="number"
            class="port-input"
            min="1024"
            max="65535"
            placeholder="6547"
          />
        </div>
      </div>

      <div class="divider" />

      <div class="setting-row">
        <div class="setting-label">
          <Monitor :size="15" class="row-icon" />
          <div>
            <div class="label-main">前端端口</div>
            <div class="label-sub">Vite 开发服务器监听端口</div>
          </div>
        </div>
        <div class="input-wrap">
          <input
            v-model.number="frontendPort"
            type="number"
            class="port-input"
            min="1024"
            max="65535"
            placeholder="6546"
          />
        </div>
      </div>

      <div class="card-footer">
        <div class="hint">⚠️ 「保存并重启」将自动重启服务，前端端口变更后浏览器会跳转</div>
        <div class="btn-group">
          <button class="save-btn secondary" @click="savePorts" :disabled="isSaving">
            <Save :size="15" />
            仅保存
          </button>
          <button class="save-btn" @click="saveAndRestart" :disabled="isSaving">
            <RefreshCw :size="15" :class="{ spin: isSaving && countdown > 0 }" />
            {{ isSaving ? '重启中...' : '保存并重启' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.system-settings {
  height: 100%;
  padding: 36px;
  box-sizing: border-box;
  overflow-y: auto;
  position: relative;
}

/* Toast */
.toast {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 999;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  max-width: 360px;
}
.toast.success    { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
.toast.error      { background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
.toast.restarting { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }

.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-12px); }

@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 1s linear infinite; }

/* 页头 */
.page-header { margin-bottom: 28px; }
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 6px 0;
  letter-spacing: -0.3px;
}
.page-desc { font-size: 14px; color: #64748b; margin: 0; }

/* 卡片 */
.settings-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  overflow: hidden;
  max-width: 680px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 24px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}
.card-icon { color: #3b82f6; }
.card-title { font-size: 15px; font-weight: 600; color: #1e293b; }

/* 设置行 */
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
}
.setting-label {
  display: flex;
  align-items: center;
  gap: 12px;
}
.row-icon { color: #94a3b8; flex-shrink: 0; }
.label-main { font-size: 14px; font-weight: 500; color: #1e293b; }
.label-sub  { font-size: 12px; color: #94a3b8; margin-top: 2px; }

.divider { height: 1px; background: #f1f5f9; margin: 0 24px; }

/* 输入框 */
.input-wrap { flex-shrink: 0; }
.port-input {
  width: 110px;
  padding: 8px 12px;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #1e293b;
  background: #f8fafc;
  text-align: center;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.port-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.12);
  background: #fff;
}

/* 卡片底部 */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-top: 1px solid #f1f5f9;
  background: #fafafa;
  gap: 12px;
  flex-wrap: wrap;
}
.hint { font-size: 12px; color: #94a3b8; flex: 1; min-width: 160px; }

.btn-group {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.save-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 20px;
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s, transform 0.1s;
}
.save-btn.secondary {
  background: #f1f5f9;
  color: #475569;
}
.save-btn.secondary:hover:not(:disabled) { background: #e2e8f0; }
.save-btn:hover:not(:disabled) { background: #2563eb; }
.save-btn:active:not(:disabled) { transform: scale(0.97); }
.save-btn:disabled { background: #cbd5e1; cursor: not-allowed; color: #fff; }
.save-btn.secondary:disabled { background: #f1f5f9; color: #94a3b8; }
</style>
