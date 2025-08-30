<template>
  <div class="console">
    <div ref="container" class="scroll-container">
      <div v-for="(line, i) in logs" :key="i" class="log">{{ line }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

const props = defineProps<{ logs: string[] }>()

const container = ref<HTMLDivElement | null>(null)

watch(
  () => props.logs.length,
  async () => {
    await nextTick()
    if (container.value) {
      container.value.scrollTop = container.value.scrollHeight
    }
  }
)
</script>

<style scoped>
.console { background: #0e0f12; border: 1px solid #222; border-radius: 8px; padding: 12px; max-height: 360px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 12px; }
.scroll-container { max-height: 336px; overflow: auto; }
.log { padding: 2px 0; white-space: pre-wrap; }
</style>

