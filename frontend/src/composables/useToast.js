import { reactive } from 'vue'

export const toasts = reactive([])
let nextId = 1

/** toast('Saved') or toast('Seat taken', 'error'). Messages disappear after a few seconds. */
export function toast(message, kind = 'info', ms = 4500) {
  const id = nextId++
  toasts.push({ id, message, kind })
  setTimeout(() => dismiss(id), ms)
  return id
}

export function dismiss(id) {
  const index = toasts.findIndex((item) => item.id === id)
  if (index !== -1) toasts.splice(index, 1)
}
