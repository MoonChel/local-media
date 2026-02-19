import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import './style.css'

import App from './App.vue'
import LibraryPage from './pages/LibraryPage.vue'
import TorrentsPage from './pages/TorrentsPage.vue'
import YouTubePage from './pages/YouTubePage.vue'
import WatchPage from './pages/WatchPage.vue'
import SettingsPage from './pages/SettingsPage.vue'
import PastebinPage from './pages/PastebinPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: LibraryPage },
    { path: '/torrents', component: TorrentsPage },
    { path: '/youtube', component: YouTubePage },
    { path: '/pastebin', component: PastebinPage },
    { path: '/watch/:videoId', component: WatchPage },
    { path: '/settings', component: SettingsPage },
  ],
})

createApp(App).use(router).mount('#app')
