<script setup>
import { ref, onMounted, computed } from 'vue'
import embeddingApi from '../../services/embeddingApi'
import { useToast } from 'vue-toastification'
import EmbeddingDialog from './EmbeddingDialog.vue'
import EmbeddingEditor from './EmbeddingEditor.vue'

const toast = useToast()

// 状态
const embeddings = ref({})
const selectedId = ref(null)
const loading = ref(true)
const isDialogOpen = ref(false)
const rebuilding = ref(false)
const compatibility = ref(null)

// 检查兼容性
const checkCompatibility = async () => {
  try {
    compatibility.value = await embeddingApi.checkCompatibility()
  } catch (error) {
    console.error('检查兼容性失败:', error)
  }
}

// 重建向量数据库
const rebuildDatabase = async () => {
  if (!confirm(
    '重建向量数据库\n\n' +
    '此操作将：\n' +
    '1. 删除所有现有的向量数据\n' +
    '2. 从消息表重新生成所有 embedding\n' +
    '3. 可能需要较长时间（取决于消息数量）\n\n' +
    '确定要继续吗？'
  )) {
    return
  }

  rebuilding.value = true
  try {
    const result = await embeddingApi.rebuildEmbeddings()

    toast.success(
      `重建完成！\n` +
      `总计: ${result.total}\n` +
      `成功: ${result.success}\n` +
      `失败: ${result.failed}`
    )

    // 重建后重新检查兼容性
    await checkCompatibility()
  } catch (error) {
    const msg = error.response?.data?.detail || '重建失败'
    toast.error(msg)
  } finally {
    rebuilding.value = false
  }
}

const loadEmbeddings = async () => {
  loading.value = true
  try {
    const data = await embeddingApi.getEmbeddings()
    // 强制校验格式：后端返回 dict { id: {} }
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      embeddings.value = data
    } else {
      embeddings.value = {}
    }

    // 维持选中状态
    if (selectedId.value && !embeddings.value[selectedId.value]) {
      selectedId.value = null
    }

    // 检查兼容性
    await checkCompatibility()
  } catch (e) {
    console.error('[EmbeddingManager] Load error:', e)
    toast.error('无法同步 Embedding 配置，请检查服务状态')
  } finally {
    loading.value = false
  }
}

const onAdded = async (newId) => {
  isDialogOpen.value = false
  await loadEmbeddings()
  if (newId) selectedId.value = newId
}

const deleteEmbedding = async (id, event) => {
  if (event) event.stopPropagation()
  if (!confirm(`确定要移除 "${id}" 吗？\n此操作将删除该 Embedding 的所有配置。`)) return

  try {
    await embeddingApi.deleteEmbedding(id)
    toast.success(`已成功移除 ${id}`)
    if (selectedId.value === id) selectedId.value = null
    await loadEmbeddings()
  } catch (e) {
    toast.error(e.response?.data?.detail || '删除失败')
  }
}

// 计算列表
const embeddingEntries = computed(() => {
  return Object.entries(embeddings.value || {}).map(([id, data]) => ({
    id,
    ...data
  }))
})

const selectedEmbeddingData = computed(() => {
  return selectedId.value ? embeddings.value[selectedId.value] : null
})

onMounted(loadEmbeddings)
</script>

<template>
  <div class="embedding-manager">
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">Embedding 模型</span>
        <button class="add-btn" @click="isDialogOpen = true">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <path d="M12 5v14M5 12h14"/>
          </svg>
          新增
        </button>
      </div>

      <div class="list-container" v-if="!loading">
        <!-- 空状态 -->
        <div class="empty-state" v-if="embeddingEntries.length === 0">
          <div class="empty-icon">+</div>
          <p>暂无 Embedding 配置</p>
          <button @click="isDialogOpen = true">立即添加</button>
        </div>

        <!-- 列表 -->
        <div
          v-for="e in embeddingEntries"
          :key="e.id"
          class="item"
          :class="{ active: selectedId === e.id, disabled: !e.enabled }"
          @click="selectedId = e.id"
        >
          <div class="item-visual">
            {{ String(e.id).charAt(0).toUpperCase() }}
          </div>
          <div class="item-info">
            <span class="item-name">{{ e.id }}</span>
            <span class="item-meta">
              {{ e.dimension ? `${e.dimension}维` : '未检测' }}
              <span v-if="!e.enabled" class="disabled-tag">已禁用</span>
            </span>
          </div>
          <button class="item-remove" @click.stop="deleteEmbedding(e.id, $event)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- 重建按钮 -->
      <div class="sidebar-footer" v-if="embeddingEntries.length > 0">
        <!-- 兼容性状态 -->
        <div class="compatibility-status" v-if="compatibility">
          <div class="status-indicator" :class="{ compatible: compatibility.compatible, incompatible: !compatibility.compatible }">
            <svg v-if="compatibility.compatible" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <path d="M20 6L9 17l-5-5"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <path d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <span>{{ compatibility.message }}</span>
          </div>
        </div>

        <button class="rebuild-btn" @click="rebuildDatabase" :disabled="rebuilding">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
          </svg>
          {{ rebuilding ? '重建中...' : '重建向量数据库' }}
        </button>
      </div>

      <div class="loading-state" v-else>
        <div class="spinner"></div>
      </div>
    </aside>

    <main class="content">
      <div class="placeholder" v-if="!selectedId">
        <div class="placeholder-icon">🧠</div>
        <h3>选择一个 Embedding 模型开始配置</h3>
        <p>配置本地模型路径，用于语义检索和记忆功能</p>
      </div>

      <EmbeddingEditor
        v-else-if="selectedEmbeddingData"
        :key="selectedId"
        :embedding-id="selectedId"
        :embedding-data="selectedEmbeddingData"
        @updated="loadEmbeddings"
      />
    </main>

    <EmbeddingDialog
      v-if="isDialogOpen"
      @close="isDialogOpen = false"
      @success="onAdded"
    />
  </div>
</template>

<style scoped>
.embedding-manager {
  display: flex;
  height: 100%;
  background: #ffffff;
}

.sidebar {
  width: 260px;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 20px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #f1f5f9;
}

.sidebar-title {
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
}

.add-btn {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.2);
  color: #3b82f6;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.add-btn:hover {
  background: rgba(59, 130, 246, 0.2);
  transform: translateY(-1px);
}

.list-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.compatibility-status {
  margin-bottom: 10px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
  transition: all 0.2s;
}

.status-indicator.compatible {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.status-indicator.incompatible {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.status-indicator svg {
  flex-shrink: 0;
}

.status-indicator span {
  flex: 1;
  line-height: 1.4;
}

.rebuild-btn {
  width: 100%;
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  border: none;
  color: white;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
}

.rebuild-btn:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.4);
  transform: translateY(-1px);
}

.rebuild-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.rebuild-btn svg {
  animation: rotate 2s linear infinite;
}

.rebuild-btn:not(:disabled) svg {
  animation: none;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: all 0.2s;
  position: relative;
}

.item:hover { background: #f8fafc; }
.item.active { background: rgba(59, 130, 246, 0.08); }
.item.disabled { opacity: 0.6; }

.item-visual {
  width: 34px;
  height: 34px;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #3b82f6;
  font-weight: 800;
  font-size: 14px;
}

.item-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.item-name {
  font-size: 14px;
  color: #1e293b;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-meta {
  font-size: 11px;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 6px;
}

.disabled-tag {
  background: #fef2f2;
  color: #ef4444;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

.item-remove {
  position: absolute;
  right: 12px;
  opacity: 0;
  background: transparent;
  border: none;
  color: #ef4444;
  cursor: pointer;
  padding: 5px;
  border-radius: 4px;
  transition: all 0.2s;
}

.item:hover .item-remove { opacity: 1; }
.item-remove:hover { background: rgba(239, 68, 68, 0.1); }

/* 主区域 */
.content { flex: 1; overflow: hidden; background: #ffffff; }

.placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  text-align: center;
}

.placeholder-icon { font-size: 48px; margin-bottom: 20px; opacity: 0.2; }
.placeholder h3 { margin: 0 0 8px; color: #64748b; }

.empty-state {
  text-align: center;
  padding: 40px 10px;
}
.empty-icon { font-size: 24px; color: #cbd5e1; margin-bottom: 10px; }
.empty-state button {
  background: transparent;
  border: 1px solid #e2e8f0;
  color: #64748b;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  margin-top: 10px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #f1f5f9;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 20px auto;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
