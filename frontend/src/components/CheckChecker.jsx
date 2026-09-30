import { useEffect, useState } from 'react'
import { api, ASSISTANT_NAMES } from '../api.js'
import { pretty } from './Matrix.jsx'

// People review random checker verdicts; the agreement rate is the checker's measured accuracy.
export default function CheckChecker({ bizId, t, lang }) {
  const [d, setD] = useState(null)
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const load = () => api.nextLabel(bizId).then(setD).catch(() => setD(null))
  useEffect(() => { load() }, [bizId])  // eslint-disable-line react-hooks/exhaustive-deps
  if (!d) return null
  const s = d.stats, c = d.claim
  async function vote(v) {
    if (!name.trim()) { setErr(t.approverRequired); return }
    setErr('')
    await api.label(c.id, name, v); await load()
  }
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.ccTitle}</h2>
        <span className="cc-stat">{s.labeled ? t.ccStat(s.agree, s.labeled, s.accuracy) : t.ccNone}</span>
      </div>
      <p className="muted" style={{ maxWidth: '75ch', marginBottom: '0.8rem' }}>{t.ccHint}</p>
      {!c ? <p className="success">{t.ccAllDone}</p> : (
        <div className="cc-card">
          <p className="faint">{ASSISTANT_NAMES[c.assistant] || c.assistant} · “{c.question}”</p>
          <pre>{c.excerpt}</pre>
          <div className="compare">
            <div className="said"><small>{t.ccAiSaid(c.fact)}</small>{pretty(c.category, c.ai_value, lang)}</div>
            <div className="true"><small>{t.verifiedValue}</small>{pretty(c.category, c.truth, lang)}</div>
          </div>
          <p>{t.ccChecker}: <span className={`verdict ${c.checker}`}>{t[c.checker]}</span> · {t.ccQuestion}</p>
          <div className="approve-row">
            <input aria-label={t.approverName} placeholder={t.approverName} value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn small" onClick={() => vote('match')}>{t.ccMatch}</button>
            <button className="btn small" onClick={() => vote('wrong')}>{t.ccWrong}</button>
            <button className="btn ghost small" onClick={() => vote('unclear')}>{t.ccUnclear}</button>
          </div>
          {err && <p className="error">{err}</p>}
        </div>
      )}
    </section>
  )
}
