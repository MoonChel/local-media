<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import FolderPicker from '../components/FolderPicker.vue'

const sources = ref([])
const jobs = ref([])
const jobsLoading = ref(false)
const error = ref('')

const url = ref('')
const selectedFolder = ref(null)
const showFolderPicker = ref(false)
let jobsInterval = null

async function loadJobs() {
  jobsLoading.value = true
  try {
    const res = await fetch('/api/youtube')
    if (!res.ok) throw new Error(`Downloads failed: ${res.status}`)
    jobs.value = await res.json()
  } catch (e) {
    showTemporaryError(String(e))
  } finally {
    jobsLoading.value = false
  }
}

function startDownload() {
  if (!url.value.trim()) return
  showFolderPicker.value = true
}

async function onFolderSelected(folder) {
  showFolderPicker.value = false
  if (!folder) return
  
  error.value = ''
  const res = await fetch('/api/youtube/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      url: url.value.trim(), 
      path: folder.path || ''
    }),
  })
  if (!res.ok) {
    const text = await res.text()
    let errorMsg = text
    try {
      const json = JSON.parse(text)
      errorMsg = json.detail || text
    } catch {}
    showTemporaryError(`Failed: ${res.status} ${errorMsg}`)
    return
  }
  url.value = ''
  await loadJobs()
}

async function retryJob(jobId) {
  try {
    const res = await fetch(`/api/youtube/${jobId}/retry`, { method: 'POST' })
    if (!res.ok) {
      const text = await res.text()
      let errorMsg = text
      try {
        const json = JSON.parse(text)
        errorMsg = json.detail || text
      } catch {}
      throw new Error(`Failed: ${res.status} ${errorMsg}`)
    }
    await loadJobs()
  } catch (e) {
    showTemporaryError(String(e))
  }
}

async function deleteJob(jobId) {
  if (!confirm('Delete this download?')) return
  
  try {
    const res = await fetch(`/api/youtube/${jobId}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    await loadJobs()
  } catch (e) {
    showTemporaryError(String(e))
  }
}

function showTemporaryError(message) {
  error.value = message
  setTimeout(() => {
    if (error.value === message) {
      error.value = ''
    }
  }, 3000)
}

onMounted(async () => {
  await loadJobs()
  jobsInterval = setInterval(loadJobs, 5000)
})

onBeforeUnmount(() => {
  if (jobsInterval) clearInterval(jobsInterval)
})
</script>

<template>
  <main class="mx-auto max-w-6xl p-4 md:p-8">
    <header class="mb-6">
      <h2 class="text-3xl font-bold">YouTube Downloads</h2>
      <p class="text-sm text-muted">Download videos from YouTube and other supported sites using yt-dlp.</p>
    </header>

    <div v-if="error" class="mb-4 flex items-center justify-between rounded border border-red-500/60 bg-red-950/30 p-3 text-red-300">
      <span>{{ error }}</span>
      <button @click="error = ''" class="ml-2 rounded px-2 py-1 text-xs hover:bg-red-900/50">✕</button>
    </div>

    <section class="rounded-lg border border-white/10 bg-panel p-4">
      <div class="grid gap-3 md:grid-cols-[1fr_auto] md:items-center">
        <input v-model="url" type="text" placeholder="https://www.youtube.com/watch?v=..." class="w-full rounded border border-white/20 bg-black/30 px-3 py-2 text-sm" @keyup.enter="startDownload" />
        <button @click="startDownload" class="rounded bg-accent px-3 py-2 text-sm font-medium text-black">Download</button>
      </div>

      <div class="mt-3 flex items-center gap-3">
        <button @click="loadJobs" class="rounded border border-white/20 px-3 py-2 text-sm">Refresh jobs</button>
        <span class="text-xs text-muted">Supports YouTube, Vimeo, and 1000+ sites</span>
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
              <td class="max-w-[300px] truncate py-2 pr-3" :title="job.display_name || job.url">
                <RouterLink 
                  v-if="job.video_id && job.status === 'done'" 
                  :to="`/watch/${job.video_id}`"
                  class="text-accent hover:underline"
                >
                  {{ job.display_name || job.url }}
                </RouterLink>
                <span v-else>{{ job.display_name || job.url }}</span>
              </td>
              <td class="py-2 pr-3">
                <span :class="{
                  'text-yellow-400': job.status === 'downloading' || job.status === 'queued',
                  'text-green-400': job.status === 'done',
                  'text-red-400': job.status === 'failed'
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
                    v-if="job.status === 'done' && job.video_id"
                    @click="$router.push(`/watch/${job.video_id}`)"
                    class="rounded border border-accent/50 px-2 py-1 text-xs text-accent hover:bg-accent/20"
                    title="Watch"
                  >
                    Watch
                  </button>
                  <button 
                    v-if="job.status === 'failed'"
                    @click="retryJob(job.id)"
                    class="rounded border border-yellow-500/50 px-2 py-1 text-xs text-yellow-300 hover:bg-yellow-500/20"
                    title="Retry"
                  >
                    Retry
                  </button>
                  <button 
                    @click="deleteJob(job.id)"
                    class="rounded border border-red-500/50 px-2 py-1 text-xs text-red-300 hover:bg-red-500/20"
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
      @update:modelValue="onFolderSelected"
      @close="showFolderPicker = false"
    />
  </main>
</template>
