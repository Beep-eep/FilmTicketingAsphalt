import { api } from '@/api'

const STORAGE_KEY = 'asphalt.auth'

function load() {
  try {
    // Remove keys written by the old version of the site (they used a different format).
    for (const old of ['access_token', 'refresh_token', 'username', 'user_id']) localStorage.removeItem(old)
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    if (saved?.access && saved?.refresh && saved?.user) return saved
  } catch {
    /* corrupted or blocked storage: start signed out */
  }
  return { access: null, refresh: null, user: null }
}

function save(state) {
  try {
    if (state.access) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ access: state.access, refresh: state.refresh, user: state.user }))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    /* ignore */
  }
}

let refreshing = null // one refresh at a time, shared by every request that needs it

export const auth = {
  namespaced: true,
  state: load,
  getters: {
    loggedIn: (state) => Boolean(state.access && state.user),
    username: (state) => state.user?.username || '',
  },
  mutations: {
    signedIn(state, { access, refresh, user }) {
      state.access = access
      state.refresh = refresh
      state.user = user
      save(state)
    },
    tokens(state, { access, refresh }) {
      state.access = access
      if (refresh) state.refresh = refresh
      save(state)
    },
    signedOut(state) {
      state.access = null
      state.refresh = null
      state.user = null
      save(state)
    },
  },
  actions: {
    async login({ commit }, { login, password }) {
      const result = await api.login(login, password)
      commit('signedIn', result)
      return result.user
    },
    adopt({ commit }, result) {
      // After registering (without email confirmation) or confirming an email.
      commit('signedIn', result)
    },
    refresh({ state, commit }) {
      if (!refreshing) {
        refreshing = api
          .refresh(state.refresh)
          .then((tokens) => commit('tokens', tokens))
          .finally(() => {
            refreshing = null
          })
      }
      return refreshing
    },
    async logout({ state, commit }, { remote = true } = {}) {
      const refresh = state.refresh
      commit('signedOut')
      if (remote && refresh) {
        try {
          await api.logout(refresh)
        } catch {
          /* already signed out locally */
        }
      }
    },
  },
}
