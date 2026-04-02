<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'
const SYSTEM_NAME = '智能助手'

function createSessionId() {
  return `session_${Date.now()}`
}

const storedSessionId = localStorage.getItem('chat_session_id')
const sessionId = ref(storedSessionId || createSessionId())
const inputText = ref('')
const isStreaming = ref(false)
const errorText = ref('')
const chatListRef = ref(null)
const abortController = ref(null)

const messages = ref([
  {
    id: 'welcome',
    role: 'assistant',
    text: '你好，我是你的智能助手。请输入你的问题，我会以流式方式回复。'
  }
])

const canSend = computed(() => !isStreaming.value && inputText.value.trim().length > 0)

function saveSessionId() {
  localStorage.setItem('chat_session_id', sessionId.value.trim())
}

function resetSession() {
  sessionId.value = createSessionId()
  saveSessionId()
  messages.value = [
    {
      id: `assistant_${Date.now()}`,
      role: 'assistant',
      text: '已创建新会话，你可以开始新的对话。'
    }
  ]
}

function scrollToBottom() {
  nextTick(() => {
    const container = chatListRef.value
    if (!container) return
    container.scrollTop = container.scrollHeight
  })
}

function appendAssistantText(targetMessage, chunk) {
  targetMessage.text += chunk
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function appendWithTypewriter(targetMessage, chunk, delayMs = 18) {
  for (const char of chunk) {
    appendAssistantText(targetMessage, char)
    scrollToBottom()
    await sleep(delayMs)
  }
}

function parseSseData(rawData) {
  const trimmed = rawData.trim()
  if (!trimmed) return ''
  if (trimmed === '[DONE]') return '[DONE]'
  try {
    return JSON.parse(trimmed)
  } catch {
    return trimmed
  }
}

function getTokenText(parsed) {
  if (!parsed || typeof parsed === 'string') return parsed || ''
  return parsed.token || parsed.delta || parsed.content || parsed.text || ''
}

function getDoneReply(parsed) {
  if (!parsed || typeof parsed === 'string') return parsed || ''
  return parsed.reply || parsed.content || parsed.text || ''
}

function getErrorText(parsed) {
  if (!parsed || typeof parsed === 'string') return ''
  return parsed.error || ''
}

async function consumeStreamResponse(response, assistantMessage) {
  if (!response.body) {
    throw new Error('后端未返回可读取的流。')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const processFrame = async (event) => {
    const lines = event.split(/\r?\n/)
    let eventName = 'message'
    const dataLines = []

    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim()
        continue
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }

    if (!dataLines.length) return
    const parsed = parseSseData(dataLines.join('\n'))

    if (parsed === '[DONE]') {
      throw new Error('__SSE_DONE__')
    }

    if (eventName === 'error') {
      throw new Error(getErrorText(parsed) || '流式调用失败')
    }

    if (eventName === 'done') {
      const replyText = getDoneReply(parsed)
      if (replyText && !assistantMessage.text.trim()) {
        await appendWithTypewriter(assistantMessage, replyText)
      }
      throw new Error('__SSE_DONE__')
    }

    const tokenText = getTokenText(parsed)
    if (tokenText) {
      await appendWithTypewriter(assistantMessage, tokenText)
    }
  }

  while (true) {
    try {
      const { done, value } = await reader.read()
      if (done) {
        buffer += decoder.decode()
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split(/\r?\n\r?\n/)
      buffer = events.pop() || ''

      for (const event of events) {
        await processFrame(event)
      }
    } catch (error) {
      if (error?.message === '__SSE_DONE__') {
        return
      }
      throw error
    }
  }

  if (buffer.trim()) {
    try {
      await processFrame(buffer)
    } catch (error) {
      if (error?.message !== '__SSE_DONE__') {
        throw error
      }
    }
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  const sid = sessionId.value.trim()

  if (!text || !sid || isStreaming.value) return

  errorText.value = ''
  saveSessionId()

  messages.value.push({
    id: `user_${Date.now()}`,
    role: 'user',
    text
  })

  const assistantMessage = reactive({
    id: `assistant_${Date.now()}`,
    role: 'assistant',
    text: ''
  })
  messages.value.push(assistantMessage)
  inputText.value = ''
  scrollToBottom()

  const controller = new AbortController()
  abortController.value = controller
  isStreaming.value = true

  try {
    const endpoint = `${API_BASE}/api/v1/sessions/${encodeURIComponent(sid)}/messages`
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream'
      },
      signal: controller.signal,
      body: JSON.stringify({
        input_text: text
      })
    })

    if (!response.ok) {
      throw new Error(`请求失败（${response.status}）`)
    }

    await consumeStreamResponse(response, assistantMessage)

    if (!assistantMessage.text.trim()) {
      assistantMessage.text = '后端未返回可显示的内容。'
    }
  } catch (error) {
    if (error?.name === 'AbortError') {
      assistantMessage.text = assistantMessage.text || '已停止生成。'
    } else {
      assistantMessage.text = assistantMessage.text || '抱歉，请求失败，请稍后重试。'
      errorText.value = error?.message || '未知错误'
    }
  } finally {
    isStreaming.value = false
    abortController.value = null
    scrollToBottom()
  }
}

function stopStreaming() {
  if (abortController.value) {
    abortController.value.abort()
  }
}

function onEnterSend(event) {
  if (event.shiftKey) return
  event.preventDefault()
  sendMessage()
}

onMounted(() => {
  saveSessionId()
  scrollToBottom()
})

onBeforeUnmount(() => {
  if (abortController.value) {
    abortController.value.abort()
  }
})
</script>

<template>
  <div class="chat-page">
    <header class="chat-header">
      <div class="title-area">
        <h1>{{ SYSTEM_NAME }}</h1>
        <p>多轮会话 · SSE 流式返回</p>
      </div>
      <div class="session-tools">
        <label>
          Session
          <input v-model="sessionId" type="text" @blur="saveSessionId" />
        </label>
        <button class="ghost" type="button" @click="resetSession">新会话</button>
      </div>
    </header>

    <main ref="chatListRef" class="chat-list">
      <div v-for="item in messages" :key="item.id" class="row" :class="item.role">
        <div class="avatar">{{ item.role === 'user' ? '我' : 'AI' }}</div>
        <article class="bubble">{{ item.text }}</article>
      </div>
    </main>

    <footer class="composer">
      <p v-if="errorText" class="error">{{ errorText }}</p>
      <textarea
        v-model="inputText"
        placeholder="输入消息，Enter 发送，Shift+Enter 换行"
        @keydown.enter="onEnterSend"
      ></textarea>
      <div class="actions">
        <button type="button" class="ghost" :disabled="!isStreaming" @click="stopStreaming">
          停止
        </button>
        <button type="button" class="primary" :disabled="!canSend" @click="sendMessage">
          {{ isStreaming ? '生成中...' : '发送' }}
        </button>
      </div>
    </footer>
  </div>
</template>
