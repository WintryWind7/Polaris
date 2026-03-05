<script setup>
import { ref, onMounted, computed } from 'vue'
import providerApi from '../../services/providerApi'
import { useToast } from 'vue-toastification'
import ProviderDialog from './ProviderDialog.vue'
import ProviderEditor from './ProviderEditor.vue'

const toast = useToast()

// 状态
const providers = ref({})
const selectedId = ref(null)
const loading = ref(true)
const isDialogOpen = ref(false)

const loadProviders = async () => {
  loading.value = true
  try {
    const data = await providerApi.getProviders()
    // 强制校验格式：后端返回 dict { id: {} }
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      providers.value = data
    } else if (Array.isArray(data)) {
      // 容错处理：如果是数组则转为对象
      const obj = {}
      data.forEach(p => { if (p.provider_id) obj[p.provider_id] = p })
      providers.value = obj
    } else {
      providers.value = {}
    }

    // 维持选中状态
    if (selectedId.value && !providers.value[selectedId.value]) {
      selectedId.value = null
    }
  } catch (e) {
    console.error('[ProviderManager] Load error:', e)
    toast.error('无法同步接入配置，请检查服务状态')
  } finally {
    loading.value = false
  }
}

const onAdded = async (newId) => {
  isDialogOpen.value = false
  await loadProviders()
  if (newId) selectedId.value = newId
}

const deleteProvider = async (id, event) => {
  if (event) event.stopPropagation()
  if (!confirm(`确定要移除 "${id}" 吗？\n此操作将删除该 Provider 下的所有配置。`)) return
  
  try {
    await providerApi.deleteProvider(id)
    toast.success(`已成功移除 ${id}`)
    if (selectedId.value === id) selectedId.value = null
    await loadProviders()
  } catch (e) {
    toast.error(e.response?.data?.detail || '删除失败')
  }
}

// 计算列表，增加安全性
const providerEntries = computed(() => {
  return Object.entries(providers.value || {}).map(([id, data]) => ({
    id,
    ...data
  }))
})

const selectedProviderData = computed(() => {
  return selectedId.value ? providers.value[selectedId.value] : null
})

onMounted(loadProviders)
</script>

<template>
  <div class="provider-manager">
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">模型接入</span>
        <button class="add-btn" @click="isDialogOpen = true">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <path d="M12 5v14M5 12h14"/>
          </svg>
          新增
        </button>
      </div>

      <div class="list-container" v-if="!loading">
        <!-- 空状态 -->
        <div class="empty-state" v-if="providerEntries.length === 0">
          <div class="empty-icon">+</div>
          <p>暂无接入记录</p>
          <button @click="isDialogOpen = true">立即添加</button>
        </div>

        <!-- 列表 -->
        <div
          v-for="p in providerEntries"
          :key="p.id"
          class="item"
          :class="{ active: selectedId === p.id }"
          @click="selectedId = p.id"
        >
          <div class="item-visual">
            {{ String(p.id).charAt(0).toUpperCase() }}
          </div>
          <div class="item-info">
            <span class="item-name">{{ p.id }}</span>
            <span class="item-count">{{ p.models?.length || 0 }} 个模型</span>
          </div>
          <button class="item-remove" @click.stop="deleteProvider(p.id, $event)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>
            </svg>
          </button>
        </div>
      </div>
      
      <div class="loading-state" v-else>
        <div class="spinner"></div>
      </div>
    </aside>

    <main class="content">
      <div class="placeholder" v-if="!selectedId">
        <div class="placeholder-icon">🤖</div>
        <h3>选择一个提供商开始配置</h3>
        <p>配置 API Key 和部署的模型列表，实时生效</p>
      </div>

      <ProviderEditor
        v-else-if="selectedProviderData"
        :key="selectedId"
        :provider-id="selectedId"
        :provider-data="selectedProviderData"
        @updated="loadProviders"
      />
    </main>

    <ProviderDialog
      v-if="isDialogOpen"
      @close="isDialogOpen = false"
      @success="onAdded"
    />
  </div>
</template>

<style scoped>
.provider-manager {
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
}

.item-name {
  font-size: 14px;
  color: #1e293b;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-count {
  font-size: 11px;
  color: #94a3b8;
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
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
