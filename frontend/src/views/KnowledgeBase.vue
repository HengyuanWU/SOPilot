<template>
  <div class="knowledge-base">
    <div class="page-header">
      <h1>知识库管理</h1>
      <p class="subtitle">管理文档、索引状态和RAG调试</p>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 左侧：文档管理 -->
      <div class="left-panel">
        <div class="panel-header">
          <h2>文档管理</h2>
          <div class="actions">
            <button @click="reindexAll" :disabled="loading" class="btn-reindex">
              <i class="icon-refresh"></i>
              {{ loading ? '重建中...' : '重建索引' }}
            </button>
            <label class="btn-upload">
              <i class="icon-upload"></i>
              上传文档
              <input type="file" multiple @change="uploadFiles" accept=".pdf,.txt,.md,.docx" style="display: none;">
            </label>
          </div>
        </div>

        <!-- 文档列表 -->
        <div class="documents-list">
          <div v-if="documents.length === 0" class="empty-state">
            <p>暂无文档，请上传文档开始使用</p>
          </div>
          <div v-else class="document-table">
            <div class="table-header">
              <div class="col-name">文件名</div>
              <div class="col-size">大小</div>
              <div class="col-time">更新时间</div>
              <div class="col-status">索引状态</div>
              <div class="col-actions">操作</div>
            </div>
            <div v-for="doc in documents" :key="doc.name" class="table-row">
              <div class="col-name" :title="doc.name">{{ doc.name }}</div>
              <div class="col-size">{{ formatFileSize(doc.size) }}</div>
              <div class="col-time">{{ formatTime(doc.updated_at) }}</div>
              <div class="col-status">
                <span :class="['status-badge', doc.indexed ? 'indexed' : 'pending']">
                  {{ doc.indexed ? '已索引' : '待索引' }}
                </span>
              </div>
              <div class="col-actions">
                <button @click="deleteDocument(doc.name)" class="btn-delete" title="删除">
                  <i class="icon-delete"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：RAG调试面板 -->
      <div class="right-panel">
        <div class="panel-header">
          <h2>RAG调试面板</h2>
        </div>

        <div class="debug-panel">
          <!-- 查询输入 -->
          <div class="query-section">
            <label>测试查询</label>
            <textarea v-model="debugQuery" placeholder="输入要测试的查询内容..." rows="3"></textarea>
          </div>

          <!-- 调试按钮组 -->
          <div class="debug-actions">
            <button @click="testVector" :disabled="!debugQuery.trim() || !!testing" class="btn-test">
              {{ testing === 'vector' ? '测试中...' : '向量检索' }}
            </button>
            <button @click="testKG" :disabled="!debugQuery.trim() || !!testing" class="btn-test">
              {{ testing === 'kg' ? '测试中...' : 'KG检索' }}
            </button>
            <button @click="testDual" :disabled="!debugQuery.trim() || !!testing" class="btn-test primary">
              {{ testing === 'dual' ? '测试中...' : '混合检索' }}
            </button>
          </div>

          <!-- 结果展示 -->
          <div v-if="debugResults" class="results-section">
            <h3>检索结果</h3>
            
            <!-- 向量检索结果 -->
            <div v-if="debugResults.vector_hits" class="result-group">
              <h4>向量检索 ({{ debugResults.vector_hits.length }} 条)</h4>
              <div v-for="(hit, idx) in debugResults.vector_hits" :key="idx" class="result-item">
                <div class="result-header">
                  <span class="score">分数: {{ hit.score?.toFixed(3) }}</span>
                  <span class="source">{{ hit.doc }}</span>
                </div>
                <div class="result-content">{{ hit.chunk }}</div>
              </div>
            </div>

            <!-- KG检索结果 -->
            <div v-if="debugResults.kg_hits" class="result-group">
              <h4>知识图谱检索 ({{ debugResults.kg_hits.length }} 条)</h4>
              <div v-for="(hit, idx) in debugResults.kg_hits" :key="idx" class="result-item">
                <div class="result-header">
                  <span class="score">分数: {{ hit.score?.toFixed(3) }}</span>
                </div>
                <div class="result-content">{{ hit.path }}</div>
              </div>
            </div>

            <!-- 合并结果 -->
            <div v-if="debugResults.merged" class="result-group">
              <h4>合并重排结果 ({{ debugResults.merged.length }} 条)</h4>
              <div v-for="(item, idx) in debugResults.merged" :key="idx" class="result-item">
                <div class="result-header">
                  <span class="score">最终分数: {{ item.score?.toFixed(3) }}</span>
                  <span class="type">{{ item.type === 'chunk' ? '文档片段' : 'KG路径' }}</span>
                </div>
              </div>
            </div>

            <!-- Prompt预览 -->
            <div v-if="debugResults.prompt_preview" class="result-group">
              <h4>Prompt 预览</h4>
              <pre class="prompt-preview">{{ debugResults.prompt_preview }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传进度模态框 -->
    <div v-if="uploadProgress.show" class="modal-overlay">
      <div class="modal">
        <h3>上传进度</h3>
        <div class="upload-list">
          <div v-for="file in uploadProgress.files" :key="file.name" class="upload-item">
            <span class="filename">{{ file.name }}</span>
            <span :class="['status', file.status]">{{ getUploadStatusText(file.status) }}</span>
          </div>
        </div>
        <div class="modal-actions">
          <button @click="closeUploadModal" :disabled="uploadProgress.uploading">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

// 状态管理
const documents = ref<any[]>([])
const loading = ref(false)
const debugQuery = ref('')
const debugResults = ref<any>(null)
const testing = ref<string | null>(null)

// 上传进度
const uploadProgress = ref({
  show: false,
  uploading: false,
  files: [] as Array<{name: string, status: 'pending' | 'uploading' | 'success' | 'error'}>
})

// API基础URL - 使用相对路径，由Vite代理转发

// 页面加载时获取文档列表
onMounted(() => {
  loadDocuments()
})

// 加载文档列表
async function loadDocuments() {
  try {
    const response = await fetch('/api/v1/rag/docs')
    if (response.ok) {
      documents.value = await response.json()
    }
  } catch (error) {
    console.error('加载文档列表失败:', error)
  }
}

// 上传文件
async function uploadFiles(event: Event) {
  const files = (event.target as HTMLInputElement).files
  if (!files || files.length === 0) return

  // 显示进度模态框
  uploadProgress.value = {
    show: true,
    uploading: true,
    files: Array.from(files).map(f => ({ name: f.name, status: 'pending' }))
  }

  // 逐个上传文件
  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    const progressFile = uploadProgress.value.files[i]
    
    try {
      progressFile.status = 'uploading'
      
      const formData = new FormData()
      formData.append('files', file)
      
      const response = await fetch('/api/v1/rag/docs', {
        method: 'POST',
        body: formData
      })
      
      if (response.ok) {
        progressFile.status = 'success'
      } else {
        progressFile.status = 'error'
      }
    } catch (error) {
      console.error(`上传文件 ${file.name} 失败:`, error)
      progressFile.status = 'error'
    }
  }

  uploadProgress.value.uploading = false
  
  // 刷新文档列表
  await loadDocuments()
  
  // 清空文件输入框
  ;(event.target as HTMLInputElement).value = ''
}

// 删除文档
async function deleteDocument(name: string) {
  if (!confirm(`确定要删除文档 "${name}" 吗？`)) return
  
  try {
    const response = await fetch(`/api/v1/rag/docs/${encodeURIComponent(name)}`, {
      method: 'DELETE'
    })
    
    if (response.ok) {
      await loadDocuments()
    } else {
      alert('删除失败')
    }
  } catch (error) {
    console.error('删除文档失败:', error)
    alert('删除失败')
  }
}

// 重建索引
async function reindexAll() {
  if (!confirm('确定要重建全部索引吗？这可能需要一些时间。')) return
  
  loading.value = true
  try {
    const response = await fetch('/api/v1/rag/reindex', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clean: true })
    })
    
    if (response.ok) {
      alert('重建索引任务已启动')
      await loadDocuments()
    } else {
      alert('重建索引失败')
    }
  } catch (error) {
    console.error('重建索引失败:', error)
    alert('重建索引失败')
  } finally {
    loading.value = false
  }
}

// 测试向量检索
async function testVector() {
  await runTest('vector', '/api/v1/rag/test_vector', {
    query: debugQuery.value,
    top_k: 5
  })
}

// 测试KG检索
async function testKG() {
  await runTest('kg', '/api/v1/rag/test_kg', {
    query: debugQuery.value,
    hop: 2,
    rel_types: ['DEFINES', 'MENTIONS', 'HAS_CHUNK']
  })
}

// 测试混合检索
async function testDual() {
  await runTest('dual', '/api/v1/rag/test_dual', {
    query: debugQuery.value
  })
}

// 运行测试
async function runTest(type: string, url: string, payload: any) {
  testing.value = type
  debugResults.value = null
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    
    if (response.ok) {
      debugResults.value = await response.json()
    } else {
      const error = await response.text()
      alert(`测试失败: ${error}`)
    }
  } catch (error) {
    console.error(`测试${type}失败:`, error)
    alert(`测试失败: ${error}`)
  } finally {
    testing.value = null
  }
}

// 关闭上传模态框
function closeUploadModal() {
  if (!uploadProgress.value.uploading) {
    uploadProgress.value.show = false
  }
}

// 工具函数
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleString('zh-CN')
}

function getUploadStatusText(status: string): string {
  const statusMap = {
    pending: '等待中',
    uploading: '上传中',
    success: '成功',
    error: '失败'
  }
  return statusMap[status as keyof typeof statusMap] || status
}
</script>

<style scoped>
.knowledge-base {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 30px;
}

.page-header h1 {
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.subtitle {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.main-content {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 30px;
  height: calc(100vh - 150px);
}

.left-panel, .right-panel {
  background: white;
  border-radius: 8px;
  border: 1px solid #e5e5e5;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 20px 20px 16px;
  border-bottom: 1px solid #e5e5e5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: #1a1a1a;
}

.actions {
  display: flex;
  gap: 12px;
}

.btn-reindex, .btn-upload {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid #d1d5db;
  background: white;
  color: #374151;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.btn-reindex:hover, .btn-upload:hover {
  background: #f9fafb;
  border-color: #9ca3af;
}

.btn-upload {
  background: #3b82f6;
  color: white;
  border-color: #3b82f6;
}

.btn-upload:hover {
  background: #2563eb;
  border-color: #2563eb;
}

.documents-list {
  flex: 1;
  overflow: auto;
}

.empty-state {
  padding: 60px 20px;
  text-align: center;
  color: #9ca3af;
}

.document-table {
  display: flex;
  flex-direction: column;
}

.table-header, .table-row {
  display: grid;
  grid-template-columns: 1fr 80px 120px 80px 60px;
  gap: 16px;
  align-items: center;
  padding: 12px 20px;
}

.table-header {
  background: #f9fafb;
  font-weight: 600;
  font-size: 13px;
  color: #374151;
  border-bottom: 1px solid #e5e5e5;
}

.table-row {
  border-bottom: 1px solid #f3f4f6;
  font-size: 14px;
}

.table-row:hover {
  background: #f9fafb;
}

.col-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.col-size, .col-time {
  color: #6b7280;
  font-size: 13px;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.indexed {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.pending {
  background: #fef3c7;
  color: #92400e;
}

.btn-delete {
  padding: 6px;
  border: none;
  background: none;
  color: #dc2626;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;
}

.btn-delete:hover {
  background: #fee2e2;
}

.debug-panel {
  padding: 20px;
  flex: 1;
  overflow: auto;
}

.query-section {
  margin-bottom: 20px;
}

.query-section label {
  display: block;
  font-weight: 500;
  margin-bottom: 8px;
  color: #374151;
}

.query-section textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  resize: vertical;
  box-sizing: border-box;
}

.debug-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.btn-test {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  background: white;
  color: #374151;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-test:hover {
  background: #f9fafb;
}

.btn-test.primary {
  background: #3b82f6;
  color: white;
  border-color: #3b82f6;
}

.btn-test.primary:hover {
  background: #2563eb;
}

.btn-test:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.results-section {
  border-top: 1px solid #e5e5e5;
  padding-top: 20px;
}

.results-section h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
  color: #1a1a1a;
}

.result-group {
  margin-bottom: 20px;
}

.result-group h4 {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: #374151;
}

.result-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
}

.score {
  background: #dbeafe;
  color: #1e40af;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.source, .type {
  color: #6b7280;
}

.result-content {
  font-size: 13px;
  line-height: 1.4;
  color: #374151;
}

.prompt-preview {
  background: #f3f4f6;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.4;
  white-space: pre-wrap;
  max-height: 200px;
  overflow: auto;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  border-radius: 8px;
  padding: 24px;
  min-width: 400px;
  max-width: 500px;
}

.modal h3 {
  margin: 0 0 16px 0;
  font-size: 18px;
  font-weight: 600;
}

.upload-list {
  margin-bottom: 20px;
}

.upload-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f3f4f6;
}

.filename {
  flex: 1;
  font-size: 14px;
}

.status {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status.pending {
  background: #f3f4f6;
  color: #6b7280;
}

.status.uploading {
  background: #dbeafe;
  color: #1e40af;
}

.status.success {
  background: #d1fae5;
  color: #065f46;
}

.status.error {
  background: #fee2e2;
  color: #dc2626;
}

.modal-actions {
  text-align: right;
}

.modal-actions button {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  background: white;
  border-radius: 6px;
  cursor: pointer;
}

.modal-actions button:hover {
  background: #f9fafb;
}

.icon-refresh, .icon-upload, .icon-delete {
  width: 16px;
  height: 16px;
}

.icon-refresh::before { content: "🔄"; }
.icon-upload::before { content: "📁"; }
.icon-delete::before { content: "🗑️"; }
</style>