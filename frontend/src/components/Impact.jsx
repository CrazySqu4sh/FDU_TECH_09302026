import { useState } from 'react'
import Locked from './Locked.jsx'
import ReferralLog from './ReferralLog.jsx'

// Validated pair (dataviz validator: CVD ΔE 28.5, contrast ≥ 3:1 on white).
export const SEARCH = '#2f63c4'
export const AI = '#c47f0a'
const W = 560, H = 220, PAD = { l: 52, r: 16, t: 16, b: 28 }

export const money = (v, lang) => new Intl.NumberFormat(lang === 'es' ? 'es-US' : 'en-US',
  { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v ?? 0)
const num = (v, lang) => new Intl.NumberFormat(lang === 'es' ? 'es-US' : 'en-US').format(v ?? 0)

export function niceMax(v) {
  if (!v) return 1
  const p = 10 ** Math.floor(Math.log10(v))
  return [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].map((m) => m * p).find((m) => m >= v)
}

// One shared frame for both charts: x = week, one y-axis, crosshair + tooltip on hover.
export function Chart({ weeks, max, fmt, marker, markerLabel, label, tooltip, children, inset = 0 }) {
  const [hover, setHover] = useState(null)
  const span = W - PAD.l - PAD.r - 2 * inset  // inset keeps edge bars inside the frame
  const x = (i) => PAD.l + inset + (weeks.length === 1 ? span / 2 : (i * span) / (weeks.length - 1))
  const y = (v) => H - PAD.b - ((v ?? 0) / max) * (H - PAD.t - PAD.b)
  const step = span / Math.max(weeks.length - 1, 1)
  function move(e) {
    const r = e.currentTarget.getBoundingClientRect()
    const vx = ((e.clientX - r.left) / r.width) * W
    setHover(Math.max(0, Math.min(weeks.length - 1, Math.round((vx - PAD.l - inset) / step))))
  }
  const mi = weeks.findIndex((w) => w.week === marker)
  return (
    <div className="chart" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={label} onMouseMove={move}>
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(max * f)} y2={y(max * f)} stroke="var(--line)" />
            <text x={PAD.l - 8} y={y(max * f) + 4} fontSize="11" textAnchor="end" fill="var(--ink-faint)">{fmt(max * f)}</text>
          </g>
        ))}
        {weeks.map((w, i) => (i % 2 === 0 || i === weeks.length - 1) && (
          <text key={w.week} x={x(i)} y={H - 8} fontSize="11" textAnchor="middle" fill="var(--ink-faint)">{w.week + 1}</text>
        ))}
        {mi >= 0 && (
          <g>
            <line x1={x(mi)} x2={x(mi)} y1={PAD.t} y2={H - PAD.b} stroke="var(--ink-soft)" strokeDasharray="3 3" />
            <text x={x(mi) - 6} y={PAD.t + 10} fontSize="11" textAnchor="end" fill="var(--ink-soft)">{markerLabel}</text>
          </g>
        )}
        {children({ x, y, step })}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={PAD.t} y2={H - PAD.b} stroke="var(--ink-faint)" />}
      </svg>
      {hover != null && (
        <div className="tip" style={{ left: `${(x(hover) / W) * 100}%` }}>{tooltip(weeks[hover])}</div>
      )}
    </div>
  )
}

export function Legend({ items }) {
  return (
    <div className="legend">
      {items.map((it) => (
        <span key={it.label}>
          <svg width="18" height="10" aria-hidden="true">
            {it.bar ? <rect x="3" y="0" width="12" height="10" rx="2" fill={it.color} opacity={it.opacity ?? 1} />
              : <line x1="0" x2="18" y1="5" y2="5" stroke={it.color} strokeWidth="2" strokeDasharray={it.dash || ''} />}
          </svg>
          {it.label}
        </span>
      ))}
    </div>
  )
}

export default function Impact({ data, t, lang, onUpgrade }) {
  const S = data.sales
  const [table, setTable] = useState(false)
  if (!S) return <div className="panel empty">{t.impactEmpty}</div>
  const weeks = S.weeks
  const last = weeks[weeks.length - 1]
  const visitsMax = niceMax(Math.max(...weeks.flatMap((w) => [w.search_sessions, w.ai_sessions])))
  const revMax = niceMax(Math.max(...weeks.flatMap((w) => [w.ai_revenue, w.expected_revenue || 0])))
  const after = weeks.filter((w) => w.phase === 'after' && w.week !== S.monitoring_week)
  const barW = (step) => Math.max(4, Math.min(28, step * 0.6))
  const line = (x, y, key, ws = weeks) => ws.map((w) => `${ws.indexOf(w) ? 'L' : 'M'}${x(weeks.indexOf(w))},${y(w[key])}`).join(' ')

  return (
    <div className="stack">
      <section className="hero">
        <h1>{t.impactHero(S.ai_share_now, S.ai_share_start, S.weeks_span)}</h1>
        <p>{t.impactSub(Math.abs(S.search_change ?? 0))}</p>
      </section>

      <div className="figures">
        <div className="figure"><b>{money(S.ai_revenue_last, lang)}</b><span>{t.aiSalesLast}</span></div>
        {S.locked ? (
          <div className="figure span3">
            <Locked t={t} plan="gold" text={t.lockedSalesFull} onUpgrade={onUpgrade} compact />
          </div>
        ) : (
          <>
            <div className="figure">
              <b>{S.extra_revenue == null ? '–' : `${S.extra_revenue >= 0 ? '+' : ''}${money(S.extra_revenue, lang)}`}</b>
              <span>{S.revenue_lift == null ? t.extraSalesPending : t.extraSales(S.revenue_lift)}</span>
            </div>
            <div className="figure"><b>{S.lost_revenue_last == null ? '–' : money(S.lost_revenue_last, lang)}</b><span>{t.lostSales}</span></div>
            <div className="figure">
              <b>{S.misinfo_contacts_last ?? '–'}</b>
              <span>{t.misinfoContacts}{S.misinfo_contacts_start != null && ` (${t.wasN(S.misinfo_contacts_start)})`}</span>
            </div>
          </>
        )}
      </div>

      <div className="two even">
        <section className="panel">
          <div className="panel-head"><h2>{t.visitsTitle}</h2><span className="faint">{t.perWeek}</span></div>
          <Chart weeks={weeks} max={visitsMax} fmt={(v) => num(Math.round(v), lang)} marker={S.monitoring_week}
            markerLabel={t.monitoringStarted} label={t.visitsTitle}
            tooltip={(w) => <><b>{t.week} {w.week + 1}</b><br />{t.fromSearch}: {num(w.search_sessions, lang)}<br />{t.fromAi}: {num(w.ai_sessions, lang)}</>}>
            {({ x, y }) => [['search_sessions', SEARCH], ['ai_sessions', AI]].map(([k, c]) => (
              <g key={k}>
                <path d={line(x, y, k)} fill="none" stroke={c} strokeWidth="2" />
                <circle cx={x(weeks.length - 1)} cy={y(last[k])} r="4" fill={c} stroke="var(--surface)" strokeWidth="2" />
              </g>
            ))}
          </Chart>
          <Legend items={[{ label: t.fromSearch, color: SEARCH }, { label: t.fromAi, color: AI }]} />
        </section>

        <section className="panel">
          <div className="panel-head"><h2>{t.aiSalesTitle}</h2><span className="faint">{t.perWeek}</span></div>
          <Chart weeks={weeks} max={revMax} fmt={(v) => money(v, lang)} marker={S.monitoring_week}
            markerLabel={t.monitoringStarted} label={t.aiSalesTitle} inset={18}
            tooltip={(w) => <><b>{t.week} {w.week + 1}</b><br />{t.aiSales}: {money(w.ai_revenue, lang)}
              {w.phase === 'after' && w.expected_revenue != null && <><br />{t.withoutAparece}: {money(w.expected_revenue, lang)}</>}
              {w.accuracy != null && <><br />{t.accuracy}: {w.accuracy}%</>}</>}>
            {({ x, y, step }) => (
              <>
                {weeks.map((w, i) => {
                  const bw = barW(step), top = y(w.ai_revenue), h = Math.max(1, y(0) - top)
                  return <path key={w.week} fill={AI} opacity={w.phase === 'before' ? 0.45 : 1}
                    d={`M${x(i) - bw / 2},${y(0)} V${top + Math.min(4, h)} Q${x(i) - bw / 2},${top} ${x(i) - bw / 2 + 4},${top} H${x(i) + bw / 2 - 4} Q${x(i) + bw / 2},${top} ${x(i) + bw / 2},${top + Math.min(4, h)} V${y(0)} Z`} />
                })}
                {after.length > 0 && S.source === 'simulated' && !S.locked && (
                  <path d={line(x, y, 'expected_revenue', weeks.filter((w) => w.phase === 'after'))} fill="none"
                    stroke="var(--ink)" strokeWidth="2" strokeDasharray="5 4" />
                )}
              </>
            )}
          </Chart>
          <Legend items={[
            { label: t.aiSalesBefore, color: AI, bar: true, opacity: 0.45 },
            { label: t.aiSales, color: AI, bar: true },
            ...(S.source === 'simulated' && !S.locked ? [{ label: t.withoutAparece, color: 'var(--ink)', dash: '5 4' }] : []),
          ]} />
        </section>
      </div>

      <p className="note">{S.source === 'simulated' ? t.salesSimulated : t.salesImported}</p>
      <ReferralLog bizId={data.business.id} t={t} lang={lang} rows={data.referrals} readOnly onChanged={() => {}} />

      <section className="panel">
        <div className="panel-head">
          <h2>{t.weeklyNumbers}</h2>
          <button className="linkish" onClick={() => setTable(!table)}>{table ? t.hideTable : t.showTable}</button>
        </div>
        {table && (
          <div className="matrix-wrap">
            <table className="audit">
              <thead><tr><th>{t.week}</th><th>{t.fromSearch}</th><th>{t.fromAi}</th><th>{t.orders}</th><th>{t.aiSales}</th><th>{t.withoutAparece}</th><th>{t.accuracy}</th></tr></thead>
              <tbody>
                {weeks.map((w) => (
                  <tr key={w.week}>
                    <td>{w.week + 1}{w.week === S.monitoring_week ? ` · ${t.monitoringStarted}` : ''}</td>
                    <td>{num(w.search_sessions, lang)}</td><td>{num(w.ai_sessions, lang)}</td><td>{w.ai_orders}</td>
                    <td>{money(w.ai_revenue, lang)}</td>
                    <td>{w.phase === 'after' && w.expected_revenue != null ? money(w.expected_revenue, lang) : '–'}</td>
                    <td>{w.accuracy != null ? `${w.accuracy}%` : '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
