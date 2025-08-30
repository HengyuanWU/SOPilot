<template>
  <div class="kg-graph-container">
    <div class="kg-graph-header">
      <h3>{{ props.bookId ? '整本书知识图谱' : '知识图谱' }}</h3>
      <p v-if="props.bookId" class="graph-description">展示完整的知识结构和概念关系</p>
      <div class="graph-controls">
        <button @click="refreshGraph" :disabled="loading" class="btn btn-secondary">
          {{ loading ? '加载中...' : '刷新图谱' }}
        </button>
        <button @click="resetLayout" class="btn btn-secondary">重置布局</button>
      </div>
    </div>
    
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
    
    <div 
      ref="graphContainer" 
      class="graph-canvas"
      :class="{ loading: loading }"
    ></div>
    
    <div v-if="graphStats" class="graph-stats">
      节点: {{ graphStats.nodes }} | 边: {{ graphStats.edges }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import cytoscape from 'cytoscape'
import { getKnowledgeGraph } from '../services/api'

interface Props {
  bookId?: string
  sectionId?: string
}

const props = defineProps<Props>()

const graphContainer = ref<HTMLDivElement>()
const loading = ref(false)
const error = ref<string>('')
const graphStats = ref<{ nodes: number; edges: number } | null>(null)

let cy: cytoscape.Core | null = null

const initCytoscape = () => {
  if (!graphContainer.value) return

  cy = cytoscape({
    container: graphContainer.value,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': '#0074D9',
          'label': 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'color': '#fff',
          'font-size': '12px',
          'width': 40,
          'height': 40,
          'overlay-padding': '6px',
          'z-index': 10
        }
      },
      {
        selector: 'node[type="concept"]',
        style: {
          'background-color': '#FF851B'
        }
      },
      {
        selector: 'node[type="entity"]',
        style: {
          'background-color': '#2ECC40'
        }
      },
      {
        selector: 'node[type="relationship"]',
        style: {
          'background-color': '#B10DC9',
          'shape': 'diamond'
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#ccc',
          'target-arrow-color': '#ccc',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 1.2,
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '10px',
          'text-background-color': '#fff',
          'text-background-opacity': 0.8,
          'text-background-padding': '2px'
        }
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 3,
          'border-color': '#FF4136'
        }
      },
      {
        selector: 'edge:selected',
        style: {
          'line-color': '#FF4136',
          'target-arrow-color': '#FF4136',
          'width': 3
        }
      }
    ],
    layout: {
      name: 'cose',
      idealEdgeLength: 100,
      nodeOverlap: 20,
      refresh: 20,
      fit: true,
      padding: 30,
      randomize: false,
      componentSpacing: 100,
      nodeRepulsion: 400000,
      edgeElasticity: 100,
      nestingFactor: 5,
      gravity: 80,
      numIter: 1000,
      initialTemp: 200,
      coolingFactor: 0.95,
      minTemp: 1.0
    }
  })

  // 添加交互事件
  cy.on('tap', 'node', (evt) => {
    const node = evt.target
    console.log('节点详情:', node.data())
  })

  cy.on('tap', 'edge', (evt) => {
    const edge = evt.target
    console.log('边详情:', edge.data())
  })
}

const loadGraphData = async () => {
  if (!cy) return

  loading.value = true
  error.value = ''

  try {
    const data = await getKnowledgeGraph(props.bookId, props.sectionId)
    
    if (!data.nodes || !data.edges) {
      throw new Error('图谱数据格式错误')
    }

    // 转换数据格式为 Cytoscape 所需
    const cytoscapeData = [
      ...data.nodes.map((node: any) => ({
        data: {
          id: node.id,
          label: node.label || node.name || node.id,
          type: node.type || 'concept',
          ...(node.properties || {})
        }
      })),
      ...data.edges.map((edge: any) => ({
        data: {
          id: edge.id || `${(edge.source || edge.source_id)}-${(edge.target || edge.target_id)}`,
          source: edge.source || edge.source_id,
          target: edge.target || edge.target_id,
          label: edge.label || edge.type || '',
          type: edge.type || 'relation',
          ...(edge.properties || {})
        }
      }))
    ]

    cy.elements().remove()
    cy.add(cytoscapeData)
    cy.layout({ name: 'cose' }).run()

    graphStats.value = {
      nodes: data.nodes.length,
      edges: data.edges.length
    }

  } catch (err: any) {
    error.value = err.message || '加载图谱数据失败'
    console.error('KG Graph loading error:', err)
  } finally {
    loading.value = false
  }
}

const refreshGraph = () => {
  if (props.bookId || props.sectionId) {
    loadGraphData()
  }
}

const resetLayout = () => {
  if (cy) {
    cy.layout({ name: 'cose' }).run()
  }
}

// 监听 props 变化
watch([() => props.bookId, () => props.sectionId], ([newBookId, newSectionId]) => {
  if (newBookId || newSectionId) {
    loadGraphData()
  }
}, { immediate: true })

onMounted(() => {
  initCytoscape()
})

onUnmounted(() => {
  if (cy) {
    cy.destroy()
  }
})
</script>

<style scoped>
.kg-graph-container {
  display: flex;
  flex-direction: column;
  height: 500px;
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow: hidden;
}

.kg-graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #ddd;
}

.kg-graph-header h3 {
  margin: 0;
  font-size: 16px;
  color: #333;
}

.graph-description {
  margin: 4px 0 0 0;
  font-size: 12px;
  color: #666;
}

.graph-controls {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 4px 12px;
  font-size: 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  cursor: pointer;
  background: white;
  transition: background-color 0.2s;
}

.btn:hover:not(:disabled) {
  background-color: #f5f5f5;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.btn-secondary {
  background-color: #6c757d;
  color: white;
  border-color: #6c757d;
}

.btn.btn-secondary:hover:not(:disabled) {
  background-color: #5a6268;
}

.error-message {
  padding: 10px 15px;
  background-color: #f8d7da;
  color: #721c24;
  border-bottom: 1px solid #ddd;
  font-size: 14px;
}

.graph-canvas {
  flex: 1;
  position: relative;
  background-color: #fafafa;
}

.graph-canvas.loading {
  opacity: 0.6;
}

.graph-canvas.loading::after {
  content: '加载中...';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(255, 255, 255, 0.9);
  padding: 10px 20px;
  border-radius: 4px;
  font-size: 14px;
  color: #666;
}

.graph-stats {
  padding: 8px 15px;
  background-color: #e9ecef;
  border-top: 1px solid #ddd;
  font-size: 12px;
  color: #6c757d;
}
</style>