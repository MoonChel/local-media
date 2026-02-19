<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import videojs from 'video.js'
import 'video.js/dist/video-js.css'
import 'videojs-seek-buttons/dist/videojs-seek-buttons.css'
import 'videojs-seek-buttons'
import 'videojs-hotkeys'
import Breadcrumbs from '../components/Breadcrumbs.vue'

const route = useRoute()
const router = useRouter()
const videoId = computed(() => route.params.videoId)
const playerEl = ref(null)
const player = ref(null)
const details = ref(null)
const error = ref('')
const seekTime = ref(10)
let progressTimer = null
let lastSavedPosition = 0

const breadcrumbs = computed(() => {
  if (!details.value) return []
  const path = details.value.rel_path || ''
  const parts = path.split('/').filter(Boolean)
  parts.pop() // Remove filename
  
  const crumbs = []
  let currentPath = ''
  
  for (const part of parts) {
    currentPath = currentPath ? `${currentPath}/${part}` : part
    crumbs.push({
      source: details.value.source_id,
      path: currentPath,
      label: part
    })
  }
  
  return crumbs
})

const canGoUp = computed(() => breadcrumbs.value.length > 0)

function goUp() {
  if (breadcrumbs.value.length === 0) {
    router.push('/')
  } else {
    const parent = breadcrumbs.value[breadcrumbs.value.length - 1]
    router.push(`/?source=${parent.source}&path=${encodeURIComponent(parent.path)}`)
  }
}

function navigateTo(crumb) {
  router.push(`/?source=${crumb.source}&path=${encodeURIComponent(crumb.path)}`)
}

function mimeTypeFromPath(path) {
  const p = String(path || '').toLowerCase()
  if (p.endsWith('.mp4') || p.endsWith('.m4v')) return 'video/mp4'
  if (p.endsWith('.webm')) return 'video/webm'
  if (p.endsWith('.ogg') || p.endsWith('.ogv')) return 'video/ogg'
  if (p.endsWith('.mov')) return 'video/quicktime'
  if (p.endsWith('.mkv')) return 'video/x-matroska'
  if (p.endsWith('.avi')) return 'video/x-msvideo'
  return 'video/mp4'
}

async function loadVideo() {
  try {
    const settingsRes = await fetch('/api/settings')
    if (settingsRes.ok) {
      const settings = await settingsRes.json()
      seekTime.value = Number(settings.player?.seek_time ?? 10)
    }

    const listRes = await fetch('/api/videos')
    if (!listRes.ok) throw new Error(`Failed: ${listRes.status}`)
    const all = await listRes.json()
    const found = all.find((x) => x.id === videoId.value)
    if (!found) {
      error.value = 'Video not found'
      return
    }
    details.value = found
    await nextTick()

    if (!playerEl.value) {
      throw new Error('Player element is not ready')
    }

    if (player.value) player.value.dispose()

    player.value = videojs(playerEl.value, {
      controls: true,
      fluid: true,
      responsive: true,
      aspectRatio: '16:9',
      preload: 'auto',
      playbackRates: [0.5, 0.75, 1, 1.25, 1.5, 2],
      controlBar: {
        children: [
          'playToggle',
          'volumePanel',
          'currentTimeDisplay',
          'timeDivider',
          'durationDisplay',
          'progressControl',
          'remainingTimeDisplay',
          'playbackRateMenuButton',
          'pictureInPictureToggle',
          'fullscreenToggle'
        ]
      }
    })

    player.value.src({
      src: found.stream_url,
      type: mimeTypeFromPath(found.rel_path),
    })
    player.value.seekButtons({ forward: seekTime.value, back: seekTime.value })
    player.value.hotkeys({ seekStep: seekTime.value, volumeStep: 0.1 })
    player.value.on('timeupdate', () => {
      const pos = Number(player.value?.currentTime() || 0)
      if (Math.abs(pos - lastSavedPosition) >= 2) {
        saveProgress()
      }
    })

    const progressRes = await fetch(`/api/progress/${videoId.value}`)
    if (!progressRes.ok) throw new Error(`Failed: ${progressRes.status}`)
    const pr = await progressRes.json()
    const startFrom = Number(pr.position_seconds || 0)
    player.value.one('loadedmetadata', () => {
      const duration = Number(player.value?.duration() || 0)
      if (startFrom > 0 && startFrom < duration - 3) {
        player.value.currentTime(startFrom)
      }
    })

    if (progressTimer) clearInterval(progressTimer)
    progressTimer = setInterval(saveProgress, 5000)
  } catch (e) {
    error.value = String(e)
  }
}

async function saveProgress(opts = {}) {
  if (!player.value || !videoId.value) return
  const position = Number(player.value.currentTime() || 0)
  lastSavedPosition = position
  await fetch(`/api/progress/${videoId.value}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    keepalive: Boolean(opts.keepalive),
    body: JSON.stringify({ position_seconds: position }),
  })
}

function saveProgressOnLeave() {
  // Best effort save during navigation/reload.
  void saveProgress({ keepalive: true })
}

watch(videoId, loadVideo, { immediate: true })
window.addEventListener('pagehide', saveProgressOnLeave)
window.addEventListener('beforeunload', saveProgressOnLeave)
onBeforeUnmount(() => {
  window.removeEventListener('pagehide', saveProgressOnLeave)
  window.removeEventListener('beforeunload', saveProgressOnLeave)
  void saveProgress({ keepalive: true })
  if (progressTimer) clearInterval(progressTimer)
  if (player.value) player.value.dispose()
})
</script>

<template>
  <main class="mx-auto max-w-6xl p-4 md:p-8">
    <Breadcrumbs 
      v-if="details"
      :breadcrumbs="breadcrumbs" 
      :canGoUp="canGoUp"
      :showDragHint="false"
      @goUp="goUp"
      @navigate="navigateTo"
    />

    <div v-if="error" class="rounded border border-red-500/60 bg-red-950/30 p-3 text-red-300">{{ error }}</div>
    <div v-else-if="details" class="space-y-3">
      <h2 class="text-2xl font-semibold">{{ details.title }}</h2>
      <p class="text-xs text-muted">{{ details.source_label || details.source_id }} • {{ details.rel_path }}</p>
      <video ref="playerEl" class="video-js vjs-big-play-centered w-full rounded-lg border border-white/10 bg-black mb-8"></video>
    </div>
  </main>
</template>
