import { useState } from 'react'

// Columns that look like customer records. We never need them, so we drop them before anything is sent.
const PII = /(e-?mail|correo|customer|client|cliente|buyer|comprador|address|direcci|ssn|social|card|tarjeta|birth|nacimiento|dob)/i

export function parseCsv(text) {
  const out = []
  let row = [], cell = '', quoted = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++ }
      else if (c === '"') quoted = false
      else cell += c
    } else if (c === '"') quoted = true
    else if (c === ',') { row.push(cell.trim()); cell = '' }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++
      row.push(cell.trim()); cell = ''
      if (row.some(Boolean)) out.push(row)
      row = []
    } else cell += c
  }
  row.push(cell.trim())
  if (row.some(Boolean)) out.push(row)
  return out
}

const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')

export const TEMPLATES = {
  products: 'product,product_es,price,stock\nLeather boots,botas de piel,149.00,in stock\n',
  tech: 'product,product_es,price,stock,RAM,Storage\nRefurbished ThinkPad T14,ThinkPad T14 reacondicionado,429.00,in stock,16 GB,512 GB\n',
  services: 'service,service_es,price\nRoof repair (starting at),reparación de techo (desde),350.00\nFree estimates,estimados gratis,\n',
  sales: 'phase,search_sessions,ai_sessions,ai_orders,ai_revenue\nbefore,1400,90,4,380.00\nafter,1350,120,7,690.00\n',
}

// Turns a catalog or price-list CSV into verified facts (evidence: document, source: the file name).
function toFacts(rows, segment, file) {
  const [head, ...body] = rows
  const cols = head.map((h) => h.toLowerCase())
  const dropped = head.filter((h) => PII.test(h))
  const at = (r, name) => r[cols.indexOf(name)] ?? ''
  const base = { evidence: 'document', source: `CSV: ${file}` }
  const facts = []
  const shop = segment === 'ecommerce' || segment === 'tech'
  for (const r of body) {
    if (shop) {
      const product = at(r, 'product'); if (!product) continue
      const p = { product, product_es: at(r, 'product_es') }
      const id = slug(product)
      if (at(r, 'price')) facts.push({ ...base, ...p, key: `product.${id}.price`, label: 'Price', label_es: 'precio', value: at(r, 'price').replace('$', ''), category: 'price', evidence: 'system' })
      if (at(r, 'stock')) facts.push({ ...base, ...p, key: `product.${id}.stock`, label: 'Stock', label_es: 'inventario', value: at(r, 'stock'), category: 'stock', evidence: 'system' })
      if (segment === 'tech') {
        head.forEach((h, i) => {
          if (['product', 'product_es', 'price', 'stock'].includes(cols[i]) || PII.test(h) || !r[i]) return
          facts.push({ ...base, ...p, key: `product.${id}.${slug(h)}`, label: h, label_es: h, value: r[i], category: 'spec' })
        })
      }
    } else {
      const service = at(r, 'service'); if (!service) continue
      const id = slug(service)
      facts.push({ ...base, key: `service.${id}`, product: '', product_es: '', label: service, label_es: at(r, 'service_es'), value: 'yes', category: 'service' })
      if (at(r, 'price')) facts.push({ ...base, key: `price.${id}`, product: '', product_es: '', label: service, label_es: at(r, 'service_es'), value: at(r, 'price').replace('$', ''), category: 'price' })
    }
  }
  return { facts, dropped }
}

export function downloadText(name, text, type = 'text/csv') {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type }))
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function CsvImport({ t, segment, onFacts }) {
  const [result, setResult] = useState(null)
  const [err, setErr] = useState('')
  const kind = segment === 'tech' ? 'tech' : segment === 'ecommerce' ? 'products' : 'services'

  async function read(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setErr(''); setResult(null)
    const rows = parseCsv(await file.text())
    if (rows.length < 2) { setErr(t.csvEmpty); return }
    const res = toFacts(rows, segment, file.name)
    if (!res.facts.length) { setErr(t.csvNoRows(kind === 'services' ? 'service' : 'product')); return }
    setResult(res)
    e.target.value = ''
  }

  return (
    <div className="csv">
      <div className="csv-row">
        <label className="btn ghost small file-btn">{t.csvChoose}<input type="file" accept=".csv,text/csv" onChange={read} /></label>
        <button className="linkish" type="button" onClick={() => downloadText(`aparece-${kind}-template.csv`, TEMPLATES[kind])}>{t.csvTemplate}</button>
      </div>
      <p className="faint">{t.csvHint[kind]}</p>
      {result && (
        <div className="csv-result">
          <p>{t.csvFound(result.facts.length)}</p>
          {result.dropped.length > 0 && <p className="warn">{t.csvDropped(result.dropped.join(', '))}</p>}
          <button className="btn small" type="button" onClick={() => { onFacts(result.facts); setResult(null) }}>{t.csvAdd(result.facts.length)}</button>
        </div>
      )}
      {err && <p className="error" role="alert">{err}</p>}
    </div>
  )
}
