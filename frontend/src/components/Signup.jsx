import { useState } from 'react'
import { api } from '../api.js'

const SEGMENTS = ['cleaning', 'trades', 'services', 'ecommerce', 'tech']
const REASONS = ['fewer_calls', 'competitors', 'wrong_info', 'curious', 'spanish', 'referred', 'other']
const ISSUES = ['not_found', 'wrong_info', 'website', 'no_time', 'reviews', 'spanish', 'unsure']
const ROLES = ['owner', 'manager', 'marketing', 'other']

// Sign-up before the free scan: who they are, why they came, and what they think we can help with.
export default function Signup({ t, lang, initialUrl, onDone }) {
  const S = t.signup
  const [f, setF] = useState({ contact_name: '', email: '', phone: '', role: 'owner', business_name: '', website: initialUrl || '',
    city: '', segment: 'cleaning', reasons: [], issues: [], issue_text: '', help_text: '', consent: false })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => { setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }); setErr('') }
  const toggle = (k, v) => setF({ ...f, [k]: f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v] })

  async function submit(e) {
    e.preventDefault()
    if (f.contact_name.trim().length < 2 || !/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(f.email.trim()) || f.business_name.trim().length < 2 || !/\.[a-z]{2,}/i.test(f.website)) {
      setErr(S.required); return
    }
    if (!f.consent) { setErr(S.consentNeeded); return }
    setBusy(true)
    try { const { id } = await api.createLead({ ...f, lang }); onDone({ id, ...f }) }
    catch (e2) { setErr(e2.message); setBusy(false) }
  }

  return (
    <form className="signup stack" onSubmit={submit}>
      <section className="hero wide">
        <p className="eyebrow">{S.eyebrow}</p>
        <h1>{S.title}</h1>
        <p>{S.sub}</p>
      </section>

      <section className="panel stack">
        <h2>{S.aboutYou}</h2>
        <div className="form-grid">
          <label className="field">{S.name} *<input value={f.contact_name} onChange={set('contact_name')} autoComplete="name" /></label>
          <label className="field">{S.email} *<input type="email" value={f.email} onChange={set('email')} autoComplete="email" /></label>
          <label className="field">{S.phone}<input type="tel" value={f.phone} onChange={set('phone')} autoComplete="tel" /></label>
          <label className="field">{S.role}<select value={f.role} onChange={set('role')}>{ROLES.map((r) => <option key={r} value={r}>{S.roles[r]}</option>)}</select></label>
        </div>
      </section>

      <section className="panel stack">
        <h2>{S.yourBusiness}</h2>
        <div className="form-grid">
          <label className="field">{S.bizName} *<input value={f.business_name} onChange={set('business_name')} autoComplete="organization" /></label>
          <label className="field">{S.website} *<input value={f.website} onChange={set('website')} placeholder="yourbusiness.com" /></label>
          <label className="field">{S.city}<input value={f.city} onChange={set('city')} placeholder="Houston, TX" /></label>
          <label className="field">{t.type}<select value={f.segment} onChange={set('segment')}>{SEGMENTS.map((s) => <option key={s} value={s}>{t.segment[s]}</option>)}</select></label>
        </div>
      </section>

      <section className="panel stack">
        <div><h2>{S.whyTitle}</h2><p className="faint">{S.pickAny}</p></div>
        <div className="choice-grid">
          {REASONS.map((r) => (
            <label key={r} className={`choice ${f.reasons.includes(r) ? 'on' : ''}`}>
              <input type="checkbox" checked={f.reasons.includes(r)} onChange={() => toggle('reasons', r)} />{S.reasons[r]}
            </label>
          ))}
        </div>
        <div><h2>{S.issueTitle}</h2><p className="faint">{S.pickAny}</p></div>
        <div className="choice-grid">
          {ISSUES.map((r) => (
            <label key={r} className={`choice ${f.issues.includes(r) ? 'on' : ''}`}>
              <input type="checkbox" checked={f.issues.includes(r)} onChange={() => toggle('issues', r)} />{S.issues[r]}
            </label>
          ))}
        </div>
        <label className="field">{S.issueText}<textarea rows={3} value={f.issue_text} onChange={set('issue_text')} placeholder={S.issuePh} /></label>
        <label className="field">{S.helpText}<textarea rows={3} value={f.help_text} onChange={set('help_text')} placeholder={S.helpPh} /></label>
      </section>

      <section className="panel stack">
        <label className="consent"><input type="checkbox" checked={f.consent} onChange={set('consent')} /> <span>{S.consent}</span></label>
        <p className="faint">{S.whyWeAsk}</p>
        <div className="confirm-bar" style={{ marginTop: 0 }}>
          <button className="btn marigold" type="submit" disabled={busy}>{busy ? S.starting : S.submit}</button>
          {err && <p className="error" role="alert">{err}</p>}
        </div>
      </section>
    </form>
  )
}
