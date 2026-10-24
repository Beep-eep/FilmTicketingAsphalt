import { computed, onBeforeUnmount, ref, watch } from 'vue'

/** Seconds left until `target` (a ref or getter returning an ISO date), ticking every second. */
export function useCountdown(target, onExpire) {
  const now = ref(Date.now())
  const timer = setInterval(() => {
    now.value = Date.now()
  }, 1000)
  onBeforeUnmount(() => clearInterval(timer))

  const seconds = computed(() => {
    const value = typeof target === 'function' ? target() : target.value
    if (!value) return 0
    return Math.max(0, Math.round((new Date(value).getTime() - now.value) / 1000))
  })
  const label = computed(() => {
    const s = seconds.value
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  })
  if (onExpire) {
    watch(seconds, (s, previous) => {
      if (s === 0 && previous > 0) onExpire()
    })
  }
  return { seconds, label }
}
