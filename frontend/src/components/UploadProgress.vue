<script setup>
defineProps({
  uploads: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['remove'])
</script>

<template>
  <div v-if="uploads.length > 0" class="mb-4 space-y-2">
    <div v-for="(upload, idx) in uploads" :key="idx" class="rounded border bg-black/20 p-3" :class="{
      'border-blue-500/60 bg-blue-950/30': upload.status === 'uploading',
      'border-green-500/60 bg-green-950/30': upload.status === 'done',
      'border-red-500/60 bg-red-950/30': upload.status === 'failed'
    }">
      <div class="flex items-start justify-between gap-2">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span v-if="upload.status === 'uploading'" class="text-blue-400 text-sm font-medium">⏳ Uploading</span>
            <span v-else-if="upload.status === 'done'" class="text-green-400 text-sm font-medium">✓ Upload Complete</span>
            <span v-else-if="upload.status === 'failed'" class="text-red-400 text-sm font-medium">✗ Upload Failed</span>
          </div>
          <p class="text-sm truncate">{{ upload.name }}</p>
          <p v-if="upload.error" class="mt-1 text-xs text-red-300">{{ upload.error }}</p>
        </div>
        <button @click="emit('remove', idx)" class="rounded px-2 py-1 text-xs hover:bg-white/10">✕</button>
      </div>
    </div>
  </div>
</template>
