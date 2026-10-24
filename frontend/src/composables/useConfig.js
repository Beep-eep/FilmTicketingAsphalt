import { reactive } from 'vue'
import { api } from '@/api'

/** Site settings from /api/config/, loaded once and shared. */
export const config = reactive({
  loaded: false,
  cinema_name: 'Asphalt Cinema',
  currency: 'usd',
  time_zone: 'America/Los_Angeles',
  payment_provider: 'demo',
  stripe_mode: null,
  require_email_verification: true,
  email_delivery: 'EmailBackend',
  max_seats_per_order: 8,
  seat_hold_minutes: 10,
  refund_cutoff_minutes: 60,
  uses_tmdb: false,
})

let pending = null

export function loadConfig() {
  if (!pending) {
    pending = api
      .config()
      .then((data) => Object.assign(config, data, { loaded: true }))
      .catch(() => {
        pending = null // try again on the next call
      })
  }
  return pending
}
