<script setup>
import { computed, ref } from 'vue'
import { filmTitle } from '@/i18n'

const props = defineProps({
  film: { type: Object, required: true },
  eager: Boolean,
})

// Posters that ship with the site (src/assets/posters/<name>.jpg)
const bundled = import.meta.glob('@/assets/posters/*.jpg', { eager: true, import: 'default' })
const bundledByName = Object.fromEntries(
  Object.entries(bundled).map(([path, url]) => [path.split('/').pop().replace('.jpg', ''), url]),
)

const failed = ref(false)
const src = computed(() => {
  if (failed.value) return ''
  return bundledByName[props.film.local_poster] || props.film.poster_url || ''
})

// Generated poster: a quiet typographic design in the film's own colour.
const layout = computed(() => (props.film.id ?? 0) % 3)
const accent = computed(() => props.film.accent_color || '#363a41')
const director = computed(() => props.film.director || '')
</script>

<template>
  <div class="poster" :style="{ '--accent': accent }">
    <img
      v-if="src"
      :src="src"
      :alt="''"
      :loading="eager ? 'eager' : 'lazy'"
      decoding="async"
      @error="failed = true"
    />
    <div v-else class="art" :class="`layout-${layout}`" aria-hidden="true">
      <span class="shape"></span>
      <span class="year">{{ film.year }}</span>
      <span class="title">{{ filmTitle(film) }}</span>
      <span v-if="director" class="credit">{{ director }}</span>
    </div>
  </div>
</template>

<style scoped>
.poster {
  position: relative;
  aspect-ratio: 2 / 3;
  overflow: hidden;
  border-radius: var(--radius-s);
  background: var(--accent);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.06) inset;
}

.poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.art {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  padding: 9% 9% 8%;
  color: var(--marquee);
  background:
    radial-gradient(120% 80% at 20% 0%, rgba(255, 255, 255, 0.16), transparent 60%),
    linear-gradient(180deg, transparent 40%, rgba(0, 0, 0, 0.35)),
    var(--accent);
  container-type: inline-size;
}

.art::after {
  /* print grain */
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.5;
  mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='1.1' numOctaves='2'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23n)' opacity='.55'/%3E%3C/svg%3E");
}

.shape {
  position: absolute;
  border: 2px solid rgba(243, 244, 239, 0.4);
}

.year {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 9cqi;
  letter-spacing: 0.08em;
  opacity: 0.85;
}

.title {
  margin-top: auto;
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 15cqi;
  line-height: 0.9;
  text-transform: uppercase;
  overflow-wrap: anywhere;
}

.title:lang(zh),
.title:lang(zh-CN) {
  text-transform: none;
}

.credit {
  margin-top: 6%;
  font-size: 6cqi;
  font-weight: 600;
  opacity: 0.8;
}

/* three compositions so a wall of generated posters doesn't look stamped out */
.layout-0 .shape {
  width: 62%;
  aspect-ratio: 1;
  right: -14%;
  top: 14%;
  border-radius: 50%;
}

.layout-1 .shape {
  left: 9%;
  right: 9%;
  top: 30%;
  height: 0;
  border-width: 3px 0 0;
}

.layout-1 .title {
  margin-top: 36%;
}

.layout-1 .credit {
  margin-top: auto;
}

.layout-2 .shape {
  width: 40%;
  height: 58%;
  left: 9%;
  top: 18%;
  border-radius: 999px 999px 0 0;
}

.layout-2 .title {
  text-align: right;
}

.layout-2 .credit {
  text-align: right;
}
</style>
