<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, FolderOpen, Trash2, MessageSquare, ArrowLeft, X, Folder, ChevronRight, HardDrive } from 'lucide-vue-next'
import workspaceApi from '../services/workspaceApi'
import filesystemApi from '../services/filesystemApi'

const route = useRoute()
const router = useRouter()

const workspaces = ref([])
const currentWorkspace = ref(null)
const workspaceSessions = ref([])
const showCreateDialog = ref(false)
const newWorkspacePath = ref('')
const isLoading = ref(false)
const showDirBrowser = ref(false)
const dirCurrentPath = ref('')
const dirParent = ref(null)
const dirEntries = ref([])
const dirLoading = ref(false)
const dirError = ref('')

const selectedWorkspaceId = computed(() => route.query.workspace)

async function loadWorkspaces() {
  try {
    const data = await workspaceApi.getWorkspaces()
    workspaces.value = data.workspaces
  } catch (err) {
    console.error('加载工作空间失败:', err)
  }
}

async function selectWorkspace(id) {
  try {
    const ws = await workspaceApi.getWorkspace(id)
    currentWorkspace.value = ws

    const data = await workspaceApi.getWorkspaceSessions(id)
    workspaceSessions.value = data.sessions

    router.replace({ query: { workspace: id } })
  } catch (err) {
    console.error('加载工作空间详情失败:', err)
  }
}

function backToList() {
  currentWorkspace.value = null
  workspaceSessions.value = []
  router.replace({ query: {} })
}

function extractNameFromPath(path) {
  const normalized = path.replace(/\\/g, '/').replace(/\/+$/, '')
  const parts = normalized.split('/')
  return parts[parts.length - 1] || '新工作空间'
}

async function createWorkspace() {
  if (!newWorkspacePath.value.trim()) return

  const name = extractNameFromPath(newWorkspacePath.value.trim())
  try {
    await workspaceApi.createWorkspace({
      name,
      path: newWorkspacePath.value.trim()
    })
    showCreateDialog.value = false
    newWorkspacePath.value = ''
    await loadWorkspaces()
  } catch (err) {
    console.error('创建失败:', err)
    alert(err.response?.data?.detail || '创建失败')
  }
}

async function openDirBrowser() {
  showDirBrowser.value = true
  await loadDir('')
}

async function loadDir(path) {
  dirLoading.value = true
  dirError.value = ''
  try {
    const data = await filesystemApi.listDir(path)
    dirCurrentPath.value = data.current_path
    dirParent.value = data.parent
    dirEntries.value = data.dirs
    if (data.error) dirError.value = data.error
  } catch (err) {
    dirError.value = '加载目录失败'
    console.error('加载目录失败:', err)
  } finally {
    dirLoading.value = false
  }
}

function selectDirPath(path) {
  newWorkspacePath.value = path
  showDirBrowser.value = false
}


async function deleteWorkspace(id, event) {
  if (event) event.stopPropagation()
  if (!confirm('确定要删除这个工作空间吗？会话不会被删除，只会断开关联。')) return

  try {
    await workspaceApi.deleteWorkspace(id)
    if (currentWorkspace.value?.id === id) {
      backToList()
    }
    await loadWorkspaces()
  } catch (err) {
    console.error('删除失败:', err)
  }
}

function startNewChat() {
  if (!currentWorkspace.value) return
  router.push({ path: '/chat', query: { workspace: currentWorkspace.value.id } })
}

function openSession(sessionId) {
  router.push({ path: '/chat', query: { workspace: currentWorkspace.value.id, session: sessionId } })
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

onMounted(async () => {
  await loadWorkspaces()
  if (selectedWorkspaceId.value) {
    await selectWorkspace(selectedWorkspaceId.value)
  }
})
</script>

<template>
  <div class="workspace-view">
    <!-- 工作空间详情视图 -->
    <template v-if="currentWorkspace">
      <div class="detail-header">
        <button class="back-btn" @click="backToList">
          <ArrowLeft :size="18" />
          返回列表
        </button>
        <div class="workspace-info">
          <div class="workspace-icon"><FolderOpen :size="20" /></div>
          <div>
            <h2>{{ currentWorkspace.name }}</h2>
            <p class="workspace-path">{{ currentWorkspace.path }}</p>
          </div>
        </div>
        <button class="new-chat-btn" @click="startNewChat">
          <Plus :size="16" />
          开始新对话
        </button>
      </div>

      <div class="sessions-section">
        <h3>会话记录</h3>
        <div v-if="workspaceSessions.length > 0" class="session-list">
          <div
            v-for="session in workspaceSessions"
            :key="session.id"
            class="session-card"
            @click="openSession(session.id)"
          >
            <MessageSquare :size="16" class="session-icon" />
            <div class="session-info">
              <div class="session-title">{{ session.title }}</div>
              <div class="session-time">{{ formatRelativeTime(session.updated_at) }}</div>
            </div>
          </div>
        </div>
        <div v-else class="empty-sessions">
          <p>还没有对话记录</p>
          <p class="hint">点击"开始新对话"创建第一个会话</p>
        </div>
      </div>
    </template>

    <!-- 工作空间列表视图 -->
    <template v-else>
      <div class="list-header">
        <h2>工作空间</h2>
        <button class="create-btn" @click="showCreateDialog = true">
          <Plus :size="16" />
          新建工作空间
        </button>
      </div>

      <div v-if="workspaces.length > 0" class="workspace-grid">
        <div
          v-for="ws in workspaces"
          :key="ws.id"
          class="workspace-card"
          @click="selectWorkspace(ws.id)"
        >
          <div class="card-header">
            <FolderOpen :size="24" class="card-icon" />
            <button class="delete-btn" @click="(e) => deleteWorkspace(ws.id, e)" title="删除">
              <Trash2 :size="14" />
            </button>
          </div>
          <div class="card-body">
            <h3>{{ ws.name }}</h3>
            <p class="card-path">{{ ws.path }}</p>
          </div>
          <div class="card-footer">
            <span class="session-count">{{ ws.session_count || 0 }} 个会话</span>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <FolderOpen :size="48" class="empty-icon" />
        <p>还没有工作空间</p>
        <p class="hint">创建一个工作空间，将 AI 绑定到你的项目目录</p>
      </div>
    </template>

    <!-- 创建对话框 -->
    <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
      <div class="dialog">
        <div class="dialog-header">
          <h3>新建工作空间</h3>
          <button class="dialog-close" @click="showCreateDialog = false">
            <X :size="18" />
          </button>
        </div>
        <div class="dialog-body">
          <div class="form-group">
            <label>项目目录路径</label>
            <div class="path-input-row">
              <input v-model="newWorkspacePath" placeholder="输入项目目录路径，如 D:\Projects\MyApp" />
              <button class="browse-btn" @click="openDirBrowser" type="button">浏览</button>
            </div>
            <p v-if="newWorkspacePath.trim()" class="path-preview">
              工作空间名称：{{ extractNameFromPath(newWorkspacePath.trim()) }}
            </p>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="cancel-btn" @click="showCreateDialog = false">取消</button>
          <button
            class="confirm-btn"
            @click="createWorkspace"
            :disabled="!newWorkspacePath.trim()"
          >
            创建
          </button>
        </div>
      </div>
    </div>

    <!-- 目录浏览器对话框 -->
    <div v-if="showDirBrowser" class="dialog-overlay" @click.self="showDirBrowser = false">
      <div class="dialog dir-browser-dialog">
        <div class="dialog-header">
          <h3>选择目录</h3>
          <button class="dialog-close" @click="showDirBrowser = false">
            <X :size="18" />
          </button>
        </div>
        <div class="dir-browser-body">
          <div class="dir-breadcrumb">
            <button v-if="dirParent !== null" class="breadcrumb-btn" @click="loadDir(dirParent)">
              ← 上级
            </button>
            <span class="breadcrumb-path">{{ dirCurrentPath || '选择驱动器' }}</span>
          </div>
          <div v-if="dirLoading" class="dir-loading">加载中...</div>
          <div v-else-if="dirError" class="dir-error">{{ dirError }}</div>
          <div v-else class="dir-list">
            <div
              v-for="entry in dirEntries"
              :key="entry.path"
              class="dir-entry"
              @click="entry.type === 'drive' ? loadDir(entry.path) : loadDir(entry.path)"
            >
              <HardDrive v-if="entry.type === 'drive'" :size="16" class="entry-icon" />
              <Folder v-else :size="16" class="entry-icon" />
              <span class="entry-name">{{ entry.name }}</span>
              <ChevronRight :size="14" class="entry-arrow" />
            </div>
            <div v-if="dirEntries.length === 0 && dirCurrentPath" class="dir-empty">
              此目录下没有子目录
            </div>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="cancel-btn" @click="showDirBrowser = false">取消</button>
          <button
            class="confirm-btn"
            @click="selectDirPath(dirCurrentPath)"
            :disabled="!dirCurrentPath"
          >
            选择此目录
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workspace-view {
  padding: 32px;
  height: 100%;
  overflow-y: auto;
}

/* 列表视图 */
.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.list-header h2 {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.create-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.create-btn:hover {
  background: #2563eb;
}

.workspace-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.workspace-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.workspace-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-icon {
  color: #3b82f6;
}

.delete-btn {
  background: transparent;
  border: none;
  color: #cbd5e1;
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s;
}

.workspace-card:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #ef4444;
  background: #fee2e2;
}

.card-body h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 6px;
}

.card-path {
  font-size: 13px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.session-count {
  font-size: 13px;
  color: #94a3b8;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 40px;
  border: 1px dashed #e2e8f0;
  border-radius: 16px;
  margin-top: 40px;
}

.empty-icon {
  color: #cbd5e1;
  margin-bottom: 16px;
}

.empty-state p {
  color: #64748b;
  font-size: 15px;
  margin: 4px 0;
}

.empty-state .hint {
  font-size: 13px;
  color: #94a3b8;
}

/* 详情视图 */
.detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: transparent;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #64748b;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.back-btn:hover {
  background: #f8fafc;
  color: #1e293b;
}

.workspace-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.workspace-icon {
  width: 40px;
  height: 40px;
  background: #eff6ff;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #3b82f6;
}

.workspace-info h2 {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.workspace-path {
  font-size: 13px;
  color: #64748b;
  margin: 2px 0 0;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.new-chat-btn:hover {
  background: #2563eb;
}

.sessions-section h3 {
  font-size: 15px;
  font-weight: 600;
  color: #64748b;
  margin: 0 0 16px;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.session-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.session-card:hover {
  border-color: #3b82f6;
  background: #f8fafc;
}

.session-icon {
  color: #94a3b8;
  flex-shrink: 0;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-time {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.empty-sessions {
  padding: 40px;
  text-align: center;
}

.empty-sessions p {
  color: #64748b;
  margin: 4px 0;
}

.empty-sessions .hint {
  font-size: 13px;
  color: #94a3b8;
}

/* 创建对话框 */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog {
  background: #ffffff;
  border-radius: 16px;
  width: 460px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #f1f5f9;
}

.dialog-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: #1e293b;
}

.dialog-close {
  background: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.dialog-close:hover {
  color: #64748b;
}

.dialog-body {
  padding: 24px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}

.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #1e293b;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-group input:focus {
  border-color: #3b82f6;
}

.path-preview {
  margin: 8px 0 0;
  font-size: 13px;
  color: #64748b;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 24px;
  border-top: 1px solid #f1f5f9;
}

.cancel-btn {
  padding: 10px 18px;
  background: transparent;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #64748b;
  cursor: pointer;
}

.cancel-btn:hover {
  background: #f8fafc;
}

.confirm-btn {
  padding: 10px 18px;
  background: #3b82f6;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  color: white;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.confirm-btn:hover:not(:disabled) {
  background: #2563eb;
}

.confirm-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

/* 路径输入行 */
.path-input-row {
  display: flex;
  gap: 8px;
}

.path-input-row input {
  flex: 1;
}

.browse-btn {
  padding: 10px 16px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #475569;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}

.browse-btn:hover {
  background: #e2e8f0;
}

/* 目录浏览器 */
.dir-browser-dialog {
  width: 520px;
  height: 520px;
  display: flex;
  flex-direction: column;
}

.dir-browser-body {
  padding: 16px 24px;
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.dir-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}

.breadcrumb-btn {
  padding: 4px 10px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  white-space: nowrap;
}

.breadcrumb-btn:hover {
  background: #e2e8f0;
}

.breadcrumb-path {
  font-size: 13px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dir-list {
  flex: 1;
  overflow-y: auto;
}

.dir-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.dir-entry:hover {
  background: #f1f5f9;
}

.entry-icon {
  color: #64748b;
  flex-shrink: 0;
}

.entry-name {
  flex: 1;
  font-size: 14px;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.entry-arrow {
  color: #cbd5e1;
  flex-shrink: 0;
}

.dir-loading,
.dir-empty {
  padding: 40px;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}

.dir-error {
  padding: 20px;
  text-align: center;
  color: #ef4444;
  font-size: 14px;
}
</style>
