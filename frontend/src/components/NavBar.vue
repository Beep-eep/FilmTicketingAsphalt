<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { useI18n } from '@/i18n'
import { toast } from '@/composables/useToast'

const { t, locale, setLocale } = useI18n()
const store = useStore()
const route = useRoute()
const router = useRouter()

const loggedIn = computed(() => store.getters['auth/loggedIn'])
const username = computed(() => store.getters['auth/username'])
const query = ref(String(route.query.q || ''))
const menuOpen = ref(false)

watch(() => route.query.q, (q) => {
  query.value = String(q || '')
})

let typing = null
function onSearch() {
  clearTimeout(typing)
  typing = setTimeout(() => {
    const q = query.value.trim()
    const next = { name: 'home', query: { ...(route.name === 'home' ? route.query : {}), q: q || undefined } }
    if (route.name === 'home') router.replace(next)
    else if (q) router.push(next)
  }, 250)
}

function submitSearch() {
  clearTimeout(typing)
  const q = query.value.trim()
  router.push({ name: 'home', query: { q: q || undefined }, hash: '#programme' })
}

async function signOut() {
  menuOpen.value = false
  await store.dispatch('auth/logout')
  toast(t('auth.signedOut'))
  if (route.meta.requiresAuth) router.push({ name: 'home' })
}
</script>

<template>
  <header class="bar">
    <div class="inner">
      <RouterLink to="/" class="wordmark" aria-label="Asphalt Cinema, home">
        <span class="word">Asphalt</span>
        <span class="lane" aria-hidden="true"></span>
      </RouterLink>

      <form class="search" role="search" @submit.prevent="submitSearch">
        <label class="visually-hidden" for="site-search">{{ t('nav.search') }}</label>
        <svg class="search-icon" viewBox="0 0 20 20" aria-hidden="true">
          <circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" stroke-width="2" />
          <path d="m13 13 4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
        <input
          id="site-search"
          v-model="query"
          type="search"
          class="search-input"
          :placeholder="t('nav.search')"
          autocomplete="off"
          @input="onSearch"
        />
      </form>

      <nav class="links" :aria-label="t('nav.account')">
        <RouterLink to="/" class="nav-link" :class="{ active: route.name === 'home' }">{{ t('nav.films') }}</RouterLink>
        <RouterLink v-if="loggedIn" to="/tickets" class="nav-link">{{ t('nav.tickets') }}</RouterLink>

        <div class="lang" role="group" :aria-label="t('nav.language')">
          <button type="button" :aria-pressed="locale === 'en'" @click="setLocale('en')">EN</button>
          <button type="button" :aria-pressed="locale === 'zh'" lang="zh-CN" @click="setLocale('zh')">中</button>
        </div>

        <RouterLink
          v-if="!loggedIn"
          :to="{ name: 'login', query: route.name && route.name !== 'login' ? { next: route.fullPath } : {} }"
          class="btn btn-primary signin"
        >
          {{ t('nav.signIn') }}
        </RouterLink>
        <div v-else class="user">
          <button type="button" class="user-button" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen">
            <span class="avatar" aria-hidden="true">{{ username.slice(0, 1).toUpperCase() }}</span>
            <span class="user-name">{{ username }}</span>
          </button>
          <div v-if="menuOpen" class="menu" @keydown.esc="menuOpen = false">
            <RouterLink to="/tickets" class="menu-item" @click="menuOpen = false">{{ t('nav.tickets') }}</RouterLink>
            <button type="button" class="menu-item" @click="signOut">{{ t('nav.signOut') }}</button>
          </div>
        </div>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.bar {
  position: sticky;
  top: 0;
  z-index: 40;
  background: rgba(23, 24, 27, 0.9);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--asphalt-800);
}

.inner {
  display: flex;
  align-items: center;
  gap: 20px;
  max-width: var(--content);
  margin: 0 auto;
  padding: 10px var(--gutter);
}

.wordmark {
  display: inline-grid;
  gap: 2px;
  text-decoration: none;
  flex-shrink: 0;
}

.word {
  font-family: var(--font-display);
  font-size: 1.9rem;
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--marquee);
}

/* the dashed centre line of a road */
.lane {
  height: 3px;
  background: repeating-linear-gradient(90deg, var(--sodium) 0 14px, transparent 14px 22px);
  border-radius: 2px;
}

.search {
  position: relative;
  flex: 1;
  max-width: 420px;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  width: 18px;
  height: 18px;
  transform: translateY(-50%);
  color: var(--asphalt-300);
  pointer-events: none;
}

.search-input {
  width: 100%;
  min-height: 42px;
  padding: 0.5em 0.9em 0.5em 2.4em;
  border: 1px solid var(--asphalt-700);
  border-radius: 999px;
  background: var(--asphalt-900);
}

.search-input:focus-visible {
  border-color: var(--sodium);
}

.links {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.nav-link {
  padding: 8px 10px;
  border-radius: var(--radius-s);
  color: var(--asphalt-300);
  font-weight: 600;
  text-decoration: none;
}

.nav-link:hover,
.nav-link.router-link-exact-active {
  color: var(--chalk);
}

.lang {
  display: inline-flex;
  margin: 0 6px;
  border: 1px solid var(--asphalt-700);
  border-radius: 999px;
  overflow: hidden;
}

.lang button {
  min-width: 38px;
  min-height: 34px;
  border: 0;
  background: transparent;
  color: var(--asphalt-300);
  font-size: var(--step--1);
  font-weight: 700;
  cursor: pointer;
}

.lang button[aria-pressed='true'] {
  background: var(--asphalt-700);
  color: var(--chalk);
}

.signin {
  min-height: 40px;
  padding: 0.45em 1em;
}

.user {
  position: relative;
}

.user-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 4px 10px 4px 4px;
  border: 1px solid var(--asphalt-700);
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
}

.avatar {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--sodium);
  color: var(--ink);
  font-weight: 800;
}

.user-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}

.menu {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  min-width: 180px;
  padding: 6px;
  border: 1px solid var(--asphalt-700);
  border-radius: var(--radius-m);
  background: var(--asphalt-850);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45);
}

.menu-item {
  display: block;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-radius: var(--radius-s);
  background: none;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
}

.menu-item:hover {
  background: var(--asphalt-700);
}

@media (max-width: 760px) {
  .inner {
    flex-wrap: wrap;
    gap: 10px 12px;
  }

  .search {
    order: 3;
    flex-basis: 100%;
    max-width: none;
  }

  .nav-link:first-child,
  .user-name {
    display: none;
  }

  .word {
    font-size: 1.6rem;
  }
}
</style>
