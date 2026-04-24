# Polaris 前端

Vue 3 + Vite 构建的 Web UI，与后端通过 HTTP API 和 WebSocket 通信。

## 快速启动

```bash
# 安装依赖
npm install

# 开发模式（HMR）
npm run dev

# 生产构建
npm run build
```

启动后访问 http://127.0.0.1:6546

## 目录结构

```
frontend/
├── src/
│   ├── App.vue        # 根组件
│   ├── main.js        # 入口
│   ├── router/        # Vue Router 路由配置
│   ├── layouts/       # 布局组件（DashboardLayout）
│   ├── views/         # 页面视图
│   │   ├── HomeView.vue       # 首页
│   │   ├── ChatView.vue       # 聊天界面
│   │   ├── LogsView.vue       # 实时日志查看
│   │   ├── SettingsView.vue   # 设置入口
│   │   ├── providers/         # LLM Provider 管理
│   │   └── embeddings/        # Embedding 模型管理
│   ├── components/    # 通用组件（ChatInterface, FileBrowser）
│   ├── services/      # API 调用封装（axios）
│   ├── config/        # 前端配置（日志模块定义等）
│   └── style.css      # 全局样式
├── index.html         # HTML 模板
├── vite.config.js     # Vite 配置
└── package.json
```

## 技术栈

- **框架**: Vue 3（Composition API）
- **路由**: Vue Router 4
- **构建**: Vite 7
- **HTTP**: Axios
- **图标**: Lucide Vue
- **通知**: Vue Toastification
