import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { AI, SEARCH } from './Impact.jsx'

function Pair({ label, before, after, t }) {
  const d = (after ?? 0) - (before ?? 0)
  return (
    <div className="pair">
      <span className="pair-label">{label}</span>
      <div className="pair-bars">
        <div className="pb"><div style={{ width: `${before ?? 0}%`, background: SEARCH }} /><b>{before ?? '–'}%</b><span>{t.labBefore}</span></div>
        <div className="pb"><div style={{ width: `${after ?? 0}%`, background: AI }} /><b>{after ?? '–'}%</b><span>{t.labAfter}</span></div>
      </div>
      <b className={d >= 0 ? 'up' : 'down'}>{d > 0 ? '+' : ''}{d} {t.pts}</b>
    </div>
  )
}

export default function ProofLab({ bizId, t, mode }) {
  const [r, setR] = useState(null)
  const [busy, setBusy] = useState(false)
  const [repeats, setRepeats] = useState(3)
  const [err, setErr] = useState('')
  useEffect(() => { api.lab(bizId).then(setR).catch(() => setR(null)) }, [bizId])
  async function run() {
    setBusy(true); setErr('')
    try { setR(await api.runLab(bizId, repeats)) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  const S = r?.summary
  return (
    <div className="stack">
      <section className="hero wide">
        <h1>{t.labHero}</h1>
        <p>{t.labSub}</p>
      </section>
      <div className="sim-bar">
        <span>{mode === 'demo' ? t.labDemo : t.labLive}</span>
        <span className="lab-run">
          <label>{t.labRepeats} <select value={repeats} onChange={(e) => setRepeats(Number(e.target.value))}>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></label>
          <button className="btn small" onClick={run} disabled={busy}>{busy ? t.labRunning : t.labRun}</button>
        </span>
      </div>
      {err && <p className="error">{err}</p>}
      {!r ? <div className="panel empty">{t.labEmpty}</div> : (
        <>
          <section className="panel">
            <div className="panel-head">
              <h2>{t.labResults}</h2>
              <span className="faint">{t.labMeta(r.questions, r.repeats, r.summary.before.answers + r.summary.after.answers, r.mode === 'demo' ? t.simulatedTag : r.model)}</span>
            </div>
            {r.mode === 'demo' && <p className="warn" style={{ marginBottom: '0.8rem' }}>{t.labSimWarn}</p>}
            <div className="pairs">
              <Pair t={t} label={t.labRecommended} before={S.before.recommended} after={S.after.recommended} />
              <Pair t={t} label={t.labEn} before={S.before.recommended_en} after={S.after.recommended_en} />
              <Pair t={t} label={t.labEs} before={S.before.recommended_es} after={S.after.recommended_es} />
              <Pair t={t} label={t.labFacts} before={S.before.facts_correct} after={S.after.facts_correct} />
            </div>
            <p className="faint" style={{ marginTop: '0.6rem' }}>{t.labWrong(S.before.wrong_facts, S.after.wrong_facts)}</p>
            <div className="confirm-bar"><a className="btn ghost small" href={`/api/businesses/${bizId}/proof-lab.csv`}>{t.labCsv}</a></div>
          </section>

          <section className="panel">
            <div className="panel-head"><h2>{t.labPerQ}</h2><span className="faint">{t.labPerQHint}</span></div>
            <div className="matrix-wrap">
              <table className="audit">
                <thead><tr><th>{t.question}</th><th>{t.labBefore}</th><th>{t.labAfter}</th><th></th></tr></thead>
                <tbody>{r.per_question.map((q) => (
                  <tr key={q.question}><td><span className="lang-tag">{q.language.toUpperCase()}</span> {q.question}</td>
                    <td>{q.before}%</td><td><strong>{q.after}%</strong></td>
                    <td className={q.after - q.before >= 0 ? 'up' : 'down'}>{q.after - q.before > 0 ? '+' : ''}{q.after - q.before}</td></tr>
                ))}</tbody>
              </table>
            </div>
          </section>

          <div className="two even">
            <section className="panel"><div className="panel-head"><h2>{t.labPageBefore}</h2></div><pre className="lab-page">{r.pages.before}</pre></section>
            <section className="panel"><div className="panel-head"><h2>{t.labPageAfter}</h2></div><pre className="lab-page">{r.pages.after}</pre></section>
          </div>
          <p className="note">{t.labLimit}</p>
        </>
      )}
    </div>
  )
}
