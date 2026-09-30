import { useState } from 'react'
import { api } from '../api.js'
import { money } from './Impact.jsx'

const monday = () => { const d = new Date(); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); return d.toISOString().slice(0, 10) }

// "How did you hear about us?" counts, logged weekly. The simplest real sales number a small business has.
export default function ReferralLog({ bizId, t, lang, rows, onChanged, readOnly = false }) {
  const [f, setF] = useState({ week_start: monday(), total_jobs: '', ai_jobs: '', ai_revenue: '' })
  const [err, setErr] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  async function save() {
    setErr('')
    try {
      await api.logReferrals(bizId, { week_start: f.week_start, total_jobs: Number(f.total_jobs) || 0, ai_jobs: Number(f.ai_jobs) || 0,
        ai_revenue: f.ai_revenue === '' ? null : Number(f.ai_revenue) })
      setF({ ...f, total_jobs: '', ai_jobs: '', ai_revenue: '' }); await onChanged()
    } catch (e) { setErr(e.message) }
  }
  const max = Math.max(1, ...rows.map((r) => r.total_jobs))
  const ai = rows.reduce((a, r) => a + r.ai_jobs, 0), total = rows.reduce((a, r) => a + r.total_jobs, 0)
  if (readOnly && !rows.length) return null
  return (
    <section className="panel">
      <div className="panel-head"><h2>{t.refTitle}</h2><span className="faint">{rows.length ? t.refSummary(ai, total) : t.refHint}</span></div>
      {!readOnly && (
        <div className="ref-form">
          <label className="field">{t.refWeek}<input type="date" value={f.week_start} onChange={set('week_start')} /></label>
          <label className="field">{t.refTotal}<input inputMode="numeric" value={f.total_jobs} onChange={set('total_jobs')} /></label>
          <label className="field">{t.refAi}<input inputMode="numeric" value={f.ai_jobs} onChange={set('ai_jobs')} /></label>
          <label className="field">{t.refRevenue}<input inputMode="decimal" value={f.ai_revenue} onChange={set('ai_revenue')} /></label>
          <button className="btn" onClick={save}>{t.refSave}</button>
        </div>
      )}
      {err && <p className="error">{err}</p>}
      {rows.length > 0 && (
        <div className="ref-bars" role="img" aria-label={t.refTitle}>
          {rows.map((r) => (
            <div key={r.week_start} className="ref-bar" title={`${r.week_start}: ${r.ai_jobs}/${r.total_jobs}`}>
              <div className="ref-stack" style={{ height: `${(r.total_jobs / max) * 100}%` }}>
                <div className="ref-ai" style={{ height: `${r.total_jobs ? (r.ai_jobs / r.total_jobs) * 100 : 0}%` }} />
              </div>
              <span>{r.week_start.slice(5)}</span>
              <b>{r.ai_jobs}{r.ai_revenue ? ` · ${money(r.ai_revenue, lang)}` : ''}</b>
            </div>
          ))}
        </div>
      )}
      {rows.length > 0 && <div className="legend"><span><span className="swatch ai" /> {t.refAiLegend}</span><span><span className="swatch all" /> {t.refAllLegend}</span></div>}
    </section>
  )
}
