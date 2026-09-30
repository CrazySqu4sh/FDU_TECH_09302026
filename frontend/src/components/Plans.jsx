import { useEffect, useState } from 'react'
import { api } from '../api.js'

const ORDER = ['trial', 'silver', 'gold', 'enterprise']

export default function Plans({ t, data, onChanged }) {
  const [cat, setCat] = useState(null)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  useEffect(() => { api.plans().then(setCat).catch((e) => setErr(e.message)) }, [])
  if (!cat) return <p className="empty">{err || '…'}</p>
  const plans = Object.fromEntries(cat.plans.map((p) => [p.id, p]))
  const current = data?.plan?.id

  async function choose(id) {
    if (!data) return
    setBusy(id); setErr('')
    try { await api.changePlan(data.business.id, id); await onChanged() } catch (e) { setErr(e.message) } finally { setBusy('') }
  }
  const price = (p) => (p.price == null ? t.custom : p.price === 0 ? t.free : `$${p.price}`)

  return (
    <div className="stack">
      <section className="hero wide">
        <h1>{t.plansHero}</h1>
        <p>{t.plansSub}</p>
      </section>

      <div className="community">
        <strong>{t.communityTitle}</strong>
        <span>{t.communityText(cat.community_silver_price)}</span>
      </div>

      <div className="plan-grid">
        {ORDER.map((id, i) => {
          const p = plans[id]
          const prev = i ? plans[ORDER[i - 1]] : null
          const added = p.features.filter((f) => !prev?.features.includes(f))
          return (
            <section key={id} className={`plan-card ${id} ${current === id ? 'current' : ''}`}>
              <span className={`plan-chip ${id}`}>{t.planName[id]}</span>
              <div className="plan-price"><b>{price(p)}</b>{p.price ? <span>/{t.month}</span> : id === 'trial' ? <span>{t.trialDays(cat.trial_days)}</span> : null}</div>
              <p className="muted">{t.planFor[id]}</p>
              <ul className="limits">
                <li>{p.assistants ? t.nAssistants(p.assistants) : t.allAssistants}</li>
                <li>{t.nQuestions(p.journeys / 2)}</li>
                <li>{p.fix_drafts ? t.nFixes(p.fix_drafts) : t.unlimitedFixes}</li>
                <li>{t.scanFreq[p.scan_frequency]}</li>
              </ul>
              {prev && <p className="faint">{t.everythingIn(t.planName[prev.id])}</p>}
              <ul className="feats">
                {added.map((f) => <li key={f}>{t.feature[f]}</li>)}
              </ul>
              {id === 'gold' && <p className="guarantee-note">{t.guaranteeNote(cat.guarantee.accuracy, cat.guarantee.days)}</p>}
              {data && (current === id
                ? <button className="btn ghost" disabled>{t.currentPlan}</button>
                : <button className="btn" disabled={!!busy} onClick={() => choose(id)}>{id === 'enterprise' ? t.talkToUs : t.choosePlan(t.planName[id])}</button>)}
            </section>
          )
        })}
      </div>
      {err && <p className="error" role="alert">{err}</p>}
      {data && <p className="note">{t.planDemoNote(data.business.name)}</p>}

      <section className="panel">
        <div className="panel-head"><h2>{t.compare}</h2></div>
        <div className="matrix-wrap">
          <table className="compare-table">
            <thead><tr><th></th>{ORDER.map((id) => <th key={id}>{t.planName[id]}</th>)}</tr></thead>
            <tbody>
              {cat.features.map((f) => (
                <tr key={f}>
                  <td>{t.feature[f]}</td>
                  {ORDER.map((id) => <td key={id} className={plans[id].features.includes(f) ? 'yes' : 'no'}>
                    {plans[id].features.includes(f) ? '✓' : '–'}<span className="sr-only">{plans[id].features.includes(f) ? t.included : t.notIncluded}</span></td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note" style={{ marginTop: '0.75rem' }}>{t.governanceAll}</p>
      </section>
    </div>
  )
}
