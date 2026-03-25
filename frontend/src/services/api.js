const BASE = 'http://localhost:8000'

async function fetchJSON(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function postJSON(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  health: () => fetchJSON('/health'),
  orders: () => fetchJSON('/metrics/orders'),
  revenue: () => fetchJSON('/metrics/revenue'),
  cancellations: () => fetchJSON('/metrics/cancellations'),
  ceoSummary: () => fetchJSON('/metrics/ceo-summary'),
  cities: () => fetchJSON('/metrics/cities'),
  restaurants: () => fetchJSON('/metrics/restaurants'),
  weekComparison: () => fetchJSON('/metrics/week-comparison'),
  calls: () => fetchJSON('/calls/'),
  evaluations: () => fetchJSON('/evaluations/'),
  abResults: () => fetchJSON('/evaluations/ab-results'),
  anomalies: () => fetchJSON('/evaluations/anomalies'),
  escalations: () => fetchJSON('/evaluations/escalations'),
  // Chat API
  chatStart: () => postJSON('/chat/start', {}),
  chatMessage: (session_id, text) => postJSON('/chat/message', { session_id, text }),
  chatEnd: (session_id) => postJSON('/chat/end', { session_id }),
}
