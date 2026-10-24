import axios from 'axios'
import { t } from '@/i18n'

// All requests go to /api on the same address the page came from. In
// development Vite forwards them to Django (see vite.config.js); in production
// Django serves both. That's why the site also works through a public tunnel.
const common = {
  baseURL: '/api/',
  timeout: 15000,
  headers: { 'ngrok-skip-browser-warning': '1' },
}

/** Plain client for sign-in and token refresh (no automatic retry). */
export const authHttp = axios.create(common)

/** Client for everything else: adds the access token and refreshes it once on 401. */
export const http = axios.create(common)

let store = null
let router = null

export function bindAuth(vuexStore, vueRouter) {
  store = vuexStore
  router = vueRouter
}

http.interceptors.request.use((config) => {
  const token = store?.state.auth.access
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && original && !original._retried && store?.state.auth.refresh) {
      original._retried = true
      try {
        await store.dispatch('auth/refresh')
        original.headers.Authorization = `Bearer ${store.state.auth.access}`
        return http(original)
      } catch {
        await store.dispatch('auth/logout', { remote: false })
        router?.push({ name: 'login', query: { next: router.currentRoute.value.fullPath, expired: '1' } })
      }
    }
    return Promise.reject(error)
  },
)

/** Turn any request error into one sentence a person can act on. */
export function errorMessage(error, fallback = t('common.genericError')) {
  if (!error) return fallback
  if (!error.response) return t('common.networkError')
  const data = error.response.data
  if (data && typeof data === 'object' && data.detail) return data.detail
  return fallback
}

export function errorCode(error) {
  return error?.response?.data?.code || null
}

export function fieldErrors(error) {
  const fields = error?.response?.data?.fields
  if (!fields || typeof fields !== 'object') return {}
  return Object.fromEntries(
    Object.entries(fields).map(([key, value]) => [key, Array.isArray(value) ? value.join(' ') : String(value)]),
  )
}
