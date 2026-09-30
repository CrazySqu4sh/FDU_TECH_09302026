import { useEffect, useState } from 'react'
import { api, ASSISTANT_NAMES } from '../api.js'
import { pretty } from './Matrix.jsx'

export default function Perception({ bizId, t, lang, name, scanCount }) {
  const [p, setP] = useState(null)
  useEffect(() => { api.perception(bizId).then(setP).catch(() => setP(null)) }, [bizId, scanCount])
  if (!p) return <div className="panel empty">{t.noScan}</div>
  const causes = p.sources.filter((s) => s.likely_cause)

  return (
    <div className="stack">
      <section className="hero wide">
        <h1>{t.perceptionHero(name)}</h1>
        <p>{t.perceptionSub}</p>
      </section>

      <div className="two even">
        <section className="panel">
          <div className="panel-head"><h2>{t.associations}</h2><span className="faint">{t.associationsHint}</span></div>
          <div className="chips">
            {p.associations.map((a) => <span key={a.word} className="chip">{a.word}<b>{a.count}</b></span>)}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head"><h2>{t.unknownTitle}</h2><span className="faint">{t.unknownHint}</span></div>
          {p.never_mentioned.length === 0 ? <p className="muted">{t.unknownNone}</p> : (
            <div className="chips">{p.never_mentioned.map((l) => <span key={l} className="chip missing">{l}</span>)}</div>
          )}
        </section>
      </div>

      <section className="panel">
        <div className="panel-head"><h2>{t.sourcesTitle}</h2><span className="faint">{t.sourcesHint}</span></div>
        {causes.length > 0 && <p className="cause-banner">{t.causeBanner(causes.map((c) => c.label).join(', '))}</p>}
        {p.sources.length === 0 ? <p className="muted">{t.noSources}</p> : (
          <div className="matrix-wrap">
            <table className="audit sources">
              <thead><tr><th>{t.source}</th><th>{t.citedIn}</th><th>{t.withWrong}</th><th>{t.whatToDo}</th></tr></thead>
              <tbody>
                {p.sources.map((s) => (
                  <tr key={s.domain} className={s.likely_cause ? 'cause' : ''}>
                    <td><strong>{s.label}</strong><br /><span className="faint">{s.domain} · {t.sourceKind[s.kind]}</span></td>
                    <td>{t.nAnswers(s.cited)}<br /><span className="faint">{s.assistants.map((a) => ASSISTANT_NAMES[a] || a).join(', ')}</span></td>
                    <td>
                      <div className="mini-bar"><div className={s.wrong_share >= 60 ? 'high' : ''} style={{ width: `${s.wrong_share}%` }} /></div>
                      <span>{s.wrong_share}%</span>
                      {s.likely_cause && <span className="verdict wrong">{t.likelyCause}</span>}
                    </td>
                    <td className="muted">{t.sourceAction[s.kind]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="note" style={{ marginTop: '0.75rem' }}>{t.sourcesNote}</p>
      </section>

      <div className="ai-grid">
        {p.assistants.map((a) => {
          const off = a.beliefs.filter((b) => b.verdict !== 'match')
          const ok = a.beliefs.length - off.length
          return (
            <section className="panel ai-card" key={a.provider}>
              <div className="panel-head">
                <h2>{ASSISTANT_NAMES[a.provider] || a.provider}</h2>
                {a.tone && <span className={`tone ${a.tone}`}>{t.tone[a.tone]}</span>}
              </div>
              <div className="ai-stats">
                <span><b>{a.inclusion}%</b> {t.namedShort}</span>
                <span><b>{a.avg_position ? `#${a.avg_position}` : '–'}</b> {t.avgRank}</span>
              </div>
              {a.description ? <blockquote>“{a.description}”</blockquote> : <p className="muted">{t.neverDescribes}</p>}
              {a.descriptors.length > 0 && <div className="chips small">{a.descriptors.map((w) => <span key={w} className="chip">{w}</span>)}</div>}
              <h3>{t.believes}</h3>
              {off.length === 0 ? <p className="success">{t.allCorrect(ok)}</p> : (
                <table className="audit">
                  <tbody>
                    {off.map((b) => (
                      <tr key={b.key}>
                        <td>{b.product ? `${b.product} · ` : ''}{b.label}</td>
                        <td>{pretty(b.category, b.value, lang)}<br /><span className="faint">{t.verifiedValue}: {pretty(b.category, b.truth, lang)}</span></td>
                        <td><span className={`verdict ${b.verdict}`}>{t[b.verdict]}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {off.length > 0 && ok > 0 && <p className="faint">{t.plusCorrect(ok)}</p>}
            </section>
          )
        })}
      </div>
    </div>
  )
}
