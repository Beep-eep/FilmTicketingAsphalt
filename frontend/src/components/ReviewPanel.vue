<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api'
import { errorMessage } from '@/api/client'
import { useI18n } from '@/i18n'
import { formatShortDate } from '@/composables/format'
import { toast } from '@/composables/useToast'

const props = defineProps({ filmId: { type: Number, required: true }, loggedIn: Boolean })
const emit = defineEmits(['changed'])
const { t } = useI18n()
const route = useRoute()

const reviews = ref([])
const mine = ref(null)
const score = ref(0)
const hover = ref(0)
const comment = ref('')
const saving = ref(false)

async function load() {
  try {
    const data = await api.reviews(props.filmId)
    reviews.value = data.results
    mine.value = data.mine
    if (data.mine) {
      score.value = Number(data.mine.score)
      comment.value = data.mine.comment
    }
  } catch {
    /* reviews are optional */
  }
}
onMounted(load)

async function save() {
  if (!score.value) {
    toast(t('reviews.pickScore'), 'error')
    return
  }
  saving.value = true
  try {
    await api.saveReview(props.filmId, { score: score.value, comment: comment.value })
    toast(t('reviews.saved'), 'success')
    await load()
    emit('changed')
  } catch (err) {
    toast(errorMessage(err), 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="reviews" aria-labelledby="reviews-title">
    <h2 id="reviews-title">{{ t('reviews.title') }}</h2>

    <form v-if="loggedIn" class="form" @submit.prevent="save">
      <fieldset class="scale">
        <legend>{{ t('reviews.yourRating') }}</legend>
        <div class="dots" @mouseleave="hover = 0">
          <label v-for="n in 10" :key="n" class="dot" :class="{ on: n <= (hover || score) }" @mouseenter="hover = n">
            <input v-model="score" type="radio" name="score" :value="n" class="visually-hidden" />
            <span aria-hidden="true">{{ n }}</span>
            <span class="visually-hidden">{{ t('reviews.scoreLabel', { n }) }}</span>
          </label>
        </div>
      </fieldset>
      <div class="field">
        <label for="review-comment">{{ t('reviews.commentLabel') }}</label>
        <textarea
          id="review-comment"
          v-model="comment"
          class="input"
          rows="3"
          maxlength="500"
          :placeholder="t('reviews.commentPlaceholder')"
        ></textarea>
      </div>
      <div>
        <button type="submit" class="btn btn-primary" :disabled="saving">
          {{ mine ? t('reviews.update') : t('reviews.save') }}
        </button>
      </div>
    </form>
    <p v-else>
      <RouterLink :to="{ name: 'login', query: { next: route.fullPath } }" class="btn btn-ghost">
        {{ t('reviews.signInToRate') }}
      </RouterLink>
    </p>

    <p v-if="!reviews.length" class="muted">{{ t('reviews.empty') }}</p>
    <ul v-else class="list">
      <li v-for="r in reviews" :key="r.id" class="review">
        <div class="review-head">
          <span class="review-score">{{ Number(r.score) }}</span>
          <strong>{{ r.username }}</strong>
          <span class="muted">{{ formatShortDate(r.updated_at) }}</span>
        </div>
        <p v-if="r.comment" class="review-text">{{ r.comment }}</p>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.reviews {
  display: grid;
  gap: 18px;
  margin-top: 56px;
}

.reviews h2 {
  font-size: var(--step-4);
}

.form {
  display: grid;
  gap: 16px;
  max-width: 620px;
  padding: 20px;
  border: 1px solid var(--asphalt-700);
  border-radius: var(--radius-m);
  background: var(--asphalt-900);
}

.scale {
  margin: 0;
  padding: 0;
  border: 0;
}

.scale legend {
  margin-bottom: 8px;
  font-size: var(--step--1);
  font-weight: 600;
  color: var(--asphalt-300);
}

.dots {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.dot {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--asphalt-600);
  border-radius: 50%;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.1s, color 0.1s;
}

.dot.on {
  border-color: var(--sodium);
  background: var(--sodium);
  color: var(--ink);
}

.dot:has(input:focus-visible) {
  box-shadow: var(--focus);
}

.list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
  max-width: 760px;
}

.review {
  padding: 14px 0;
  border-top: 1px solid var(--asphalt-800);
}

.review-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.review-score {
  display: grid;
  place-items: center;
  min-width: 34px;
  height: 34px;
  border-radius: var(--radius-s);
  background: var(--asphalt-700);
  font-family: var(--font-display);
  font-size: var(--step-1);
  font-weight: 800;
}

.review-text {
  margin-top: 8px;
  max-width: 65ch;
}
</style>
