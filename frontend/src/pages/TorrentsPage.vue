<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import FolderPicker from '../components/FolderPicker.vue'

const sources = ref([])
const jobs = ref([])
const jobsLoading = ref(false)
const error = ref('')

const magnet = ref('')
const selectedFolder = ref(null)
const showFolderPicker = ref(false)
const uploading = ref(false)
const actionInProgress = ref({})
let jobsInterval = null

async function loadSources() {
  const res = await fetch('/api/sources')
  if (!res.ok) throw new Error(`Sources failed: ${res.status}`)
  sources.value = await res.json()
}

async function loadJobs() {
  jobsLoading.value = true
  try {
    const res = await fetch('/api/torrents')
    if (!res.ok) throw new Error(`Downloads failed: ${res.status}`)
    jobs.value = await res.json()
  } catch (e) {
    error.value = String(e)
  } finally {
    jobsLoading.value = false
  }
}

function startDownload() {
  if (!magnet.value.trim()) return
  showFolderPicker.value = true
}

async function onFolderSelected(folder) {
  showFolderPicker.value = false
  if (!folder) return
  
  const res = await fetch('/api/torrents/magnet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ magnet: magnet.value.trim(), source_id: folder.sourceId }),
  })
  if (!res.ok) {
    error.value = `Failed: ${res.status} ${await res.text()}`
    return
  }
  magnet.value = ''
  await loadJobs()
}

async function submitTorrentFile(event) {
  const file = event.target.files?.[0]
  if (!file || !sourceId.value) return
  uploading.value = true
  error.value = ''
  try {
    const form = new FormData()
    form.append('source_id', sourceId.value)
    form.append('torrent_file', file)
    const res = await fetch('/api/torrents/upload', { method: 'POST', body: form })
    if (!res.ok) throw new Error(`Failed: ${res.status} ${await res.text()}`)
    event.target.value = ''
    await loadJobs()
  } catch (e) {
    error.value = String(e)
  } finally {
    uploading.value = false
  }
}

async function stopJob(jobId) {
  actionInProgress.value[jobId] = true
  try {
    const res = await fetch(`/api/torrents/${jobId}/stop`, { method: 'POST' })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    await loadJobs()
  } catch (e) {
    error.value = String(e)
  } finally {
    delete actionInProgress.value[jobId]
  }
}

async function restartJob(jobId) {
  actionInProgress.value[jobId] = true
  try {
    const res = await fetch(`/api/torrents/${jobId}/restart`, { method: 'POST' })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    await loadJobs()
  } catch (e) {
    error.value = String(e)
  } finally {
    delete actionInProgress.value[jobId]
  }
}

async function deleteJob(jobId) {
  if (!confirm('Delete this download?')) return
  actionInProgress.value[jobId] = true
  try {
    const res = await fetch(`/api/torrents/${jobId}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    await loadJobs()
  } catch (e) {
    error.value = String(e)
  } finally {
    delete actionInProgress.value[jobId]
  }
}

onMounted(async () => {
  await Promise.all([loadSources(), loadJobs()])
  jobsInterval = setInterval(loadJobs, 5000)
})

onBeforeUnmount(() => {
  if (jobsInterval) clearInterval(jobsInterval)
})
</script>

<template>
  <main class="mx-auto max-w-6xl p-4 md:p-8">
    <header class="mb-6">
      <h2 class="text-3xl font-bold">Torrents</h2>
      <p class="text-sm text-muted">Upload a torrent or add magnet and choose the target media folder.</p>
    </header>

    <section class="rounded-lg border border-white/10 bg-panel p-4">
      <div class="grid gap-3 md:grid-cols-[1fr_auto] md:items-center">
        <input v-model="magnet" type="text" placeholder="magnet:?xt=urn:btih:..." class="w-full rounded border border-white/20 bg-black/30 px-3 py-2 text-sm" @keyup.enter="startDownload" />
        <button @click="startDownload" class="rounded bg-accent px-3 py-2 text-sm font-medium text-black">Add Magnet</button>
      </div>

      <div class="mt-3 flex items-center gap-3">
        <label class="cursor-pointer rounded border border-white/20 px-3 py-2 text-sm">
          <input type="file" class="hidden" accept=".torrent" @change="submitTorrentFile" />
          {{ uploading ? 'Uploading...' : 'Upload .torrent' }}
        </label>
        <button @click="loadJobs" class="rounded border border-white/20 px-3 py-2 text-sm">Refresh jobs</button>
      </div>

      <div v-if="error" class="mt-3 flex items-center justify-between rounded border border-red-500/60 bg-red-950/30 p-3 text-red-300">
        <span>{{ error }}</span>
        <button @click="error = ''" class="ml-2 rounded px-2 py-1 text-xs hover:bg-red-900/50">✕</button>
      </div>
      <div class="mt-4 overflow-x-auto">
        <table class="min-w-full text-left text-sm">
          <thead class="text-muted">
            <tr>
              <th class="py-1 pr-3">Name</th>
              <th class="py-1 pr-3">Status</th>
              <th class="py-1 pr-3">Progress</th>
              <th class="py-1 pr-3">Folder</th>
              <th class="py-1 pr-3">Updated</th>
              <th class="py-1 pr-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="jobsLoading"><td colspan="6" class="py-2 text-muted">Loading jobs...</td></tr>
            <tr v-else-if="jobs.length === 0"><td colspan="6" class="py-2 text-muted">No jobs</td></tr>
            <tr v-for="job in jobs" :key="job.id" class="border-t border-white/10">
              <td class="max-w-[300px] truncate py-2 pr-3" :title="job.display_name || job.source_value">
                {{ job.display_name || job.source_value }}
              </td>
              <td class="py-2 pr-3">
                <span :class="{
                  'text-yellow-400': job.status === 'downloading' || job.status === 'queued',
                  'text-green-400': job.status === 'done',
                  'text-red-400': job.status === 'failed',
                  'text-gray-400': job.status === 'stopped'
                }">
                  {{ job.status }}
                </span>
              </td>
              <td class="py-2 pr-3">
                <div v-if="job.status === 'downloading' && job.progress_percent != null" class="flex items-center gap-2 min-w-[120px]">
                  <div class="h-2 flex-1 rounded-full bg-white/10 overflow-hidden">
                    <div 
                      class="h-full bg-accent transition-all duration-300"
                      :style="{ width: `${job.progress_percent}%` }"
                    ></div>
                  </div>
                  <span class="text-xs text-muted whitespace-nowrap">{{ Math.round(job.progress_percent) }}%</span>
                </div>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="py-2 pr-3">{{ job.source_label || job.source_id }}</td>
              <td class="py-2 pr-3 text-xs text-muted">{{ new Date(job.updated_at).toLocaleString() }}</td>
              <td class="py-2 pr-3">
                <div class="flex items-center gap-1">
                  <button 
                    v-if="job.status === 'downloading' || job.status === 'queued'"
                    @click="stopJob(job.id)"
                    :disabled="actionInProgress[job.id]"
                    class="rounded border border-white/20 px-2 py-1 text-xs hover:bg-white/10 disabled:opacity-50"
                    title="Stop"
                  >
                    Stop
                  </button>
                  <button 
                    v-if="job.status === 'stopped' || job.status === 'failed'"
                    @click="restartJob(job.id)"
                    :disabled="actionInProgress[job.id]"
                    class="rounded border border-white/20 px-2 py-1 text-xs hover:bg-white/10 disabled:opacity-50"
                    title="Restart"
                  >
                    Restart
                  </button>
                  <button 
                    @click="deleteJob(job.id)"
                    :disabled="actionInProgress[job.id]"
                    class="rounded border border-red-500/50 px-2 py-1 text-xs text-red-300 hover:bg-red-500/20 disabled:opacity-50"
                    title="Delete"
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <FolderPicker 
      v-if="showFolderPicker"
      :sources="sources"
      @update:modelValue="onFolderSelected"
      @close="showFolderPicker = false"
    />
  </main>
</template>
