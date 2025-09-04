<template>
  <div class="page">
    <!-- Header -->
    <div class="header">
      <div class="header-info">
    <h1>运行详情</h1>
        <p class="run-id"><strong>ID</strong>: {{ id }}</p>
        <div class="status-badge" :class="statusClass">{{ statusText }}</div>
      </div>
    <div class="toolbar">
        <button @click="refresh" class="btn btn-primary">刷新状态</button>
        <button @click="copyId" class="btn btn-secondary">复制 ID</button>
        <router-link to="/" class="btn btn-outline">返回 Home</router-link>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs-container">
      <div class="tabs">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="['tab', { active: activeTab === tab.id }]"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Tab Contents -->
      <div class="tab-content">
        <!-- Overview Tab -->
        <div v-if="activeTab === 'overview'" class="tab-panel">
          <div class="overview-grid">
            <div class="status-panel">
              <h3>运行状态</h3>
              <pre class="status-json">{{ status }}</pre>
            </div>
            <div class="console-panel">
              <h3>运行日志</h3>
    <RunConsole :logs="logs" />
            </div>
          </div>
        </div>

        <!-- Knowledge Graph Tab -->
        <div v-if="activeTab === 'kg'" class="tab-panel">
    <div class="kg-panel">
            <div class="kg-header">
              <h3>知识图谱</h3>
      <p v-if="bookId" class="kg-info">整本书视图 (bookId={{ bookId }})</p>
      <p v-else-if="sectionId" class="kg-info">小节视图 (sectionId={{ sectionId }})</p>
              <p v-else class="kg-info">暂无图谱数据</p>
            </div>
            <KgGraph v-if="bookId || sectionId" :bookId="bookId" :sectionId="sectionId" />
          </div>
        </div>

        <!-- Artifacts Tab -->
        <div v-if="activeTab === 'artifacts'" class="tab-panel">
          <div class="artifacts-panel">
            <div class="artifacts-header">
              <h3>产物下载</h3>
              <button @click="refreshArtifacts" class="btn btn-secondary">刷新</button>
            </div>
            
            <div v-if="artifactsLoading" class="loading">加载中...</div>
            <div v-else-if="artifacts.length === 0" class="empty">暂无产物文件</div>
            <div v-else class="artifacts-grid">
              <div class="download-all">
                <button @click="downloadArchive" class="btn btn-primary">
                  <span>📦</span> 下载全部 (ZIP)
                </button>
              </div>
              
              <div class="artifacts-list">
                <div 
                  v-for="artifact in artifacts" 
                  :key="artifact.name"
                  class="artifact-item"
                >
                  <div class="artifact-info">
                    <div class="artifact-name">{{ artifact.name }}</div>
                    <div class="artifact-meta">
                      <span class="artifact-type">{{ getFileTypeLabel(artifact.type) }}</span>
                      <span class="artifact-size">{{ formatFileSize(artifact.size) }}</span>
                      <span class="artifact-modified">{{ formatDate(artifact.modified) }}</span>
                    </div>
                  </div>
                  <button 
                    @click="downloadFile(artifact.name)" 
                    class="btn btn-outline btn-sm"
                  >
                    下载
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useRunsStore } from '../store/runs'
import { getRunArtifacts, downloadRunFile, downloadRunArchive, type ArtifactFile } from '../services/api'
import RunConsole from '../components/RunConsole.vue'
import KgGraph from '../components/KgGraph.vue'

const route = useRoute()
const runs = useRunsStore()
const activeTab = ref('overview')
const artifacts = ref<ArtifactFile[]>([])
const artifactsLoading = ref(false)

const tabs = [
  { id: 'overview', label: '概览' },
  { id: 'kg', label: '知识图谱' },
  { id: 'artifacts', label: '产物下载' }
]

const id = computed(() => String(route.params.id || ''))
const status = computed(() => JSON.stringify(runs.status, null, 2))
const logs = computed(() => runs.logs)

const statusText = computed(() => {
  const s = runs.status?.status || 'unknown'
  const statusMap: Record<string, string> = {
    pending: '等待中',
    running: '运行中', 
    succeeded: '已完成',
    failed: '失败'
  }
  return statusMap[s] || s
})

const statusClass = computed(() => {
  const s = runs.status?.status || 'unknown'
  return `status-${s}`
})

const sectionId = computed(() => {
  const res = (runs.status && (runs.status as any).result) || null
  const sid = (res && (res as any).section_id) || null
  const sids = (res && (res as any).section_ids) || null
  if (sid) return sid
  if (Array.isArray(sids) && sids.length > 0) return sids[0]
  return ''
})

const bookId = computed(() => {
  const res = (runs.status && (runs.status as any).result) || null
  return (res && (res as any).book_id) || null
})

async function refresh() {
  if (!id.value) return
  await runs.fetchStatus(id.value)
}

async function copyId() {
  try {
    await navigator.clipboard.writeText(id.value)
    // 可根据需要添加轻提示
  } catch {}
}

async function refreshArtifacts() {
  if (!id.value) return
  artifactsLoading.value = true
  try {
    artifacts.value = await getRunArtifacts(id.value)
  } catch (error) {
    console.error('Failed to load artifacts:', error)
    artifacts.value = []
  } finally {
    artifactsLoading.value = false
  }
}

function downloadFile(fileName: string) {
  const url = downloadRunFile(id.value, fileName)
  window.open(url, '_blank')
}

function downloadArchive() {
  const url = downloadRunArchive(id.value)
  window.open(url, '_blank')
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function formatDate(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString()
}

function getFileTypeLabel(type: string): string {
  const typeLabels: Record<string, string> = {
    markdown: 'Markdown',
    json: 'JSON',
    text: '文本',
    logs: '日志'
  }
  return typeLabels[type] || type
}

onMounted(async () => {
  if (id.value) {
    await runs.fetchStatus(id.value)
    runs.watchStream(id.value)
    // 如果运行已完成，自动加载产物
    if (runs.status?.status === 'succeeded') {
      await refreshArtifacts()
    }
  }
})
</script>

<style scoped>
.page { 
  max-width: 1200px; 
  margin: 20px auto; 
  padding: 0 20px;
}

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #2a2a2a;
}

.header-info h1 {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 700;
  color: #ffffff;
}

.run-id {
  margin: 0 0 12px 0;
  color: #888;
  font-size: 14px;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.status-pending { background: #4a5568; color: #ffffff; }
.status-badge.status-running { background: #3182ce; color: #ffffff; }
.status-badge.status-succeeded { background: #38a169; color: #ffffff; }
.status-badge.status-failed { background: #e53e3e; color: #ffffff; }

.toolbar { 
  display: flex; 
  gap: 12px; 
  align-items: center; 
}

/* Buttons */
.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.btn-primary { background: #66fcf1; color: #000; }
.btn-primary:hover { background: #4dd9d0; }

.btn-secondary { background: #4a5568; color: #ffffff; }
.btn-secondary:hover { background: #2d3748; }

.btn-outline { 
  background: transparent; 
  color: #66fcf1; 
  border: 1px solid #66fcf1; 
}
.btn-outline:hover { 
  background: #66fcf1; 
  color: #000; 
}

.btn-sm { padding: 4px 12px; font-size: 14px; }

/* Tabs */
.tabs-container {
  background: #1a1a1a;
  border-radius: 8px;
  overflow: hidden;
}

.tabs {
  display: flex;
  background: #2a2a2a;
  border-bottom: 1px solid #3a3a3a;
}

.tab {
  padding: 12px 24px;
  background: transparent;
  border: none;
  color: #888;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
}

.tab:hover {
  color: #ffffff;
  background: #333;
}

.tab.active {
  color: #66fcf1;
  background: #1a1a1a;
  border-bottom-color: #66fcf1;
}

/* Tab Content */
.tab-content {
  min-height: 400px;
}

.tab-panel {
  padding: 24px;
}

/* Overview Tab */
.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.status-panel, .console-panel {
  background: #0e0f12;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 16px;
}

.status-panel h3, .console-panel h3 {
  margin: 0 0 12px 0;
  color: #ffffff;
  font-size: 16px;
}

.status-json {
  background: transparent;
  border: none;
  color: #66fcf1;
  font-size: 12px;
  line-height: 1.4;
  max-height: 300px;
  overflow-y: auto;
}

/* Knowledge Graph Tab */
.kg-panel {
  background: #0e0f12;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 20px;
}

.kg-header h3 {
  margin: 0 0 8px 0;
  color: #ffffff;
  font-size: 18px;
}

.kg-info {
  margin: 0 0 16px 0;
  color: #888;
  font-size: 14px;
}

/* Artifacts Tab */
.artifacts-panel {
  background: #0e0f12;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 20px;
}

.artifacts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.artifacts-header h3 {
  margin: 0;
  color: #ffffff;
  font-size: 18px;
}

.loading, .empty {
  text-align: center;
  color: #888;
  padding: 40px;
  font-size: 16px;
}

.download-all {
  margin-bottom: 20px;
  text-align: center;
}

.artifacts-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.artifact-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  transition: all 0.2s;
}

.artifact-item:hover {
  border-color: #66fcf1;
  background: #1e1e1e;
}

.artifact-info {
  flex: 1;
}

.artifact-name {
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 4px;
}

.artifact-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #888;
}

.artifact-type {
  background: #2a2a2a;
  padding: 2px 8px;
  border-radius: 4px;
  color: #66fcf1;
}

@media (max-width: 768px) {
  .page { padding: 0 16px; }
  .header { flex-direction: column; gap: 16px; }
  .overview-grid { grid-template-columns: 1fr; }
  .artifact-meta { flex-direction: column; gap: 4px; }
  .tabs { flex-wrap: wrap; }
}
</style>

