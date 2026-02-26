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
const videoId = computed(() => route?.params?.videoId || '')
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
  // Files that will be transcoded to MP4 on the backend
  if (p.endsWith('.mkv') || p.endsWith('.avi') || p.endsWith('.wmv') || 
      p.endsWith('.flv') || p.endsWith('.mov') || p.endsWith('.m4v')) {
    return 'video/mp4'  // Backend transcodes these to MP4
  }
  if (p.endsWith('.mp4')) return 'video/mp4'
  if (p.endsWith('.webm')) return 'video/webm'
  if (p.endsWith('.ogg') || p.endsWith('.ogv')) return 'video/ogg'
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

    // Check if this is an HLS stream (master.m3u8 in path)
    const isHLS = found.rel_path.toLowerCase().includes('master.m3u8') || 
                  found.rel_path.toLowerCase().includes('_hls/')
    
    let videoSrc = found.stream_url
    let videoType = 'video/mp4'
    
    if (isHLS) {
      // For HLS folders, construct the master playlist URL
      videoSrc = found.stream_url.replace(/\/[^/]+$/, '/master.m3u8')
      videoType = 'application/x-mpegURL'
      console.log(`Using HLS: ${videoSrc}`)
    } else {
      // Check if format is supported
      const ext = found.rel_path.toLowerCase().split('.').pop()
      const unsupportedFormats = ['mkv', 'avi', 'wmv', 'flv', 'mov', 'm4v']
      
      if (unsupportedFormats.includes(ext)) {
        error.value = `Format .${ext} is not supported for direct playback. Please use Jellyfin for transcoding support.`
        return
      }
      
      videoType = mimeTypeFromPath(found.rel_path)
      console.log(`Direct playback: ${videoSrc}`)
    }

    player.value = videojs(playerEl.value, {
      controls: true,
      fluid: true,
      responsive: true,
      aspectRatio: '16:9',
      preload: 'auto',
      playbackRates: [0.5, 0.75, 1, 1.25, 1.5, 2],
      html5: {
        nativeTextTracks: false,  // Use Video.js text tracks
        nativeAudioTracks: false,  // Use Video.js audio tracks
        vhs: {
          overrideNative: !videojs.browser.IS_IOS,  // Use native HLS on iOS
          enableLowInitialPlaylist: true
        }
      },
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
          'audioTrackButton',  // Audio track selector
          'subsCapsButton',    // Subtitles/captions
          'pictureInPictureToggle',
          'fullscreenToggle'
        ]
      }
    })

    player.value.src({
      src: videoSrc,
      type: videoType,
    })
    
    // Debug logging
    player.value.on('loadstart', () => {
      console.log('Player: loadstart')
      console.log('Source:', player.value.currentSrc())
    })
    
    player.value.on('loadedmetadata', () => {
      console.log('Player: loadedmetadata')
      
      // Log the tech being used
      const tech = player.value.tech({ IWillNotUseThisInPlugins: true })
      console.log('Tech:', tech?.name_)
      
      // Log HLS info if available
      if (player.value.tech_?.vhs) {
        console.log('VHS/HLS tech loaded')
        const vhs = player.value.tech_.vhs
        console.log('Master playlist:', vhs.masterPlaylistController_?.masterPlaylistLoader_?.srcUrl)
        console.log('Media playlists:', vhs.masterPlaylistController_?.masterPlaylistLoader_?.master?.playlists)
      }
    })
    
    player.value.on('loadeddata', () => {
      console.log('Player: loadeddata')
    })
    
    player.value.on('canplay', () => {
      console.log('Player: canplay')
    })
    
    player.value.on('playing', () => {
      console.log('Player: playing')
    })
    
    player.value.on('waiting', () => {
      console.log('Player: waiting for data')
    })
    
    player.value.on('error', (e) => {
      console.error('Player error:', e)
      const error = player.value.error()
      if (error) {
        console.error('Error details:', error.code, error.message)
      }
      
      // Log VHS errors if available
      if (player.value.tech_?.vhs) {
        const vhs = player.value.tech_.vhs
        console.error('VHS error:', vhs.error_)
      }
    })
    
    player.value.seekButtons({ forward: seekTime.value, back: seekTime.value })
    player.value.hotkeys({ seekStep: seekTime.value, volumeStep: 0.1 })
    
    // Simple quality selector using VHS API
    player.value.ready(() => {
      console.log('Setting up quality selector')
      
      // Wait for VHS to load
      player.value.on('loadedmetadata', () => {
        const vhs = player.value.tech({ IWillNotUseThisInPlugins: true })?.vhs
        
        if (vhs && vhs.representations) {
          console.log('VHS representations available:', vhs.representations().length)
          
          // Create quality button
          const Button = videojs.getComponent('Button')
          
          class QualityButton extends Button {
            constructor(player, options) {
              super(player, options)
              this.controlText('Quality')
              this.addClass('vjs-quality-button')
              
              // Update label when quality changes
              this.updateLabel()
              player.on('loadedmetadata', () => this.updateLabel())
            }
            
            updateLabel() {
              const vhs = this.player_.tech({ IWillNotUseThisInPlugins: true })?.vhs
              if (vhs && vhs.representations) {
                const current = vhs.representations().filter(r => r.enabled)[0]
                if (current) {
                  this.controlText(`${current.height}p`)
                }
              }
            }
            
            handleClick() {
              const vhs = this.player_.tech({ IWillNotUseThisInPlugins: true })?.vhs
              if (!vhs || !vhs.representations) return
              
              const reps = vhs.representations()
              const current = reps.filter(r => r.enabled)[0]
              const currentIndex = reps.indexOf(current)
              const nextIndex = (currentIndex + 1) % reps.length
              
              // Disable all
              reps.forEach(r => r.enabled(false))
              // Enable next
              reps[nextIndex].enabled(true)
              
              this.updateLabel()
              console.log('Switched to quality:', reps[nextIndex].height + 'p')
            }
            
            buildCSSClass() {
              return `vjs-quality-button ${super.buildCSSClass()}`
            }
          }
          
          videojs.registerComponent('QualityButton', QualityButton)
          
          // Add button to control bar
          const controlBar = player.value.controlBar
          const fullscreenToggle = controlBar.getChild('fullscreenToggle')
          if (fullscreenToggle) {
            const index = controlBar.children().indexOf(fullscreenToggle)
            controlBar.addChild('QualityButton', {}, index)
            console.log('Quality button added')
          }
        }
      })
    })
    
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
window.addEventListener('pagehide', saveProgressOnLeave)
window.addEventListener('beforeunload', saveProgressOnLeave)
onBeforeUnmount(() => {
  window.removeEventListener('click', handleClickOutside)
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

    <div v-if="error" class="rounded border border-red-500/60 bg-red-950/30 p-3 text-red-300 flex items-center justify-between mb-4">
      <span>{{ error }}</span>
      <button @click="error = ''" class="ml-2 rounded px-2 py-1 text-xs hover:bg-red-900/50">✕</button>
    </div>
    <div v-else-if="details" class="space-y-3">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-2xl font-semibold">{{ details.title }}</h2>
          <p class="text-xs text-muted">{{ details.source_label || details.source_id }} • {{ details.rel_path }}</p>
        </div>
      </div>
      
      <div class="relative">
        <video ref="playerEl" class="video-js vjs-big-play-centered w-full rounded-lg border border-white/10 bg-black mb-8" playsinline webkit-playsinline></video>
      </div>
    </div>
  </main>
</template>
