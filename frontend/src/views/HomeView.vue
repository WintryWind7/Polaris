<script setup>
// 空白首页
</script>

<template>
  <div class="home-view">
    <div class="welcome-box">
      <h2>Welcome to Polaris</h2>
      <p class="subtitle">AI Assistant Dashboard</p>
      
      <div class="empty-state">
        <div class="glow-orb"></div>
        <p>系统准备就绪，等待新指令</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-view {
  height: 100%;
  padding: 40px;
  display: flex;
  flex-direction: column;
}

.welcome-box {
  margin-bottom: 40px;
}

h2 {
  font-size: 32px;
  font-weight: 700;
  margin: 0;
  color: #1e293b;
  letter-spacing: -0.5px;
}

.subtitle {
  font-size: 16px;
  color: #64748b;
  margin-top: 8px;
  font-weight: 500;
}

.empty-state {
  margin-top: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  border: 1px dashed #e2e8f0;
  border-radius: 24px;
  background: #f8fafc;
  position: relative;
  overflow: hidden;
}

.glow-orb {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.2) 0%, rgba(59, 130, 246, 0) 70%);
  filter: blur(15px);
  animation: float 4s ease-in-out infinite;
  margin-bottom: 20px;
}

@keyframes float {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-15px) scale(1.1); }
}

.empty-state p {
  color: #64748b;
  font-size: 14px;
  letter-spacing: 0.5px;
}
</style>
