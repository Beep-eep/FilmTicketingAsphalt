import { authHttp, http } from './client'

const data = (promise) => promise.then((response) => response.data)

export const api = {
  config: () => data(http.get('config/')),

  films: (params = {}) => data(http.get('films/', { params })),
  film: (id) => data(http.get(`films/${id}/`)),
  showtimes: (filmId) => data(http.get(`films/${filmId}/showtimes/`)),
  reviews: (filmId) => data(http.get(`films/${filmId}/reviews/`)),
  saveReview: (filmId, body) => data(http.post(`films/${filmId}/reviews/`, body)),
  showtime: (id) => data(http.get(`showtimes/${id}/`)),

  orders: () => data(http.get('orders/')),
  order: (code) => data(http.get(`orders/${code}/`)),
  createOrder: (showtime, seats) => data(http.post('orders/', { showtime, seats })),
  checkout: (code, locale) => data(http.post(`orders/${code}/checkout/`, { locale })),
  cancelOrder: (code) => data(http.post(`orders/${code}/cancel/`)),
  refund: (code, ticketIds) => data(http.post(`orders/${code}/refund/`, { ticket_ids: ticketIds })),
  confirmStripe: (sessionId) => data(http.post('payments/stripe/confirm/', { session_id: sessionId })),
  demoPay: (code, outcome) => data(http.post(`payments/demo/${code}/`, { outcome })),

  register: (body) => data(authHttp.post('auth/register/', body)),
  login: (login, password) => data(authHttp.post('auth/token/', { username: login, password })),
  refresh: (refresh) => data(authHttp.post('auth/token/refresh/', { refresh })),
  logout: (refresh) => data(authHttp.post('auth/logout/', { refresh })),
  verifyEmail: (uid, token) => data(authHttp.post('auth/verify-email/', { uid, token })),
  resendVerification: (email) => data(authHttp.post('auth/resend-verification/', { email })),
  requestPasswordReset: (email) => data(authHttp.post('auth/password-reset/', { email })),
  resetPassword: (uid, token, newPassword) =>
    data(authHttp.post('auth/password-reset/confirm/', { uid, token, new_password: newPassword })),
}
