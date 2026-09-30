import { useState } from 'react'
import { api } from '../api.js'
import FactsEditor, { blankFact } from './FactsEditor.jsx'
import CsvImport from './CsvImport.jsx'

const f = (o) => ({ product: '', product_es: '', label_es: '', value: '', evidence: 'owner', source: 'Owner entry', ...o })

const STARTERS = {
  ecommerce: [
    f({ product: '', label: 'Price', label_es: 'precio', category: 'price', evidence: 'system', source: 'Shopify' }),
    f({ product: '', label: 'Stock', label_es: 'inventario', value: 'in stock', category: 'stock', evidence: 'system', source: 'Shopify' }),
    f({ label: 'Shipping time', label_es: 'tiempo de envío', value: '3-5', category: 'shipping', key: 'store.shipping' }),
    f({ label: 'Return window', label_es: 'plazo de devolución', value: '30', category: 'returns', key: 'store.returns' }),
    f({ label: 'Bilingual customer support', label_es: 'atención al cliente bilingüe', value: 'yes', category: 'language', key: 'language.spanish' }),
  ],
  cleaning: [
    f({ label: 'Deep clean, 3 bedrooms (from)', label_es: 'limpieza profunda, 3 recámaras (desde)', category: 'price', key: 'price.deep_clean', evidence: 'document', source: 'Price sheet' }),
    f({ label: 'Bonded and insured', label_es: 'con fianza y seguro', value: 'yes', category: 'insurance', key: 'credential.insurance', evidence: 'document', source: 'Certificate of insurance' }),
    f({ label: 'Background-checked staff', label_es: 'personal con revisión de antecedentes', value: 'yes', category: 'service', key: 'service.background_check' }),
    f({ label: 'Move-out cleaning', label_es: 'limpieza de mudanza', value: 'yes', category: 'service', key: 'service.move_out' }),
    f({ label: 'Brings own supplies', label_es: 'trae sus propios productos', value: 'yes', category: 'service', key: 'service.supplies' }),
    f({ label: 'Service area', label_es: 'zona de servicio', category: 'service_area', key: 'area.service' }),
    f({ label: 'Phone number', label_es: 'teléfono', category: 'contact', key: 'contact.phone' }),
    f({ label: 'Spanish-speaking team', label_es: 'equipo que habla español', value: 'yes', category: 'language', key: 'language.spanish' }),
  ],
  trades: [
    f({ label: 'Contractor license / registration', label_es: 'licencia de contratista', category: 'license', key: 'credential.license', evidence: 'document', source: 'License record' }),
    f({ label: 'Liability insurance', label_es: 'seguro de responsabilidad', value: 'yes', category: 'insurance', key: 'credential.insurance', evidence: 'document', source: 'Certificate of insurance' }),
    f({ label: 'Service area', label_es: 'zona de servicio', category: 'service_area', key: 'area.service' }),
    f({ label: 'Free estimates', label_es: 'estimados gratis', value: 'yes', category: 'service', key: 'service.free_estimate' }),
    f({ label: 'Phone number', label_es: 'teléfono', category: 'contact', key: 'contact.phone' }),
    f({ label: 'Spanish-speaking crew', label_es: 'equipo que habla español', value: 'yes', category: 'language', key: 'language.spanish' }),
  ],
  tech: [
    f({ product: '', label: 'Price', label_es: 'precio', category: 'price', evidence: 'system', source: 'Shopify' }),
    f({ product: '', label: 'Stock', label_es: 'inventario', value: 'in stock', category: 'stock', evidence: 'system', source: 'Shopify' }),
    f({ product: '', label: 'RAM', label_es: 'memoria RAM', category: 'spec', evidence: 'document', source: 'Manufacturer spec sheet' }),
    f({ label: 'Warranty', label_es: 'garantía', value: '12', category: 'warranty', key: 'store.warranty', evidence: 'document', source: 'Warranty policy page' }),
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
  const [segment, setSegment] = useState('cleaning')
  const [form, setForm] = useState({ name: '', category: '', category_es: '', city: '', website: '', competitors: '' })
  const [facts, setFacts] = useState(STARTERS.cleaning)
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
        {['cleaning', 'trades', 'services', 'ecommerce', 'tech'].map((s) => (
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
          placeholder={{ ecommerce: 'handmade jewelry store', tech: 'refurbished laptop store', trades: 'roofing contractor', cleaning: 'house cleaning service' }[segment] || 'bakery'} /></label>
        <label className="field">{t.typeEs}<input value={form.category_es} onChange={set('category_es')}
          placeholder={{ ecommerce: 'tienda de joyería artesanal', tech: 'tienda de laptops reacondicionadas', trades: 'techero', cleaning: 'servicio de limpieza de casas' }[segment] || 'panadería'} /></label>
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
      <div className="import-box">
        <h3>{segment === 'ecommerce' || segment === 'tech' ? t.importProducts : t.importServices}</h3>
        <CsvImport t={t} segment={segment} onFacts={(rows) => setFacts([...facts.filter((x) => x.value.trim()), ...rows])} />
      </div>
      <div className="ask-note">
        <strong>{t.weAsk}</strong> {t.weAskShort} <strong>{t.weNever}</strong> {t.weNeverShort}
      </div>
      <div className="confirm-bar">
        <button className="btn" onClick={create} disabled={busy}>{t.create}</button>
        <button className="btn ghost" onClick={onCancel}>{t.cancel}</button>
        {err && <p className="error" role="alert">{err}</p>}
      </div>
    </section>
  )
}
