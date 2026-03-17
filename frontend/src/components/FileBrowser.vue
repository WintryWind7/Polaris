<script setup>
import { ref, onMounted, computed } from 'vue'
import embeddingApi from '../services/embeddingApi'
import { useToast } from 'vue-toastification'

const props = defineProps({
  initialPath: String
})

const emit = defineEmits(['close', 'select'])
const toast = useToast()

const currentPath = ref('')
const parentPath = ref(null)
const folders = ref([])
const loading = ref(false)
const isValidModel = ref(false)
const manualPath = ref('')

// 浏览目录
const browseDirectory = async (path = '') => {
  loading.value = true
  try {
    const result = await embeddingApi.browseDirectory(path)
    currentPath.value = result.current_path
    parentPath.value = result.parent_path
    folders.value = result.folders
    isValidModel.value = result.is_valid_model
    manualPath.value = ''
  } catch (error) {
    const msg = error.response?.data?.detail || '浏览目录失败'
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

// 进入子文件夹
const enterFolder = (folderName) => {
  const separator = currentPath.value.includes('\\') ? '\\' : '/'
  const newPath = currentPath.value.endsWith(separator)
    ? `${currentPath.value}${folderName}`
    : `${currentPath.value}${separator}${folderName}`
  browseDirectory(newPath)
}

// 返回上级目录
const goUp = () => {
  if (parentPath.value) {
    browseDirectory(parentPath.value)
  }
}

// 选择当前目录
const selectCurrent = () => {
  emit('select', currentPath.value)
}

// 手动输入路径
const goToPath = () => {
  if (manualPath.value.trim()) {
    browseDirectory(manualPath.value.trim())
  }
}

// 格式化路径显示
const displayPath = computed(() => {
  if (!currentPath.value) return ''

  const path = currentPath.value
  const maxLength = 50

  // 如果路径不长，直接显示
  if (path.length <= maxLength) return path

  // 路径过长，智能省略中间部分
  const parts = path.split(/[/\\]/)

  if (parts.length <= 3) {
    // 路径层级少，直接截断
    return path.substring(0, maxLength - 3) + '...'
  }

  // 保留开头（盘符或根目录）和结尾（最后2级目录）
  const start = parts[0]
  const end = parts.slice(-2).join('\\')
  const separator = path.includes('\\') ? '\\' : '/'

  return `${start}${separator}...${separator}${end}`
})

onMounted(() => {
  browseDirectory(props.initialPath || '')
})
</script>

<template>
  <div class="browser-overlay" @click.self="$emit('close')">
    <div class="browser">
      <!-- 头部 -->
      <div class="browser-header">
        <div class="header-left">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <h3>选择模型文件夹</h3>
        </div>
        <button class="close-btn" @click="$emit('close')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <!-- 工具栏 -->
      <div class="browser-toolbar">
        <button class="btn-nav" @click="goUp" :disabled="!parentPath || loading" title="返回上级">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
        </button>

        <div class="path-display">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
          </svg>
          <span>{{ displayPath }}</span>
          <span v-if="isValidModel" class="valid-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <path d="M20 6L9 17l-5-5"/>
            </svg>
            有效模型
          </span>
        </div>
      </div>

      <!-- 手动输入 -->
      <div class="manual-input">
        <input
          v-model="manualPath"
          type="text"
          placeholder="或直接输入路径..."
          @keyup.enter="goToPath"
          :disabled="loading"
        />
        <button @click="goToPath" :disabled="loading || !manualPath.trim()">
          前往
        </button>
      </div>

      <!-- 文件夹列表 -->
      <div class="browser-body">
        <div class="folder-list" v-if="!loading">
          <div
            v-for="folder in folders"
            :key="folder"
            class="folder-item"
            @click="enterFolder(folder)"
          >
            <div class="folder-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
            </div>
            <span class="folder-name">{{ folder }}</span>
            <svg class="folder-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 18l6-6-6-6"/>
            </svg>
          </div>

          <div v-if="folders.length === 0" class="empty">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <p>此目录下没有子文件夹</p>
          </div>
        </div>

        <div class="loading-state" v-else>
          <div class="spinner"></div>
          <p>加载中...</p>
        </div>
      </div>

      <!-- 底部 -->
      <div class="browser-footer">
        <button class="btn-cancel" @click="$emit('close')">
          取消
        </button>
        <button class="btn-select" @click="selectCurrent" :disabled="loading">
          选择此目录
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.browser-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1001;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.browser {
  background: white;
  border-radius: 16px;
  width: 700px;
  max-width: 90vw;
  height: 600px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.browser-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left svg {
  color: #3b82f6;
}

.browser-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}

.close-btn {
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 6px;
  border-radius: 8px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: #f1f5f9;
  color: #64748b;
}

.browser-toolbar {
  padding: 12px 24px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  gap: 12px;
  align-items: center;
  flex-shrink: 0;
  background: #f8fafc;
}

.btn-nav {
  padding: 8px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.btn-nav:hover:not(:disabled) {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.btn-nav:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.path-display {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  color: #475569;
  font-family: 'Consolas', 'Monaco', monospace;
  overflow: hidden;
}

.path-display svg {
  flex-shrink: 0;
  color: #94a3b8;
}

.path-display span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.valid-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #dcfce7;
  color: #16a34a;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.manual-input {
  padding: 12px 24px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.manual-input input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  transition: all 0.2s;
}

.manual-input input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.manual-input button {
  padding: 8px 16px;
  background: #3b82f6;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
}

.manual-input button:hover:not(:disabled) {
  background: #2563eb;
}

.manual-input button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.browser-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.folder-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.folder-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 2px;
  position: relative;
}

.folder-item:hover {
  background: #f8fafc;
}

.folder-item:active {
  background: #f1f5f9;
  transform: scale(0.98);
}

.folder-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.folder-icon svg {
  color: white;
}

.folder-name {
  flex: 1;
  font-size: 14px;
  color: #1e293b;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-arrow {
  color: #cbd5e1;
  flex-shrink: 0;
  transition: all 0.2s;
}

.folder-item:hover .folder-arrow {
  color: #3b82f6;
  transform: translateX(2px);
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #94a3b8;
}

.empty svg {
  margin-bottom: 16px;
  opacity: 0.3;
}

.empty p {
  margin: 0;
  font-size: 14px;
}

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #f1f5f9;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-state p {
  color: #94a3b8;
  font-size: 14px;
  margin: 0;
}

.browser-footer {
  padding: 16px 24px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  flex-shrink: 0;
}

.btn-cancel,
.btn-select {
  padding: 10px 24px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel {
  background: white;
  border: 1px solid #e2e8f0;
  color: #64748b;
}

.btn-cancel:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.btn-select {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  color: white;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.btn-select:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
  transform: translateY(-1px);
}

.btn-select:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* 滚动条样式 */
.folder-list::-webkit-scrollbar {
  width: 8px;
}

.folder-list::-webkit-scrollbar-track {
  background: transparent;
}

.folder-list::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

.folder-list::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
