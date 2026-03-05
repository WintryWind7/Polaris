<script setup>
import { ref, watch } from 'vue'
import providerApi from '../../services/providerApi'
import { useToast } from 'vue-toastification'

const props = defineProps({
  providerId: { type: String, required: true },
  providerData: { type: Object, required: true }
})

const emit = defineEmits(['updated'])
const toast = useToast()

// 保存状态: idle / saving / saved / error
const saveStatus = ref('idle')
let debounceTimer = null

// 本地表单（深拷贝避免直接改 props）
const form = ref({
  api_key: props.providerData.api_key || '',
  api_base_url: props.providerData.api_base_url || '',
  models: JSON.parse(JSON.stringify(props.providerData.models || []))
})

// 防抖自动保存（字段修改 800ms 后触发）
const triggerAutoSave = () => {
  console.log('[ProviderEditor] Auto-save triggered for:', props.providerId)
  clearTimeout(debounceTimer)
  saveStatus.value = 'pending'
  debounceTimer = setTimeout(autoSave, 800)
}

const autoSave = async () => {
  saveStatus.value = 'saving'
  try {
    const payload = {
      api_base_url: form.value.api_base_url,
      models: form.value.models.filter(m => m.model_id.trim())
    }
    // 只有用户填写了新 key 才更新
    if (form.value.api_key.trim()) {
      payload.api_key = form.value.api_key.trim()
    }

    console.log('[ProviderEditor] Updating provider:', props.providerId, 'payload:', payload)
    await providerApi.updateProvider(props.providerId, payload)
    console.log('[ProviderEditor] Update success')
    saveStatus.value = 'saved'
    emit('updated')
    // 3s 后回到 idle
    setTimeout(() => { saveStatus.value = 'idle' }, 3000)
  } catch (e) {
    console.error('[ProviderEditor] Update error:', e)
    saveStatus.value = 'error'
    toast.error(e.response?.data?.detail || '保存失败')
    setTimeout(() => { saveStatus.value = 'idle' }, 4000)
  }
}

watch(
  () => form.value.api_base_url,
  triggerAutoSave
)

// 监听 API Key 变化
watch(
  () => form.value.api_key,
  triggerAutoSave
)


// 模型操作
const addModel = () => {
  form.value.models.push({ model_id: '', display_name: '' })
}

const removeModel = (index) => {
  form.value.models.splice(index, 1)
  triggerAutoSave()
}

// 模型字段 blur 时触发保存
const onModelBlur = () => triggerAutoSave()

const statusText = {
  idle: '',
  pending: '待保存...',
  saving: '保存中...',
  saved: '✓ 已保存',
  error: '✕ 保存失败'
}
</script>

<template>
  <div class="provider-editor">
    <!-- 编辑器顶部 -->
    <div class="editor-header">
      <div class="editor-title">
        <h3>{{ providerId }}</h3>
      </div>
      <div class="save-status" :class="saveStatus">
        <span v-if="saveStatus !== 'idle'">{{ statusText[saveStatus] }}</span>
      </div>
    </div>

    <!-- 表单区域 -->
    <div class="editor-body">
      <!-- 基础信息 -->
      <section class="section">
        <h4 class="section-title">基本信息</h4>

        <div class="field">
          <label>API Base URL</label>
          <input
            type="text"
            v-model="form.api_base_url"
            placeholder="https://"
          />
        </div>

        <div class="field">
          <label>
            API Key
            <span class="key-status" :class="providerData.api_key ? 'set' : 'unset'">
              {{ providerData.api_key ? '已设置' : '未设置' }}
            </span>
          </label>
          <input
            type="text"
            v-model="form.api_key"
            placeholder="请输入 API Key"
          />
        </div>
      </section>

      <!-- 模型管理 -->
      <section class="section">
        <div class="section-header">
          <h4 class="section-title">挂载模型</h4>
          <button class="btn-add" @click="addModel">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            添加模型
          </button>
        </div>

        <div class="models-list" v-if="form.models.length > 0">
          <div class="model-item" v-for="(m, i) in form.models" :key="i">
            <div class="model-index">{{ i + 1 }}</div>
            <input
              type="text"
              v-model="m.model_id"
              placeholder="模型 ID（必填）"
              @blur="onModelBlur"
            />
            <input
              type="text"
              v-model="m.display_name"
              placeholder="显示别名（选填）"
              @blur="onModelBlur"
            />
            <button class="btn-del" @click="removeModel(i)" title="删除该模型">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>

        <div class="models-empty" v-else>
          暂无挂载模型 — 点击上方「添加模型」开始配置
        </div>
      </section>

      <!-- 只读信息 -->
      <section class="section muted-section">
        <h4 class="section-title">访问标识</h4>
        <div class="readonly-row">
          <span class="readonly-label">Provider ID</span>
          <code class="readonly-value">{{ providerId }}</code>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.provider-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 顶部 */
.editor-header {
  padding: 20px 28px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.editor-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.editor-title h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}


/* 保存状态指示器 */
.save-status {
  font-size: 12px;
  font-weight: 500;
  padding: 4px 12px;
  border-radius: 20px;
  transition: all 0.3s;
  min-width: 80px;
  text-align: center;
}

.save-status.pending { color: #94a3b8; }
.save-status.saving  { color: #d97706; }
.save-status.saved   { color: #10b981; background: rgba(16, 185, 129, 0.1); }
.save-status.error   { color: #ef4444; background: rgba(239, 68, 68, 0.1); }

/* 主体滚动区域 */
.editor-body {
  flex-grow: 1;
  overflow-y: auto;
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* 字段 */
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.field label {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}

.key-status {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 20px;
}
.key-status.set   { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.key-status.unset { background: rgba(239, 68, 68, 0.1); color: #ef4444; }

.field input {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 11px 14px;
  color: #1e293b;
  font-size: 14px;
  outline: none;
  transition: all 0.2s;
  width: 100%;
  box-sizing: border-box;
}

.field input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  background: #ffffff;
}

/* 模型列表 */
.btn-add {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.2);
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-add:hover { background: rgba(59, 130, 246, 0.15); }

.models-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.model-item {
  display: grid;
  grid-template-columns: 28px 1fr 1fr 32px;
  gap: 12px;
  align-items: center;
  padding: 8px 12px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  transition: all 0.2s;
}

.model-item:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.model-index {
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
  font-family: monospace;
}

.model-item input {
  background: transparent;
  border: none;
  border-bottom: 1px solid #f1f5f9;
  border-radius: 0;
  padding: 8px 4px;
  color: #1e293b;
  font-size: 13px;
  outline: none;
  transition: all 0.2s;
  width: 100%;
  box-sizing: border-box;
}

.model-item input:focus {
  border-bottom-color: #3b82f6;
}

.btn-del {
  background: transparent;
  border: none;
  color: rgba(239, 68, 68, 0.5);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.btn-del:hover { color: #ef4444; background: rgba(239, 68, 68, 0.08); }

.models-empty {
  padding: 32px;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
  border: 2px dashed #f1f5f9;
  border-radius: 12px;
}

/* 只读区 */
.muted-section {
  padding-top: 24px;
  border-top: 1px solid #f1f5f9;
}

.readonly-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.readonly-label {
  font-size: 13px;
  color: #94a3b8;
  width: 100px;
  flex-shrink: 0;
}

.readonly-value {
  font-size: 13px;
  color: #64748b;
  font-family: monospace;
  background: #f1f5f9;
  padding: 5px 12px;
  border-radius: 8px;
}
</style>
