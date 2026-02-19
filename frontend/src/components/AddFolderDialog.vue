<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: Boolean
})

const emit = defineEmits(['close', 'submit'])

const folderName = ref('')
const adding = ref(false)

watch(() => props.show, (newVal) => {
  if (newVal) {
    folderName.value = ''
    adding.value = false
  }
})

async function handleSubmit() {
  if (!folderName.value.trim()) return
  
  adding.value = true
  try {
    await emit('submit', folderName.value.trim())
  } finally {
    adding.value = false
  }
}
</script>

<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70" @click.self="emit('close')">
    <div class="w-full max-w-md rounded-lg border border-white/20 bg-panel p-6">
      <h3 class="mb-4 text-xl font-bold">Add Media Folder</h3>
      
      <div class="space-y-3">
        <div>
          <label class="mb-1 block text-sm text-muted">Folder name</label>
          <input 
            v-model="folderName" 
            type="text" 
            placeholder="e.g. My Movies or Documentaries" 
            class="w-full rounded border border-white/20 bg-black/30 px-3 py-2 text-sm"
            @keyup.enter="handleSubmit"
          />
          <p class="mt-1 text-xs text-muted">Will be created at: /media/{{ folderName || '...' }}</p>
        </div>
      </div>
      
      <div class="mt-6 flex justify-end gap-2">
        <button @click="emit('close')" class="rounded border border-white/20 px-4 py-2 text-sm">Cancel</button>
        <button @click="handleSubmit" :disabled="adding || !folderName.trim()" class="rounded bg-accent px-4 py-2 text-sm text-black disabled:opacity-50">
          {{ adding ? 'Adding...' : 'Add Folder' }}
        </button>
      </div>
    </div>
  </div>
</template>
