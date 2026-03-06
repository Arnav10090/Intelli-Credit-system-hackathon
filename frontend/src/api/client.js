const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function req(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body) opts.body = JSON.stringify(body)
  const r = await fetch(`${BASE}/api/v1${path}`, opts)
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

export const api = {
  // Cases
  listCases:    ()          => req('GET',  '/cases'),
  createCase:   (data)      => req('POST', '/cases', data),
  loadDemo:     (id)        => req('POST', `/cases/${id}/load-demo`),
  analyze:      (id)        => req('POST', `/cases/${id}/analyze`),
  listFlags:    (id)        => req('GET',  `/cases/${id}/flags`),
  listDocs:     (id)        => req('GET',  `/cases/${id}/documents`),

  // Scoring
  runScore:     (id)        => req('POST', `/cases/${id}/score`),
  getScore:     (id)        => req('GET',  `/cases/${id}/score`),
  getAudit:     (id)        => req('GET',  `/cases/${id}/audit`),

  // Research
  loadResearch: (id)        => req('POST', `/cases/${id}/research/load-cache`),
  getResearch:  (id)        => req('GET',  `/cases/${id}/research`),
  getResearchSummary: (id)  => req('GET',  `/cases/${id}/research/summary`),
  getLitigation:(id)        => req('GET',  `/cases/${id}/research/litigation`),

  // CAM
  generateCam:  (id, analyst) => req('POST', `/cases/${id}/cam?analyst_id=${analyst || 'Analyst'}`),
  getCamStatus: (id)          => req('GET',  `/cases/${id}/cam/status`),
  camDownloadUrl: (id)        => `${BASE}/api/v1/cases/${id}/cam/download`,
}