<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import { errorMessage } from '@/api/client'
import { useI18n } from '@/i18n'
import { formatRuntime, formatShortDate, formatTime, localDateKey, upcomingDays } from '@/composables/format'
import DateStrip from '@/components/DateStrip.vue'
import FilmCard from '@/components/FilmCard.vue'
import MarqueeBoard from '@/components/MarqueeBoard.vue'

const { t, filmTitle, locale, genreName } = useI18n()
const route = useRoute()
const router = useRouter()

const films = ref([])
const soon = ref([])
const loading = ref(true)
const error = ref('')

const q = computed(() => String(route.query.q || '').trim())
const day = computed(() => String(route.query.day || ''))
const genre = computed(() => String(route.query.genre || ''))
const sort = computed(() => String(route.query.sort || 'popular'))

function setQuery(patch) {
  router.replace({ query: { ...route.query, ...patch }, hash: '#programme' })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [now, upcoming] = await Promise.all([
      api.films(q.value ? { search: q.value } : {}),
      q.value ? Promise.resolve([]) : api.films({ status: 'soon' }),
    ])
    films.value = now
    soon.value = upcoming
  } catch (err) {
    error.value = errorMessage(err, t('home.loadError'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(q, load)

// --- filters -------------------------------------------------------------
const genres = computed(() => {
  const counts = new Map()
  for (const f of films.value) for (const g of f.genres) counts.set(g, (counts.get(g) || 0) + 1)
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([g]) => g)
})

const datesWithShows = computed(() => [...new Set(films.value.flatMap((f) => f.show_dates))])

const visible = computed(() => {
  let list = films.value
  if (day.value) list = list.filter((f) => f.show_dates.includes(day.value))
  if (genre.value) list = list.filter((f) => f.genres.includes(genre.value))
  const sorted = [...list]
  const byTitle = (a, b) => filmTitle(a).localeCompare(filmTitle(b), locale.value === 'zh' ? 'zh-CN' : 'en')
  if (sort.value === 'rating') sorted.sort((a, b) => (b.avg_rating ?? -1) - (a.avg_rating ?? -1) || byTitle(a, b))
  else if (sort.value === 'newest') sorted.sort((a, b) => b.release_date.localeCompare(a.release_date))
  else if (sort.value === 'title') sorted.sort(byTitle)
  else sorted.sort((a, b) => b.popularity - a.popularity)
  return sorted
})

// --- the marquee -----------------------------------------------------------
const featured = computed(() => {
  const today = upcomingDays(2).map((d) => d.key)
  const showing = films.value.filter((f) => f.show_dates.some((d) => today.includes(d)))
  return [...(showing.length ? showing : films.value)].sort((a, b) => b.popularity - a.popularity).slice(0, 8)
})
const featureIndex = ref(0)
const feature = computed(() => featured.value[featureIndex.value % Math.max(featured.value.length, 1)])
const featureTimes = ref([])

function step(delta) {
  const n = featured.value.length
  if (n) featureIndex.value = (featureIndex.value + delta + n) % n
}

watch(feature, async (film) => {
  featureTimes.value = []
  if (!film) return
  try {
    const shows = await api.showtimes(film.id)
    if (feature.value?.id === film.id) featureTimes.value = shows.filter((s) => s.booking_open).slice(0, 5)
  } catch {
    /* the marquee still works without times */
  }
})

function isToday(iso) {
  return localDateKey(iso) === upcomingDays(1)[0].key
}
</script>

<template>
  <div class="home">
    <section v-if="feature" class="hero" :style="{ '--accent': feature.accent_color || '#363a41' }">
      <div class="glow" aria-hidden="true">
        <img v-if="feature.backdrop_url" :src="feature.backdrop_url" alt="" />
      </div>
      <div class="page hero-inner">
        <div class="frame">
          <MarqueeBoard :text="filmTitle(feature)" />
        </div>
        <div class="hero-info">
          <div class="hero-meta">
            <p class="hero-credit">
              <span>{{ feature.director }}</span>
              <span>{{ feature.year }}</span>
              <span v-if="feature.runtime_minutes">{{ formatRuntime(feature.runtime_minutes) }}</span>
            </p>
            <p class="hero-overview">{{ feature.overview }}</p>
          </div>
          <div class="hero-times">
            <h2 class="visually-hidden">{{ t('home.tonight') }}</h2>
            <RouterLink
              v-for="s in featureTimes"
              :key="s.id"
              :to="{ name: 'seats', params: { id: s.id } }"
              class="time"
            >
              <strong>{{ formatTime(s.begin_time) }}</strong>
              <span>{{ isToday(s.begin_time) ? t('common.today') : formatShortDate(s.begin_time) }}, {{ s.room.name }}</span>
            </RouterLink>
            <RouterLink :to="{ name: 'film', params: { id: feature.id } }" class="btn btn-primary">
              {{ t('home.seeTimes') }}
            </RouterLink>
          </div>
        </div>
        <div v-if="featured.length > 1" class="hero-nav">
          <button type="button" class="arrow" :aria-label="t('home.prev')" @click="step(-1)">
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M12.5 4 6.5 10l6 6" /></svg>
          </button>
          <span class="count" aria-live="polite">{{ featureIndex + 1 }} / {{ featured.length }}</span>
          <button type="button" class="arrow" :aria-label="t('home.next')" @click="step(1)">
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m7.5 4 6 6-6 6" /></svg>
          </button>
        </div>
      </div>
    </section>
    <section v-else-if="loading" class="hero">
      <div class="page hero-inner"><div class="skeleton" style="height: 220px"></div></div>
    </section>

    <section id="programme" class="page programme" aria-labelledby="programme-title">
      <div class="programme-head">
        <h2 id="programme-title">{{ q ? t('home.searchResults', { n: visible.length, q }) : t('home.whatsOn') }}</h2>
        <label class="sort">
          <span class="muted">{{ t('home.sortBy') }}</span>
          <select :value="sort" class="input" @change="setQuery({ sort: $event.target.value === 'popular' ? undefined : $event.target.value })">
            <option value="popular">{{ t('home.sort.popular') }}</option>
            <option value="rating">{{ t('home.sort.rating') }}</option>
            <option value="newest">{{ t('home.sort.newest') }}</option>
            <option value="title">{{ t('home.sort.title') }}</option>
          </select>
        </label>
      </div>

      <DateStrip
        :model-value="day"
        allow-any
        :available="datesWithShows"
        @update:model-value="setQuery({ day: $event || undefined })"
      />

      <div class="genres" role="group">
        <button type="button" class="chip" :aria-pressed="!genre" @click="setQuery({ genre: undefined })">
          {{ t('home.allGenres') }}
        </button>
        <button
          v-for="g in genres"
          :key="g"
          type="button"
          class="chip"
          :aria-pressed="genre === g"
          @click="setQuery({ genre: genre === g ? undefined : g })"
        >
          {{ genreName(g) }}
        </button>
      </div>

      <div v-if="error" class="notice notice-danger state">
        <p>{{ error }}</p>
        <button type="button" class="btn btn-ghost" @click="load">{{ t('home.retry') }}</button>
      </div>

      <div v-else-if="loading" class="grid">
        <div v-for="n in 10" :key="n">
          <div class="skeleton" style="aspect-ratio: 2/3"></div>
          <div class="skeleton" style="height: 14px; margin-top: 10px; width: 70%"></div>
        </div>
      </div>

      <div v-else-if="!visible.length" class="state">
        <h3>{{ t('home.emptyTitle') }}</h3>
        <p class="muted">{{ t('home.emptyBody') }}</p>
        <button type="button" class="btn btn-ghost" @click="router.replace({ query: {} })">{{ t('home.clearFilters') }}</button>
      </div>

      <TransitionGroup v-else tag="div" name="grid" class="grid">
        <FilmCard v-for="(film, i) in visible" :key="film.id" :film="film" :eager="i < 6" />
      </TransitionGroup>
    </section>

    <section v-if="soon.length" class="page programme" aria-labelledby="soon-title">
      <h2 id="soon-title" class="soon-title">{{ t('home.comingSoon') }}</h2>
      <div class="grid">
        <FilmCard v-for="film in soon" :key="film.id" :film="film" />
      </div>
    </section>
  </div>
</template>

<style scoped>
/* --- hero: the marquee ------------------------------------------------------ */
.hero {
  position: relative;
  overflow: hidden;
  padding: clamp(28px, 5vw, 56px) 0 clamp(28px, 4vw, 44px);
  border-bottom: 1px solid var(--asphalt-800);
}

.glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(60% 70% at 50% 0%, color-mix(in srgb, var(--accent) 70%, transparent), transparent 70%),
    linear-gradient(180deg, transparent 60%, var(--asphalt-950));
  transition: background 0.6s;
}

.glow img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.28;
  filter: blur(2px) saturate(0.9);
  mask-image: linear-gradient(180deg, #000 30%, transparent);
}

.hero-inner {
  position: relative;
  display: grid;
  gap: 24px;
}

.hero-inner > * {
  min-width: 0;
}

/* the frame and bulbs around the letterboard */
.frame {
  position: relative;
  max-width: 980px;
  width: 100%;
  margin: 0 auto;
  padding: 18px;
  border-radius: 10px;
  background:
    radial-gradient(circle, var(--sodium-bright) 0 3.5px, rgba(255, 195, 90, 0.35) 4.5px, transparent 7px) 0 0 / 26px 26px,
    #232428;
  box-shadow:
    0 0 0 1px #3a3c42,
    0 30px 60px rgba(0, 0, 0, 0.55),
    0 0 120px color-mix(in srgb, var(--sodium) 18%, transparent);
}

.hero-info {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 28px;
  max-width: 980px;
  width: 100%;
  margin: 8px auto 0;
  align-items: start;
}

.hero-credit {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  font-weight: 700;
}

.hero-credit span + span {
  color: var(--asphalt-300);
  font-weight: 500;
}

.hero-overview {
  margin-top: 8px;
  max-width: 60ch;
  color: var(--asphalt-300);
}

.hero-times {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: stretch;
}

.time {
  display: grid;
  align-content: center;
  gap: 1px;
  min-height: 52px;
  padding: 6px 12px;
  border: 1px solid var(--asphalt-600);
  border-radius: var(--radius-s);
  background: rgba(23, 24, 27, 0.6);
  text-decoration: none;
  transition: border-color 0.15s, background-color 0.15s;
}

.time strong {
  font-family: var(--font-display);
  font-size: var(--step-2);
  font-weight: 800;
  line-height: 1;
}

.time span {
  color: var(--asphalt-300);
  font-size: 0.75rem;
}

.time:hover {
  border-color: var(--sodium);
  background: var(--asphalt-850);
}

.hero-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
}

.arrow {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: 1px solid var(--asphalt-600);
  border-radius: 50%;
  background: rgba(23, 24, 27, 0.6);
  cursor: pointer;
}

.arrow svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.arrow:hover {
  border-color: var(--chalk);
}

.count {
  min-width: 48px;
  text-align: center;
  color: var(--asphalt-300);
  font-variant-numeric: tabular-nums;
}

/* --- programme ----------------------------------------------------------------- */
.programme {
  display: grid;
  gap: 18px;
  padding-top: 40px;
  scroll-margin-top: 70px;
}

.programme-head {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  justify-content: space-between;
  gap: 12px;
}

.programme-head h2,
.soon-title {
  font-size: var(--step-4);
}

.sort {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--step--1);
}

.sort .input {
  width: auto;
  min-height: 40px;
  padding-right: 2em;
}

.genres {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(156px, 1fr));
  gap: 28px 20px;
}

.grid-move {
  transition: transform 0.35s var(--ease-out);
}

.grid-enter-active {
  transition: opacity 0.25s;
}

.grid-enter-from,
.grid-leave-to {
  opacity: 0;
}

.grid-leave-active {
  position: absolute;
  opacity: 0;
}

.state {
  display: grid;
  justify-items: start;
  gap: 10px;
  padding: 40px 0;
}

.state h3 {
  font-size: var(--step-3);
}

@media (max-width: 760px) {
  .hero-info {
    grid-template-columns: 1fr;
  }

  .frame {
    padding: 12px;
    background-size: 20px 20px;
  }

  .grid {
    grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
    gap: 22px 14px;
  }
}
</style>
