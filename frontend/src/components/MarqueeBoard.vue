<script setup>
import { computed } from 'vue'

// A backlit cinema letterboard: each character is its own changeable letter tile.
const props = defineProps({
  text: { type: String, required: true },
  small: Boolean,
})

const words = computed(() =>
  props.text
    .toUpperCase()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => Array.from(word)),
)
const longest = computed(() => Math.max(4, ...words.value.map((w) => w.length)))
</script>

<template>
  <div class="board" :class="{ small }" :style="{ '--longest': longest }">
    <span class="visually-hidden">{{ text }}</span>
    <div :key="text" class="letters" aria-hidden="true">
      <span v-for="(word, w) in words" :key="w" class="word">
        <span
          v-for="(ch, i) in word"
          :key="i"
          class="tile"
          :style="{ '--i': words.slice(0, w).reduce((n, x) => n + x.length, 0) + i }"
          >{{ ch }}</span
        >
      </span>
    </div>
  </div>
</template>

<style scoped>
.board {
  /* Big letters, but never so big that the longest word overflows a phone screen */
  --tile-h: min(clamp(40px, 7.4vw, 84px), calc((100vw - 2 * var(--gutter) - 64px) / var(--longest) / 0.8));
  position: relative;
  padding: clamp(14px, 2.4vw, 26px);
  border-radius: 6px;
  background:
    repeating-linear-gradient(180deg, transparent 0 calc(var(--tile-h) + 6px), rgba(0, 0, 0, 0.07) calc(var(--tile-h) + 6px) calc(var(--tile-h) + 8px)),
    linear-gradient(180deg, #fbfbf8, var(--marquee) 40%, var(--marquee-shade));
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.4),
    0 0 60px rgba(255, 238, 200, 0.18),
    inset 0 0 30px rgba(255, 255, 255, 0.6);
}

.board.small {
  --tile-h: min(clamp(30px, 4vw, 44px), calc((100vw - 2 * var(--gutter) - 48px) / var(--longest) / 0.8));
  padding: 12px;
}

.letters {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px calc(var(--tile-h) * 0.32);
}

.word {
  display: inline-flex;
  gap: 3px;
}

.tile {
  display: inline-grid;
  place-items: center;
  min-width: calc(var(--tile-h) * 0.56);
  height: var(--tile-h);
  padding: 0 2px;
  color: var(--ink);
  font-family: var(--font-display);
  font-weight: 800;
  font-size: calc(var(--tile-h) * 0.86);
  line-height: 1;
  /* the slot rail behind each changeable letter */
  background: linear-gradient(180deg, transparent 47%, rgba(0, 0, 0, 0.06) 47% 53%, transparent 53%);
  animation: hang 0.5s var(--ease-out) both;
  animation-delay: calc(var(--i) * 35ms);
  transform-origin: 50% 0;
}

@keyframes hang {
  from {
    opacity: 0;
    transform: rotateX(80deg) translateY(-8px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
