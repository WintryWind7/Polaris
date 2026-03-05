import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',  // 监听所有网络接口
    port: 6546,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:6547',
        changeOrigin: true,
      },
    },
    watch: {
      ignored: ['**/__pycache__/**', '**/*.pyc'],
    },
  },
})
