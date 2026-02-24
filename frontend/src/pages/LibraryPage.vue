<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VideoCard from '../components/VideoCard.vue'
import FolderCard from '../components/FolderCard.vue'
import MoveDialog from '../components/MoveDialog.vue'
import AddFolderDialog from '../components/AddFolderDialog.vue'
import UploadProgress from '../components/UploadProgress.vue'
import Breadcrumbs from '../components/Breadcrumbs.vue'
import { useNotification } from '../composables/useNotification'

const route = useRoute()
const router = useRouter()
const { showNotification } = useNotification()

const videos = ref([])
const folders = ref([])
const browsedItems = ref({ folders: [], files: [] })
const loading = ref(true)
const error = ref('')

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

const selectionMode = ref(false)
const selectedVideos = ref(new Set())
const selectedFolders = ref(new Set())
const convertingVideos = ref(new Set())
const showBulkActionsMenu = ref(false)

const moveFolderPath = ref('')
const moveFolderName = ref('')

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
  currentPath.value = normalizePath(route.query.path || '')
  search.value = String(route.query.q || '')
}

function syncQueryState() {
  const query = {}
  if (currentPath.value) query.path = currentPath.value
  if (search.value.trim()) query.q = search.value.trim()
  router.push({ path: '/', query })
}

async function loadLibrary() {
  loading.value = true
  error.value = ''
  try {
    const videosRes = await fetch('/api/videos')
    if (!videosRes.ok) throw new Error(`Videos failed: ${videosRes.status}`)

    videos.value = await videosRes.json()

    applyQueryState()
    
    // Always load folders
    await loadFolders()
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

async function loadFolders() {
  try {
    const params = new URLSearchParams()
    if (currentPath.value) {
      params.append('path', currentPath.value)
    }
    const res = await fetch(`/api/browse?${params}`)
    if (res.ok) {
      const data = await res.json()
      browsedItems.value = data
    } else {
      browsedItems.value = { folders: [], files: [] }
    }
  } catch (e) {
    console.error('Failed to load folders:', e)
    browsedItems.value = { folders: [], files: [] }
  }
}

const folderEntries = computed(() => {
  // Use filesystem structure from browse API
  const folderList = (browsedItems.value.folders || []).map(f => ({
    type: 'folder',
    name: f.name,
    path: f.path
  }))
  
  const fileList = (browsedItems.value.files || []).map(f => ({
    type: 'file',
    ...f,
    name: f.title
  }))

  return [...folderList, ...fileList]
})

const searchResults = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return []
  return videos.value
    .filter(v => v.title.toLowerCase().includes(q) || v.rel_path.toLowerCase().includes(q))
    .sort((a, b) => a.rel_path.localeCompare(b.rel_path))
})

const breadcrumbs = computed(() => {
  const out = [{ label: '/media', path: '' }]
  
  const segments = currentPath.value ? currentPath.value.split('/').filter(Boolean) : []
  let acc = ''
  for (const seg of segments) {
    acc = normalizePath(acc ? `${acc}/${seg}` : seg)
    out.push({ label: seg, path: acc })
  }
  return out
})

function openFolder(path) {
  currentPath.value = normalizePath(path)
  syncQueryState()
  loadFolders()
}

function openFile(videoId) {
  router.push(`/watch/${videoId}`)
}

function openBreadcrumb(crumb) {
  currentPath.value = normalizePath(crumb.path || '')
  syncQueryState()
  loadFolders()
}

function goUp() {
  if (!currentPath.value) return
  
  const parts = currentPath.value.split('/')
  parts.pop()
  currentPath.value = parts.join('/')
  syncQueryState()
  loadFolders()
}

watch(() => route.query, applyQueryState)

onMounted(() => {
  loadLibrary()
  
  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.relative')) {
      showBulkActionsMenu.value = false
    }
  })
})

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

async function convertVideo(video) {
  convertingVideos.value.add(video.id)
  
  try {
    const res = await fetch(`/api/videos/${video.id}/convert`, { method: 'POST' })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || `Failed: ${res.status}`)
    }
    const result = await res.json()
    
    showNotification(result.message + '\n\nClick "Rescan" to see the HLS version.', 'success')
  } catch (e) {
    error.value = String(e)
    showNotification(`Conversion failed: ${e}`, 'error')
  } finally {
    convertingVideos.value.delete(video.id)
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
    // Check if bulk move (comma-separated IDs)
    const videoIds = moveVideoId.value.split(',')
    
    if (videoIds.length > 1) {
      // Bulk move
      const promises = videoIds.map(videoId =>
        fetch(`/api/videos/${videoId}/move`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_source_id: data.targetSource,
            target_rel_path: data.targetPath
          })
        })
      )
      await Promise.all(promises)
      selectedVideos.value.clear()
      selectionMode.value = false
    } else {
      // Single move
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
    }

    showMoveDialog.value = false
    await loadLibrary()
  } catch (e) {
    error.value = String(e)
  }
}

function toggleSelectionMode() {
  selectionMode.value = !selectionMode.value
  if (!selectionMode.value) {
    selectedVideos.value.clear()
    selectedFolders.value.clear()
  }
}

function toggleVideoSelection(videoId) {
  if (selectedVideos.value.has(videoId)) {
    selectedVideos.value.delete(videoId)
  } else {
    selectedVideos.value.add(videoId)
  }
}

function toggleFolderSelection(folderPath) {
  if (selectedFolders.value.has(folderPath)) {
    selectedFolders.value.delete(folderPath)
  } else {
    selectedFolders.value.add(folderPath)
  }
}

function selectAll() {
  folderEntries.value.forEach(entry => {
    if (entry.type === 'folder') {
      selectedFolders.value.add(entry.path)
    } else if (entry.type === 'file') {
      selectedVideos.value.add(entry.id)
    }
  })
}

function deselectAll() {
  selectedVideos.value.clear()
  selectedFolders.value.clear()
}

async function bulkDelete() {
  const count = selectedVideos.value.size
  if (count === 0) return
  if (!confirm(`Delete ${count} selected video(s)?`)) return
  
  try {
    const promises = Array.from(selectedVideos.value).map(videoId =>
      fetch(`/api/videos/${videoId}`, { method: 'DELETE' })
    )
    await Promise.all(promises)
    selectedVideos.value.clear()
    selectionMode.value = false
    await loadLibrary()
  } catch (e) {
    error.value = String(e)
  }
}

function bulkMove() {
  if (selectedVideos.value.size === 0) return
  const firstVideo = displayedVideos.value.find(v => selectedVideos.value.has(v.id))
  if (!firstVideo) return
  
  moveVideoId.value = Array.from(selectedVideos.value).join(',')
  moveVideoName.value = `${selectedVideos.value.size} videos`
  moveInitialSource.value = firstVideo.source_id
  moveInitialPath.value = firstVideo.rel_path
  showMoveDialog.value = true
}

async function bulkConvert() {
  if (selectedVideos.value.size === 0) return
  
  const videosToConvert = displayedVideos.value.filter(v => 
    selectedVideos.value.has(v.id) && 
    v.rel_path && 
    v.rel_path.match(/\.(mkv|avi|wmv|flv|mov|m4v)$/i)
  )
  
  if (videosToConvert.length === 0) {
    showNotification('No convertible videos selected (MKV/AVI/WMV/FLV/MOV/M4V)', 'error')
    return
  }
  
  showNotification(`Converting ${videosToConvert.length} video(s)...`, 'info')
  
  for (const video of videosToConvert) {
    await convertVideo(video)
  }
  
  selectedVideos.value.clear()
  selectionMode.value = false
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
    // Create folder in current directory
    const newFolderPath = currentPath.value 
      ? `${currentPath.value}/${folderName}` 
      : folderName
    
    const res = await fetch('/api/browse/create-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: newFolderPath
      }),
    })
    
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text)
    }
    
    showAddFolderDialog.value = false
    await loadFolders()
  } catch (e) {
    error.value = String(e.message || e)
  }
}

function removeUpload(idx) {
  uploadProgress.value.splice(idx, 1)
}

function openMoveFolder(folder) {
  moveFolderPath.value = folder.path
  moveFolderName.value = folder.name
  // TODO: Implement folder move dialog
  showNotification('Folder move not yet implemented', 'info')
}

async function deleteFolder(folder) {
  if (!confirm(`Delete folder "${folder.name}" and all its contents?`)) return
  
  try {
    const params = new URLSearchParams({ path: folder.path })
    const res = await fetch(`/api/browse?${params}`, { method: 'DELETE' })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text)
    }
    
    await loadLibrary()
  } catch (e) {
    error.value = String(e)
  }
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
        <button 
          v-if="!selectionMode"
          @click="toggleSelectionMode" 
          class="rounded border border-white/20 px-3 py-2 text-sm font-medium hover:bg-white/5"
        >
          Select
        </button>
        <template v-else>
          <button @click="selectAll" class="rounded border border-white/20 px-3 py-2 text-sm font-medium hover:bg-white/5">Select All</button>
          <button @click="deselectAll" class="rounded border border-white/20 px-3 py-2 text-sm font-medium hover:bg-white/5">Deselect All</button>
          
          <!-- Bulk Actions Dropdown -->
          <div class="relative">
            <button 
              @click="showBulkActionsMenu = !showBulkActionsMenu"
              :disabled="selectedVideos.size === 0 && selectedFolders.size === 0"
              class="rounded bg-purple-600 px-3 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-40 flex items-center gap-1"
            >
              Actions ({{ selectedVideos.size + selectedFolders.size }})
              <span class="text-xs">▼</span>
            </button>
            <div 
              v-if="showBulkActionsMenu && (selectedVideos.size > 0 || selectedFolders.size > 0)"
              class="absolute right-0 top-full mt-1 w-48 rounded border border-white/20 bg-black/95 shadow-lg z-10"
            >
              <button 
                v-if="selectedVideos.size > 0"
                @click="bulkConvert(); showBulkActionsMenu = false" 
                class="w-full px-4 py-2 text-left text-sm hover:bg-white/10 flex items-center gap-2"
              >
                <span class="text-green-400">▶</span> Convert to MP4
              </button>
              <button 
                @click="bulkMove(); showBulkActionsMenu = false" 
                class="w-full px-4 py-2 text-left text-sm hover:bg-white/10 flex items-center gap-2"
              >
                <span class="text-blue-400">→</span> Move
              </button>
              <button 
                @click="bulkDelete(); showBulkActionsMenu = false" 
                class="w-full px-4 py-2 text-left text-sm hover:bg-white/10 flex items-center gap-2 text-red-400"
              >
                <span>✕</span> Delete
              </button>
            </div>
          </div>
          
          <button @click="toggleSelectionMode" class="rounded border border-white/20 px-3 py-2 text-sm font-medium hover:bg-white/5">Cancel</button>
        </template>
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
        :can-go-up="!!currentPath"
        :show-drag-hint="false"
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
            :selected="selectedVideos.has(item.id)"
            :selectionMode="selectionMode"
            :converting="convertingVideos.has(item.id)"
            @play="openFile"
            @move="openMoveDialog"
            @delete="deleteVideo"
            @toggleSelect="toggleVideoSelection"
            @convert="convertVideo"
          />
        </div>
      </div>

      <!-- Folder Contents -->
      <div>
        <p class="mb-3 text-sm text-muted">{{ folderEntries.length }} item(s)</p>
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <FolderCard
            v-for="entry in folderEntries.filter(e => e.type === 'folder')"
            :key="`d:${entry.path}`"
            :folder="entry"
            :selected="selectedFolders.has(entry.path)"
            :selectionMode="selectionMode"
            @open="openFolder(entry.path)"
            @move="openMoveFolder"
            @delete="deleteFolder"
            @toggleSelect="toggleFolderSelection"
          />
          <VideoCard
            v-for="entry in folderEntries.filter(e => e.type === 'file')"
            :key="`f:${entry.id || entry.rel_path}`"
            :video="entry"
            :selected="selectedVideos.has(entry.id)"
            :selectionMode="selectionMode"
            :converting="convertingVideos.has(entry.id)"
            @play="openFile"
            @move="openMoveDialog"
            @delete="deleteVideo"
            @toggleSelect="toggleVideoSelection"
            @convert="convertVideo"
          />
        </div>
      </div>
    </section>

    <MoveDialog
      :show="showMoveDialog"
      :video-name="moveVideoName"
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
