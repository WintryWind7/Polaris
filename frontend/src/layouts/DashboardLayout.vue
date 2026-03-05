<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LayoutDashboard, Settings, MessageSquare, Terminal } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const navigation = [
  { name: '仪表盘', path: '/', icon: LayoutDashboard },
  { name: '智能对话', path: '/chat', icon: MessageSquare },
  { name: '运行日志', path: '/logs', icon: Terminal },
  { name: '对话配置', path: '/settings', icon: Settings },
]

const currentPath = computed(() => route.path)

const navigateTo = (path) => {
  router.push(path)
}
</script>

<template>
  <div class="dashboard-layout">
    <!-- 侧边导航栏 -->
    <aside class="sidebar">
      <div class="logo-area">
        <div class="logo-icon">✨</div>
        <h1 class="logo-text">Polaris</h1>
      </div>

      <nav class="nav-menu">
        <div 
          v-for="item in navigation" 
          :key="item.path"
          class="nav-item"
          :class="{ active: currentPath === item.path }"
          @click="navigateTo(item.path)"
        >
          <component :is="item.icon" class="nav-icon" :size="20" />
          <span class="nav-label">{{ item.name }}</span>
        </div>
      </nav>

      <div class="sidebar-footer">
        <div class="status-indicator">
          <span class="dot online"></span>
          <span class="text">系统在线</span>
        </div>
      </div>
    </aside>

    <!-- 主内容区域 -->
    <main class="main-content">
      <div class="glass-container">
        <!-- 路由匹配到的视图将渲染在这里 -->
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<style scoped>
.dashboard-layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background-color: #f8fafc;
  color: #1e293b;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* 侧边导航栏 - 玻璃拟态设计 */
.sidebar {
  width: 260px;
  height: 100%;
  background: #f1f5f9;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  padding: 24px 16px;
  z-index: 10;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 12px;
  margin-bottom: 40px;
}

.logo-icon {
  font-size: 24px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.logo-text {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.5px;
  margin: 0;
  background: linear-gradient(90deg, #1e293b, #64748b);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.nav-menu {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  color: #64748b;
  position: relative;
  overflow: hidden;
}

.nav-item:hover {
  background: rgba(59, 130, 246, 0.05);
  color: #1e293b;
}

.nav-item.active {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  font-weight: 600;
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  height: 60%;
  width: 4px;
  background: #3b82f6;
  border-radius: 0 4px 4px 0;
}

.nav-icon {
  transition: transform 0.3s ease;
}

.nav-item:hover .nav-icon {
  transform: scale(1.1);
}

.sidebar-footer {
  padding: 16px 12px 0;
  border-top: 1px solid #e2e8f0;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #64748b;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.online {
  background: #4ade80;
  box-shadow: 0 0 10px rgba(74, 222, 128, 0.4);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { opacity: 1; box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.4); }
  70% { opacity: 0.8; box-shadow: 0 0 0 6px rgba(74, 222, 128, 0); }
  100% { opacity: 1; box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }
}

/* 主内容区域 */
.main-content {
  flex: 1;
  padding: 0;
  position: relative;
  overflow-y: auto;
  background: #ffffff;
}

.glass-container {
  background: #ffffff;
  width: 100%;
  min-height: 100vh;
  position: relative;
  z-index: 1;
  overflow: hidden;
}

/* 页面切换动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
