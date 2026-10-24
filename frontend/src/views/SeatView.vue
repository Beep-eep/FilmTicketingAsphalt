<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { api } from '@/api'
import { errorCode, errorMessage } from '@/api/client'
import { useI18n } from '@/i18n'
import { config } from '@/composables/useConfig'
import { extraFormat, formatDate, formatMoney, formatTime } from '@/composables/format'
import { toast } from '@/composables/useToast'
import SeatMap from '@/components/SeatMap.vue'

const props = defineProps({ id: { type: String, required: true } })
const { t, filmTitle, locale, languageName } = useI18n()
const store = useStore()
const route = useRoute()
const router = useRouter()

const show = ref(null)
const error = ref('')
const selected = ref([])
const busy = ref(false)
const loggedIn = computed(() => store.getters['auth/loggedIn'])

async function load({ quiet = false } = {}) {
  try {
    const data = await api.showtime(props.id)
    const first = !show.value
    show.value = data
    if (first) {
      selected.value = data.seats.filter((s) => s.status === 'held').map((s) => s.id)
      if (data.my_pending_order) toast(t('seats.alreadyHeld'))
      document.title = `${filmTitle(data.film)} | Asphalt Cinema`
    } else {
      // Someone else may have taken a seat you were looking at.
      const lost = data.seats.filter((s) => s.status === 'taken' && selected.value.includes(s.id))
      if (lost.length) {
        selected.value = selected.value.filter((id) => !lost.some((s) => s.id === id))
        toast(`${lost.map((s) => s.label).join(', ')}: ${t('seats.seatState.taken')}`, 'error')
      }
    }
  } catch (err) {
    if (!quiet) error.value = errorMessage(err)
  }
}

let poll = null
onMounted(() => {
  load()
  poll = setInterval(() => document.visibilityState === 'visible' && !busy.value && load({ quiet: true }), 20000)
})
onBeforeUnmount(() => clearInterval(poll))

const chosen = computed(() => {
  if (!show.value) return []
  const set = new Set(selected.value)
  return show.value.seats.filter((s) => set.has(s.id)).sort((a, b) => a.number - b.number)
})
const total = computed(() => chosen.value.reduce((sum, s) => sum + Number(s.price), 0))

function onLimit(message) {
  toast(message || t('seats.max', { n: config.max_seats_per_order }), 'error')
}

async function continueToPayment() {
  if (!loggedIn.value) {
    router.push({ name: 'login', query: { next: route.fullPath } })
    return
  }
  busy.value = true
  try {
    const order = await api.createOrder(Number(props.id), selected.value)
    const { checkout_url: url } = await api.checkout(order.code, locale.value)
    toast(t('seats.redirecting'))
    const target = new URL(url, window.location.origin)
    if (target.origin === window.location.origin) router.push(target.pathname + target.search)
    else window.location.assign(url)
  } catch (err) {
    toast(errorMessage(err), 'error')
    if (errorCode(err) === 'seats_taken') await load({ quiet: true })
    busy.value = false
  }
}
</script>

<template>
  <div class="page seat-page">
    <p v-if="error" class="notice notice-danger">{{ error }}</p>

    <template v-else-if="show">
      <header class="head">
        <RouterLink :to="{ name: 'film', params: { id: show.film.id } }" class="back">{{ filmTitle(show.film) }}</RouterLink>
        <h1>{{ t('seats.pick') }}</h1>
        <p class="when">
          <strong>{{ formatDate(show.begin_time) }}, {{ formatTime(show.begin_time) }}</strong>
          <span>{{ show.room.name }}</span>
          <span v-if="extraFormat(show.format, show.room.name)">{{ show.format }}</span>
          <span v-if="show.subtitles">{{ t('film.subtitles', { lang: languageName(show.subtitles) }) }}</span>
        </p>
      </header>

      <p v-if="!show.booking_open" class="notice notice-danger">{{ t('seats.closed') }}</p>

      <div class="layout">
        <SeatMap
          v-model:selected="selected"
          :room="show.room"
          :seats="show.seats"
          :max-seats="config.max_seats_per_order"
          :disabled="!show.booking_open || busy"
          @limit="onLimit"
        />

        <aside class="stub" aria-labelledby="summary-title">
          <div class="stub-top">
            <h2 id="summary-title" class="stub-film">{{ filmTitle(show.film) }}</h2>
            <p class="muted">{{ formatTime(show.begin_time) }}, {{ show.room.name }}</p>
          </div>
          <div class="perforation" aria-hidden="true"></div>
          <div class="stub-body">
            <p class="count">{{ t('seats.selectedCount', { n: chosen.length }) }}</p>
            <TransitionGroup tag="ul" name="line" class="lines">
              <li v-for="s in chosen" :key="s.id" class="line">
                <span class="seat-tag">{{ s.label }}</span>
                <span class="kind">{{ s.premium ? t('seats.premium') : t('seats.standard') }}</span>
                <span class="amount">{{ formatMoney(s.price) }}</span>
              </li>
            </TransitionGroup>
            <div class="total">
              <span>{{ t('seats.total') }}</span>
              <strong>{{ formatMoney(total) }}</strong>
            </div>
            <button
              type="button"
              class="btn btn-primary btn-block"
              :disabled="!chosen.length || busy || !show.booking_open"
              @click="continueToPayment"
            >
              {{ loggedIn ? t('seats.continue') : t('seats.signInToBook') }}
            </button>
            <button v-if="chosen.length" type="button" class="btn-link clear" @click="selected = []">
              {{ t('seats.clear') }}
            </button>
            <p class="hold muted">{{ t('seats.holdNote', { m: config.seat_hold_minutes }) }}</p>
          </div>
        </aside>
      </div>

      <div v-if="chosen.length" class="mobile-bar">
        <div>
          <span class="muted">{{ t('seats.selectedCount', { n: chosen.length }) }}</span>
          <strong>{{ formatMoney(total) }}</strong>
        </div>
        <button type="button" class="btn btn-primary" :disabled="busy || !show.booking_open" @click="continueToPayment">
          {{ loggedIn ? t('seats.continue') : t('seats.signInToBook') }}
        </button>
      </div>
    </template>

    <div v-else class="skeleton" style="height: 480px; margin-top: 32px"></div>
  </div>
</template>

<style scoped>
.seat-page {
  padding-top: 24px;
}

.head {
  display: grid;
  gap: 6px;
  margin-bottom: 20px;
}

.back {
  color: var(--asphalt-300);
  font-weight: 600;
  text-decoration: none;
  justify-self: start;
}

.back::before {
  content: '‹ ';
}

.back:hover {
  color: var(--chalk);
}

.head h1 {
  font-size: var(--step-5);
}

.when {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  color: var(--asphalt-300);
}

.when strong {
  color: var(--chalk);
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 28px;
  align-items: start;
  margin-top: 16px;
}

/* --- the ticket stub summary ------------------------------------------------- */
.stub {
  position: sticky;
  top: 84px;
  border-radius: var(--radius-m);
  background: var(--marquee);
  color: var(--ink);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45);
}

.stub-top {
  padding: 18px 20px 14px;
}

.stub-top .muted {
  color: #55585f;
}

.stub-film {
  font-size: var(--step-3);
  text-transform: uppercase;
}

.perforation {
  position: relative;
  height: 0;
  margin: 0 14px;
  border-top: 2px dashed #b9bbb3;
}

.perforation::before,
.perforation::after {
  content: '';
  position: absolute;
  top: -12px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--asphalt-950);
}

.perforation::before {
  left: -26px;
}

.perforation::after {
  right: -26px;
}

.stub-body {
  display: grid;
  gap: 12px;
  padding: 16px 20px 20px;
}

.count {
  font-weight: 700;
}

.lines {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.line {
  display: grid;
  grid-template-columns: 54px 1fr auto;
  align-items: center;
  gap: 8px;
}

.seat-tag {
  display: grid;
  place-items: center;
  height: 30px;
  border-radius: var(--radius-s);
  background: var(--ink);
  color: var(--marquee);
  font-family: var(--font-display);
  font-size: var(--step-1);
  font-weight: 800;
}

.kind {
  color: #55585f;
  font-size: var(--step--1);
}

.amount {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.total {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding-top: 10px;
  border-top: 1px solid #d0d2ca;
}

.total strong {
  font-family: var(--font-display);
  font-size: var(--step-4);
  line-height: 1;
}

.stub .btn-primary {
  background: var(--ink);
  color: var(--marquee);
}

.stub .btn-primary:hover:not(:disabled) {
  background: #000;
}

.clear {
  justify-self: center;
  color: #55585f;
}

.hold {
  color: #55585f !important;
  font-size: var(--step--1);
  text-align: center;
}

.line-enter-active,
.line-leave-active {
  transition: opacity 0.2s, transform 0.2s var(--ease-out);
}

.line-enter-from,
.line-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}

.mobile-bar {
  display: none;
}

@media (max-width: 900px) {
  .mobile-bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 30;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px var(--gutter) calc(12px + env(safe-area-inset-bottom));
    border-top: 1px solid var(--asphalt-700);
    background: rgba(23, 24, 27, 0.96);
  }

  .mobile-bar div {
    display: grid;
  }

  .mobile-bar strong {
    font-family: var(--font-display);
    font-size: var(--step-3);
    line-height: 1;
  }

  .layout {
    grid-template-columns: 1fr;
  }

  .stub {
    position: static;
  }
}
</style>
