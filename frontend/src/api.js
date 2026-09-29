async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(', ') : data.detail
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return data
}

export const api = {
  status: () => request('/status'),
  businesses: () => request('/businesses'),
  createBusiness: (body) => request('/businesses', { method: 'POST', body }),
  dashboard: (id) => request(`/businesses/${id}/dashboard`),
  confirmFacts: (id, facts, confirmed_by) =>
    request(`/businesses/${id}/facts`, { method: 'PUT', body: { facts, confirmed_by } }),
  deleteFact: (id, key) => request(`/businesses/${id}/facts/${encodeURIComponent(key)}`, { method: 'DELETE' }),
  journeys: (id) => request(`/businesses/${id}/journeys`),
  regenerateJourneys: (id) => request(`/businesses/${id}/journeys/regenerate`, { method: 'POST' }),
  scan: (id) => request(`/businesses/${id}/scans`, { method: 'POST' }),
  answers: (id) => request(`/businesses/${id}/answers`),
  draftFix: (iid) => request(`/incidents/${iid}/draft-fix`, { method: 'POST' }),
  approve: (iid, approver, note = '') => request(`/incidents/${iid}/approve`, { method: 'POST', body: { approver, note } }),
  dismiss: (iid, approver, note = '') => request(`/incidents/${iid}/dismiss`, { method: 'POST', body: { approver, note } }),
  audit: (id) => request(`/businesses/${id}/audit`),
}

export const ASSISTANT_NAMES = { chatgpt: 'ChatGPT', claude: 'Claude', gemini: 'Gemini', perplexity: 'Perplexity' }
