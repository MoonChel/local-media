<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: Boolean,
  videoName: String,
  initialPath: String
})

const emit = defineEmits(['close', 'submit'])

const targetPath = ref('')
const moving = ref(false)

watch(() => props.show, (newVal) => {
  if (newVal) {
    targetPath.value = props.initialPath || ''
    moving.value = false
  }
})

async function handleSubmit() {
  if (!targetPath.value) return
  
  moving.value = true
  try {
    await emit('submit', {
      targetPath: targetPath.value
    })
  } finally {
    moving.value = false
  }
}
</script>

<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70" @click.self="emit('close')">
    <div class="w-full max-w-md rounded-lg border border-white/20 bg-panel p-6">
      <h3 class="mb-4 text-xl font-bold">Move Video</h3>
      <p class="mb-4 text-sm text-muted">Moving: {{ videoName }}</p>
      
      <div class="space-y-3">
        <div>
          <label class="mb-1 block text-sm text-muted">New Path (relative to /media)</label>
          <input v-model="targetPath" type="text" placeholder="videos/folder/video.mp4" class="w-full rounded border border-white/20 bg-black/30 px-3 py-2 text-sm" />
        </div>
      </div>
      
      <div class="mt-6 flex justify-end gap-2">
        <button @click="emit('close')" class="rounded border border-white/20 px-4 py-2 text-sm">Cancel</button>
        <button @click="handleSubmit" :disabled="moving" class="rounded bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50">
          {{ moving ? 'Moving...' : 'Move' }}
        </button>
      </div>
    </div>
  </div>
</template>
