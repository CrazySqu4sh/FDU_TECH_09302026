import { useState } from 'react'
import { api } from '../api.js'
import FactsEditor, { blankFact } from './FactsEditor.jsx'

const f = (o) => ({ product: '', product_es: '', label_es: '', value: '', evidence: 'owner', source: 'Owner entry', ...o })

const STARTERS = {
  ecommerce: [
    f({ product: '', label: 'Price', label_es: 'precio', category: 'price', evidence: 'system', source: 'Shopify' }),
    f({ product: '', label: 'Stock', label_es: 'inventario', value: 'in stock', category: 'stock', evidence: 'system', source: 'Shopify' }),
    f({ label: 'Shipping time', label_es: 'tiempo de envío', value: '3-5', category: 'shipping', key: 'store.shipping' }),
    f({ label: 'Return window', label_es: 'plazo de devolución', value: '30', category: 'returns', key: 'store.returns' }),
    f({ label: 'Bilingual customer support', label_es: 'atención al cliente bilingüe', value: 'yes', category: 'language', key: 'language.spanish' }),
  ],
  services: [
    f({ label: 'Saturday hours', label_es: 'horario del sábado', category: 'hours', key: 'hours.saturday' }),
    f({ label: 'Sunday hours', label_es: 'horario del domingo', category: 'hours', key: 'hours.sunday' }),
    f({ label: 'Spanish-speaking staff', label_es: 'personal que habla español', value: 'yes', category: 'language', key: 'language.spanish' }),
    f({ label: 'Phone number', label_es: 'teléfono', category: 'contact', key: 'contact.phone' }),
    blankFact('services'),
  ],
}

export default function NewBusiness({ t, onCancel, onCreated }) {
  const [segment, setSegment] = useState('ecommerce')
  const [form, setForm] = useState({ name: '', category: '', category_es: '', city: '', website: '', competitors: '' })
  const [facts, setFacts] = useState(STARTERS.ecommerce)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); setErr('') }
  const pick = (s) => { setSegment(s); setFacts(STARTERS[s]) }

  async function create() {
    if (!form.name.trim() || !form.category.trim() || !form.city.trim()) { setErr(t.required); return }
    setBusy(true)
    try {
      const { id } = await api.createBusiness({
        ...form, segment,
        competitors: form.competitors.split(',').map((s) => s.trim()).filter(Boolean),
        facts: facts.filter((x) => x.label.trim() && x.value.trim()),
      })
      onCreated(id)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <section className="panel stack">
      <h2>{t.newBizTitle}</h2>
      <fieldset className="segments">
        <legend>{t.segmentQ}</legend>
        {['ecommerce', 'services'].map((s) => (
          <label key={s} className={`segment-option ${segment === s ? 'on' : ''}`}>
            <input type="radio" name="segment" checked={segment === s} onChange={() => pick(s)} />
            <strong>{t.segment[s]}</strong>
            <span className="faint">{t.segmentHint[s]}</span>
          </label>
        ))}
      </fieldset>
      <div className="form-grid">
        <label className="field">{t.name}<input value={form.name} onChange={set('name')} /></label>
        <label className="field">{t.type}<input value={form.category} onChange={set('category')}
          placeholder={segment === 'ecommerce' ? 'handmade jewelry store' : 'bakery'} /></label>
        <label className="field">{t.typeEs}<input value={form.category_es} onChange={set('category_es')}
          placeholder={segment === 'ecommerce' ? 'tienda de joyería artesanal' : 'panadería'} /></label>
        <label className="field">{t.city}<input value={form.city} onChange={set('city')} placeholder="Houston, TX" /></label>
        <label className="field">{t.website}<input value={form.website} onChange={set('website')} /></label>
        <label className="field">{t.competitors}<input value={form.competitors} onChange={set('competitors')} /></label>
      </div>
      <div>
        <div className="panel-head">
          <h3>{t.profile}</h3>
          <button className="btn ghost small" onClick={() => setFacts([...facts, blankFact(segment)])}>{t.addFact}</button>
        </div>
        <FactsEditor facts={facts} setFacts={setFacts} t={t} segment={segment}
          onRemove={(i) => setFacts(facts.filter((_, j) => j !== i))} />
      </div>
      <div className="confirm-bar">
        <button className="btn" onClick={create} disabled={busy}>{t.create}</button>
        <button className="btn ghost" onClick={onCancel}>{t.cancel}</button>
        {err && <p className="error" role="alert">{err}</p>}
      </div>
    </section>
  )
}
