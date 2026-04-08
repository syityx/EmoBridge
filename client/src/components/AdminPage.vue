<script setup>
import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'

const props = defineProps({
  currentUserName: { type: String, default: '' },
  authToken: { type: String, default: '' },
  onLogout: { type: Function, default: null },
})

const outputText = ref('')
const isUploading = ref(false)
const isFetching = ref(false)
const isClearing = ref(false)
const fileInputRef = ref(null)

function triggerFileInput() {
  fileInputRef.value?.click()
}

async function uploadPDF(event) {
  const file = event.target.files?.[0]
  if (!file) return

  isUploading.value = true
  outputText.value = `正在上传 ${file.name}，请稍候...`

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await fetch(`${API_BASE}/api/v1/admin/upload`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${props.authToken}`,
      },
      body: formData,
    })
    const result = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(result?.detail || `上传失败（${response.status}）`)
    }
    outputText.value = JSON.stringify(result, null, 2)
  } catch (error) {
    outputText.value = `错误：${error?.message || '上传失败'}`
  } finally {
    isUploading.value = false
    // Reset file input so same file can be re-uploaded
    event.target.value = ''
  }
}

async function fetchChromaData() {
  isFetching.value = true
  outputText.value = '正在获取 Chroma 数据，请稍候...'

  try {
    const response = await fetch(`${API_BASE}/api/v1/admin/chroma-data`, {
      headers: {
        Authorization: `Bearer ${props.authToken}`,
      },
    })
    const result = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(result?.detail || `请求失败（${response.status}）`)
    }
    outputText.value = JSON.stringify(result, null, 2)
  } catch (error) {
    outputText.value = `错误：${error?.message || '获取失败'}`
  } finally {
    isFetching.value = false
  }
}

async function clearChromaData() {
  const confirmed = window.confirm('确定要清空整个知识库吗？此操作不可恢复。')
  if (!confirmed) return

  isClearing.value = true
  outputText.value = '正在清空知识库，请稍候...'

  try {
    const response = await fetch(`${API_BASE}/api/v1/admin/chroma-data`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${props.authToken}`,
      },
    })
    const result = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(result?.detail || `请求失败（${response.status}）`)
    }
    outputText.value = JSON.stringify(result, null, 2)
  } catch (error) {
    outputText.value = `错误：${error?.message || '清空失败'}`
  } finally {
    isClearing.value = false
  }
}
</script>

<template>
  <div class="admin-page">
    <header class="admin-header">
      <div class="title-area">
        <h1>管理员控制台</h1>
        <p>用户：{{ currentUserName }}</p>
      </div>
      <button class="ghost" type="button" @click="onLogout">退出</button>
    </header>

    <main class="admin-main">
      <div class="admin-actions">
        <input
          ref="fileInputRef"
          type="file"
          accept=".pdf"
          style="display: none"
          @change="uploadPDF"
        />
        <button
          class="primary"
          type="button"
          :disabled="isUploading || isFetching"
          @click="triggerFileInput"
        >
          {{ isUploading ? '上传中...' : '上传 PDF' }}
        </button>
        <button
          class="ghost"
          type="button"
          :disabled="isUploading || isFetching || isClearing"
          @click="fetchChromaData"
        >
          {{ isFetching ? '查询中...' : '查看 Chroma 数据' }}
        </button>
        <button
          class="danger"
          type="button"
          :disabled="isUploading || isFetching || isClearing"
          @click="clearChromaData"
        >
          {{ isClearing ? '清空中...' : '清空知识库' }}
        </button>
      </div>

      <textarea
        class="admin-output"
        readonly
        :value="outputText"
        placeholder="操作结果将在此处显示..."
      ></textarea>
    </main>
  </div>
</template>

<style scoped>
.admin-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--color-bg, #f5f5f5);
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.admin-header .title-area h1 {
  margin: 0;
  font-size: 1.25rem;
}

.admin-header .title-area p {
  margin: 2px 0 0;
  font-size: 0.85rem;
  color: #6b7280;
}

.admin-main {
  display: flex;
  flex-direction: column;
  flex: 1;
  padding: 24px;
  gap: 16px;
  overflow: hidden;
}

.admin-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.admin-output {
  flex: 1;
  resize: none;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 12px;
  font-family: 'Courier New', monospace;
  font-size: 0.85rem;
  line-height: 1.5;
  background: #fff;
  color: #111827;
  outline: none;
}

button.primary {
  padding: 8px 20px;
  background: #6366f1;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}

button.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button.ghost {
  padding: 8px 20px;
  background: transparent;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}

button.ghost:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button.danger {
  padding: 8px 20px;
  background: #dc2626;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}

button.danger:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
