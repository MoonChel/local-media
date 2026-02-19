<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VideoCard from '../components/VideoCard.vue'
import MoveDialog from '../components/MoveDialog.vue'
import AddFolderDialog from '../components/AddFolderDialog.vue'
import UploadProgress from '../components/UploadProgress.vue'
import Breadcrumbs from '../components/Breadcrumbs.vue'

const route = useRoute()
const router = useRouter()

const videos = ref([])
const sources = ref([])
const loading = ref(true)
const error = ref('')

const selectedSource = ref('')
const currentPath = ref('')
const search = ref('')

const showMoveDialog = ref(false)
const moveVideoId = ref('')
const moveVideoName = ref('')
const moveInitialSource = ref('')
const moveInitialPath = ref('')

const showAddFolderDialog = ref(false)

const isDragging = ref(false)
const uploadProgress = ref([])

function normalizePath(value) {
  return String(value || '')
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
    .replace(/\/+$/, '')
}

function sourceFolderName(src) {
  const p = normalizePath(src?.path || '')
  const parts = p.split('/').filter(Boolean)
  return parts[parts.length - 1] || src?.label || src?.id || 'folder'
}

function applyQueryState() {
  selectedSource.value = String(route.query.source || '')
  currentPath.value = normalizePath(route.query.path || '')
  search.value = String(route.query.q || '')
}

function syncQueryState() {
  const query = {}
  if (selectedSource.value) query.source = selectedSource.value
  if (currentPath.value) query.path = currentPath.value
  if (search.value.trim()) query.q = search.value.trim()
  router.push({ path: '/', query })
}

async function loadLibrary() {
  loading.value = true
  error.value = ''
  try {
    const [videosRes, sourcesRes] = await Promise.all([fetch('/api/videos'), fetch('/api/sources')])
    if (!videosRes.ok) throw new Error(`Videos failed: ${videosRes.status}`)
    if (!sourcesRes.ok) throw new Error(`Sources failed: ${sourcesRes.status}`)

    videos.value = await videosRes.json()
    sources.value = await sourcesRes.json()

    applyQueryState()
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

const selectedSourceItem = computed(() => sources.value.find(s => s.id === selectedSource.value) || null)
const sourceVideos = computed(() => videos.value.filter(v => v.source_id === selectedSource.value))

const mediaRootEntries = computed(() => {
  const out = sources.value.map((s) => ({
    type: 'source',
    id: s.id,
    name: sourceFolderName(s),
    label: s.label,
  }))
  return out.sort((a, b) => a.name.localeCompare(b.name))
})

const folderEntries = computed(() => {
  if (!selectedSource.value) return []
  const base = currentPath.value
  const folders = new Map()
  const files = []

  for (const item of sourceVideos.value) {
    const rel = normalizePath(item.rel_path)
    if (base && !(rel === base || rel.startsWith(base + '/'))) continue

    const rest = base ? rel.slice(base.length + (rel === base ? 0 : 1)) : rel
    if (!rest) continue

    const parts = rest.split('/')
    if (parts.length > 1) {
      const folderName = parts[0]
      if (!folders.has(folderName)) {
        const full = normalizePath(base ? `${base}/${folderName}` : folderName)
        folders.set(folderName, {
          type: 'folder',
          name: folderName,
          path: full,
        })
      }
    } else {
      files.push({ type: 'file', ...item, name: item.title })
    }
  }

  const folderList = Array.from(folders.values()).sort((a, b) => a.name.localeCompare(b.name))
  const fileList = files.sort((a, b) => a.rel_path.localeCompare(b.rel_path))
  return [...folderList, ...fileList]
})

const searchResults = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return []
  const pool = selectedSource.value ? sourceVideos.value : videos.value
  return pool
    .filter(v => v.title.toLowerCase().includes(q) || v.rel_path.toLowerCase().includes(q))
    .sort((a, b) => a.rel_path.localeCompare(b.rel_path))
})

const breadcrumbs = computed(() => {
  const out = [{ label: '/media', source: '', path: '' }]
  if (!selectedSource.value) return out

  const src = selectedSourceItem.value
  out.push({ label: sourceFolderName(src), source: selectedSource.value, path: '' })

  const segments = currentPath.value ? currentPath.value.split('/').filter(Boolean) : []
  let acc = ''
  for (const seg of segments) {
    acc = normalizePath(acc ? `${acc}/${seg}` : seg)
    out.push({ label: seg, source: selectedSource.value, path: acc })
  }
  return out
})

function openSource(sourceId) {
  selectedSource.value = sourceId
  currentPath.value = ''
  syncQueryState()
}

function openFolder(path) {
  currentPath.value = normalizePath(path)
  syncQueryState()
}

function openFile(videoId) {
  router.push(`/watch/${videoId}`)
}

function openBreadcrumb(crumb) {
  selectedSource.value = crumb.source || ''
  currentPath.value = normalizePath(crumb.path || '')
  syncQueryState()
}

function goUp() {
  if (!selectedSource.value) return
  if (!currentPath.value) {
    selectedSource.value = ''
    syncQueryState()
    return
  }
  const parts = currentPath.value.split('/')
  parts.pop()
  currentPath.value = parts.join('/')
  syncQueryState()
}

watch(() => route.query, applyQueryState)

onMounted(loadLibrary)

async function deleteVideo(videoId, videoName) {
  if (!confirm(`Delete "${videoName}"?`)) return
  
  try {
    const res = await fetch(`/api/videos/${videoId}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    await loadLibrary()
  } catch (e) {
    error.value = String(e)
  }
}

function openMoveDialog(video) {
  moveVideoId.value = video.id
  moveVideoName.value = video.title
  moveInitialSource.value = video.source_id
  moveInitialPath.value = video.rel_path
  showMoveDialog.value = true
}

async function submitMove(data) {
  if (!moveVideoId.value) return
  
  error.value = ''
  
  try {
    const res = await fetch(`/api/videos/${moveVideoId.value}/move`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_source_id: data.targetSource,
        target_rel_path: data.targetPath
      })
    })
    
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`Failed: ${res.status} ${text}`)
    }
    
    showMoveDialog.value = false
    await loadLibrary()
  } catch (e) {
    error.value = String(e)
  }
}

function handleDragOver(event) {
  event.preventDefault()
  isDragging.value = true
}

function handleDragLeave(event) {
  event.preventDefault()
  isDragging.value = false
}

async function handleDrop(event) {
  event.preventDefault()
  isDragging.value = false
  
  if (!selectedSource.value) {
    showTemporaryError('Please select a folder first')
    return
  }
  
  const files = Array.from(event.dataTransfer.files).filter(f => 
    f.type.startsWith('video/') || 
    /\.(mp4|mkv|avi|mov|wmv|flv|webm|m4v)$/i.test(f.name)
  )
  
  if (files.length === 0) {
    showTemporaryError('No video files found')
    return
  }
  
  for (const file of files) {
    await uploadFileDirectly(file)
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

async function uploadFileDirectly(file) {
  const targetPath = currentPath.value ? `${currentPath.value}/${file.name}` : file.name
  
  uploadProgress.value.push({
    name: file.name,
    progress: 0,
    status: 'uploading'
  })
  
  const progressIndex = uploadProgress.value.length - 1
  
  try {
    const formData = new FormData()
    formData.append('source_id', selectedSource.value)
    formData.append('rel_path', targetPath)
    formData.append('video_file', file)
    
    const res = await fetch('/api/videos/upload', {
      method: 'POST',
      body: formData
    })
    
    if (!res.ok) {
      const text = await res.text()
      let errorMsg = text
      try {
        const json = JSON.parse(text)
        errorMsg = json.detail || text
      } catch {}
      throw new Error(errorMsg)
    }
    
    uploadProgress.value[progressIndex].status = 'done'
    uploadProgress.value[progressIndex].progress = 100
    
    setTimeout(() => {
      const idx = uploadProgress.value.findIndex(u => u.name === file.name && u.status === 'done')
      if (idx !== -1) {
        uploadProgress.value.splice(idx, 1)
      }
    }, 3000)
    
    await loadLibrary()
  } catch (e) {
    uploadProgress.value[progressIndex].status = 'failed'
    uploadProgress.value[progressIndex].error = String(e.message || e)
  }
}

async function submitAddFolder(folderName) {
  error.value = ''
  
  try {
    const folderId = folderName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
    const folderPath = `/media/${folderName}`
    
    const res = await fetch('/api/settings/sources', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: folderId,
        label: folderName,
        path: folderPath,
        create_if_missing: true,
      }),
    })
    
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text)
    }
    
    showAddFolderDialog.value = false
    await loadLibrary()
  } catch (e) {
    error.value = String(e.message || e)
  }
}

function removeUpload(idx) {
  uploadProgress.value.splice(idx, 1)
}
</script>

<template>
  <main class="mx-auto max-w-6xl p-4 md:p-8">
    <header class="mb-6 flex items-center justify-between">
      <div>
        <h2 class="text-3xl font-bold">Library</h2>
        <p class="text-sm text-muted">Finder/S3 style browse rooted at /media</p>
      </div>
      <div class="flex gap-2">
        <button @click="showAddFolderDialog = true" class="rounded border border-white/20 px-3 py-2 text-sm font-medium hover:bg-white/5">+ Add Folder</button>
        <button @click="loadLibrary" class="rounded bg-accent px-3 py-2 text-sm font-medium text-black hover:opacity-90">Rescan</button>
      </div>
    </header>

    <section class="mb-5 rounded-lg border border-white/10 bg-panel p-4">
      <input v-model="search" @input="syncQueryState" type="text" placeholder="Search files (full text in title/path)" class="w-full rounded border border-white/20 bg-black/30 px-3 py-2 text-sm" />
    </section>

    <div v-if="loading" class="text-muted">Loading videos...</div>
    <div v-else-if="error" class="mb-4 flex items-center justify-between rounded border border-red-500/60 bg-red-950/30 p-3 text-red-300">
      <span>{{ error }}</span>
      <button @click="error = ''" class="ml-2 rounded px-2 py-1 text-xs hover:bg-red-900/50">✕</button>
    </div>
    <section 
      v-else 
      class="rounded-lg border border-white/10 bg-panel p-4 relative"
      :class="{ 'border-accent border-2': isDragging }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <!-- Drag overlay -->
      <div v-if="isDragging" class="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-accent/20 backdrop-blur-sm">
        <div class="text-center">
          <p class="text-2xl font-bold">Drop video files here</p>
          <p class="text-sm text-muted">Files will be uploaded to current folder</p>
        </div>
      </div>

      <UploadProgress :uploads="uploadProgress" @remove="removeUpload" />

      <Breadcrumbs 
        v-if="!search.trim()"
        :breadcrumbs="breadcrumbs"
        :can-go-up="!!selectedSource"
        :show-drag-hint="!!selectedSource"
        @go-up="goUp"
        @navigate="openBreadcrumb"
      />

      <!-- Search Results -->
      <div v-if="search.trim()">
        <p class="mb-3 text-sm text-muted">Search results: {{ searchResults.length }}</p>
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <VideoCard
            v-for="item in searchResults"
            :key="item.id"
            :video="item"
            @play="openFile"
            @move="openMoveDialog"
            @delete="deleteVideo"
          />
        </div>
      </div>

      <!-- Media Root -->
      <div v-else-if="!selectedSource">
        <p class="mb-3 text-sm text-muted">/media</p>
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <div v-for="entry in mediaRootEntries" :key="entry.id" class="rounded-md border border-white/10 bg-black/15 p-3 flex items-center">
            <button @click="openSource(entry.id)" class="min-w-0 text-left w-full">
              <p class="truncate text-base font-semibold text-gray-200 capitalize">📁 {{ entry.name }}</p>
            </button>
          </div>
        </div>
      </div>

      <!-- Folder Contents -->
      <div v-else>
        <p class="mb-3 text-sm text-muted">{{ folderEntries.length }} item(s)</p>
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <div
            v-for="entry in folderEntries"
            :key="entry.type === 'folder' ? `d:${entry.path}` : `f:${entry.id}`"
            :class="[
              'rounded-md border border-white/10 bg-black/15 p-3',
              entry.type === 'folder' ? 'flex items-center' : ''
            ]"
          >
            <button
              v-if="entry.type === 'folder'"
              @click="openFolder(entry.path)"
              class="min-w-0 text-left w-full"
            >
              <p class="truncate text-base font-semibold text-gray-200 capitalize">📁 {{ entry.name }}</p>
            </button>
            <VideoCard
              v-else
              :video="entry"
              @play="openFile"
              @move="openMoveDialog"
              @delete="deleteVideo"
            />
          </div>
        </div>
      </div>
    </section>

    <MoveDialog
      :show="showMoveDialog"
      :video-name="moveVideoName"
      :sources="sources"
      :initial-source="moveInitialSource"
      :initial-path="moveInitialPath"
      @close="showMoveDialog = false"
      @submit="submitMove"
    />

    <AddFolderDialog
      :show="showAddFolderDialog"
      @close="showAddFolderDialog = false"
      @submit="submitAddFolder"
    />
  </main>
</template>
