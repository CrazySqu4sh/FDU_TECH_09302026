import { useEffect, useState } from 'react'
import { api } from '../api.js'
import FactsEditor, { blankFact } from './FactsEditor.jsx'

export default function Profile({ data, t, onSaved }) {
  const bizId = data.business.id
  const segment = data.business.segment
  const [facts, setFacts] = useState(data.facts)
  const [name, setName] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [journeys, setJourneys] = useState([])
  const [busy, setBusy] = useState(false)

  useEffect(() => { setFacts(data.facts) }, [data.facts])
  useEffect(() => { api.journeys(bizId).then(setJourneys).catch(() => {}) }, [bizId])

  async function confirm() {
    setErr(''); setMsg('')
    if (!name.trim()) { setErr(t.approverRequired); return }
    const clean = facts.filter((f) => f.label.trim() && f.value.trim())
    try {
      await api.confirmFacts(bizId, clean, name)
      setMsg(t.saved)
      await onSaved()
    } catch (e) { setErr(e.message) }
  }
  async function remove(i) {
    const f = facts[i]
    if (f.key) { await api.deleteFact(bizId, f.key); await onSaved() }
    else setFacts(facts.filter((_, j) => j !== i))
  }
  async function regenerate() {
    setBusy(true)
    try { setJourneys(await api.regenerateJourneys(bizId)) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head">
          <h2>{t.profile}</h2>
          <button className="btn ghost small" onClick={() => setFacts([...facts, blankFact(segment)])}>{t.addFact}</button>
        </div>
        <p className="muted" style={{ marginBottom: '1rem', maxWidth: '75ch' }}>{t.profileHint}</p>
        <FactsEditor facts={facts} setFacts={setFacts} t={t} onRemove={remove} segment={segment} />
        <div className="confirm-bar">
          <div>
            <input aria-label={t.confirmedBy} placeholder={t.confirmedBy} value={name}
              onChange={(e) => { setName(e.target.value); setErr('') }} />
            {err && <p className="error" role="alert">{err}</p>}
          </div>
          <button className="btn" onClick={confirm}>{t.confirmProfile}</button>
          {msg && <span className="success">{msg}</span>}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>{t.journeys}</h2>
          <button className="btn ghost small" onClick={regenerate} disabled={busy}>{t.regenerate}</button>
        </div>
        <ol className="journey-list">
          {journeys.map((j) => (
            <li key={j.id}><span className="lang-tag">{j.language.toUpperCase()}</span>{j.question}</li>
          ))}
        </ol>
      </section>
    </div>
  )
}
