<script setup>
const props = defineProps({
  video: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['play', 'move', 'delete'])

function playPreview(event) {
  const el = event.currentTarget
  if (!(el instanceof HTMLVideoElement)) return
  el.currentTime = 5  // Start from 5 seconds
  el.play().catch(() => {})
}

function stopPreview(event) {
  const el = event.currentTarget
  if (!(el instanceof HTMLVideoElement)) return
  el.pause()
  el.currentTime = 5  // Reset to 5 seconds
}
</script>

<template>
  <button
    @click="emit('play', video.id)"
    class="rounded-md border border-white/10 bg-black/15 p-3 text-left hover:border-white/25 relative group overflow-hidden"
  >
    <div class="min-w-0">
      <div class="mb-2 h-32 w-full rounded bg-black overflow-hidden">
        <video
          :src="video.stream_url"
          muted
          playsinline
          preload="metadata"
          class="h-full w-full object-cover"
          @mouseenter="playPreview"
          @mouseleave="stopPreview"
        ></video>
      </div>
      <p class="truncate text-sm font-semibold text-gray-200">{{ video.title }}</p>
    </div>
    <div class="absolute top-2 right-2 hidden group-hover:flex gap-1">
      <button @click.stop="emit('move', video)" class="rounded bg-blue-600 px-2 py-1 text-xs text-white" title="Move">Move</button>
      <button @click.stop="emit('delete', video.id, video.title)" class="rounded bg-red-600 px-2 py-1 text-xs text-white" title="Delete">Del</button>
    </div>
  </button>
</template>
