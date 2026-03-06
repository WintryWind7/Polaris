import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

// 从 data/config.json 动态读取端口
// 这样用户在 UI「系统设置」里改了端口后，重启服务即自动生效
function loadPolarisConfig() {
  const configPath = resolve(__dirname, '../data/config.json')
  try {
    if (existsSync(configPath)) {
      const data = JSON.parse(readFileSync(configPath, 'utf-8'))
      return {
        backendPort: data?.server?.port ?? 6547,
        frontendPort: data?.server?.frontend_port ?? 6546
      }
    }
  } catch (e) {
    console.warn('[vite.config] 读取 config.json 失败，使用默认端口:', e.message)
  }
  return { backendPort: 6547, frontendPort: 6546 }
}

const { backendPort, frontendPort } = loadPolarisConfig()

console.log(`[Polaris] 前端端口: ${frontendPort}，后端代理: ${backendPort}`)

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: frontendPort,
    strictPort: true,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
    },
    watch: {
      ignored: ['**/__pycache__/**', '**/*.pyc'],
    },
  },
})
