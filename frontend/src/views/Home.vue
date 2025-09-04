<template>
  <div class="page">
    <h1>新建运行</h1>
    
    <!-- 工作流选择器 -->
    <div class="workflow-selector" v-if="workflows.length > 0">
      <h2>选择工作流</h2>
      <div class="workflow-cards">
        <div 
          v-for="workflow in workflows" 
          :key="workflow.id"
          :class="['workflow-card', { active: selectedWorkflow?.id === workflow.id }]"
          @click="selectWorkflow(workflow)"
        >
          <h3>{{ workflow.name }}</h3>
          <p>{{ workflow.description }}</p>
          <div class="workflow-tags">
            <span v-for="tag in workflow.tags" :key="tag" class="tag">{{ tag }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 动态表单 -->
    <form v-if="selectedWorkflow" @submit.prevent="onSubmit" class="dynamic-form">
      <h2>配置参数</h2>
      
      <!-- 基本参数 -->
      <div class="form-group">
        <label>
          主题
          <input v-model="formData.topic" placeholder="请输入主题" required />
        </label>
      </div>
      
      <!-- 动态渲染工作流特定参数 -->
      <div v-for="(field, key) in workflowFields" :key="key" class="form-group">
        <label>
          {{ field.title || key }}
          
          <!-- 文本输入 -->
          <input 
            v-if="field.type === 'string' && !field.enum"
            v-model="formData[key]"
            :type="field.ui_widget === 'textarea' ? 'text' : 'text'"
            :placeholder="field.ui_placeholder || field.description"
            :required="isRequired(String(key))"
          />
          
          <!-- 选择框 -->
          <select 
            v-else-if="field.type === 'string' && field.enum"
            v-model="formData[key]"
            :required="isRequired(String(key))"
          >
            <option v-for="option in field.enum" :key="option" :value="option">{{ option }}</option>
          </select>
          
          <!-- 数字输入 -->
          <input 
            v-else-if="field.type === 'integer' || field.type === 'number'"
            v-model.number="formData[key]"
            type="number"
            :min="field.minimum"
            :max="field.maximum"
            :required="isRequired(String(key))"
          />
          
          <!-- 布尔值复选框 -->
          <input 
            v-else-if="field.type === 'boolean'"
            v-model="formData[key]"
            type="checkbox"
          />
          
          <!-- 数组多选框 -->
          <div v-else-if="field.type === 'array' && field.items?.enum" class="checkbox-group">
            <label v-for="option in field.items.enum" :key="option" class="checkbox-label">
              <input 
                type="checkbox" 
                :value="option"
                @change="toggleArrayValue(String(key), option)"
                :checked="formData[key]?.includes(option)"
              />
              {{ option }}
            </label>
          </div>
          
        </label>
        <small v-if="field.description" class="field-description">{{ field.description }}</small>
      </div>
      
      <button type="submit" :disabled="!selectedWorkflow || isSubmitting">
        {{ isSubmitting ? '创建中...' : '创建运行' }}
      </button>
    </form>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading">
      正在加载工作流...
    </div>

    <!-- 创建结果 -->
    <p v-if="runId">
      已创建：<router-link :to="{ name: 'run-detail', params: { id: runId } }">{{ runId }}</router-link> 
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useRunsStore } from '../store/runs'
import { getWorkflows, type WorkflowMetadata } from '../services/api'

const runs = useRunsStore()
const router = useRouter()

// 状态管理
const loading = ref(false)
const isSubmitting = ref(false)
const runId = ref<string | null>(null)
const workflows = ref<WorkflowMetadata[]>([])
const selectedWorkflow = ref<WorkflowMetadata | null>(null)
const formData = ref<Record<string, any>>({
  topic: '',
  language: '中文',
  chapter_count: 8
})

// 计算属性
const workflowFields = computed(() => {
  if (!selectedWorkflow.value?.input_schema?.properties) return {}
  
  const fields = { ...selectedWorkflow.value.input_schema.properties }
  
  // 移除已经在基本参数中处理的字段
  delete fields.topic
  
  return fields
})

// 工具函数
function isRequired(fieldName: string): boolean {
  return selectedWorkflow.value?.input_schema?.required?.includes(fieldName) || false
}

function toggleArrayValue(fieldName: string, value: string) {
  if (!formData.value[fieldName]) {
    formData.value[fieldName] = []
  }
  
  const arr = formData.value[fieldName] as string[]
  const index = arr.indexOf(value)
  
  if (index > -1) {
    arr.splice(index, 1)
  } else {
    arr.push(value)
  }
}

// 工作流相关函数
function selectWorkflow(workflow: WorkflowMetadata) {
  selectedWorkflow.value = workflow
  
  // 重置表单数据并应用默认值
  formData.value = {
    topic: formData.value.topic || '',
    language: '中文',
    chapter_count: 8
  }
  
  // 应用工作流Schema中的默认值
  if (workflow.input_schema?.properties) {
    Object.entries(workflow.input_schema.properties).forEach(([key, field]: [string, any]) => {
      if (field.default !== undefined) {
        formData.value[key] = field.default
      }
    })
  }
}

async function loadWorkflows() {
  try {
    loading.value = true
    workflows.value = await getWorkflows()
    
    // 默认选择第一个工作流（通常是textbook）
    if (workflows.value.length > 0) {
      selectWorkflow(workflows.value[0])
    }
  } catch (error) {
    console.error('Failed to load workflows:', error)
  } finally {
    loading.value = false
  }
}

async function onSubmit() {
  if (!selectedWorkflow.value) return
  
  try {
    isSubmitting.value = true
    
    // 准备提交数据
    const payload: any = {
      topic: formData.value.topic,
      language: formData.value.language || '中文',
      chapter_count: formData.value.chapter_count || 8,
      workflow_id: selectedWorkflow.value.id
    }
    
    // 添加工作流特定参数
    const workflowParams: Record<string, any> = {}
    Object.keys(workflowFields.value).forEach(key => {
      if (formData.value[key] !== undefined) {
        workflowParams[key] = formData.value[key]
      }
    })
    
    if (Object.keys(workflowParams).length > 0) {
      payload.workflow_params = workflowParams
    }
    
    const created = await runs.createRun(payload)
    runId.value = created.id
    router.push({ name: 'run-detail', params: { id: created.id } })
  } catch (error) {
    console.error('Failed to create run:', error)
    alert('创建运行失败，请重试')
  } finally {
    isSubmitting.value = false
  }
}

// 生命周期
onMounted(() => {
  loadWorkflows()
})
</script>

<style scoped>
.page { 
  max-width: 900px; 
  margin: 32px auto; 
  padding: 0 16px;
}

/* 工作流选择器样式 */
.workflow-selector {
  margin-bottom: 32px;
}

.workflow-selector h2 {
  margin-bottom: 16px;
  color: #eee;
}

.workflow-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.workflow-card {
  border: 2px solid #333;
  border-radius: 8px;
  padding: 16px;
  background: #1a1a1a;
  cursor: pointer;
  transition: all 0.2s ease;
}

.workflow-card:hover {
  border-color: #66fcf1;
  transform: translateY(-2px);
}

.workflow-card.active {
  border-color: #66fcf1;
  background: #1a2a2a;
}

.workflow-card h3 {
  margin: 0 0 8px 0;
  color: #66fcf1;
  font-size: 1.2em;
}

.workflow-card p {
  margin: 0 0 12px 0;
  color: #ccc;
  font-size: 0.9em;
  line-height: 1.4;
}

.workflow-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  background: #333;
  color: #66fcf1;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.8em;
}

/* 动态表单样式 */
.dynamic-form {
  background: #1a1a1a;
  border-radius: 8px;
  padding: 24px;
  border: 1px solid #333;
}

.dynamic-form h2 {
  margin: 0 0 20px 0;
  color: #eee;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 4px;
  color: #eee;
  font-weight: 500;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #333;
  background: #111;
  color: #eee;
  font-size: 14px;
  box-sizing: border-box;
}

.form-group input[type="checkbox"] {
  width: auto;
  margin-right: 8px;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  font-size: 14px;
  color: #ccc;
  margin-bottom: 0 !important;
}

.checkbox-label input[type="checkbox"] {
  margin-right: 8px;
  margin-bottom: 0;
}

.field-description {
  color: #999;
  font-size: 0.8em;
  margin-top: 4px;
  display: block;
}

button {
  padding: 12px 24px;
  border: none;
  border-radius: 6px;
  background: #66fcf1;
  color: #000;
  font-weight: 600;
  cursor: pointer;
  font-size: 16px;
  margin-top: 16px;
  transition: all 0.2s ease;
}

button:hover:not(:disabled) {
  background: #5ae6db;
  transform: translateY(-1px);
}

button:disabled {
  background: #333;
  color: #666;
  cursor: not-allowed;
  transform: none;
}

.loading {
  text-align: center;
  color: #66fcf1;
  padding: 40px;
  font-size: 1.1em;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .page {
    margin: 16px auto;
    padding: 0 12px;
  }
  
  .workflow-cards {
    grid-template-columns: 1fr;
  }
  
  .dynamic-form {
    padding: 16px;
  }
}
</style>

