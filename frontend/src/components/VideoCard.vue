<script setup>
const props = defineProps({
  video: {
    type: Object,
    required: true
  },
  selected: {
    type: Boolean,
    default: false
  },
  selectionMode: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['play', 'move', 'delete', 'toggleSelect'])

function playPreview(event) {
  const el = event.currentTarget
  if (!(el instanceof HTMLVideoElement)) return
  
  // Wait for metadata to load to get duration
  if (el.duration && !isNaN(el.duration)) {
    el.currentTime = el.duration * 0.2  // Start at 20% of video duration
  } else {
    // Fallback to 5 seconds if duration not available yet
    el.currentTime = 5
  }
  
  el.play().catch(() => {})
}

function stopPreview(event) {
  const el = event.currentTarget
  if (!(el instanceof HTMLVideoElement)) return
  el.pause()
  
  // Reset to 20% position
  if (el.duration && !isNaN(el.duration)) {
    el.currentTime = el.duration * 0.2
  } else {
    el.currentTime = 5
  }
}

function handleClick(event) {
  if (props.selectionMode) {
    event.preventDefault()
    emit('toggleSelect', props.video.id)
  }
}
</script>

<template>
  <div class="relative">
    <a
      :href="`/watch/${video.id}`"
      @click="handleClick"
      :class="[
        'block rounded-md border p-3 text-left hover:border-white/25 relative group overflow-hidden flex flex-col h-full',
        selected ? 'border-blue-500 bg-blue-950/30' : 'border-white/10 bg-black/15'
      ]"
    >
      <div v-if="selectionMode" class="absolute top-2 left-2 z-10">
        <input
          type="checkbox"
          :checked="selected"
          @click.stop
          @change="emit('toggleSelect', video.id)"
          class="h-5 w-5 rounded border-white/20 bg-black/50"
        />
      </div>
      <div class="flex-1 flex flex-col min-w-0">
        <div class="mb-2 aspect-video w-full rounded bg-black overflow-hidden flex-shrink-0">
          <video
            :src="video.stream_url"
            muted
            playsinline
            preload="metadata"
            class="h-full w-full object-contain"
            @mouseenter="playPreview"
            @mouseleave="stopPreview"
          ></video>
        </div>
        <p class="text-sm font-semibold text-gray-200 line-clamp-2 min-h-[2.5rem]">{{ video.title }}</p>
      </div>
      <div v-if="!selectionMode" class="absolute top-2 right-2 hidden group-hover:flex gap-1">
        <button @click.stop.prevent="emit('move', video)" class="rounded bg-blue-600 px-2 py-1 text-xs text-white" title="Move">Move</button>
        <button @click.stop.prevent="emit('delete', video.id, video.title)" class="rounded bg-red-600 px-2 py-1 text-xs text-white" title="Delete">Del</button>
      </div>
    </a>
  </div>
</template>
