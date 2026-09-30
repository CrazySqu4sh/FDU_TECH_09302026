import { useEffect, useState } from 'react'
import { api, ASSISTANT_NAMES } from '../api.js'
import { downloadText } from './CsvImport.jsx'

const short = (h) => (h ? `${h.slice(0, 10)}…` : '–')
const when = (iso) => (iso ? new Date(iso).toLocaleString() : '–')

// The proof behind one finding, readable on screen and downloadable as one file.
export default function Evidence({ inc, t, lang }) {
  const [rep, setRep] = useState(null)
  useEffect(() => { api.evidence(inc.id).then(setRep).catch(() => setRep(null)) }, [inc.id, inc.origin])
  if (!rep) return <p className="faint">…</p>
  return (
    <div className="evidence-box">
      <div className="ev-head">
        <strong>{t.evTitle}</strong>
        <button className="btn ghost small" onClick={() => downloadText(`aparece-evidence-${inc.id}.json`, JSON.stringify(rep, null, 2), 'application/json')}>{t.evDownload}</button>
      </div>
      <div className="ev-grid">
        <section>
          <h4>{t.evTruth}</h4>
          <p><strong>{rep.truth.fact}: {rep.truth.value}</strong></p>
          <p className="faint">{t.evLevel}: {t.evidence[rep.truth.evidence_level] || rep.truth.evidence_level} · {rep.truth.source}</p>
          {rep.truth.confirmed_by.length > 0 && <p className="faint">{t.confirmedByCol}: {rep.truth.confirmed_by.join(', ')}</p>}
          {rep.truth.disagreeing_listings.length > 0 && <p className="warn">{t.disagreesCol}: {rep.truth.disagreeing_listings.map((d) => `${d.domain} (${d.value})`).join(', ')}</p>}
        </section>
        {rep.ai_answers.length > 0 && (
          <section>
            <h4>{t.evAnswers(rep.ai_answers.length)}</h4>
            {rep.ai_answers.slice(0, 2).map((a, i) => (
              <div key={i} className="ev-item">
                <p className="faint">{ASSISTANT_NAMES[a.assistant] || a.assistant} · {a.model} · {when(a.asked_at)} · “{a.question}”</p>
                <pre>{a.excerpt}</pre>
                <p className="faint mono">SHA-256 {short(a.sha256)}</p>
              </div>
            ))}
          </section>
        )}
        {rep.cited_pages.length > 0 && (
          <section>
            <h4>{t.evCited}</h4>
            <table className="audit">
              <tbody>
                {rep.cited_pages.map((c) => (
                  <tr key={c.url}>
                    <td>{c.domain}{c.simulated ? <span className="tag">{t.simulatedTag}</span> : null}</td>
                    <td>{c.supports == null ? <span className="verdict needs_review">{t.evUnreadable}</span>
                      : c.supports ? <span className="verdict wrong">{t.evSaysIt}</span> : <span className="faint">{t.evNotThere}</span>}
                      {c.snippet && <div className="faint ev-snip">“{c.snippet}”</div>}</td>
                    <td className="faint mono">{when(c.fetched_at)}<br />SHA-256 {short(c.sha256)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
        <section>
          <h4>{t.evTrail}</h4>
          {rep.approval_trail.length === 0 ? <p className="faint">–</p> :
            <ul className="ev-trail">{rep.approval_trail.map((a, i) => <li key={i}>{t.dataAction[a.action] || a.action} · {a.by} · {when(a.at)}</li>)}</ul>}
          {rep.checker.labeled > 0 && <p className="faint">{t.checkerLine(rep.checker.agree, rep.checker.labeled, rep.checker.accuracy)}</p>}
        </section>
      </div>
    </div>
  )
}
