<script setup>
defineProps({
  breadcrumbs: {
    type: Array,
    default: () => []
  },
  canGoUp: Boolean,
  showDragHint: Boolean
})

const emit = defineEmits(['goUp', 'navigate'])
</script>

<template>
  <div class="mb-4 flex flex-wrap items-center gap-2 text-sm">
    <button @click="emit('goUp')" :disabled="!canGoUp" class="rounded border border-white/20 px-2 py-1 disabled:opacity-40">Up</button>
    <span class="text-muted">Path:</span>
    <button
      v-for="crumb in breadcrumbs"
      :key="`${crumb.source}:${crumb.path || 'root'}`"
      @click="emit('navigate', crumb)"
      class="rounded border border-white/20 px-2 py-1"
    >
      {{ crumb.label }}
    </button>
    <span v-if="showDragHint" class="ml-auto text-xs text-muted">💡 Drag & drop video files to upload</span>
  </div>
</template>
