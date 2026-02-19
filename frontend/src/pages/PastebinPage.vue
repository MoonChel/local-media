<script setup>
import { onBeforeUnmount, onMounted, ref, computed } from 'vue'

const content = ref('')
const ttlMinutes = ref(60)
const expiresAt = ref(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const timeRemaining = ref('')

let refreshInterval = null
let countdownInterval = null

async function loadPastebin() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/pastebin')
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    const data = await res.json()
    content.value = data.content || ''
    expiresAt.value = data.expires_at
    ttlMinutes.value = data.ttl_minutes || 60
    updateCountdown()
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

async function savePastebin() {
  saving.value = true
  error.value = ''
  try {
    const res = await fetch('/api/pastebin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: content.value,
        ttl_minutes: ttlMinutes.value,
      }),
    })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    const data = await res.json()
    expiresAt.value = data.expires_at
    updateCountdown()
  } catch (e) {
    error.value = String(e)
  } finally {
    saving.value = false
  }
}

async function clearPastebin() {
  if (!confirm('Clear the pastebin?')) return
  
  error.value = ''
  try {
    const res = await fetch('/api/pastebin', { method: 'DELETE' })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    content.value = ''
    expiresAt.value = null
    timeRemaining.value = ''
  } catch (e) {
    error.value = String(e)
  }
}

function updateCountdown() {
  if (!expiresAt.value) {
    timeRemaining.value = ''
    return
  }
  
  const now = Date.now() / 1000
  const remaining = expiresAt.value - now
  
  if (remaining <= 0) {
    timeRemaining.value = 'Expired'
    loadPastebin() // Reload to clear expired content
    return
  }
  
  const hours = Math.floor(remaining / 3600)
  const minutes = Math.floor((remaining % 3600) / 60)
  const seconds = Math.floor(remaining % 60)
  
  if (hours > 0) {
    timeRemaining.value = `${hours}h ${minutes}m ${seconds}s`
  } else if (minutes > 0) {
    timeRemaining.value = `${minutes}m ${seconds}s`
  } else {
    timeRemaining.value = `${seconds}s`
  }
}

onMounted(async () => {
  await loadPastebin()
  refreshInterval = setInterval(loadPastebin, 30000) // Refresh every 30s
  countdownInterval = setInterval(updateCountdown, 1000) // Update countdown every second
})

onBeforeUnmount(() => {
  if (refreshInterval) clearInterval(refreshInterval)
  if (countdownInterval) clearInterval(countdownInterval)
})
</script>

<template>
  <main class="mx-auto max-w-6xl p-4 md:p-8">
    <header class="mb-6">
      <h2 class="text-3xl font-bold">Pastebin</h2>
      <p class="text-sm text-muted">Share text temporarily between devices. Content auto-expires.</p>
    </header>

    <div v-if="error" class="mb-4 flex items-center justify-between rounded border border-red-500/60 bg-red-950/30 p-3 text-red-300">
      <span>{{ error }}</span>
      <button @click="error = ''" class="ml-2 rounded px-2 py-1 text-xs hover:bg-red-900/50">✕</button>
    </div>

    <div v-if="loading" class="text-muted">Loading...</div>
    <section v-else class="space-y-4">
      <div class="rounded-lg border border-white/10 bg-panel p-4">
        <div class="mb-3 flex items-center justify-between">
          <label class="text-sm font-medium">Content</label>
          <div class="flex items-center gap-3">
            <div v-if="timeRemaining" class="text-sm text-muted">
              Expires in: <span class="text-orange-300">{{ timeRemaining }}</span>
            </div>
            <button @click="clearPastebin" class="rounded border border-red-500/50 px-3 py-1.5 text-xs text-red-300 hover:bg-red-500/20">
              Clear
            </button>
          </div>
        </div>
        <textarea 
          v-model="content" 
          placeholder="Paste your text here..."
          class="w-full rounded border border-white/20 bg-black/30 px-3 py-2 text-sm font-mono"
          rows="15"
        ></textarea>
      </div>

      <div class="rounded-lg border border-white/10 bg-panel p-4">
        <div class="flex items-center gap-4">
          <label class="text-sm">
            <span class="mb-1 block text-muted">Auto-expire after (minutes)</span>
            <input 
              v-model.number="ttlMinutes" 
              type="number" 
              min="1" 
              max="1440"
              class="w-32 rounded border border-white/20 bg-black/30 px-3 py-2 text-sm"
            />
          </label>
          <div class="flex-1"></div>
          <button 
            @click="savePastebin" 
            :disabled="saving"
            class="rounded bg-accent px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
          >
            {{ saving ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>
    </section>
  </main>
</template>
