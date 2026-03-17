<script setup>
import { ref, watch } from 'vue'
import embeddingApi from '../../services/embeddingApi'
import { useToast } from 'vue-toastification'
import FileBrowser from '../../components/FileBrowser.vue'

const props = defineProps({
  embeddingId: String,
  embeddingData: Object
})

const emit = defineEmits(['updated'])
const toast = useToast()

// 本地表单数据
const form = ref({
  model_path: '',
  enabled: true
})

const saving = ref(false)
const hasChanges = ref(false)
const showBrowser = ref(false)

// 监听 props 变化，重置表单
watch(() => props.embeddingData, (newData) => {
  if (newData) {
    form.value = {
      model_path: newData.model_path || '',
      enabled: newData.enabled !== false
    }
    hasChanges.value = false
  }
}, { immediate: true })

// 监听表单变化
watch(form, () => {
  hasChanges.value = true
}, { deep: true })

// 打开文件浏览器
const openBrowser = () => {
  showBrowser.value = true
}

// 选择路径
const onSelectPath = (path) => {
  form.value.model_path = path
  showBrowser.value = false
}

// 保存更改
const save = async () => {
  if (!hasChanges.value) {
    toast.info('没有需要保存的更改')
    return
  }

  // 如果要启用此模型，且之前是禁用状态，需要确认
  if (form.value.enabled && !props.embeddingData.enabled) {
    if (!confirm(
      '切换 Embedding 模型\n\n' +
      '注意：同一时间只能启用一个 Embedding 模型。\n' +
      '启用此模型将自动禁用其他模型。\n\n' +
      '切换模型后，需要手动重建向量数据库才能生效。\n\n' +
      '确定要切换吗？'
    )) {
      return
    }
  }

  saving.value = true

  try {
    const updates = {}

    if (form.value.model_path !== props.embeddingData.model_path) {
      updates.model_path = form.value.model_path
    }

    if (form.value.enabled !== props.embeddingData.enabled) {
      updates.enabled = form.value.enabled
    }

    await embeddingApi.updateEmbedding(props.embeddingId, updates)

    toast.success('保存成功')
    hasChanges.value = false
    emit('updated')
  } catch (error) {
    const msg = error.response?.data?.detail || '保存失败'
    toast.error(msg)
  } finally {
    saving.value = false
  }
}

// 重置表单
const reset = () => {
  form.value = {
    model_path: props.embeddingData.model_path || '',
    enabled: props.embeddingData.enabled !== false
  }
  hasChanges.value = false
}
</script>

<template>
  <div class="editor">
    <div class="editor-header">
      <h3>{{ embeddingId }}</h3>
      <div class="actions">
        <button v-if="hasChanges" class="btn-reset" @click="reset" :disabled="saving">
          重置
        </button>
        <button class="btn-save" @click="save" :disabled="saving || !hasChanges">
          {{ saving ? '保存中...' : '保存更改' }}
        </button>
      </div>
    </div>

    <div class="editor-body">
      <div class="section">
        <h4>基本信息</h4>

        <div class="form-group">
          <label>Embedding ID</label>
          <input type="text" :value="embeddingId" disabled />
        </div>

        <div class="form-group">
          <label>模型类型</label>
          <input type="text" :value="embeddingData.model_type" disabled />
        </div>

        <div class="form-group">
          <label>向量维度</label>
          <input type="text" :value="embeddingData.dimension || '未检测'" disabled />
        </div>
      </div>

      <div class="section">
        <h4>模型配置</h4>

        <div class="form-group">
          <label>模型路径</label>
          <div class="path-input">
            <input
              v-model="form.model_path"
              type="text"
              placeholder="输入模型文件夹的绝对路径"
              :disabled="saving"
            />
            <button class="btn-browse" @click="openBrowser" :disabled="saving" title="浏览文件夹">
              ⋯
            </button>
          </div>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              v-model="form.enabled"
              type="checkbox"
              :disabled="saving"
            />
            <span>启用此模型</span>
          </label>
        </div>
      </div>
    </div>

    <!-- 文件浏览器 -->
    <FileBrowser
      v-if="showBrowser"
      :initial-path="form.model_path"
      @close="showBrowser = false"
      @select="onSelectPath"
    />
  </div>
</template>

<style scoped>
.editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: white;
}

.editor-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.editor-header h3 {
  margin: 0;
  font-size: 18px;
  color: #1e293b;
}

.actions {
  display: flex;
  gap: 12px;
}

.btn-reset,
.btn-save {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-reset {
  background: white;
  border: 1px solid #e2e8f0;
  color: #64748b;
}

.btn-reset:hover:not(:disabled) {
  background: #f8fafc;
}

.btn-save {
  background: #3b82f6;
  border: 1px solid #3b82f6;
  color: white;
}

.btn-save:hover:not(:disabled) {
  background: #2563eb;
}

.btn-reset:disabled,
.btn-save:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.editor-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.section {
  margin-bottom: 32px;
}

.section:last-child {
  margin-bottom: 0;
}

.section h4 {
  margin: 0 0 16px;
  font-size: 14px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
}

.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

.form-group input[type="text"] {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  transition: all 0.2s;
}

.form-group input[type="text"]:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-group input[type="text"]:disabled {
  background: #f8fafc;
  color: #94a3b8;
  cursor: not-allowed;
}

.path-input {
  display: flex;
  gap: 8px;
  align-items: center;
}

.path-input input {
  flex: 1;
}

.btn-browse {
  padding: 10px 12px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
  font-weight: bold;
  line-height: 1;
}

.btn-browse:hover:not(:disabled) {
  background: #e2e8f0;
  color: #1e293b;
}

.btn-browse:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.checkbox-label input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"]:disabled {
  cursor: not-allowed;
}

.checkbox-label span {
  font-size: 14px;
  color: #334155;
}
</style>


