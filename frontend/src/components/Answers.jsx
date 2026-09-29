import { useEffect, useState } from 'react'
import { api, ASSISTANT_NAMES } from '../api.js'

export default function Answers({ bizId, t, scanCount }) {
  const [answers, setAnswers] = useState(null)
  useEffect(() => { api.answers(bizId).then(setAnswers).catch(() => setAnswers([])) }, [bizId, scanCount])
  if (!answers) return <p className="empty">…</p>
  if (!answers.length) return <div className="panel empty">{t.noScan}</div>
  return (
    <section className="panel">
      <div className="panel-head"><h2>{t.answers}</h2><span className="faint">{answers.length}</span></div>
      {answers.map((a) => (
        <div className="answer" key={a.id}>
          <div className="answer-meta">
            <span className="tag">{a.language.toUpperCase()}</span>
            <strong>{ASSISTANT_NAMES[a.provider] || a.provider}</strong>
            <span className="muted">{a.question}</span>
          </div>
          <pre>{a.text}</pre>
          <div className="answer-meta">
            {a.mentioned ? <span className="named">{t.named}{a.position ? `, ${t.position(a.position)}` : ''}</span>
              : <span className="notnamed">{t.notNamed}</span>}
            {a.claims.map((c, i) => <span key={i} className={`verdict ${c.verdict}`}>{c.fact_key}: {c.value}</span>)}
          </div>
        </div>
      ))}
    </section>
  )
}
