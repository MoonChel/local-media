<script setup>
const props = defineProps({
  folder: {
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

const emit = defineEmits(['open', 'move', 'delete', 'toggleSelect'])

function handleClick(event) {
  if (props.selectionMode) {
    emit('toggleSelect', props.folder.path)
  } else {
    emit('open', props.folder.path)
  }
}
</script>

<template>
  <div
    @click="handleClick"
    :class="[
      'block rounded-md border p-4 text-left hover:border-white/25 relative group cursor-pointer flex flex-col items-center justify-center',
      selected ? 'border-blue-500 bg-blue-950/30' : 'border-white/10 bg-black/15'
    ]"
  >
    <div v-if="selectionMode" class="absolute top-2 left-2 z-10">
      <input
        type="checkbox"
        :checked="selected"
        @click.stop
        @change="emit('toggleSelect', folder.path)"
        class="h-5 w-5 rounded border-white/20 bg-black/50"
      />
    </div>
    
    <!-- Large folder icon -->
    <div class="text-8xl mb-3">📁</div>
    
    <!-- Folder name underneath -->
    <p class="text-sm font-semibold text-gray-200 text-center line-clamp-2 w-full px-2">
      {{ folder.name }}
    </p>
    
    <!-- Action buttons on hover -->
    <div v-if="!selectionMode" class="absolute top-2 right-2 hidden group-hover:flex gap-1">
      <button 
        @click.stop.prevent="emit('move', folder)" 
        class="rounded bg-blue-600 hover:bg-blue-700 px-2 py-1 text-xs font-medium text-white"
        title="Move"
      >
        Move
      </button>
      <button 
        @click.stop.prevent="emit('delete', folder)" 
        class="rounded bg-red-600 hover:bg-red-700 px-2 py-1 text-xs font-medium text-white"
        title="Delete"
      >
        Delete
      </button>
    </div>
  </div>
</template>
