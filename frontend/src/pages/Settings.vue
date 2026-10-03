<template>
  <div>
    <h1 class="brand">设置</h1>
    <label>家庭名 <input v-model="household" /></label>
    <button @click="save">保存</button>
    <p class="muted" style="margin-top:16px">健康检查：{{ health }}</p>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const household = ref('')
const health = ref('')
async function load() {
  const s = await api('/settings'); household.value = s.household || ''
  const h = await api('/health'); health.value = JSON.stringify(h)
}
async function save() { await api('/settings', { method: 'PUT', body: JSON.stringify({ household: household.value }) }) }
onMounted(load)
</script>
