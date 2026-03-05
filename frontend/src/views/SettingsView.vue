<script setup>
import { ref } from 'vue'
import ProviderManager from './providers/ProviderManager.vue'
import GeneralSettings from './GeneralSettings.vue'

const activeTab = ref('providers')

const tabs = [
  { id: 'providers', label: 'Providers', component: ProviderManager },
  { id: 'general', label: '通用设置', component: GeneralSettings }
]
</script>

<template>
  <div class="settings-view">
    <div class="top-nav">
      <div class="header">
        <h2>对话配置</h2>
      </div>
      <div class="tabs">
        <div
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-item"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </div>
      </div>
    </div>

    <div class="tab-content">
      <keep-alive>
        <component :is="tabs.find(t => t.id === activeTab)?.component" />
      </keep-alive>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.top-nav {
  padding: 28px 36px 0;
  flex-shrink: 0;
}

.header h2 {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 16px 0;
  letter-spacing: -0.3px;
}

.tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #e2e8f0;
}

.tab-item {
  padding: 10px 18px;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
  position: relative;
  top: 1px;
  user-select: none;
}

.tab-item:hover {
  color: #1e293b;
  background: #f1f5f9;
}

.tab-item.active {
  color: #3b82f6;
  font-weight: 600;
  border-bottom: 2px solid #3b82f6;
}

.tab-content {
  flex-grow: 1;
  overflow: hidden;
}
</style>
