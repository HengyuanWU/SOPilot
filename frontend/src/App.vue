<template>
  <div id="app">
    <!-- 导航栏 -->
    <nav class="navbar">
      <div class="nav-container">
        <h1 class="nav-title">SOPilot</h1>
        <div class="nav-links">
          <router-link to="/" class="nav-link">首页</router-link>
          <router-link to="/prompts" class="nav-link">Prompt Studio</router-link>
        </div>
      </div>
    </nav>
    
    <!-- 主内容区域 -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
</script>

<style>
/* 全局样式 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 导航栏样式 */
.navbar {
  background: #fff;
  border-bottom: 1px solid #e1e5e9;
  box-shadow: 0 2px 4px rgba(0,0,0,0.08);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
}

.nav-title {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
  margin: 0;
}

.nav-links {
  display: flex;
  gap: 24px;
}

.nav-link {
  color: #606266;
  text-decoration: none;
  font-weight: 500;
  padding: 8px 16px;
  border-radius: 4px;
  transition: all 0.3s ease;
}

.nav-link:hover {
  background: #f5f7fa;
  color: #409eff;
}

.nav-link.router-link-active {
  background: #409eff;
  color: white;
}

/* 主内容区域 */
.main-content {
  flex: 1;
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .nav-container {
    padding: 0 16px;
  }
  
  .nav-title {
    font-size: 20px;
  }
  
  .nav-links {
    gap: 16px;
  }
  
  .nav-link {
    padding: 6px 12px;
    font-size: 14px;
  }
  
  .main-content {
    padding: 16px;
  }
}
</style>

