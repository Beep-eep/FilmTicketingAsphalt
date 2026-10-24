import { computed, ref } from 'vue'
import en from './en.js'
import zh from './zh.js'

const messages = { en, zh }
const STORAGE_KEY = 'asphalt.locale'

function initialLocale() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && messages[saved]) return saved
  } catch {
    /* storage can be blocked; fall back to the browser language */
  }
  return (navigator.language || 'en').toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

export const locale = ref(initialLocale())
document.documentElement.lang = locale.value === 'zh' ? 'zh-CN' : 'en'

export function setLocale(next) {
  locale.value = next
  document.documentElement.lang = next === 'zh' ? 'zh-CN' : 'en'
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    /* ignore */
  }
}

/** t('seats.count', { n: 3 }) → looks up the key and fills {n}. Falls back to English, then the key. */
export function t(key, params = {}) {
  const lookup = (dict) => key.split('.').reduce((node, part) => (node == null ? node : node[part]), dict)
  let text = lookup(messages[locale.value]) ?? lookup(messages.en) ?? key
  if (typeof text === 'function') text = text(params)
  return String(text).replace(/\{(\w+)\}/g, (_, name) => (params[name] ?? `{${name}}`))
}

/** Film title in the current language (Chinese title when available in 中文 mode). */
export function filmTitle(film) {
  if (!film) return ''
  return locale.value === 'zh' && film.title_zh ? film.title_zh : film.title
}

/** The other-language title, shown smaller under the main one. */
export function altTitle(film) {
  if (!film || !film.title_zh) return ''
  return locale.value === 'zh' ? film.title : film.title_zh
}

/** Genre and language names are stored in English; translate them when a translation exists. */
export function genreName(name) {
  return messages[locale.value].genre?.[name] || name
}

export function languageName(name) {
  return messages[locale.value].lang?.[name] || name
}

export const intlLocale = computed(() => (locale.value === 'zh' ? 'zh-CN' : 'en-US'))

export function useI18n() {
  return { t, locale, setLocale, filmTitle, altTitle, intlLocale, genreName, languageName }
}
