import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { AI, Chart, Legend, SEARCH, money, niceMax } from './Impact.jsx'
import Locked from './Locked.jsx'

const STEP_TAB = { critical: 'issues', facts: 'profile', spanish: 'issues', missed: 'issues', keep: 'truth' }
const STEP_COLOR = '#1f7a4d'

// Where the extra monthly sales come from: start, one bar per step, end.
function Waterfall({ w, t, lang, scale }) {
  const W = 560, H = 230, P = { l: 56, r: 12, t: 22, b: 44 }
  const bars = [{ id: 'start', label: t.wfStart, from: 0, to: w.start, kind: 'base' }]
  let level = w.start
  for (const s of w.steps) { bars.push({ id: s.id, label: t.wfStep[s.id], from: level, to: level + s.value, kind: 'step', value: s.value }); level += s.value }
  bars.push({ id: 'end', label: t.wfEnd, from: 0, to: w.end, kind: 'end' })
  const max = niceMax(w.end * scale)
  const y = (v) => H - P.b - ((v * scale) / max) * (H - P.t - P.b)
  const bw = (W - P.l - P.r) / bars.length
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={t.wfTitle}>
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={P.l} x2={W - P.r} y1={y((max * f) / scale)} y2={y((max * f) / scale)} stroke="var(--line)" />
          <text x={P.l - 6} y={y((max * f) / scale) + 4} fontSize="11" textAnchor="end" fill="var(--ink-faint)">{money(max * f, lang)}</text>
        </g>
      ))}
      {bars.map((b, i) => {
        const x = P.l + i * bw + bw * 0.18, width = bw * 0.64
        const top = y(Math.max(b.from, b.to)), h = Math.max(2, Math.abs(y(b.from) - y(b.to)))
        const fill = b.kind === 'base' ? SEARCH : b.kind === 'end' ? AI : STEP_COLOR
        return (
          <g key={b.id}>
            <rect x={x} y={top} width={width} height={h} rx="3" fill={fill}>
              <title>{`${b.label}: ${money((b.kind === 'step' ? b.value : b.to) * scale, lang)}`}</title>
            </rect>
            {i < bars.length - 1 && <line x1={x + width} x2={x + bw} y1={y(b.to)} y2={y(b.to)} stroke="var(--ink-faint)" strokeDasharray="2 2" />}
            <text x={x + width / 2} y={top - 6} fontSize="11" textAnchor="middle" fill="var(--ink)" fontWeight="600">
              {b.kind === 'step' ? `+${money(b.value * scale, lang)}` : money(b.to * scale, lang)}
            </text>
            <text x={x + width / 2} y={H - P.b + 16} fontSize="10.5" textAnchor="middle" fill="var(--ink-soft)">
              {b.label.split(' ').slice(0, 2).join(' ')}
            </text>
            <text x={x + width / 2} y={H - P.b + 29} fontSize="10.5" textAnchor="middle" fill="var(--ink-soft)">
              {b.label.split(' ').slice(2).join(' ')}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export default function Growth({ bizId, t, lang, scanCount, onGo, onUpgrade }) {
  const [g, setG] = useState(null)
  const [open, setOpen] = useState({})
  const [aovInput, setAovInput] = useState('')
  useEffect(() => { api.growth(bizId).then(setG).catch(() => setG(null)) }, [bizId, scanCount])
  if (!g) return <div className="panel empty">{t.noScan}</div>
  const { a, b } = g
  const userAov = Number(aovInput)
  const scale = g.aov && userAov > 0 ? userAov / g.aov : 1  // revenue follows the owner's own average job value
  const m = (v) => money(v * scale, lang)
  const proj = g.projection?.map((p, i) => ({ ...p, week: i }))
  const rows = [
    { label: t.accuracy, a: `${a.accuracy}%`, b: `${b.accuracy}%` },
    { label: t.inclusion, a: `${a.inclusion}%`, b: `${b.inclusion}%` },
    { label: t.spanish, a: `${a.inclusion_es}%`, b: `${b.inclusion_es}%` },
    ...(proj ? [{ label: t.aiSalesWeek, a: m(a.revenue_week), b: `${m(b.revenue_week)}*` }] : []),
  ]
  const max = proj ? niceMax(Math.max(...proj.map((p) => p.high)) * scale) / scale : 1
  const roi = g.roi && scale !== 1 ? Math.round(g.roi * scale * 10) / 10 : g.roi

  return (
    <div className="stack">
      <section className="hero wide">
        <h1>{proj ? t.growthHeroJobs(g.extra_jobs_month3, m(g.extra_month3)) : t.growthHeroNoSales(a.accuracy, b.accuracy)}</h1>
        <p>{t.growthSub}</p>
      </section>

      {proj && (
        <div className="figures">
          <div className="figure"><b>+{g.extra_jobs_month3}</b><span>{t.figJobs}</span></div>
          <div className="figure"><b>{m(g.extra_90_low)}–{m(g.extra_90_high)}</b><span>{t.figRange}</span></div>
          <div className="figure"><b>{roi ? `${roi}×` : '–'}</b><span>{roi ? t.figRoi(g.plan_price) : t.figRoiNone}</span></div>
          <div className="figure aov">
            <label>{t.aovLabel}
              <input inputMode="decimal" placeholder={`$${g.aov}`} value={aovInput} onChange={(e) => setAovInput(e.target.value.replace(/[^0-9.]/g, ''))} />
            </label>
            <span>{t.aovHint}</span>
          </div>
        </div>
      )}

      <div className="ab">
        <section className="ab-card">
          <span className="ab-tag">{t.pointA}</span>
          {rows.map((r) => <div key={r.label}><span>{r.label}</span><b>{r.a}</b></div>)}
        </section>
        <div className="ab-arrow" aria-hidden="true">→</div>
        <section className="ab-card b">
          <span className="ab-tag">{t.pointB}</span>
          {rows.map((r) => <div key={r.label}><span>{r.label}</span><b>{r.b}</b></div>)}
          {proj && <p className="faint">* {t.pointBNote}</p>}
        </section>
      </div>

      {proj ? (
        <div className="two even">
          <section className="panel">
            <div className="panel-head"><h2>{t.projectionTitle}</h2><span className="faint">{t.projectionHint(g.weeks)}</span></div>
            <Chart weeks={proj} max={max} fmt={(v) => money(v * scale, lang)} label={t.projectionTitle}
              tooltip={(w) => <><b>{t.week} {w.week + 1}</b><br />{t.withPlan}: {m(w.plan)}<br />{t.range}: {m(w.low)}–{m(w.high)}<br />{t.ifNothing}: {m(w.stay)}</>}>
              {({ x, y }) => (
                <>
                  <path d={`${proj.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.high)}`).join(' ')} ${[...proj].reverse().map((p, i) => `L${x(proj.length - 1 - i)},${y(p.low)}`).join(' ')} Z`}
                    fill={AI} opacity="0.18" />
                  <path d={proj.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.stay)}`).join(' ')} fill="none" stroke={SEARCH} strokeWidth="2" strokeDasharray="5 4" />
                  <path d={proj.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.plan)}`).join(' ')} fill="none" stroke={AI} strokeWidth="2" />
                  <circle cx={x(proj.length - 1)} cy={y(proj[proj.length - 1].plan)} r="4" fill={AI} stroke="var(--surface)" strokeWidth="2" />
                </>
              )}
            </Chart>
            <Legend items={[{ label: t.withPlan, color: AI }, { label: t.range, color: AI, bar: true, opacity: 0.25 }, { label: t.ifNothing, color: SEARCH, dash: '5 4' }]} />
          </section>
          <section className="panel">
            <div className="panel-head"><h2>{t.wfTitle}</h2><span className="faint">{t.wfHint}</span></div>
            {g.waterfall && <Waterfall w={g.waterfall} t={t} lang={lang} scale={scale} />}
            <p className="faint" style={{ marginTop: '0.4rem' }}>{t.wfNote}</p>
          </section>
        </div>
      ) : <Locked t={t} plan="silver" text={t.lockedProjection} onUpgrade={onUpgrade} />}

      <section className="panel">
        <div className="panel-head"><h2>{t.stepsTitle}</h2><span className="faint">{t.stepsHint}</span></div>
        <ol className="steps">
          {g.steps.map((s) => (
            <li key={s.id} className={s.done ? 'done' : ''}>
              <span className="when">{s.weeks === 'ongoing' ? t.ongoing : t.weeksRange(s.weeks)}</span>
              <div>
                <strong>{t.step[s.id].title}</strong>
                <p className="muted">{s.done ? t.stepDone : s.count == null && s.id === 'missed' ? t.lockedMissedShort : t.step[s.id].desc(s.count)}</p>
                <button className="linkish why-btn" onClick={() => setOpen({ ...open, [s.id]: !open[s.id] })}>
                  {open[s.id] ? t.whyHide : t.whyShow}
                </button>
                {open[s.id] && (
                  <ul className="why">
                    {s.evidence.map((e, i) => <li key={i}><span className="why-tag yours">{t.yourData}</span>{t.stepEvidence[e.id](e)}</li>)}
                    {t.research[s.id].map((r) => (
                      <li key={r.url}><span className="why-tag">{t.researchTag}</span>{r.text} <a href={r.url} target="_blank" rel="noreferrer">{r.source}</a></li>
                    ))}
                  </ul>
                )}
              </div>
              {s.done ? <span className="verdict match">{t.done}</span>
                : <button className="btn ghost small" onClick={() => onGo(STEP_TAB[s.id])}>{t.step[s.id].cta}</button>}
            </li>
          ))}
        </ol>
      </section>

      <section className="panel">
        <div className="panel-head"><h2>{t.assumptionsTitle}</h2><span className="faint">{t.assumptionsHint}</span></div>
        <table className="audit">
          <tbody>
            {t.assumptions(g.assumptions, userAov > 0 ? userAov : g.aov).map(([what, value, source, url]) => (
              <tr key={what}><td>{what}</td><td><strong>{value}</strong></td><td>{url ? <a href={url} target="_blank" rel="noreferrer">{source}</a> : <span className="faint">{source}</span>}</td></tr>
            ))}
          </tbody>
        </table>
        <p className="note" style={{ marginTop: '0.75rem' }}>{t.projectionNote}</p>
      </section>
    </div>
  )
}
