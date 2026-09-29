export const CATEGORIES = {
  ecommerce: ['price', 'stock', 'shipping', 'returns', 'service', 'language', 'contact', 'policy'],
  services: ['hours', 'price', 'service', 'language', 'contact', 'policy'],
}
const EVIDENCE = ['system', 'document', 'owner']

export const blankFact = (segment = 'services') => ({ product: '', product_es: '', label: '', label_es: '', value: '',
  category: segment === 'ecommerce' ? 'price' : 'service', evidence: 'owner', source: 'Owner entry' })

const HINTS = { hours: '08:00-16:00 or closed', price: '49.99', stock: 'in stock / out of stock', shipping: '3-5', returns: '30 or none', service: 'yes / no', language: 'yes / no' }

export default function FactsEditor({ facts, setFacts, t, onRemove, segment = 'services' }) {
  const shop = segment === 'ecommerce'
  const cats = CATEGORIES[segment] || CATEGORIES.services
  const update = (i, field, v) => setFacts(facts.map((f, j) => (j === i ? { ...f, [field]: v } : f)))
  return (
    <div className="matrix-wrap">
      <table className="edit">
        <thead>
          <tr>
            {shop && <><th>{t.product}</th><th>{t.productEs}</th></>}
            <th>{t.label}</th><th>{t.labelEs}</th><th>{t.value}</th><th>{t.category}</th>
            <th>{t.evidenceCol}</th><th>{t.source}</th><th></th>
          </tr>
        </thead>
        <tbody>
          {facts.map((f, i) => (
            <tr key={f.key || `new-${i}`}>
              {shop && <>
                <td><input aria-label={t.product} value={f.product || ''} placeholder={t.storeWide} onChange={(e) => update(i, 'product', e.target.value)} /></td>
                <td><input aria-label={t.productEs} value={f.product_es || ''} onChange={(e) => update(i, 'product_es', e.target.value)} /></td>
              </>}
              <td><input aria-label={t.label} value={f.label} onChange={(e) => update(i, 'label', e.target.value)} /></td>
              <td><input aria-label={t.labelEs} value={f.label_es || ''} onChange={(e) => update(i, 'label_es', e.target.value)} /></td>
              <td><input aria-label={t.value} value={f.value} placeholder={HINTS[f.category] || ''}
                onChange={(e) => update(i, 'value', e.target.value)} /></td>
              <td>
                <select aria-label={t.category} value={f.category} onChange={(e) => update(i, 'category', e.target.value)}>
                  {[...new Set([...cats, f.category])].map((c) => <option key={c}>{c}</option>)}
                </select>
              </td>
              <td>
                <select aria-label={t.evidenceCol} value={f.evidence} onChange={(e) => update(i, 'evidence', e.target.value)}>
                  {EVIDENCE.map((c) => <option key={c} value={c}>{t.evidence[c]}</option>)}
                </select>
              </td>
              <td><input aria-label={t.source} value={f.source || ''} onChange={(e) => update(i, 'source', e.target.value)} /></td>
              <td><button className="linkish" onClick={() => onRemove(i)}>{t.remove}</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
