# SOPilot 前后端集成规范

## 🚨 重要声明

本文档为**强制执行规范**，任何前后端集成相关的代码修改必须**严格遵守**以下条款。**不允许**开发人员自行判断或变通，必须逐条执行。

---

## 📋 总体目标（必须全部满足）

1. **开发阶段**：页面**只**从 **[http://localhost:5173](http://localhost:5173)** 访问
2. **禁止硬编码**：任何前端代码里**不得**出现 `127.0.0.1`、`localhost:8000`、`172.18.*.*` 等**硬编码**后端地址
3. **API路径规范**：API 统一写成相对路径 `/api/...`，由 **Vite 代理**转发到后端
4. **Docker网络**：前端在 Docker 容器内运行时，Vite 代理的 `target` 必须写 **`http://backend:8000`**（Docker Compose 服务名），**禁止**使用容器 IP
5. **环境变量限制**：不使用也不新增 `APP_SERVE_FRONTEND` 等环境变量开关

---

## 🔧 具体执行步骤

## A. 修改前端代理配置（必须覆盖写入整个文件）

**文件**：`frontend/vite.config.ts`
**动作**：将该文件内容**整体替换**为以下完整内容（若已有同名插件/配置，全部以此为准）：

```ts
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
```

> 解释（无需写入代码）：这里固定用 `backend:8000`，因为前端在容器里跑；禁止写 `http://172.18.0.4:8000` 或 `http://127.0.0.1:8000`。

---

## B. 移除所有硬编码 API 地址（严格搜索并替换）

**范围**：`frontend/` 目录下全部源码。
**操作**：

1. 全项目搜索以下模式，若存在则**删除常量定义**并**改造调用**：

   * `const API_BASE = 'http://127.0.0.1:8000'`
   * `const API_BASE = 'http://localhost:8000'`
   * `const API_BASE = 'http://172.18.`（任意容器 IP）
   * 以及任何以 `http://...:8000` 开头的 API BASE 硬编码

2. 将所有使用处改为**相对路径**：

   * 把 `fetch(\`\${API\_BASE}/api/...`)`、`axios.get('http://...:8000/api/...')` 等，统一改为
     **`fetch('/api/...')`** 或 **`axios.get('/api/...')`**。
   * 若有集中封装（例如 `api.ts` / `http.ts`），统一把 base 配成 `''`，并在调用处直接写 `/api/...`。

3. 严格验证：修改后，`frontend/` 内**不应再出现** `http://127.0.0.1:8000`、`localhost:8000`、`172.18.`、`API_BASE =` 等字符串。

---

## C. 确认/补充前端路由（若已存在则保持一致）

**文件**：`frontend/src/router/index.ts`
**动作**：确保存在如下路由项；若已存在 `/knowledge` 路由，保持路径与组件名一致，不做额外改动。

```ts
{
  path: '/knowledge',
  component: () => import('@/views/KnowledgeBase.vue')
}
```

---

## D. 调整 docker-compose（仅限必要改动）

**文件**：`docker-compose.yml`
**动作**：确保前端容器与后端容器配合上述代理策略运行；按下列片段**对齐/修正**相关字段（不要改服务名）。

```yaml
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    # ⚠️ 禁止使用会覆盖 /app 的整库挂载（例如 - .:/app）
    # 若当前文件存在该挂载，请删除之，仅保留必要业务挂载：
    volumes:
      - ./backend/src:/app/backend/src
      - ./backend/requirements.txt:/app/backend/requirements.txt
      - ./output:/app/output
    command: >
      sh -c "
      pip install -r /app/backend/requirements.txt &&
      python -m uvicorn app.asgi:app --host 0.0.0.0 --port 8000 --app-dir /app/backend/src --reload
      "

  frontend:
    image: node:20-bookworm-slim
    working_dir: /app/frontend
    volumes:
      - ./frontend:/app/frontend
    command: >
      sh -c "
      npm config set registry https://registry.npmmirror.com &&
      npm ci --no-audit --no-fund &&
      npm run dev -- --host
      "
    ports:
      - "5173:5173"
```

**硬性要求**：

* 不得出现 `172.18.*.*` 这类容器 IP；
* 不得新增/使用任何 `APP_SERVE_FRONTEND` 环境变量；
* 不得改变 `services.backend` 与 `services.frontend` 的服务名（供代理使用）。

---

## E. 验收清单（自检必须全部通过）

1. 运行：

```bash
docker compose down
docker compose up -d --build
```

2. 浏览器访问 **[http://localhost:5173/knowledge](http://localhost:5173/knowledge)**，修改 `frontend/src/views/KnowledgeBase.vue` 任意文案，**应立即热更新**呈现改动。

3. 打开浏览器 Network 面板，触发任意 **`/api/...`** 请求：

   * Request URL 必须是 `http://localhost:5173/api/...`；
   * 该请求被 **(Proxied)** 到 `backend:8000`，并成功返回。

4. 全局检索确认：`frontend/` 下**不存在** `127.0.0.1:8000`、`localhost:8000`、`172.18.`、`API_BASE =` 等字符串。

5. （信息提示）开发阶段**不要**用 `http://localhost:8000` 打开页面；8000 仅作 API 端口。

---

## 不要做的事（禁止项）

* 不要增加、删除或升级任何依赖；
* 不要改动后端 Python 代码与路由逻辑；
* 不要引入 Nginx/CDN/网关配置；
* 不要擅自重构前端目录或封装层；
* 不要把代理目标写成本机 `localhost:8000` 或任意 `172.18.*.*`；
* 不要创建或使用 `APP_SERVE_FRONTEND` 之类环境变量。
