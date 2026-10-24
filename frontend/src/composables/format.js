import { intlLocale, t } from '@/i18n'
import { config } from './useConfig'

// Showtimes are always shown in the cinema's own time zone, wherever the visitor is.

function fmt(value, options) {
  if (!value) return ''
  return new Intl.DateTimeFormat(intlLocale.value, { timeZone: config.time_zone, ...options }).format(new Date(value))
}

export const formatTime = (value) => fmt(value, { hour: 'numeric', minute: '2-digit' })
export const formatDate = (value) => fmt(value, { weekday: 'long', month: 'long', day: 'numeric' })
export const formatShortDate = (value) => fmt(value, { weekday: 'short', month: 'short', day: 'numeric' })
export const formatDateTime = (value) =>
  fmt(value, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })

/** "2026-10-24" (cinema-local date) for a timestamp. */
export function localDateKey(value) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: config.time_zone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(value))
  const get = (type) => parts.find((p) => p.type === type).value
  return `${get('year')}-${get('month')}-${get('day')}`
}

/** The next `count` cinema-local dates starting today, as { key, weekday, day, label }. */
export function upcomingDays(count = 7) {
  const days = []
  const todayNoon = new Date(`${localDateKey(new Date())}T12:00:00Z`)
  for (let i = 0; i < count; i++) {
    // Count calendar days in UTC from today's cinema-local date, so DST changes can't skip a day.
    const noon = new Date(todayNoon.getTime() + i * 86400000)
    const key = noon.toISOString().slice(0, 10)
    const weekday = new Intl.DateTimeFormat(intlLocale.value, { weekday: 'short', timeZone: 'UTC' }).format(noon)
    const day = new Intl.DateTimeFormat(intlLocale.value, { day: 'numeric', timeZone: 'UTC' }).format(noon)
    const month = new Intl.DateTimeFormat(intlLocale.value, { month: 'short', timeZone: 'UTC' }).format(noon)
    const label = i === 0 ? t('common.today') : i === 1 ? t('common.tomorrow') : weekday
    days.push({ key, weekday, day, month, label })
  }
  return days
}

export function formatMoney(amount, currency = config.currency) {
  const value = Number(amount)
  try {
    return new Intl.NumberFormat(intlLocale.value, { style: 'currency', currency: currency.toUpperCase() }).format(value)
  } catch {
    return `${value.toFixed(2)} ${currency.toUpperCase()}`
  }
}

export function formatRuntime(minutes) {
  if (!minutes) return ''
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h ? t('common.hoursMinutes', { h, m }) : t('common.minutes', { n: m })
}

/** Long date for a "2026-10-24" key, independent of time zones. */
export function formatDayKey(key) {
  return new Intl.DateTimeFormat(intlLocale.value, {
    weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC',
  }).format(new Date(`${key}T12:00:00Z`))
}

/** "IMAX" or "Dolby" is already in the room's name; only show formats that add information. */
export function extraFormat(format, roomName = '') {
  if (!format || roomName.toLowerCase().includes(format.toLowerCase())) return ''
  return format
}
