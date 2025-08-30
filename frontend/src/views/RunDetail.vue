<template>
  <div class="page">
    <h1>运行详情</h1>
    <p><strong>ID</strong>: {{ id }}</p>
    <div class="toolbar">
      <button @click="refresh">刷新状态</button>
      <button @click="copyId">复制 ID</button>
      <router-link to="/">返回 Home</router-link>
    </div>
    <pre class="status">{{ status }}</pre>
    <RunConsole :logs="logs" />
    <div class="kg-panel">
      <h2>知识图谱</h2>
      <p v-if="bookId" class="kg-info">整本书视图 (bookId={{ bookId }})</p>
      <p v-else-if="sectionId" class="kg-info">小节视图 (sectionId={{ sectionId }})</p>
      <KgGraph :bookId="bookId" :sectionId="sectionId" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useRunsStore } from '../store/runs'
import RunConsole from '../components/RunConsole.vue'
import KgGraph from '../components/KgGraph.vue'

const route = useRoute()
const runs = useRunsStore()
const id = computed(() => String(route.params.id || ''))
const status = computed(() => JSON.stringify(runs.status, null, 2))
const logs = computed(() => runs.logs)
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

onMounted(async () => {
  if (id.value) {
    await runs.fetchStatus(id.value)
    runs.watchStream(id.value)
  }
})
</script>

<style scoped>
.page { max-width: 960px; margin: 32px auto; }
.status { background: #0e0f12; border: 1px solid #222; padding: 12px; border-radius: 8px; }
button { margin-bottom: 12px; padding: 8px 16px; border: none; border-radius: 6px; background: #66fcf1; color: #000; font-weight: 600; cursor: pointer; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
.kg-panel { margin-top: 16px; }
.kg-panel h2 { margin: 12px 0; font-size: 18px; }
.kg-info { margin: 8px 0; font-size: 14px; color: #666; }
</style>

