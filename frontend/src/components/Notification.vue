<script setup>
defineProps({
  message: String,
  type: {
    type: String,
    default: 'error',
    validator: (value) => ['error', 'success', 'info'].includes(value)
  }
})

const emit = defineEmits(['close'])

</script>

<template>
  <div 
    v-if="message"
    class="mb-4 flex items-center justify-between rounded border p-3"
    :class="{
      'border-red-500/60 bg-red-950/30 text-red-300': type === 'error',
      'border-green-500/60 bg-green-950/30 text-green-300': type === 'success',
      'border-blue-500/60 bg-blue-950/30 text-blue-300': type === 'info'
    }"
  >
    <span>{{ message }}</span>
    <button @click="$emit('close')" class="ml-2 rounded px-2 py-1 text-xs hover:bg-white/10">✕</button>
  </div>
</template>
