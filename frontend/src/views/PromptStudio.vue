<template>
  <div class="prompt-studio">
    <div class="studio-header">
      <h1>Prompt Studio</h1>
      <p>集中管理所有智能体的提示词和模型配置</p>
    </div>

    <div class="studio-layout">
      <!-- 左侧Prompt列表 -->
      <div class="prompt-list">
        <div class="list-header">
          <h3>Prompt列表</h3>
          <button @click="refreshPrompts" class="refresh-btn">
            <i class="icon-refresh"></i> 刷新
          </button>
        </div>
        
        <div class="search-box">
          <input 
            v-model="searchQuery" 
            type="text" 
            placeholder="搜索Agent或语言..."
            class="search-input"
          >
        </div>

        <div class="prompt-items">
          <div 
            v-for="prompt in filteredPrompts" 
            :key="prompt.id"
            :class="['prompt-item', { active: selectedPrompt?.id === prompt.id }]"
            @click="selectPrompt(prompt)"
          >
            <div class="prompt-info">
              <div class="prompt-title">{{ prompt.agent }}</div>
              <div class="prompt-meta">
                <span class="locale">{{ prompt.locale }}</span>
                <span class="version">v{{ prompt.version }}</span>
              </div>
              <div class="model-info">{{ prompt.model || '未配置' }}</div>
            </div>
            <div class="status-indicator" :class="prompt.status || 'active'"></div>
          </div>
        </div>
      </div>

      <!-- 右侧编辑面板 -->
      <div class="edit-panel">
        <div v-if="!selectedPrompt" class="no-selection">
          <i class="icon-prompt"></i>
          <p>选择左侧的Prompt开始编辑</p>
        </div>

        <div v-else class="editor-container">
          <!-- 编辑器头部 -->
          <div class="editor-header">
            <h3>{{ selectedPrompt.agent }} ({{ selectedPrompt.locale }})</h3>
            <div class="editor-actions">
              <button @click="validatePrompt" class="validate-btn" :disabled="validating">
                {{ validating ? '校验中...' : '校验' }}
              </button>
              <button @click="savePrompt" class="save-btn" :disabled="saving">
                {{ saving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>

          <!-- 编辑模式切换 -->
          <div class="edit-tabs">
            <button 
              :class="['tab', { active: editMode === 'form' }]"
              @click="editMode = 'form'"
            >
              表单编辑
            </button>
            <button 
              :class="['tab', { active: editMode === 'yaml' }]"
              @click="editMode = 'yaml'"
            >
              YAML编辑
            </button>
          </div>

          <!-- 表单编辑模式 -->
          <div v-if="editMode === 'form'" class="form-editor">
            <div class="form-section">
              <label>Agent</label>
              <input v-model="editingPrompt.agent" type="text" readonly>
            </div>

            <div class="form-section">
              <label>语言/地区</label>
              <input v-model="editingPrompt.locale" type="text">
            </div>

            <div class="form-section">
              <label>模型配置</label>
              <input v-model="editingPrompt.model" type="text" placeholder="例: siliconflow:Qwen/Qwen3-Coder-30B-A3B-Instruct">
            </div>

            <div class="form-section">
              <label>System消息</label>
              <textarea 
                v-model="systemMessage" 
                class="message-textarea"
                placeholder="系统提示词..."
                rows="4"
              ></textarea>
            </div>

            <div class="form-section">
              <label>User消息</label>
              <textarea 
                v-model="userMessage" 
                class="message-textarea"
                placeholder="用户提示词模板（支持{{变量}}）..."
                rows="6"
              ></textarea>
            </div>

            <div class="form-section">
              <label>参数配置</label>
              <div class="param-grid">
                <div class="param-item">
                  <label>Temperature</label>
                  <input v-model.number="editingPrompt.meta.temperature" type="number" step="0.1" min="0" max="2">
                </div>
                <div class="param-item">
                  <label>Max Tokens</label>
                  <input v-model.number="editingPrompt.meta.max_tokens" type="number" min="1">
                </div>
              </div>
            </div>
          </div>

          <!-- YAML编辑模式 -->
          <div v-if="editMode === 'yaml'" class="yaml-editor">
            <textarea 
              v-model="yamlContent" 
              class="yaml-textarea"
              placeholder="YAML内容..."
              rows="20"
            ></textarea>
          </div>

          <!-- 校验结果 -->
          <div v-if="validationResult" class="validation-result">
            <h4>校验结果</h4>
            <div v-if="validationResult.success" class="validation-success">
              <i class="icon-check"></i>
              <span>校验通过</span>
            </div>
            <div v-else class="validation-error">
              <i class="icon-error"></i>
              <span>{{ validationResult.error }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { api } from '../services/api.ts'
import yaml from 'js-yaml'

export default {
  name: 'PromptStudio',
  data() {
    return {
      prompts: [],
      selectedPrompt: null,
      editingPrompt: null,
      searchQuery: '',
      editMode: 'form', // 'form' | 'yaml'
      yamlContent: '',
      validating: false,
      saving: false,
      validationResult: null
    }
  },
  computed: {
    filteredPrompts() {
      if (!this.searchQuery) return this.prompts
      const query = this.searchQuery.toLowerCase()
      return this.prompts.filter(p => 
        p.agent.toLowerCase().includes(query) || 
        p.locale.toLowerCase().includes(query)
      )
    },
    systemMessage: {
      get() {
        const messages = this.editingPrompt?.messages || []
        const systemMsg = messages.find(m => m.role === 'system')
        return systemMsg?.content || ''
      },
      set(value) {
        if (!this.editingPrompt?.messages) return
        const messages = this.editingPrompt.messages
        const systemIndex = messages.findIndex(m => m.role === 'system')
        if (systemIndex >= 0) {
          messages[systemIndex].content = value
        } else {
          messages.unshift({ role: 'system', content: value })
        }
      }
    },
    userMessage: {
      get() {
        const messages = this.editingPrompt?.messages || []
        const userMsg = messages.find(m => m.role === 'user')
        return userMsg?.content || ''
      },
      set(value) {
        if (!this.editingPrompt?.messages) return
        const messages = this.editingPrompt.messages
        const userIndex = messages.findIndex(m => m.role === 'user')
        if (userIndex >= 0) {
          messages[userIndex].content = value
        } else {
          messages.push({ role: 'user', content: value })
        }
      }
    }
  },
  async mounted() {
    await this.loadPrompts()
  },
  methods: {
    async loadPrompts() {
      try {
        const response = await api.get('/prompts')
        this.prompts = response.data
      } catch (error) {
        console.error('加载Prompt列表失败:', error)
        this.$message?.error('加载Prompt列表失败')
      }
    },
    async refreshPrompts() {
      await this.loadPrompts()
      this.$message?.success('Prompt列表已刷新')
    },
    async selectPrompt(prompt) {
      this.selectedPrompt = prompt
      this.validationResult = null
      
      try {
        const response = await api.get(`/prompts/${prompt.id}`)
        this.editingPrompt = JSON.parse(JSON.stringify(response.data))
        this.yamlContent = yaml.dump(this.editingPrompt, { 
          defaultFlowStyle: false,
          allowUnicode: true
        })
      } catch (error) {
        console.error('加载Prompt详情失败:', error)
        this.$message?.error('加载Prompt详情失败')
      }
    },
    async validatePrompt() {
      if (!this.editingPrompt) return
      
      this.validating = true
      this.validationResult = null
      
      try {
        let promptData = this.editingPrompt
        
        // 如果是YAML模式，先解析YAML
        if (this.editMode === 'yaml') {
          promptData = yaml.load(this.yamlContent)
        }
        
        const response = await api.post('/prompts/validate', promptData)
        this.validationResult = { success: true, data: response.data }
        this.$message?.success('Prompt校验通过')
      } catch (error) {
        this.validationResult = { 
          success: false, 
          error: error.response?.data?.detail || error.message 
        }
        this.$message?.error('Prompt校验失败')
      } finally {
        this.validating = false
      }
    },
    async savePrompt() {
      if (!this.editingPrompt) return
      
      this.saving = true
      
      try {
        let promptData = this.editingPrompt
        
        // 如果是YAML模式，先解析YAML
        if (this.editMode === 'yaml') {
          promptData = yaml.load(this.yamlContent)
        }
        
        await api.put(`/prompts/${this.selectedPrompt.id}`, promptData)
        this.$message?.success('Prompt保存成功')
        
        // 刷新列表
        await this.loadPrompts()
        
        // 更新选中的prompt
        const updated = this.prompts.find(p => p.id === this.selectedPrompt.id)
        if (updated) {
          this.selectedPrompt = updated
        }
      } catch (error) {
        console.error('保存Prompt失败:', error)
        this.$message?.error('保存Prompt失败: ' + (error.response?.data?.detail || error.message))
      } finally {
        this.saving = false
      }
    }
  },
  watch: {
    editingPrompt: {
      handler(newVal) {
        if (newVal && this.editMode === 'form') {
          // 当表单模式下数据变化时，同步更新YAML
          this.yamlContent = yaml.dump(newVal, { 
            defaultFlowStyle: false,
            allowUnicode: true
          })
        }
      },
      deep: true
    },
    editMode(newMode) {
      if (newMode === 'yaml' && this.editingPrompt) {
        // 切换到YAML模式时，从表单数据生成YAML
        this.yamlContent = yaml.dump(this.editingPrompt, { 
          defaultFlowStyle: false,
          allowUnicode: true
        })
      } else if (newMode === 'form' && this.yamlContent) {
        // 切换到表单模式时，从YAML解析数据
        try {
          this.editingPrompt = yaml.load(this.yamlContent)
        } catch (error) {
          console.error('YAML解析失败:', error)
          this.$message?.error('YAML格式错误')
        }
      }
    }
  }
}
</script>

<style scoped>
.prompt-studio {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.studio-header {
  padding: 20px 24px;
  background: white;
  border-bottom: 1px solid #e8e8e8;
}

.studio-header h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: #1f2937;
}

.studio-header p {
  margin: 0;
  color: #6b7280;
}

.studio-layout {
  flex: 1;
  display: flex;
  gap: 1px;
  background: #e8e8e8;
}

.prompt-list {
  width: 320px;
  background: white;
  display: flex;
  flex-direction: column;
}

.list-header {
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.list-header h3 {
  margin: 0;
  font-size: 16px;
  color: #1f2937;
}

.refresh-btn {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  background: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  color: #6b7280;
}

.refresh-btn:hover {
  background: #f9fafb;
}

.search-box {
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
}

.search-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.search-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.prompt-items {
  flex: 1;
  overflow-y: auto;
}

.prompt-item {
  padding: 12px 16px;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.prompt-item:hover {
  background: #f9fafb;
}

.prompt-item.active {
  background: #eff6ff;
  border-left: 3px solid #3b82f6;
}

.prompt-info {
  flex: 1;
}

.prompt-title {
  font-weight: 500;
  color: #1f2937;
  margin-bottom: 4px;
}

.prompt-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}

.locale, .version {
  padding: 2px 6px;
  background: #f3f4f6;
  border-radius: 4px;
  font-size: 12px;
  color: #6b7280;
}

.model-info {
  font-size: 12px;
  color: #9ca3af;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
}

.status-indicator.active {
  background: #10b981;
}

.edit-panel {
  flex: 1;
  background: white;
  display: flex;
  flex-direction: column;
}

.no-selection {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #9ca3af;
}

.no-selection i {
  font-size: 48px;
  margin-bottom: 16px;
}

.editor-container {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.editor-header {
  padding: 16px 24px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.editor-header h3 {
  margin: 0;
  color: #1f2937;
}

.editor-actions {
  display: flex;
  gap: 12px;
}

.validate-btn, .save-btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  border: 1px solid;
}

.validate-btn {
  border-color: #d1d5db;
  background: white;
  color: #6b7280;
}

.validate-btn:hover:not(:disabled) {
  background: #f9fafb;
}

.save-btn {
  border-color: #3b82f6;
  background: #3b82f6;
  color: white;
}

.save-btn:hover:not(:disabled) {
  background: #2563eb;
}

.validate-btn:disabled, .save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.edit-tabs {
  display: flex;
  border-bottom: 1px solid #e8e8e8;
}

.tab {
  padding: 12px 24px;
  border: none;
  background: none;
  cursor: pointer;
  color: #6b7280;
  border-bottom: 2px solid transparent;
}

.tab.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.form-editor, .yaml-editor {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.form-section {
  margin-bottom: 20px;
}

.form-section label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: #374151;
}

.form-section input, .message-textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.form-section input:focus, .message-textarea:focus {
  outline: none;
  border-color: #3b82f6;
}

.message-textarea {
  resize: vertical;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.param-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.param-item label {
  font-size: 12px;
  margin-bottom: 4px;
}

.yaml-textarea {
  width: 100%;
  height: 100%;
  padding: 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  resize: none;
}

.yaml-textarea:focus {
  outline: none;
  border-color: #3b82f6;
}

.validation-result {
  margin-top: 20px;
  padding: 16px;
  border-radius: 6px;
}

.validation-success {
  color: #059669;
  display: flex;
  align-items: center;
  gap: 8px;
}

.validation-error {
  color: #dc2626;
  display: flex;
  align-items: center;
  gap: 8px;
}

.validation-result h4 {
  margin: 0 0 12px 0;
  color: #374151;
}

/* 图标样式 (使用Unicode字符作为占位符) */
.icon-refresh:before { content: "↻"; }
.icon-prompt:before { content: "📝"; }
.icon-check:before { content: "✓"; }
.icon-error:before { content: "✗"; }
</style>