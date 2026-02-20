<script setup>
import { onMounted, ref } from 'vue'

const modules = ref({
  torrents: true,
  youtube: true,
  pastebin: true,
})

onMounted(async () => {
  try {
    const res = await fetch('/api/modules')
    if (res.ok) {
      modules.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to fetch modules:', e)
  }
})
</script>

<template>
  <div class="min-h-screen">
    <header class="border-b border-white/10 bg-black/30 backdrop-blur">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:px-8">
        <h1 class="text-lg font-semibold">Local Media</h1>
        <nav class="flex items-center gap-2 text-sm">
          <RouterLink to="/" class="rounded px-3 py-1.5 hover:bg-white/10" active-class="bg-white/10">Library</RouterLink>
          <RouterLink v-if="modules.torrents" to="/torrents" class="rounded px-3 py-1.5 hover:bg-white/10" active-class="bg-white/10">Torrents</RouterLink>
          <RouterLink v-if="modules.youtube" to="/youtube" class="rounded px-3 py-1.5 hover:bg-white/10" active-class="bg-white/10">YouTube</RouterLink>
          <RouterLink v-if="modules.pastebin" to="/pastebin" class="rounded px-3 py-1.5 hover:bg-white/10" active-class="bg-white/10">Pastebin</RouterLink>
          <RouterLink to="/settings" class="rounded px-3 py-1.5 hover:bg-white/10" active-class="bg-white/10">Settings</RouterLink>
        </nav>
      </div>
    </header>
    <RouterView />
  </div>
</template>
