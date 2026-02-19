<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  sources: Array,
  modelValue: Object, // { sourceId, path }
})

const emit = defineEmits(['update:modelValue', 'close'])

const selectedSource = ref('')
const currentPath = ref('')

// Initialize with modelValue if provided
watch(() => props.modelValue, (val) => {
  if (val) {
    selectedSource.value = val.sourceId || ''
    currentPath.value = val.path || ''
  }
}, { immediate: true })

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

const selectedSourceItem = computed(() => 
  props.sources?.find(s => s.id === selectedSource.value) || null
)

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

const mediaRootEntries = computed(() => {
  return (props.sources || []).map((s) => ({
    type: 'source',
    id: s.id,
    name: sourceFolderName(s),
    label: s.label,
  })).sort((a, b) => a.name.localeCompare(b.name))
})

// Get subfolders in current location
const subfolders = computed(() => {
  if (!selectedSource.value) return []
  
  // For now, we don't have a way to list subfolders without videos
  // So we'll just allow selecting the current folder
  return []
})

function openSource(sourceId) {
  selectedSource.value = sourceId
  currentPath.value = ''
}

function openBreadcrumb(crumb) {
  selectedSource.value = crumb.source || ''
  currentPath.value = normalizePath(crumb.path || '')
}

function selectCurrent() {
  if (!selectedSource.value) return
  
  emit('update:modelValue', {
    sourceId: selectedSource.value,
    path: currentPath.value,
    fullPath: currentPath.value ? `${selectedSourceItem.value.path}/${currentPath.value}` : selectedSourceItem.value.path,
    label: breadcrumbs.value[breadcrumbs.value.length - 1].label
  })
  emit('close')
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70" @click.self="$emit('close')">
    <div class="w-full max-w-2xl rounded-lg border border-white/20 bg-panel p-6 max-h-[80vh] overflow-y-auto">
      <h3 class="mb-4 text-xl font-bold">Select Destination Folder</h3>
      
      <!-- Breadcrumbs -->
      <div class="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <button
          v-for="crumb in breadcrumbs"
          :key="`${crumb.source}:${crumb.path || 'root'}`"
          @click="openBreadcrumb(crumb)"
          class="rounded border border-white/20 px-2 py-1 hover:bg-white/5"
          :class="{ 'bg-white/10': crumb === breadcrumbs[breadcrumbs.length - 1] }"
        >
          {{ crumb.label }}
        </button>
      </div>

      <!-- Folder list -->
      <div v-if="!selectedSource" class="mb-4">
        <p class="mb-3 text-sm text-muted">Select a folder:</p>
        <div class="grid gap-2 md:grid-cols-2">
          <button
            v-for="entry in mediaRootEntries"
            :key="entry.id"
            @click="openSource(entry.id)"
            class="rounded-md border border-white/10 bg-black/15 p-3 text-left hover:border-white/25 flex items-center"
          >
            <p class="truncate text-base font-semibold text-gray-200 capitalize">📁 {{ entry.name }}</p>
          </button>
        </div>
      </div>

      <div v-else class="mb-4">
        <p class="text-sm text-muted mb-2">Current folder: <span class="text-gray-200">{{ breadcrumbs[breadcrumbs.length - 1].label }}</span></p>
        <p class="text-xs text-muted">Files will be downloaded to this folder</p>
      </div>

      <!-- Actions -->
      <div class="flex justify-end gap-2">
        <button @click="$emit('close')" class="rounded border border-white/20 px-4 py-2 text-sm">Cancel</button>
        <button 
          @click="selectCurrent" 
          :disabled="!selectedSource"
          class="rounded bg-accent px-4 py-2 text-sm text-black disabled:opacity-50"
        >
          Select This Folder
        </button>
      </div>
    </div>
  </div>
</template>
