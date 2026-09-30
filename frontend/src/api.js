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
  plans: () => request('/plans'),
  perception: (id) => request(`/businesses/${id}/perception`),
  insights: (id) => request(`/businesses/${id}/insights`),
  simulate: (id, weeks) => request(`/businesses/${id}/demo/simulate`, { method: 'POST', body: { weeks } }),
  chat: (id, message, history, lang) => request(`/businesses/${id}/chat`, { method: 'POST', body: { message, history, lang } }),
  verifyFacts: (id) => request(`/businesses/${id}/verify-facts`, { method: 'POST' }),
  checkSources: (iid) => request(`/incidents/${iid}/check-sources`, { method: 'POST' }),
  evidence: (iid) => request(`/incidents/${iid}/evidence`),
  nextLabel: (id) => request(`/businesses/${id}/labeling/next`),
  label: (cid, reviewer, human_verdict) => request(`/claims/${cid}/label`, { method: 'POST', body: { reviewer, human_verdict } }),
  manualScan: (id, answers) => request(`/businesses/${id}/manual-scan`, { method: 'POST', body: { answers } }),
  logReferrals: (id, week) => request(`/businesses/${id}/referrals`, { method: 'PUT', body: week }),
  runLab: (id, repeats) => request(`/businesses/${id}/proof-lab`, { method: 'POST', body: { repeats } }),
  lab: (id) => request(`/businesses/${id}/proof-lab`),
  createLead: (body) => request('/leads', { method: 'POST', body }),
  leads: () => request('/leads'),
  updateLead: (id, status, note) => request(`/leads/${id}`, { method: 'PUT', body: { status, note } }),
  checkAnswers: (cid, answers) => request(`/check/${cid}/answers`, { method: 'POST', body: { answers } }),
  quickScan: (body) => request('/quick-scan', { method: 'POST', body }),
  siteAudit: (body) => request('/site-audit', { method: 'POST', body }),
  growth: (id) => request(`/businesses/${id}/growth`),
  exportData: (id) => request(`/businesses/${id}/export`),
  deleteBusiness: (id, confirm_name) => request(`/businesses/${id}`, { method: 'DELETE', body: { confirm_name } }),
  importSales: (id, weeks) => request(`/businesses/${id}/sales`, { method: 'PUT', body: weeks }),
  changePlan: (id, plan) => request(`/businesses/${id}/plan`, { method: 'PUT', body: { plan } }),
  check: (body) => request('/check', { method: 'POST', body }),
  startTrial: (cid) => request(`/check/${cid}/start-trial`, { method: 'POST' }),
}

export const ASSISTANT_NAMES = { chatgpt: 'ChatGPT', claude: 'Claude', gemini: 'Gemini', perplexity: 'Perplexity', copilot: 'Copilot', other: 'Other AI' }
