import { useEffect, useState } from 'react'
import { api, ASSISTANT_NAMES } from '../api.js'
import { Chart, Legend } from './Impact.jsx'

// Validated trio (dataviz validator: CVD ΔE ≥ 15.9, contrast ≥ 3:1). Accuracy is also dashed.
const C = { inclusion: '#2f63c4', inclusion_es: '#c47f0a', accuracy: '#8a4fbf' }

function heatColor(v) {  // sequential single hue, light -> dark blue
  if (v == null) return { background: 'var(--paper)', color: 'var(--ink-faint)' }
  const l = 96 - (v / 100) * 58
  return { background: `hsl(218 62% ${l}%)`, color: l < 62 ? '#fff' : 'var(--ink)' }
}

function Spark({ values, label }) {
  const W = 180, H = 48
  const pts = values.map((v, i) => [values.length === 1 ? W / 2 : (i * (W - 8)) / (values.length - 1) + 4, H - 4 - ((v ?? 0) / 100) * (H - 8)])
  const last = values[values.length - 1], first = values[0]
  return (
    <div className="spark">
      <div className="spark-head"><strong>{label}</strong><span>{last ?? '–'}%</span></div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`${label}: ${values.join(', ')}`}>
        <line x1="0" x2={W} y1={H - 4 - 0.5 * (H - 8)} y2={H - 4 - 0.5 * (H - 8)} stroke="var(--line)" strokeDasharray="2 3" />
        <path d={pts.map((p, i) => `${i ? 'L' : 'M'}${p[0]},${p[1]}`).join(' ')} fill="none" stroke="var(--ink)" strokeWidth="2" />
        <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="3.5" fill="var(--ink)" />
      </svg>
      <span className={`faint ${last - first > 0 ? 'up' : last - first < 0 ? 'down' : ''}`}>{last - first > 0 ? '+' : ''}{last - first} pts</span>
    </div>
  )
}

export default function Insights({ bizId, t, mode, onChanged }) {
  const [d, setD] = useState(null)
  const [busy, setBusy] = useState(false)
  const load = () => api.insights(bizId).then(setD).catch(() => setD({ scans: [] }))
  useEffect(() => { load() }, [bizId])  // eslint-disable-line react-hooks/exhaustive-deps

  async function simulate() {
    setBusy(true)
    try { await api.simulate(bizId, 6); await load(); await onChanged() } finally { setBusy(false) }
  }
  if (!d) return <p className="empty">…</p>
  const scans = d.scans.map((s) => ({ ...s, week: s.scan }))
  const few = scans.length < 3

  return (
    <div className="stack">
      <section className="hero wide">
        <h1>{t.worksHero}</h1>
        <p>{t.worksSub}</p>
      </section>
      {mode === 'demo' && (
        <div className="sim-bar">
          <span>{few ? t.simNeed(scans.length) : t.simMore}</span>
          <button className="btn small" onClick={simulate} disabled={busy}>{busy ? t.simBusy : t.simBtn}</button>
        </div>
      )}
      {few ? <div className="panel empty">{t.needScans}</div> : (
        <>
          <section className="panel">
            <div className="panel-head"><h2>{t.trendTitle}</h2><span className="faint">{t.trendHint(d.fixes_live)}</span></div>
            <div className="chart-narrow">
              <Chart weeks={scans} max={100} fmt={(v) => `${Math.round(v)}%`} label={t.trendTitle}
                tooltip={(s) => <><b>{t.scanN(s.scan + 1)}</b><br />{t.inclusion}: {s.inclusion}%<br />{t.spanish}: {s.inclusion_es}%<br />{t.accuracy}: {s.accuracy ?? '–'}%
                  {s.fixes.length > 0 && <><br /><span className="tip-fix">✓ {t.fixesLive}: {s.fixes.join(', ')}</span></>}</>}>
                {({ x, y }) => (
                  <>
                    {scans.map((s, i) => s.fixes.length > 0 && (
                      <g key={`f${i}`}>
                        <line x1={x(i)} x2={x(i)} y1={y(100)} y2={y(0)} stroke="var(--match)" strokeDasharray="3 3" />
                        <text x={x(i)} y={y(100) - 4} fontSize="11" textAnchor="middle" fill="var(--match)">✓{s.fixes.length}</text>
                      </g>
                    ))}
                    {['inclusion', 'inclusion_es', 'accuracy'].map((k) => (
                      <g key={k}>
                        <path d={scans.map((s, i) => `${i ? 'L' : 'M'}${x(i)},${y(s[k])}`).join(' ')} fill="none" stroke={C[k]} strokeWidth="2" strokeDasharray={k === 'accuracy' ? '6 4' : ''} />
                        <circle cx={x(scans.length - 1)} cy={y(scans[scans.length - 1][k])} r="4" fill={C[k]} stroke="var(--surface)" strokeWidth="2" />
                      </g>
                    ))}
                  </>
                )}
              </Chart>
            </div>
            <Legend items={[{ label: t.inclusion, color: C.inclusion }, { label: t.spanish, color: C.inclusion_es },
              { label: t.accuracy, color: C.accuracy, dash: '6 4' }, { label: t.fixesLive, color: 'var(--match)', dash: '3 3' }]} />
          </section>

          <section className="panel">
            <div className="panel-head"><h2>{t.expTitle}</h2><span className="faint">{t.expHint}</span></div>
            {d.experiments.length === 0 ? <p className="muted">{t.expNone}</p> : (
              <div className="exp">
                {d.experiments.map((e) => (
                  <div className="exp-row" key={e.label + e.metric}>
                    <div>
                      <strong>{e.label}</strong>
                      <span className="faint"> · {e.metric === 'accuracy' ? t.accuracy : t.inclusion}: {e.before}% → {e.after}% · {t.otherQuestions} {e.control_change > 0 ? '+' : ''}{e.control_change}</span>
                      {e.early && <span className="tag">{t.early}</span>}
                    </div>
                    <div className="diverge" aria-label={`${e.lift} pts`}>
                      <span className="zero" />
                      <div className={e.lift >= 0 ? 'pos' : 'neg'}
                        style={{ width: `${Math.min(Math.abs(e.lift), 60) / 60 * 50}%`, [e.lift >= 0 ? 'left' : 'right']: '50%' }} />
                    </div>
                    <b className={e.lift >= 0 ? 'up' : 'down'}>{e.lift > 0 ? '+' : ''}{e.lift} pts</b>
                    <span className="faint verdict-text">{e.lift >= 10 ? t.worked : e.lift <= -10 ? t.backfired : t.noEffect}</span>
                  </div>
                ))}
              </div>
            )}
            <p className="note" style={{ marginTop: '0.75rem' }}>{t.expNote}</p>
          </section>

          <section className="panel">
            <div className="panel-head"><h2>{t.sigTitle}</h2><span className="faint">{t.sigHint}</span></div>
            <div className="dumbbells">
              {d.signals.map((s) => (
                <div className="db-row" key={s.id}>
                  <span className="db-label">{t.signal(s.id)}</span>
                  <div className="db-track" title={`${t.whenYes}: ${s.with}% (${s.n_with}) · ${t.whenNo}: ${s.without}% (${s.n_without})`}>
                    <span className="db-line" style={{ left: `${Math.min(s.with, s.without)}%`, width: `${Math.abs(s.with - s.without)}%` }} />
                    <span className="db-dot no" style={{ left: `${s.without}%` }} />
                    <span className="db-dot yes" style={{ left: `${s.with}%` }} />
                  </div>
                  <b className={s.lift >= 0 ? 'up' : 'down'}>{s.lift > 0 ? '+' : ''}{s.lift}</b>
                  <span className="faint db-wrong">{s.wrong_with != null && s.wrong_without != null ? t.wrongVs(s.wrong_with, s.wrong_without) : ''}</span>
                </div>
              ))}
            </div>
            <div className="legend">
              <span><span className="db-dot yes static" /> {t.whenYes}</span>
              <span><span className="db-dot no static" /> {t.whenNo}</span>
            </div>
            <p className="note" style={{ marginTop: '0.75rem' }}>{t.sigNote}</p>
          </section>

          <section className="panel">
            <div className="panel-head"><h2>{t.heatTitle}</h2><span className="faint">{t.heatHint}</span></div>
            <div className="matrix-wrap">
              <table className="heat">
                <thead><tr><th>{t.question}</th>{scans.map((s) => <th key={s.id}>{s.scan + 1}</th>)}</tr></thead>
                <tbody>
                  {d.heatmap.map((h) => (
                    <tr key={h.need + h.language}>
                      <td><span className="lang-tag">{h.language.toUpperCase()}</span> {h.need}</td>
                      {h.values.map((v, i) => <td key={i} style={heatColor(v)} title={`${h.need} · ${t.scanN(i + 1)}: ${v ?? '–'}%`}>{v ?? '–'}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head"><h2>{t.perAssistant}</h2><span className="faint">{t.perAssistantHint}</span></div>
            <div className="sparks">
              {Object.entries(d.by_assistant).map(([p, vals]) => <Spark key={p} label={ASSISTANT_NAMES[p] || p} values={vals} />)}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
