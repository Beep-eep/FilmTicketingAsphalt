<script setup>
import PosterArt from '@/components/PosterArt.vue'
import { altTitle, filmTitle } from '@/i18n'
import { formatRuntime } from '@/composables/format'

defineProps({ film: { type: Object, required: true }, eager: Boolean })
</script>

<template>
  <RouterLink :to="{ name: 'film', params: { id: film.id } }" class="card">
    <PosterArt :film="film" :eager="eager" />
    <span class="title">{{ filmTitle(film) }}</span>
    <span v-if="altTitle(film)" class="alt">{{ altTitle(film) }}</span>
    <span class="meta">
      <span>{{ film.year }}</span>
      <span v-if="film.runtime_minutes">{{ formatRuntime(film.runtime_minutes) }}</span>
      <span v-if="film.avg_rating" class="score" :aria-label="`${film.avg_rating} / 10`">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.5l2 4.3 4.6.5-3.4 3.1 1 4.6L8 11.6 3.8 14l1-4.6L1.4 6.3 6 5.8z" /></svg>
        {{ film.avg_rating.toFixed(1) }}
      </span>
    </span>
  </RouterLink>
</template>

<style scoped>
.card {
  display: grid;
  align-content: start;
  gap: 4px;
  color: inherit;
  text-decoration: none;
}

.card :deep(.poster) {
  margin-bottom: 8px;
  transition: filter 0.2s;
}

.card:hover :deep(.poster) {
  filter: brightness(1.12);
}

.card:hover .title {
  text-decoration: underline;
  text-decoration-color: var(--sodium);
  text-underline-offset: 3px;
}

.card:focus-visible {
  box-shadow: none;
}

.card:focus-visible :deep(.poster) {
  box-shadow: var(--focus);
}

.title {
  font-weight: 700;
  font-size: var(--step-0);
  line-height: 1.3;
}

.alt {
  margin-top: -2px;
  color: var(--asphalt-300);
  font-size: var(--step--1);
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  color: var(--asphalt-300);
  font-size: var(--step--1);
}

.score {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: var(--sodium-bright);
  font-weight: 700;
}

.score svg {
  width: 13px;
  height: 13px;
  fill: currentColor;
}
</style>
