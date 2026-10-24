<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from '@/i18n'
import { formatMoney } from '@/composables/format'

const props = defineProps({
  room: { type: Object, required: true },
  seats: { type: Array, required: true },
  selected: { type: Array, required: true }, // seat ids
  maxSeats: { type: Number, default: 8 },
  disabled: Boolean,
})
const emit = defineEmits(['update:selected', 'limit'])
const { t } = useI18n()

function savedSize() {
  try {
    return Number(localStorage.getItem('asphalt.seatSize')) || 0
  } catch {
    return 0
  }
}
const size = ref(savedSize() || 30)
function zoom(delta) {
  size.value = Math.min(44, Math.max(20, size.value + delta))
  try {
    localStorage.setItem('asphalt.seatSize', String(size.value))
  } catch {
    /* ignore */
  }
}

const rows = computed(() => {
  const byRow = new Map()
  for (const seat of props.seats) {
    if (!byRow.has(seat.row)) byRow.set(seat.row, [])
    byRow.get(seat.row).push(seat)
  }
  return [...byRow.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([row, list]) => ({
      row,
      letter: list[0].label.replace(/\d+$/, ''),
      seats: list.sort((a, b) => a.col - b.col),
    }))
})

const selectedSet = computed(() => new Set(props.selected))
const byId = computed(() => new Map(props.seats.map((s) => [s.id, s])))

function state(seat) {
  if (selectedSet.value.has(seat.id)) return 'selected'
  return seat.status
}

function toggle(seat) {
  if (props.disabled || seat.status === 'taken' || seat.status === 'mine') return
  const next = new Set(props.selected)
  if (next.has(seat.id)) next.delete(seat.id)
  else {
    if (next.size >= props.maxSeats) {
      emit('limit')
      return
    }
    next.add(seat.id)
  }
  emit('update:selected', [...next])
}

function seatLabel(seat) {
  const s = state(seat)
  const kind = seat.premium ? `, ${t('seats.premium')}` : ''
  return `${t('seats.seatName', { label: seat.label })}, ${t(`seats.seatState.${s}`)}${kind}, ${formatMoney(seat.price)}`
}

// --- keyboard: arrow keys move between seats; only one seat is in the tab order ---
const focusId = ref(null)
const tabStop = computed(() => focusId.value ?? props.seats.find((s) => s.status === 'available')?.id ?? props.seats[0]?.id)
const grid = ref(null)

function move(seat, dRow, dCol) {
  const target = props.seats.find((s) => s.row === seat.row + dRow && s.col === seat.col + dCol)
  if (!target) return
  focusId.value = target.id
  nextTick(() => grid.value?.querySelector(`[data-seat="${target.id}"]`)?.focus())
}

function onKey(event, seat) {
  const moves = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0] }
  if (moves[event.key]) {
    event.preventDefault()
    move(seat, ...moves[event.key])
  }
}

// Fit the room to the screen the first time (phones), unless the person chose a size before.
onMounted(() => {
  if (savedSize() || !wrap.value) return
  const width = wrap.value.clientWidth - 36
  const units = props.room.columns * 1.16 + 1.6 + (props.room.aisle_after ? 0.7 : 0)
  size.value = Math.max(18, Math.min(34, Math.floor(width / units)))
  nextTick(() => {
    wrap.value.scrollLeft = (wrap.value.scrollWidth - wrap.value.clientWidth) / 2
  })
})

// --- tooltip ------------------------------------------------------------------------
const tip = ref(null)
const wrap = ref(null)
function showTip(event, seat) {
  const box = event.currentTarget.getBoundingClientRect()
  const host = wrap.value.getBoundingClientRect()
  tip.value = {
    seat,
    x: box.left - host.left + wrap.value.scrollLeft + box.width / 2,
    y: box.top - host.top + wrap.value.scrollTop,
  }
}

// --- best available: the most central block of N free seats, away from the front ---------
const bestCount = ref(2)
function pickBest() {
  const n = bestCount.value
  const rowsCount = props.room.rows
  const ideal = Math.round(rowsCount * 0.62)
  const centre = (props.room.columns + 1) / 2
  const aisle = props.room.aisle_after
  let best = null
  for (const { row, seats } of rows.value) {
    for (let i = 0; i + n <= seats.length; i++) {
      const block = seats.slice(i, i + n)
      const free = block.every((s, k) => s.status === 'available' && (k === 0 || s.col === block[k - 1].col + 1))
      if (!free) continue
      const crossesAisle = aisle && block[0].col <= aisle && block[n - 1].col > aisle
      if (crossesAisle) continue
      const mid = (block[0].col + block[n - 1].col) / 2
      const score = Math.abs(row - ideal) * 2.2 + Math.abs(mid - centre) + (row < 3 ? 6 : 0)
      if (!best || score < best.score) best = { score, ids: block.map((s) => s.id) }
    }
  }
  if (!best) {
    emit('limit', t('seats.noBlock', { n }))
    return
  }
  emit('update:selected', best.ids)
}

const premiumRows = computed(() => new Set(props.seats.filter((s) => s.premium).map((s) => s.row)))
defineExpose({ byId })
</script>

<template>
  <div class="seatmap" :style="{ '--seat': `${size}px` }">
    <div class="tools">
      <div class="best">
        <span class="best-label">{{ t('seats.bestAvailable') }}</span>
        <button type="button" class="step" :disabled="bestCount <= 1" aria-label="−1" @click="bestCount--">−</button>
        <span class="best-n" aria-live="polite">{{ bestCount }}</span>
        <button type="button" class="step" :disabled="bestCount >= maxSeats" aria-label="+1" @click="bestCount++">+</button>
        <button type="button" class="btn btn-ghost pick" :disabled="disabled" @click="pickBest">
          {{ t('seats.bestFor', { n: bestCount }) }}
        </button>
      </div>
      <div class="zoom">
        <button type="button" class="step" :aria-label="t('seats.zoomOut')" @click="zoom(-4)">−</button>
        <button type="button" class="step" :aria-label="t('seats.zoomIn')" @click="zoom(4)">+</button>
      </div>
    </div>

    <div ref="wrap" class="scroller" @mouseleave="tip = null">
      <div class="theatre">
        <div class="screen" aria-hidden="true">
          <svg viewBox="0 0 400 40" preserveAspectRatio="none">
            <path d="M8 34 Q200 -6 392 34" />
          </svg>
          <span>{{ t('seats.screen') }}</span>
        </div>

        <div ref="grid" class="rows" role="grid" :aria-label="t('seats.pick')">
          <div
            v-for="r in rows"
            :key="r.row"
            class="row"
            :class="{ premium: premiumRows.has(r.row) }"
            role="row"
          >
            <span class="letter" aria-hidden="true">{{ r.letter }}</span>
            <template v-for="seat in r.seats" :key="seat.id">
              <button
                type="button"
                class="seat"
                :class="[state(seat), { premium: seat.premium }]"
                role="gridcell"
                :data-seat="seat.id"
                :tabindex="seat.id === tabStop ? 0 : -1"
                :aria-label="seatLabel(seat)"
                :aria-pressed="state(seat) === 'selected'"
                :aria-disabled="seat.status === 'taken' || seat.status === 'mine' || disabled"
                @click="toggle(seat)"
                @focus="focusId = seat.id; showTip($event, seat)"
                @blur="tip = null"
                @mouseenter="showTip($event, seat)"
                @keydown="onKey($event, seat)"
              ></button>
              <span v-if="room.aisle_after && seat.col === room.aisle_after" class="aisle" aria-hidden="true"></span>
            </template>
            <span class="letter" aria-hidden="true">{{ r.letter }}</span>
          </div>
        </div>
      </div>

      <div v-if="tip" class="tip" :style="{ left: `${tip.x}px`, top: `${tip.y}px` }" aria-hidden="true">
        <strong>{{ tip.seat.label }}</strong>
        <span>{{ formatMoney(tip.seat.price) }}</span>
        <em v-if="tip.seat.premium">{{ t('seats.premium') }}</em>
      </div>
    </div>

    <ul class="legend">
      <li><span class="swatch available"></span>{{ t('seats.legendAvailable') }}</li>
      <li><span class="swatch available premium"></span>{{ t('seats.legendPremium') }}</li>
      <li><span class="swatch selected"></span>{{ t('seats.legendSelected') }}</li>
      <li><span class="swatch taken"></span>{{ t('seats.legendTaken') }}</li>
      <li><span class="swatch mine"></span>{{ t('seats.legendMine') }}</li>
    </ul>
  </div>
</template>

<style scoped>
.seatmap {
  display: grid;
  gap: 14px;
}

.tools {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 10px;
}

.best,
.zoom {
  display: flex;
  align-items: center;
  gap: 6px;
}

.best-label {
  margin-right: 4px;
  color: var(--asphalt-300);
  font-size: var(--step--1);
  font-weight: 600;
}

.best-n {
  min-width: 22px;
  text-align: center;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.step {
  width: 34px;
  height: 34px;
  border: 1px solid var(--asphalt-600);
  border-radius: 50%;
  background: transparent;
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
}

.step:hover:not(:disabled) {
  border-color: var(--chalk);
}

.step:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.pick {
  min-height: 36px;
  padding: 0.3em 0.9em;
  margin-left: 4px;
}

.scroller {
  position: relative;
  overflow-x: auto;
  padding: 8px 4px 16px;
  border-radius: var(--radius-m);
  background:
    radial-gradient(70% 55% at 50% 0%, rgba(243, 244, 239, 0.09), transparent 70%),
    var(--asphalt-900);
  border: 1px solid var(--asphalt-800);
}

.theatre {
  width: max-content;
  min-width: 100%;
  margin: 0 auto;
  padding: 0 12px;
}

.screen {
  display: grid;
  justify-items: center;
  margin: 6px auto 26px;
  width: min(100%, calc(var(--seat) * 14));
  color: var(--asphalt-300);
  font-size: var(--step--1);
  font-weight: 600;
}

.screen svg {
  width: 100%;
  height: 26px;
  overflow: visible;
}

.screen path {
  fill: none;
  stroke: var(--marquee);
  stroke-width: 4;
  stroke-linecap: round;
  filter: drop-shadow(0 6px 10px rgba(243, 244, 239, 0.45));
}

.rows {
  display: grid;
  gap: calc(var(--seat) * 0.22);
  justify-content: center;
}

.row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: calc(var(--seat) * 0.16);
}

.letter {
  width: calc(var(--seat) * 0.8);
  color: var(--asphalt-500);
  font-size: calc(var(--seat) * 0.42 + 4px);
  font-weight: 700;
  text-align: center;
}

.aisle {
  width: calc(var(--seat) * 0.7);
}

/* a seat: chair back on top, cushion edge underneath */
.seat {
  position: relative;
  width: var(--seat);
  height: calc(var(--seat) * 0.9);
  padding: 0;
  border: 0;
  border-radius: 34% 34% 16% 16% / 40% 40% 14% 14%;
  background: var(--asphalt-600);
  cursor: pointer;
  transition: background-color 0.12s, transform 0.12s var(--ease-out);
}

.seat::after {
  content: '';
  position: absolute;
  left: 10%;
  right: 10%;
  bottom: calc(var(--seat) * -0.12);
  height: calc(var(--seat) * 0.16);
  border-radius: 3px;
  background: inherit;
  filter: brightness(0.75);
}

.seat.premium::before {
  content: '';
  position: absolute;
  left: 22%;
  right: 22%;
  top: 14%;
  height: 2px;
  border-radius: 2px;
  background: var(--sodium);
}

.seat.available:hover {
  background: var(--asphalt-500);
  transform: translateY(-2px);
}

.seat.selected {
  background: var(--sodium);
  animation: pop 0.22s var(--ease-out);
}

.seat.selected.premium::before {
  background: var(--ink);
}

.seat.taken {
  background: var(--velvet);
  opacity: 0.55;
  cursor: not-allowed;
}

.seat.mine {
  background: var(--teal);
  cursor: default;
}

.seat.held {
  background: repeating-linear-gradient(135deg, var(--sodium) 0 4px, var(--sodium-deep) 4px 8px);
}

.seat:focus-visible {
  box-shadow: var(--focus);
  z-index: 1;
}

@keyframes pop {
  50% {
    transform: scale(1.18);
  }
}

.tip {
  position: absolute;
  z-index: 5;
  display: flex;
  gap: 8px;
  align-items: baseline;
  padding: 6px 10px;
  border-radius: var(--radius-s);
  background: var(--marquee);
  color: var(--ink);
  font-size: var(--step--1);
  white-space: nowrap;
  transform: translate(-50%, calc(-100% - 8px));
  pointer-events: none;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
}

.tip strong {
  font-family: var(--font-display);
  font-size: var(--step-1);
}

.tip em {
  font-style: normal;
  color: var(--sodium-deep);
  font-weight: 700;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px 20px;
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--asphalt-300);
  font-size: var(--step--1);
}

.legend li {
  display: flex;
  align-items: center;
  gap: 8px;
}

.swatch {
  --seat: 18px;
  position: relative;
  display: inline-block;
  width: 18px;
  height: 16px;
  border-radius: 34% 34% 16% 16% / 40% 40% 14% 14%;
  background: var(--asphalt-600);
}

.swatch.premium::before {
  content: '';
  position: absolute;
  left: 22%;
  right: 22%;
  top: 14%;
  height: 2px;
  background: var(--sodium);
}

.swatch.selected {
  background: var(--sodium);
}

.swatch.taken {
  background: var(--velvet);
  opacity: 0.55;
}

.swatch.mine {
  background: var(--teal);
}
</style>
