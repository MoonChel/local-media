<script setup>
import { onMounted, ref } from 'vue'

const settings = ref({})
const loading = ref(true)
const error = ref('')
const savingPlayer = ref(false)

const playerForm = ref({
  seek_time: 10,
})

async function loadSettings() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/settings')
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    settings.value = await res.json()
    playerForm.value.seek_time = Number(settings.value.player?.seek_time ?? 10)
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

async function savePlayerSettings() {
  savingPlayer.value = true
  error.value = ''
  try {
    const res = await fetch('/api/settings/player', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        seek_time: Number(playerForm.value.seek_time),
      }),
    })
    if (!res.ok) throw new Error(await res.text())
    await loadSettings()
  } catch (e) {
    error.value = String(e)
  } finally {
    savingPlayer.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <main class="mx-auto max-w-6xl p-4 md:p-8">
    <header class="mb-6">
      <h2 class="text-3xl font-bold">Settings</h2>
      <p class="text-sm text-muted">Configure player settings. Manage folders from the Library page.</p>
    </header>

    <div v-if="loading" class="text-muted">Loading settings...</div>
    <div v-else class="space-y-6">
      <section class="rounded-lg border border-white/10 bg-panel p-4">
        <h3 class="mb-3 text-lg font-semibold">Player</h3>
        <div class="grid gap-3 md:grid-cols-1">
          <label class="text-sm">
            <span class="mb-1 block text-muted">Seek time (seconds)</span>
            <input v-model.number="playerForm.seek_time" type="number" min="1" max="600" class="w-full rounded border border-white/20 bg-black/30 px-3 py-2 text-sm" />
          </label>
        </div>
        <div class="mt-4">
          <button :disabled="savingPlayer" @click="savePlayerSettings" class="rounded bg-accent px-3 py-2 text-sm font-medium text-black disabled:opacity-60">
            {{ savingPlayer ? 'Saving...' : 'Save player settings' }}
          </button>
        </div>
      </section>

      <div v-if="error" class="rounded border border-red-500/60 bg-red-950/30 p-3 text-red-300 flex items-center justify-between">
        <span>{{ error }}</span>
        <button @click="error = ''" class="ml-2 rounded px-2 py-1 text-xs hover:bg-red-900/50">✕</button>
      </div>
    </div>
  </main>
</template>
