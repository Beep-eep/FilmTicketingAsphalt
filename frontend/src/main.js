import { createApp } from 'vue'

import '@fontsource-variable/big-shoulders-display'
import '@fontsource-variable/archivo/wdth.css'
import './styles/base.css'

import App from './App.vue'
import router from './router'
import store from './store'
import { bindAuth } from './api/client'
import { loadConfig } from './composables/useConfig'

bindAuth(store, router)
loadConfig()

createApp(App).use(store).use(router).mount('#app')
