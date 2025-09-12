import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发期：页面只从 5173 打开；API 全部走 /api 相对路径，由此处代理到后端。
// 注意：前端容器内访问后端需用服务名 backend:8000，而不是 127.0.0.1 或 172.18.x.x。
export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
        // 若后端实际路由本就以 /api 开头，不做 rewrite
        // rewrite: (p) => p
      }
    }
  }
})