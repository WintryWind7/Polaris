<script setup>
import { ref } from 'vue'
import providerApi from '../../services/providerApi'
import { useToast } from 'vue-toastification'

const emit = defineEmits(['close', 'success'])
const toast = useToast()

const saving = ref(false)

const form = ref({
  provider_id: '',
  api_key: '',
  api_base_url: '',
  models: []
})

const addModel = () => {
  form.value.models.push({ model_id: '', display_name: '' })
}

const removeModel = (i) => {
  form.value.models.splice(i, 1)
}

const submit = async () => {
  console.log('[ProviderDialog] Submit triggered', form.value)
  if (!form.value.provider_id.trim()) {
    toast.warning('请填写 Provider 名称')
    return
  }

  saving.value = true
  try {
    const payload = { ...form.value }
    // 过滤掉空模型行
    payload.models = payload.models.filter(m => m.model_id.trim())
    console.log('[ProviderDialog] Sending payload:', payload)

    const res = await providerApi.addProvider(payload)
    console.log('[ProviderDialog] Success:', res)
    toast.success('Provider 创建成功！')
    emit('success', res.provider_id)
  } catch (e) {
    console.error('[ProviderDialog] Error:', e)
    toast.error(e.response?.data?.detail || '创建失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="dialog-overlay" @mousedown.self="emit('close')">
    <div class="dialog">
      <!-- 头部 -->
      <div class="dialog-header">
        <h2>新增 Provider</h2>
        <span class="close-btn" @click="emit('close')">&times;</span>
      </div>

      <!-- 表单 -->
      <div class="dialog-body scrollable">
        <div class="form-group">
          <label>Provider 名称 <span class="req">*</span></label>
          <input type="text" v-model="form.provider_id" placeholder="如：我的阿里云" autofocus />
          <span class="hint">此名称也是 Provider ID，如果重复会自动添加 _1 后缀</span>
        </div>

        <div class="form-group">
          <label>API Base URL</label>
          <input type="text" v-model="form.api_base_url" placeholder="https://" />
        </div>

        <div class="form-group">
          <label>API Key</label>
          <input type="password" v-model="form.api_key" autocomplete="new-password" placeholder="输入 API 密钥（可稍后填写）" />
        </div>

        <!-- 模型列表 -->
        <div class="models-section">
          <div class="models-label-row">
            <label>挂载模型（选填）</label>
            <button class="btn-add-model" @click="addModel">+ 添加</button>
          </div>
          <div class="model-rows" v-if="form.models.length > 0">
            <div class="model-row" v-for="(m, i) in form.models" :key="i">
              <input type="text" v-model="m.model_id" placeholder="模型 ID" />
              <input type="text" v-model="m.display_name" placeholder="显示别名" />
              <button class="btn-del-model" @click="removeModel(i)">×</button>
            </div>
          </div>
          <p class="models-hint">也可以后续通过编辑页再配置模型列表</p>
        </div>
      </div>

      <!-- 底部 -->
      <div class="dialog-footer">
        <button class="btn secondary" @click="emit('close')">取消</button>
        <button class="btn primary" @click="submit" :disabled="saving">
          {{ saving ? '创建中...' : '创建 Provider' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(6px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.dialog {
  width: 90%;
  max-width: 480px;
  max-height: 88vh;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  box-shadow: 0 24px 48px -12px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUp 0.28s cubic-bezier(0.16,1,0.3,1);
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

.dialog-header {
  padding: 20px 24px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.dialog-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}

.close-btn {
  font-size: 24px;
  color: #94a3b8;
  cursor: pointer;
  line-height: 1;
  transition: color 0.2s;
  user-select: none;
}
.close-btn:hover { color: #1e293b; }

.dialog-body.scrollable {
  overflow-y: auto;
  flex-grow: 1;
  padding: 24px;
}

.form-group {
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

label {
  font-size: 13px;
  color: #64748b;
  font-weight: 600;
}

.req { color: #ef4444; }

.hint {
  font-size: 11px;
  color: #94a3b8;
  margin-top: -2px;
}

input[type="text"],
input[type="password"] {
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

input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  background: #ffffff;
}

.models-section {
  border-top: 1px dashed #e2e8f0;
  padding-top: 20px;
  margin-top: 8px;
}

.models-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.btn-add-model {
  font-size: 12px;
  font-weight: 600;
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  padding: 5px 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-add-model:hover { background: rgba(59, 130, 246, 0.12); }

.model-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.model-row {
  display: grid;
  grid-template-columns: 1fr 1fr 28px;
  gap: 10px;
  align-items: center;
}

.model-row input {
  padding: 9px 12px;
  font-size: 13px;
}

.btn-del-model {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 20px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  transition: all 0.2s;
}
.btn-del-model:hover { color: #ef4444; }

.models-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #94a3b8;
}

.dialog-footer {
  padding: 16px 24px;
  border-top: 1px solid #f1f5f9;
  background: #f8fafc;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  flex-shrink: 0;
}

.btn {
  padding: 10px 24px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.btn.secondary {
  background: #ffffff;
  color: #64748b;
  border: 1px solid #e2e8f0;
}
.btn.secondary:hover { background: #f1f5f9; color: #1e293b; }

.btn.primary {
  background: #3b82f6;
  color: #fff;
  box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3);
}
.btn.primary:hover:not(:disabled) {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.4);
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
