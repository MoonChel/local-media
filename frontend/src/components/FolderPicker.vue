<script setup>
import { computed, onMounted, ref } from 'vue'

const emit = defineEmits(['update:modelValue', 'close'])

const currentPath = ref('')
const folders = ref([])
const loading = ref(false)

async function loadFolders() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (currentPath.value) {
      params.append('path', currentPath.value)
    }
    const res = await fetch(`/api/browse?${params}`)
    if (res.ok) {
      const data = await res.json()
      folders.value = data.folders || []
    } else {
      folders.value = []
    }
  } catch (e) {
    console.error('Failed to load folders:', e)
    folders.value = []
  } finally {
    loading.value = false
  }
}

function normalizePath(value) {
  return String(value || '')
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
    .replace(/\/+$/, '')
}

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
  loadFolders()
}

function openBreadcrumb(crumb) {
  currentPath.value = normalizePath(crumb.path || '')
  loadFolders()
}

function selectCurrent() {
  const fullPath = currentPath.value ? `/media/${currentPath.value}` : '/media'
  const label = breadcrumbs.value[breadcrumbs.value.length - 1].label
  
  emit('update:modelValue', {
    path: currentPath.value,
    fullPath: fullPath,
    label: label
  })
  emit('close')
}

onMounted(() => {
  loadFolders()
})
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70" @click.self="$emit('close')">
    <div class="w-full max-w-2xl rounded-lg border border-white/20 bg-panel p-6 max-h-[80vh] overflow-y-auto">
      <h3 class="mb-4 text-xl font-bold">Select Destination Folder</h3>
      
      <!-- Breadcrumbs -->
      <div class="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <button
          v-for="crumb in breadcrumbs"
          :key="crumb.path || 'root'"
          @click="openBreadcrumb(crumb)"
          class="rounded border border-white/20 px-2 py-1 hover:bg-white/5"
          :class="{ 'bg-white/10': crumb === breadcrumbs[breadcrumbs.length - 1] }"
        >
          {{ crumb.label }}
        </button>
      </div>

      <!-- Folder list -->
      <div class="mb-4">
        <p class="mb-3 text-sm text-muted">
          Current folder: <span class="text-gray-200">{{ breadcrumbs[breadcrumbs.length - 1].label }}</span>
        </p>
        
        <div v-if="loading" class="text-sm text-muted">Loading folders...</div>
        
        <div v-else-if="folders.length > 0" class="mb-3">
          <p class="text-xs text-muted mb-2">Subfolders:</p>
          <div class="grid gap-2 md:grid-cols-2">
            <button
              v-for="folder in folders"
              :key="folder.path"
              @click="openFolder(folder.path)"
              class="rounded-md border border-white/10 bg-black/15 p-3 text-left hover:border-white/25 flex items-center"
            >
              <p class="truncate text-base font-semibold text-gray-200">📁 {{ folder.name }}</p>
            </button>
          </div>
        </div>
        
        <p class="text-xs text-muted mt-2">Files will be downloaded to this folder</p>
      </div>

      <!-- Actions -->
      <div class="flex justify-end gap-2">
        <button @click="$emit('close')" class="rounded border border-white/20 px-4 py-2 text-sm">Cancel</button>
        <button 
          @click="selectCurrent" 
          class="rounded bg-accent px-4 py-2 text-sm text-black"
        >
          Select This Folder
        </button>
      </div>
    </div>
  </div>
</template>
