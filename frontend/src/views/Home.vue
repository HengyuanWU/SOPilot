<template>
  <div class="page">
    <h1>新建运行</h1>
    <form @submit.prevent="onSubmit">
      <label>
        主题
        <input v-model="topic" placeholder="测试" />
      </label>
      <label>
        语言
        <input v-model="language" placeholder="中文" />
      </label>
      <label>
        章节数
        <input v-model.number="chapterCount" type="number" min="1" />
      </label>
      <button type="submit">创建</button>
    </form>
    <p v-if="runId">
      已创建：<router-link :to="{ name: 'run-detail', params: { id: runId } }">{{ runId }}</router-link>
    </p>
  </div>
  </template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRunsStore } from '../store/runs'

const runs = useRunsStore()
const topic = ref('测试')
const language = ref('中文')
const chapterCount = ref(3)
const runId = ref<string | null>(null)

import { useRouter } from 'vue-router'
const router = useRouter()

async function onSubmit() {
  const created = await runs.createRun({ topic: topic.value, language: language.value, chapter_count: chapterCount.value })
  runId.value = created.id
  router.push({ name: 'run-detail', params: { id: created.id } })
}
</script>

<style scoped>
.page { max-width: 640px; margin: 32px auto; }
form { display: grid; gap: 12px; }
input { padding: 8px; border-radius: 6px; border: 1px solid #333; background: #111; color: #eee; }
button { padding: 10px 16px; border: none; border-radius: 6px; background: #66fcf1; color: #000; font-weight: 600; cursor: pointer; }
</style>

