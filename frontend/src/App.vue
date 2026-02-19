<template>
  <div class="min-h-screen">
    <header class="border-b border-white/10 bg-black/30 backdrop-blur">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:px-8">
        <h1 class="text-lg font-semibold">Local Media</h1>
        <nav class="flex items-center gap-2 text-sm">
          <RouterLink to="/" class="rounded px-3 py-1.5 hover:bg-white/10" active-class="bg-white/10">Library</RouterLink>
          <RouterLink to="/torrents" class="rounded px-3 py-1.5 hover:bg-white/10" active-class="bg-white/10">Torrents</RouterLink>
          <RouterLink to="/youtube" class="rounded px-3 py-1.5 hover:bg-white/10" active-class="bg-white/10">YouTube</RouterLink>
          <RouterLink to="/pastebin" class="rounded px-3 py-1.5 hover:bg-white/10" active-class="bg-white/10">Pastebin</RouterLink>
          <RouterLink to="/settings" class="rounded px-3 py-1.5 hover:bg-white/10" active-class="bg-white/10">Settings</RouterLink>
        </nav>
      </div>
    </header>
    <RouterView />
  </div>
</template>
