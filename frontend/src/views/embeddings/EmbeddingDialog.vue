<script setup>
import { ref } from 'vue'
import embeddingApi from '../../services/embeddingApi'
import { useToast } from 'vue-toastification'
import FileBrowser from '../../components/FileBrowser.vue'

const toast = useToast()
const emit = defineEmits(['close', 'success'])

// 表单数据
const form = ref({
  embedding_id: '',
  model_type: 'local',
  model_path: ''
})

const submitting = ref(false)
const showBrowser = ref(false)

// 打开文件浏览器
const openBrowser = () => {
  showBrowser.value = true
}

// 选择路径
const onSelectPath = (path) => {
  form.value.model_path = path
  showBrowser.value = false

  // 如果用户没有填写 ID，自动使用文件夹名
  if (!form.value.embedding_id) {
    const folderName = path.split(/[/\\]/).pop()
    form.value.embedding_id = folderName
  }
}

// 提交表单
const submit = async () => {
  // 验证
  if (!form.value.embedding_id.trim()) {
    toast.error('请输入 Embedding ID')
    return
  }

  if (!form.value.model_path.trim()) {
    toast.error('请选择模型路径')
    return
  }

  submitting.value = true

  try {
    const result = await embeddingApi.addEmbedding({
      embedding_id: form.value.embedding_id.trim(),
      model_type: form.value.model_type,
      model_path: form.value.model_path.trim()
    })

    toast.success(result.message || 'Embedding 添加成功')
    emit('success', result.embedding_id)
  } catch (error) {
    const msg = error.response?.data?.detail || '添加失败'
    toast.error(msg)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog">
      <div class="dialog-header">
        <h3>新增 Embedding 模型</h3>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>

      <div class="dialog-body">
        <div class="form-group">
          <label>Embedding ID <span class="required">*</span></label>
          <input
            v-model="form.embedding_id"
            type="text"
            placeholder="例如: bge-small-zh-v1.5"
            :disabled="submitting"
          />
          <p class="hint">唯一标识，用于引用此模型</p>
        </div>

        <div class="form-group">
          <label>模型类型</label>
          <select v-model="form.model_type" :disabled="submitting">
            <option value="local">本地模型</option>
            <option value="api" disabled>API 模型（暂不支持）</option>
          </select>
        </div>

        <div class="form-group">
          <label>模型路径 <span class="required">*</span></label>
          <div class="path-input">
            <input
              v-model="form.model_path"
              type="text"
              placeholder="输入模型文件夹的绝对路径..."
              :disabled="submitting"
            />
            <button class="btn-browse" @click="openBrowser" :disabled="submitting" title="浏览文件夹">
              ⋯
            </button>
          </div>
          <p class="hint">
            可以直接输入路径，或点击右侧按钮浏览文件夹
          </p>
        </div>
      </div>

      <div class="dialog-footer">
        <button class="btn-cancel" @click="$emit('close')" :disabled="submitting">
          取消
        </button>
        <button class="btn-submit" @click="submit" :disabled="submitting">
          {{ submitting ? '添加中...' : '添加' }}
        </button>
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
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: white;
  border-radius: 12px;
  width: 500px;
  max-width: 90vw;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.dialog-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dialog-header h3 {
  margin: 0;
  font-size: 18px;
  color: #1e293b;
}

.close-btn {
  background: none;
  border: none;
  font-size: 28px;
  color: #94a3b8;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #f1f5f9;
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
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

.required {
  color: #ef4444;
}

.form-group input[type="text"],
.form-group select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  transition: all 0.2s;
}

.form-group input[type="text"]:focus,
.form-group select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-group input[type="text"]:disabled,
.form-group select:disabled {
  background: #f8fafc;
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

.hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #94a3b8;
}

.dialog-footer {
  padding: 16px 24px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-cancel,
.btn-submit {
  padding: 10px 20px;
  border-radius: 8px;
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

.btn-cancel:hover:not(:disabled) {
  background: #f8fafc;
}

.btn-submit {
  background: #3b82f6;
  border: 1px solid #3b82f6;
  color: white;
}

.btn-submit:hover:not(:disabled) {
  background: #2563eb;
}

.btn-cancel:disabled,
.btn-submit:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
</style>
