import { useState } from 'react'
import { api } from '../api.js'
import { pretty } from './Matrix.jsx'

// Which independent pages confirm each fact, and which listings disagree.
export default function FactCheck({ data, t, lang, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  async function run() {
    setBusy(true); setMsg('')
    try { const r = await api.verifyFacts(data.business.id); setMsg(t.verifyDone(r.pages, r.conflicts)); await onChanged() }
    catch (e) { setMsg(e.message) } finally { setBusy(false) }
  }
  const checked = data.facts.some((f) => f.confirmed_by.length || f.disagreeing.length)
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.verifyTitle}</h2>
        <button className="btn small" onClick={run} disabled={busy}>{busy ? t.verifying : t.verifyBtn}</button>
      </div>
      <p className="muted" style={{ marginBottom: '0.8rem', maxWidth: '75ch' }}>{t.verifyHint}</p>
      {msg && <p className="success" style={{ marginBottom: '0.6rem' }}>{msg}</p>}
      {checked && (
        <div className="matrix-wrap">
          <table className="audit">
            <thead><tr><th>{t.label}</th><th>{t.value}</th><th>{t.confirmedByCol}</th><th>{t.disagreesCol}</th><th>{t.statusCol}</th></tr></thead>
            <tbody>
              {data.facts.map((f) => {
                const status = f.disagreeing.length ? 'conflict' : f.confirmed_by.length >= 2 ? 'confirmed' : 'single'
                return (
                  <tr key={f.key}>
                    <td>{f.product ? `${f.product} · ` : ''}{lang === 'es' && f.label_es ? f.label_es : f.label}</td>
                    <td><strong>{pretty(f.category, f.value, lang)}</strong></td>
                    <td><div className="chips small">{f.confirmed_by.map((d) => <span key={d} className="chip ok">{d}</span>)}</div></td>
                    <td><div className="chips small">{f.disagreeing.map((d) => <span key={d.domain} className="chip bad">{d.domain}: {pretty(f.category, d.value, lang)}</span>)}</div></td>
                    <td><span className={`verdict ${status === 'conflict' ? 'wrong' : status === 'confirmed' ? 'match' : 'needs_review'}`}>{t.factStatus[status]}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
