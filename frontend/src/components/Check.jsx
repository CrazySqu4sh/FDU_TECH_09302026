import { useState } from 'react'
import { api, ASSISTANT_NAMES } from '../api.js'
import { Bars } from './Overview.jsx'
import { pretty } from './Matrix.jsx'

// One or two facts per business type that customers ask about most, so the check can spot wrong answers.
const QUICK = {
  cleaning: [
    { label: 'Deep clean, 3 bedrooms (from)', label_es: 'limpieza profunda, 3 recámaras (desde)', category: 'price', placeholder: '180' },
    { label: 'Service area', label_es: 'zona de servicio', category: 'service_area', placeholder: 'Houston, Bellaire, Katy' },
  ],
  trades: [
    { label: 'Contractor license / registration', label_es: 'licencia de contratista', category: 'license', placeholder: 'DAL-CR-48213' },
    { label: 'Service area', label_es: 'zona de servicio', category: 'service_area', placeholder: 'Dallas, Irving, Garland' },
  ],
  services: [
    { label: 'Phone number', label_es: 'teléfono', category: 'contact', placeholder: '(312) 555-0188' },
    { label: 'Saturday hours', label_es: 'horario del sábado', category: 'hours', placeholder: '08:00-16:00 or closed' },
  ],
  ecommerce: [
    { label: 'Return window', label_es: 'plazo de devolución', category: 'returns', placeholder: '30 or none' },
    { label: 'Shipping time', label_es: 'tiempo de envío', category: 'shipping', placeholder: '3-5' },
  ],
  tech: [
    { label: 'Warranty', label_es: 'garantía', category: 'warranty', placeholder: '12 (months)' },
    { label: 'Return window', label_es: 'plazo de devolución', category: 'returns', placeholder: '30 or none' },
  ],
}

export default function Check({ t, lang, onStarted, onPlans, prefill }) {
  const [segment, setSegment] = useState(prefill?.segment || 'cleaning')
  const [form, setForm] = useState({ name: prefill?.name || '', category: prefill?.category || '', category_es: '', city: prefill?.city || '', competitors: '' })
  const [values, setValues] = useState({})
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [res, setRes] = useState(null)
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); setErr('') }

  async function run(e) {
    e.preventDefault()
    if (!form.name.trim() || !form.category.trim() || !form.city.trim()) { setErr(t.required); return }
    setBusy(true); setErr('')
    try {
      setRes(await api.check({
        ...form, segment,
        competitors: form.competitors.split(',').map((s) => s.trim()).filter(Boolean),
        facts: QUICK[segment].map((q, i) => ({ label: q.label, label_es: q.label_es, category: q.category, value: values[i] || '' }))
          .filter((f) => f.value.trim()),
      }))
    } catch (e2) { setErr(e2.message) } finally { setBusy(false) }
  }
  async function start() {
    setBusy(true)
    try { const { id } = await api.startTrial(res.id); await onStarted(id) } catch (e) { setErr(e.message); setBusy(false) }
  }

  if (res) {
    const gap = (res.inclusion_en ?? 0) - (res.inclusion_es ?? 0)
    return (
      <div className="stack">
        <section className="hero wide">
          <h1>{t.checkResult(form.name, res.inclusion)}</h1>
          <p>{gap >= 10 ? t.heroSpanish(res.inclusion_en, res.inclusion_es) : t.heroSpanishOk(res.inclusion_en, res.inclusion_es)}</p>
        </section>
        <div className="figures">
          <div className="figure"><b>{res.answers}</b><span>{t.answersChecked}</span></div>
          <div className="figure"><b>{res.missed}</b><span>{t.missed}: {t.missedHint}</span></div>
          <div className="figure"><b>{res.facts.length ? res.wrong_facts : '–'}</b><span>{res.facts.length ? t.wrongAnswersFound : t.addFactsToCheck}</span></div>
        </div>

        <section className="cta">
          <div>
            <h2>{t.ctaTitle}</h2>
            <p>{t.ctaText}</p>
          </div>
          <div className="cta-actions">
            <button className="btn marigold" onClick={start} disabled={busy}>{t.startTrial}</button>
            <button className="btn ghost" onClick={onPlans}>{t.seePlans}</button>
          </div>
        </section>

        <div className="two even">
          <section className="panel">
            <div className="panel-head"><h2>{t.namedInstead}</h2></div>
            {res.named_instead.length === 0 ? <p className="muted">{t.nobodyInstead}</p> : (
              <ol className="journey-list">
                {res.named_instead.map((c) => <li key={c.name}><strong>{c.name}</strong> <span className="faint">· {t.nTimes(c.count)}</span></li>)}
              </ol>
            )}
          </section>
          <section className="panel">
            <div className="panel-head"><h2>{t.byAssistant}</h2></div>
            <Bars items={Object.entries(res.by_assistant).map(([k, v]) => ({ label: ASSISTANT_NAMES[k] || k, value: v }))} />
          </section>
        </div>

        <section className="panel">
          <div className="panel-head"><h2>{t.byQuestion}</h2><span className="faint">{t.byQuestionHint}</span></div>
          <table className="audit">
            <thead><tr><th>{t.question}</th><th>EN</th><th>ES</th></tr></thead>
            <tbody>
              {res.by_question.map((q) => (
                <tr key={q.category}><td>{t.checkCategory[q.category] || q.category}</td><td>{q.en}%</td><td>{q.es}%</td></tr>
              ))}
            </tbody>
          </table>
        </section>

        {res.facts.map((f) => (
          <section className="panel" key={f.label}>
            <div className="panel-head"><h2>{f.label}</h2><span className="faint">{t.youSaid}: {pretty(f.category, f.value, lang)}</span></div>
            {f.said.length === 0 ? <p className="muted">{t.noAssistantMentioned}</p> : (
              <table className="audit">
                <tbody>
                  {f.said.map((s) => (
                    <tr key={s.provider}>
                      <td>{ASSISTANT_NAMES[s.provider] || s.provider}</td>
                      <td>{pretty(f.category, s.value, lang)}</td>
                      <td><span className={`verdict ${s.match === false ? 'wrong' : s.match ? 'match' : 'needs_review'}`}>
                        {s.match === false ? t.wrong : s.match ? t.match : t.needs_review}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        ))}

        {res.sample && (
          <section className="panel">
            <div className="panel-head"><h2>{t.sampleAnswer}</h2><span className="faint">{ASSISTANT_NAMES[res.sample.provider]}</span></div>
            <p className="muted" style={{ marginBottom: '0.5rem' }}>“{res.sample.question}”</p>
            <div className="answer"><pre>{res.sample.text}</pre></div>
          </section>
        )}
        {res.mode === 'demo' && <p className="note">{t.checkSimulated}</p>}
        <button className="linkish" onClick={() => setRes(null)}>{t.checkAnother}</button>
      </div>
    )
  }

  return (
    <div className="stack">
      <section className="hero wide">
        <h1>{t.checkHero}</h1>
        <p>{t.checkSub}</p>
      </section>
      <form className="panel stack" onSubmit={run}>
        <fieldset className="segments">
          <legend>{t.segmentQ}</legend>
          {['cleaning', 'trades', 'services', 'ecommerce', 'tech'].map((s) => (
            <label key={s} className={`segment-option ${segment === s ? 'on' : ''}`}>
              <input type="radio" name="check-segment" checked={segment === s} onChange={() => { setSegment(s); setValues({}) }} />
              <strong>{t.segment[s]}</strong>
              <span className="faint">{t.segmentHint[s]}</span>
            </label>
          ))}
        </fieldset>
        <div className="form-grid">
          <label className="field">{t.name}<input value={form.name} onChange={set('name')} placeholder={{ trades: 'Hernández Roofing', cleaning: 'Brillo Cleaning Co.' }[segment] || 'Panadería La Estrella'} /></label>
          <label className="field">{t.type}<input value={form.category} onChange={set('category')}
            placeholder={{ ecommerce: 'handmade jewelry store', tech: 'refurbished laptop store', trades: 'roofing contractor', cleaning: 'house cleaning service' }[segment] || 'bakery'} /></label>
          <label className="field">{t.typeEs}<input value={form.category_es} onChange={set('category_es')}
            placeholder={{ ecommerce: 'tienda de joyería artesanal', tech: 'tienda de laptops reacondicionadas', trades: 'techero', cleaning: 'servicio de limpieza de casas' }[segment] || 'panadería'} /></label>
          <label className="field">{t.city}<input value={form.city} onChange={set('city')} placeholder="Chicago, IL" /></label>
          <label className="field">{t.competitorsOptional}<input value={form.competitors} onChange={set('competitors')} /></label>
        </div>
        <div>
          <h3 style={{ marginBottom: '0.25rem' }}>{t.quickFacts}</h3>
          <p className="faint" style={{ marginBottom: '0.6rem' }}>{t.quickFactsHint}</p>
          <div className="form-grid">
            {QUICK[segment].map((q, i) => (
              <label key={q.label} className="field">{lang === 'es' ? q.label_es : q.label}
                <input value={values[i] || ''} placeholder={q.placeholder} onChange={(e) => setValues({ ...values, [i]: e.target.value })} />
              </label>
            ))}
          </div>
        </div>
        <div className="confirm-bar">
          <button className="btn marigold" type="submit" disabled={busy}>{busy ? t.checking : t.runCheck}</button>
          <span className="faint">{t.checkPrivacy}</span>
          {err && <p className="error" role="alert">{err}</p>}
        </div>
      </form>
    </div>
  )
}
