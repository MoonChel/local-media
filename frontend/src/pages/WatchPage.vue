<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import videojs from 'video.js/dist/video.es.js'
import 'video.js/dist/video-js.css'
import 'videojs-seek-buttons/dist/videojs-seek-buttons.css'
import 'videojs-seek-buttons'
import 'videojs-hotkeys'

const route = useRoute()
const videoId = computed(() => route.params.videoId)
const playerEl = ref(null)
const player = ref(null)
const details = ref(null)
const error = ref('')
const castMessage = ref('')
const castSupported = ref(true)
const seekTime = ref(10)
let progressTimer = null
let castInitPromise = null
let lastSavedPosition = 0

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

function loadCastSdk() {
  if (window.cast?.framework && window.chrome?.cast) {
    return Promise.resolve(true)
  }
  if (castInitPromise) return castInitPromise

  castInitPromise = new Promise((resolve) => {
    const timeout = setTimeout(() => resolve(false), 8000)

    window.__onGCastApiAvailable = (isAvailable) => {
      clearTimeout(timeout)
      if (!isAvailable || !window.cast?.framework || !window.chrome?.cast) {
        resolve(false)
        return
      }
      try {
        const context = window.cast.framework.CastContext.getInstance()
        context.setOptions({
          receiverApplicationId: window.chrome.cast.media.DEFAULT_MEDIA_RECEIVER_APP_ID,
          autoJoinPolicy: window.chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED,
        })
      } catch {
        resolve(false)
        return
      }
      resolve(true)
    }

    const existing = document.querySelector('script[data-gcast-sdk="1"]')
    if (!existing) {
      const script = document.createElement('script')
      script.src = 'https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1'
      script.async = true
      script.defer = true
      script.dataset.gcastSdk = '1'
      document.head.appendChild(script)
    }
  })

  return castInitPromise
}

async function requestCast() {
  const videoEl = playerEl.value
  if (!videoEl || !details.value) return
  castMessage.value = ''

  try {
    if (typeof videoEl.webkitShowPlaybackTargetPicker === 'function') {
      videoEl.webkitShowPlaybackTargetPicker()
      castMessage.value = 'AirPlay picker opened. Select a device.'
      return
    }

    const host = window.location.hostname
    if (host === 'localhost' || host === '127.0.0.1' || host === '::1') {
      castMessage.value = 'Use LAN IP (not localhost). TV cannot access localhost stream URLs.'
      return
    }

    const sdkReady = await loadCastSdk()
    if (!sdkReady) {
      castMessage.value = 'Cast SDK unavailable in this browser/session.'
      return
    }

    const context = window.cast.framework.CastContext.getInstance()
    await context.requestSession()

    const session = context.getCurrentSession()
    if (!session) {
      castMessage.value = 'No cast session selected.'
      return
    }

    const mediaUrl = new URL(details.value.stream_url, window.location.origin).href
    const mediaInfo = new window.chrome.cast.media.MediaInfo(mediaUrl, 'video/mp4')
    const metadata = new window.chrome.cast.media.GenericMediaMetadata()
    metadata.title = details.value.title
    mediaInfo.metadata = metadata

    const request = new window.chrome.cast.media.LoadRequest(mediaInfo)
    request.autoplay = true
    request.currentTime = Number(player.value?.currentTime() || 0)

    await session.loadMedia(request)
    castMessage.value = 'Cast started.'
  } catch (e) {
    if (e?.name === 'NotAllowedError' || e?.code === 'cancel') {
      castMessage.value = 'Cast canceled (no device selected).'
      return
    }
    castMessage.value = String(e)
  }
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
    castSupported.value = true
    castMessage.value = ''

    if (player.value) player.value.dispose()

    player.value = videojs(playerEl.value, {
      controls: true,
      fluid: true,
      preload: 'auto',
      playbackRates: [0.5, 0.75, 1, 1.25, 1.5, 2],
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
    <div class="mb-4 flex items-center justify-between">
      <RouterLink to="/" class="text-sm text-orange-300 hover:underline">← Back to library</RouterLink>
      <button
        v-if="castSupported"
        @click="requestCast"
        class="rounded border border-white/20 px-3 py-1.5 text-sm"
      >
        Cast
      </button>
    </div>

    <div v-if="error" class="rounded border border-red-500/60 bg-red-950/30 p-3 text-red-300">{{ error }}</div>
    <div v-else-if="details" class="space-y-3">
      <h2 class="text-2xl font-semibold">{{ details.title }}</h2>
      <p class="text-xs text-muted">{{ details.source_label || details.source_id }} • {{ details.rel_path }}</p>
      <p v-if="castMessage" class="text-xs text-orange-300">{{ castMessage }}</p>
      <video ref="playerEl" class="video-js vjs-big-play-centered w-full rounded-lg border border-white/10 bg-black"></video>
    </div>
  </main>
</template>
