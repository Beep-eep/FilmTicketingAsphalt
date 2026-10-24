<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { api } from '@/api'
import { errorMessage } from '@/api/client'
import { useI18n } from '@/i18n'
import { extraFormat, formatDayKey, formatMoney, formatRuntime, formatTime, localDateKey, upcomingDays } from '@/composables/format'
import BaseModal from '@/components/BaseModal.vue'
import DateStrip from '@/components/DateStrip.vue'
import PosterArt from '@/components/PosterArt.vue'
import ReviewPanel from '@/components/ReviewPanel.vue'

const props = defineProps({ id: { type: String, required: true } })
const { t, filmTitle, altTitle, intlLocale, genreName, languageName } = useI18n()
const store = useStore()

const film = ref(null)
const showtimes = ref([])
const loading = ref(true)
const error = ref('')
const day = ref('')
const trailerOpen = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [f, s] = await Promise.all([api.film(props.id), api.showtimes(props.id)])
    film.value = f
    showtimes.value = s
    const first = s.find((x) => x.booking_open)
    day.value = first ? localDateKey(first.begin_time) : upcomingDays(1)[0].key
    document.title = `${filmTitle(f)} | Asphalt Cinema`
  } catch (err) {
    error.value = err.response?.status === 404 ? t('film.notFound') : errorMessage(err)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => props.id, load)

const daysWithShows = computed(() => [...new Set(showtimes.value.map((s) => localDateKey(s.begin_time)))])

// Group the chosen day's showtimes by room so IMAX, Dolby etc. read as rows.
const rooms = computed(() => {
  const groups = new Map()
  for (const s of showtimes.value) {
    if (localDateKey(s.begin_time) !== day.value) continue
    const key = s.room.name
    if (!groups.has(key)) groups.set(key, { room: s.room, format: s.format, shows: [] })
    groups.get(key).shows.push(s)
  }
  return [...groups.values()]
})

function seatsTone(s) {
  if (!s.seats_available) return 'out'
  return s.seats_available / s.seats_total < 0.2 ? 'low' : 'ok'
}

const releaseDate = computed(() =>
  film.value
    ? new Intl.DateTimeFormat(intlLocale.value, { dateStyle: 'long', timeZone: 'UTC' }).format(
        new Date(`${film.value.release_date}T12:00:00Z`),
      )
    : '',
)
const loggedIn = computed(() => store.getters['auth/loggedIn'])
</script>

<template>
  <div v-if="loading" class="page film-loading">
    <div class="skeleton" style="height: 420px"></div>
  </div>

  <div v-else-if="error" class="page state">
    <p class="notice notice-danger">{{ error }}</p>
    <RouterLink to="/" class="btn btn-ghost">{{ t('film.back') }}</RouterLink>
  </div>

  <article v-else-if="film" class="film" :style="{ '--accent': film.accent_color || '#363a41' }">
    <div class="backdrop" aria-hidden="true">
      <img v-if="film.backdrop_url" :src="film.backdrop_url" alt="" />
    </div>

    <div class="page head">
      <RouterLink to="/" class="back">{{ t('film.back') }}</RouterLink>
      <div class="head-grid">
        <PosterArt class="poster" :film="film" eager />
        <div class="info">
          <h1 class="title">{{ filmTitle(film) }}</h1>
          <p v-if="altTitle(film)" class="alt-title">{{ altTitle(film) }}</p>

          <div class="rating">
            <template v-if="film.avg_rating">
              <span class="score">{{ film.avg_rating.toFixed(1) }}</span>
              <span class="muted">/ 10 {{ t('film.ratingOf', { n: film.rating_count }) }}</span>
            </template>
            <span v-else class="muted">{{ t('film.noRatings') }}</span>
          </div>

          <p class="overview">{{ film.overview }}</p>

          <dl class="facts">
            <div><dt>{{ t('film.directedBy') }}</dt><dd>{{ film.director }}</dd></div>
            <div v-if="film.cast.length"><dt>{{ t('film.cast') }}</dt><dd>{{ film.cast.join(', ') }}</dd></div>
            <div><dt>{{ t('film.released') }}</dt><dd>{{ releaseDate }}</dd></div>
            <div v-if="film.runtime_minutes"><dt>{{ t('film.runtime') }}</dt><dd>{{ formatRuntime(film.runtime_minutes) }}</dd></div>
            <div v-if="film.language"><dt>{{ t('film.language') }}</dt><dd>{{ languageName(film.language) }}</dd></div>
            <div v-if="film.genres.length"><dt>{{ t('film.genres') }}</dt><dd>{{ film.genres.map(genreName).join(', ') }}</dd></div>
          </dl>

          <button v-if="film.trailer_youtube_key" type="button" class="btn btn-ghost" @click="trailerOpen = true">
            <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M6 4.5v11l9-5.5z" fill="currentColor" /></svg>
            {{ t('film.watchTrailer') }}
          </button>
        </div>
      </div>
    </div>

    <section id="showtimes" class="page showtimes" aria-labelledby="showtimes-title">
      <h2 id="showtimes-title">{{ t('film.showtimes') }}</h2>
      <p v-if="!showtimes.length" class="muted">{{ t('film.noShowtimes') }}</p>
      <template v-else>
        <DateStrip v-model="day" :available="daysWithShows" />
        <p class="day-title">{{ formatDayKey(day) }}</p>
        <p v-if="!rooms.length" class="muted">{{ t('film.noShowtimesDay') }}</p>
        <div v-for="group in rooms" :key="group.room.id" class="room">
          <div class="room-name">
            <strong>{{ group.room.name }}</strong>
            <span v-if="extraFormat(group.format, group.room.name)" class="muted">{{ group.format }}</span>
            <span v-if="group.shows[0].subtitles" class="muted">
              {{ t('film.subtitles', { lang: languageName(group.shows[0].subtitles) }) }}
            </span>
          </div>
          <div class="times">
            <component
              :is="s.booking_open && s.seats_available ? 'RouterLink' : 'span'"
              v-for="s in group.shows"
              :key="s.id"
              :to="{ name: 'seats', params: { id: s.id } }"
              class="showtime"
              :class="[seatsTone(s), { closed: !s.booking_open }]"
            >
              <span class="clock">{{ formatTime(s.begin_time) }}</span>
              <span class="price">{{ formatMoney(s.price) }}</span>
              <span class="left">
                {{ !s.booking_open ? t('film.started') : s.seats_available ? t('film.seatsLeft', { n: s.seats_available }) : t('film.soldOut') }}
              </span>
              <span class="bar" aria-hidden="true">
                <span :style="{ width: `${100 - (100 * s.seats_available) / s.seats_total}%` }"></span>
              </span>
            </component>
          </div>
        </div>
      </template>
    </section>

    <ReviewPanel :film-id="film.id" :logged-in="loggedIn" class="page" @changed="load" />

    <BaseModal v-if="trailerOpen" wide :title="filmTitle(film)" @close="trailerOpen = false">
      <div class="trailer">
        <iframe
          :src="`https://www.youtube-nocookie.com/embed/${film.trailer_youtube_key}?autoplay=1`"
          :title="t('film.watchTrailer')"
          allow="autoplay; encrypted-media; picture-in-picture"
          allowfullscreen
        ></iframe>
      </div>
    </BaseModal>
  </article>
</template>

<style scoped>
.film {
  position: relative;
}

.backdrop {
  position: absolute;
  inset: 0 0 auto;
  height: 560px;
  z-index: -1;
  background: radial-gradient(70% 90% at 70% 0%, color-mix(in srgb, var(--accent) 75%, transparent), transparent 70%);
}

.backdrop img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.3;
  mask-image: linear-gradient(180deg, #000 20%, transparent);
}

.head {
  padding-top: 24px;
}

.back {
  display: inline-block;
  margin-bottom: 18px;
  color: var(--asphalt-300);
  font-weight: 600;
  text-decoration: none;
}

.back::before {
  content: '‹ ';
}

.back:hover {
  color: var(--chalk);
}

.head-grid {
  display: grid;
  grid-template-columns: minmax(180px, 300px) minmax(0, 1fr);
  gap: clamp(20px, 4vw, 48px);
  align-items: start;
}

.poster {
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.5);
}

.title {
  font-size: clamp(2.6rem, 6vw, var(--step-6));
  text-transform: uppercase;
  letter-spacing: 0.015em;
}

.alt-title {
  margin-top: 6px;
  color: var(--asphalt-300);
  font-size: var(--step-1);
}

.rating {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-top: 16px;
}

.score {
  font-family: var(--font-display);
  font-size: var(--step-4);
  font-weight: 800;
  color: var(--sodium-bright);
  line-height: 1;
}

.overview {
  max-width: 62ch;
  margin-top: 16px;
  font-size: var(--step-1);
  line-height: 1.5;
}

.facts {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px 28px;
  margin: 24px 0;
}

.facts dt {
  color: var(--asphalt-300);
  font-size: var(--step--1);
}

.facts dd {
  margin: 2px 0 0;
  font-weight: 600;
}

/* --- showtimes ------------------------------------------------------------------- */
.showtimes {
  display: grid;
  gap: 14px;
  margin-top: 48px;
  scroll-margin-top: 80px;
}

.showtimes h2 {
  font-size: var(--step-4);
}

.day-title {
  font-weight: 700;
  font-size: var(--step-1);
}

.room {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 16px;
  padding: 16px 0;
  border-top: 1px solid var(--asphalt-800);
}

.room-name {
  display: grid;
  align-content: start;
  gap: 2px;
}

.room-name strong {
  font-size: var(--step-1);
}

.times {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.showtime {
  display: grid;
  grid-template-columns: auto auto;
  gap: 2px 14px;
  min-width: 150px;
  padding: 10px 14px 12px;
  border: 1px solid var(--asphalt-600);
  border-radius: var(--radius-m);
  background: var(--asphalt-900);
  text-decoration: none;
  transition: border-color 0.15s, transform 0.15s var(--ease-out);
}

a.showtime:hover {
  border-color: var(--sodium);
  transform: translateY(-2px);
}

.clock {
  font-family: var(--font-display);
  font-size: var(--step-3);
  font-weight: 800;
  line-height: 1;
}

.price {
  align-self: center;
  justify-self: end;
  font-weight: 700;
}

.left {
  grid-column: 1 / -1;
  color: var(--asphalt-300);
  font-size: var(--step--1);
}

.low .left {
  color: var(--sodium-bright);
}

.bar {
  grid-column: 1 / -1;
  height: 3px;
  margin-top: 4px;
  border-radius: 2px;
  background: var(--asphalt-700);
  overflow: hidden;
}

.bar span {
  display: block;
  height: 100%;
  background: var(--asphalt-300);
}

.low .bar span {
  background: var(--sodium);
}

.out,
.closed {
  opacity: 0.45;
}

.trailer {
  aspect-ratio: 16 / 9;
}

.trailer iframe {
  width: 100%;
  height: 100%;
  border: 0;
  border-radius: var(--radius-m);
}

.state {
  display: grid;
  justify-items: start;
  gap: 14px;
  padding-top: 40px;
}

.film-loading {
  padding-top: 40px;
}

@media (max-width: 760px) {
  .head-grid {
    grid-template-columns: 1fr;
  }

  .poster {
    width: 58%;
    max-width: 240px;
  }

  .room {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .showtime {
    min-width: 136px;
  }
}
</style>
