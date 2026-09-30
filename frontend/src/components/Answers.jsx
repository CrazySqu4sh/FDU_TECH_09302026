import { useEffect, useState } from 'react'
import { api, ASSISTANT_NAMES } from '../api.js'
import PasteAnswers from './PasteAnswers.jsx'
import CheckChecker from './CheckChecker.jsx'

export default function Answers({ bizId, t, lang, scanCount, onChanged }) {
  const [answers, setAnswers] = useState(null)
  useEffect(() => { api.answers(bizId).then(setAnswers).catch(() => setAnswers([])) }, [bizId, scanCount])
  if (!answers) return <p className="empty">…</p>
  return (
    <div className="stack">
    <PasteAnswers bizId={bizId} t={t} onDone={onChanged} />
    <CheckChecker bizId={bizId} t={t} lang={lang} key={scanCount} />
    {!answers.length ? <div className="panel empty">{t.noScan}</div> : (
    <section className="panel">
      <div className="panel-head"><h2>{t.answers}</h2><span className="faint">{answers.length}</span></div>
      {answers.map((a) => (
        <div className="answer" key={a.id}>
          <div className="answer-meta">
            <span className="tag">{a.language.toUpperCase()}</span>
            <strong>{ASSISTANT_NAMES[a.provider] || a.provider}</strong>
            <span className="muted">{a.question}</span>
            {a.model === 'consumer app (pasted)' && <span className="tag">{t.pastedTag}</span>}
          </div>
          <pre>{a.text}</pre>
          <div className="answer-meta">
            {a.mentioned ? <span className="named">{t.named}{a.position ? `, ${t.position(a.position)}` : ''}</span>
              : <span className="notnamed">{t.notNamed}</span>}
            {a.claims.map((c, i) => <span key={i} className={`verdict ${c.verdict}`}>{c.fact_key}: {c.value}</span>)}
          </div>
          {a.sources?.length > 0 && (
            <div className="answer-meta"><span className="faint">{t.sourcesUsed}:</span>
              {a.sources.map((s) => <span key={s.url} className="tag">{s.domain}</span>)}</div>
          )}
        </div>
      ))}
    </section>
    )}
    </div>
  )
}
