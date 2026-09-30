import { ASSISTANT_NAMES } from '../api.js'
import Locked from './Locked.jsx'

export function Bars({ items }) {
  return (
    <div className="bars">
      {items.map((it) => (
        <div className="bar" key={it.label}>
          <span>{it.label}</span>
          <div className="track"><div className={`fill ${it.value < 40 ? 'low' : ''}`} style={{ width: `${it.value}%` }} /></div>
          <b>{it.value}</b>
        </div>
      ))}
    </div>
  )
}

function Trend({ scans, t }) {
  const W = 420, H = 150, pad = 28
  const pts = scans.slice(-8)
  const x = (i) => pad + (pts.length === 1 ? (W - 2 * pad) / 2 : (i * (W - 2 * pad)) / (pts.length - 1))
  const y = (v) => H - pad - ((v ?? 0) / 100) * (H - 2 * pad)
  const line = (key) => pts.map((s, i) => `${i ? 'L' : 'M'}${x(i)},${y(s[key])}`).join(' ')
  const series = [
    { key: 'inclusion_rate', label: t.inclusion, color: 'var(--ink)', dash: '' },
    { key: 'inclusion_es', label: t.spanish, color: 'var(--marigold)', dash: '' },
    { key: 'fact_accuracy', label: t.accuracy, color: 'var(--match)', dash: '5 4' },
  ]
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={t.trend}>
        {[0, 50, 100].map((v) => (
          <g key={v}>
            <line x1={pad} x2={W - pad} y1={y(v)} y2={y(v)} stroke="var(--line)" />
            <text x={4} y={y(v) + 4} fontSize="11" fill="var(--ink-faint)">{v}</text>
          </g>
        ))}
        {series.map((s) => (
          <g key={s.key}>
            <path d={line(s.key)} fill="none" stroke={s.color} strokeWidth="2.5" strokeDasharray={s.dash} />
            {pts.map((p, i) => <circle key={i} cx={x(i)} cy={y(p[s.key])} r="3.5" fill={s.color} />)}
          </g>
        ))}
      </svg>
      <div className="tags" style={{ marginTop: '0.5rem' }}>
        {series.map((s) => (
          <span key={s.key} className="faint" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginRight: 12 }}>
            <svg width="18" height="6" aria-hidden="true"><line x1="0" x2="18" y1="3" y2="3" stroke={s.color} strokeWidth="3" strokeDasharray={s.dash} /></svg>
            {s.label}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function Overview({ data, t, onUpgrade }) {
  const L = data.latest
  if (!L) return <div className="panel empty">{t.noScan}</div>
  const active = data.incidents.filter((i) => ['open', 'needs_review'].includes(i.status)).length
  const res = data.avg_resolution_hours
  const gap = L.language_gap ?? 0
  const shop = data.business.segment === 'ecommerce' || data.business.segment === 'tech'
  const has = (f) => data.plan.features.includes(f)
  const g = data.plan.guarantee
  return (
    <div className="stack">
      <section className="hero">
        {shop ? (
          <>
            <h1>{t.heroShop(L.fact_accuracy ?? 0)}</h1>
            <p>{t.heroShopSub(L.inclusion_rate, L.inclusion_es ?? 0)}</p>
          </>
        ) : (
          <>
            <h1>{t.heroNamed(L.inclusion_rate)}</h1>
            {L.inclusion_es != null && (
              <p>{gap >= 10 ? t.heroSpanish(L.inclusion_en, L.inclusion_es) : t.heroSpanishOk(L.inclusion_en, L.inclusion_es)}</p>
            )}
          </>
        )}
      </section>

      {L.responses < 12 && <p className="sim-bar">{t.smallSample(L.responses)}</p>}

      <div className="figures">
        {shop
          ? <div className="figure"><b>{L.inclusion_rate}%</b><span>{t.inclusion}</span></div>
          : <div className="figure"><b>{L.fact_accuracy ?? '–'}%</b><span>{t.accuracy}</span></div>}
        <div className="figure"><b>{L.missed_opportunities}</b><span>{t.missed}: {t.missedHint}</span>
          {!has('missed_opportunities') && <span className="lock-hint">🔒 {t.lockedMissedShort}</span>}</div>
        <div className="figure"><b>{active}</b><span>{t.openIssues}</span></div>
        <div className="figure"><b>{res == null ? '–' : res < 1 ? '<1 h' : res < 48 ? `${res} h` : `${Math.round(res / 24)} d`}</b><span>{t.resolution}</span></div>
      </div>

      {g && (
        <section className={`guarantee ${g.met ? 'met' : ''}`}>
          <div>
            <strong>{t.guaranteeTitle(g.target, g.days)}</strong>
            <p>{g.met ? t.guaranteeMet(g.accuracy) : t.guaranteeProgress(g.accuracy ?? 0, g.target, g.day, g.days)}</p>
          </div>
          <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={g.accuracy ?? 0} aria-label={t.accuracy}>
            <div style={{ width: `${g.accuracy ?? 0}%` }} />
            <span style={{ left: `${g.target}%` }} />
          </div>
        </section>
      )}

      <div className="two">
        <div className="stack">
          {shop && (has('product_accuracy') ? L.product_accuracy.length > 0 && (
            <section className="panel">
              <div className="panel-head"><h2>{t.productAccuracy}</h2><span className="faint">{t.productAccuracyHint}</span></div>
              <Bars items={L.product_accuracy.map((p) => ({ label: p.product, value: p.accuracy }))} />
            </section>
          ) : <Locked t={t} plan="gold" text={t.lockedProduct} onUpgrade={onUpgrade} compact />)}
          <section className="panel">
            <div className="panel-head">
              <h2>{shop ? t.byNeedShop : t.byNeed}</h2>
              <span className="faint">{shop ? t.byNeedShopHint : t.byNeedHint}</span>
            </div>
            <Bars items={L.by_need.map((n) => ({ label: n.need, value: n.inclusion }))} />
          </section>
        </div>
        <div className="stack">
          <section className="panel">
            <div className="panel-head"><h2>{t.trend}</h2></div>
            {has('scan_history') ? <Trend scans={data.scans} t={t} />
              : <Locked t={t} plan="silver" text={t.lockedHistory} onUpgrade={onUpgrade} compact />}
          </section>
          <section className="panel">
            <div className="panel-head"><h2>{t.byAssistant}</h2></div>
            <Bars items={Object.entries(L.by_assistant).map(([k, v]) => ({ label: ASSISTANT_NAMES[k] || k, value: v }))} />
          </section>
        </div>
      </div>
    </div>
  )
}
