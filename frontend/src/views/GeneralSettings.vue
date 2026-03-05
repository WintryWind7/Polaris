<script setup>
import { ref, onMounted } from 'vue'
import configApi from '../services/configApi'
import { useToast } from 'vue-toastification'

const toast = useToast()
const isLoading = ref(false)

const config = ref({
  systemPrompt: '',
  modelStream: true // 暂未实装后端，保持前端状态
})

const loadConfig = async () => {
  try {
    const data = await configApi.getConfig()
    if (data && data.agent) {
      config.value.systemPrompt = data.agent.system_prompt
    }
  } catch (e) {
    console.error('加载项目配置失败:', e)
  }
}

const saveConfig = async () => {
  isLoading.value = true
  try {
    await configApi.updateConfig({
      agent: {
        system_prompt: config.value.systemPrompt
      }
    })
    toast.success('设置保存成功，AI 角色已更新')
  } catch (e) {
    console.error('保存设置失败:', e)
    toast.error('保存失败，请检查网络连接')
  } finally {
    isLoading.value = false
  }
}

onMounted(loadConfig)
</script>

<template>
  <div class="settings-view">
    <div class="header">
      <h2>系统设定</h2>
      <p class="subtitle">调整你的 AI 助手性格、语气及全局行为规则</p>
    </div>

    <div class="settings-content">
      <!-- 模型设定 -->
      <section class="settings-card">
        <h3>对话角色行为</h3>
        
        <div class="form-group">
          <label>系统提示词 (System Prompt)</label>
          <textarea 
            v-model="config.systemPrompt" 
            rows="8" 
            placeholder="告诉 AI 它应该如何扮演角色，例如：'你是一个严谨的程序员，回答问题言简意赅'..."
          ></textarea>
          <p class="field-hint">提示：你可以使用 {current_time} 占位符来让 AI 感知当前时间。</p>
        </div>

        <div class="form-group checkbox-group">
          <label class="toggle">
            <input type="checkbox" v-model="config.modelStream" />
            <span class="slider"></span>
          </label>
          <span>启用流式输出 (暂不可用)</span>
        </div>
      </section>
      
      <!-- 操作区 -->
      <div class="actions">
        <button 
          class="btn primary" 
          @click="saveConfig" 
          :disabled="isLoading"
        >
          {{ isLoading ? '保存中...' : '保存全局设定' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  height: 100%;
  padding: 36px;
  overflow-y: auto;
  background: #ffffff;
}

.header {
  margin-bottom: 32px;
}

h2 {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  color: #1e293b;
  letter-spacing: -0.4px;
}

.subtitle {
  font-size: 14px;
  color: #64748b;
  margin-top: 6px;
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 700px;
}

.settings-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

h3 {
  font-size: 15px;
  font-weight: 600;
  color: #3b82f6;
  margin: 0 0 20px 0;
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 12px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

label {
  font-size: 13px;
  color: #64748b;
  font-weight: 600;
}

.field-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

input[type="text"],
textarea {
  width: 100%;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 16px;
  color: #1e293b;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  transition: all 0.2s ease;
  outline: none;
}

input[type="text"]:focus,
textarea:focus {
  border-color: #3b82f6;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

textarea {
  resize: vertical;
}

.checkbox-group {
  flex-direction: row;
  align-items: center;
  gap: 12px;
}

.checkbox-group span {
  font-size: 14px;
  color: #1e293b;
}

/* Custom Toggle Switch */
.toggle {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #e2e8f0;
  transition: .3s;
  border-radius: 24px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: #fff;
  transition: .3s;
  border-radius: 50%;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

input:checked + .slider {
  background-color: #3b82f6;
}

input:checked + .slider:before {
  transform: translateX(20px);
}

/* Actions */
.actions {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
}

.btn {
  padding: 12px 28px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn.primary {
  background: #3b82f6;
  color: white;
  box-shadow: 0 4px 6px rgba(59, 130, 246, 0.2);
}

.btn.primary:hover:not(:disabled) {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 6px 12px rgba(59, 130, 246, 0.3);
}

.btn.primary:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}
</style>
