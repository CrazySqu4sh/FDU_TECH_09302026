import { useState } from 'react'
import { api } from '../api.js'
import { parseCsv } from './CsvImport.jsx'

const SEGMENTS = ['cleaning', 'restaurant', 'trades', 'services', 'ecommerce', 'tech']
const copy = (text) => { try { navigator.clipboard.writeText(text) } catch { /* clipboard unavailable */ } }

export function Copyable({ label, text, t, code = false }) {
  const [done, setDone] = useState(false)
  return (
    <div className="copyable">
      <div className="copy-head"><strong>{label}</strong>
        <button className="linkish" onClick={() => { copy(text); setDone(true); setTimeout(() => setDone(false), 1500) }}>{done ? t.copied : t.copy}</button>
      </div>
      {code ? <pre className="code">{text}</pre> : <pre className="plain">{text}</pre>}
    </div>
  )
}

// Website check: how an AI assistant reads the site, what to improve, and ready-to-paste fixes.
export default function SiteCheck({ t, business, prefill, onRunCheck, onStartTrial }) {
  const src = business || prefill
  const [form, setForm] = useState({
    url: src?.website || '', name: src?.name || '', city: src?.city || '',
    segment: src?.segment && SEGMENTS.includes(src.segment) ? src.segment : 'cleaning',
  })
  const [items, setItems] = useState([])
  const [fileName, setFileName] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [r, setR] = useState(null)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function readCsv(e) {
    const file = e.target.files?.[0]; if (!file) return
    const [head, ...body] = parseCsv(await file.text())
    const cols = head.map((h) => h.toLowerCase())
    const at = (row, ...names) => { const i = cols.findIndex((c) => names.includes(c)); return i >= 0 ? row[i] || '' : '' }
    setItems(body.map((row) => ({ name: at(row, 'service', 'product', 'name', 'servicio', 'producto'),
      name_es: at(row, 'service_es', 'product_es', 'name_es'), price: at(row, 'price', 'precio').replace('$', '') }))
      .filter((x) => x.name))
    setFileName(file.name); e.target.value = ''
  }
  async function run(e) {
    e.preventDefault()
    if (!form.url.trim()) { setErr(t.siteNeedUrl); return }
    setBusy(true); setErr(''); setR(null)
    try {
      const res = await api.siteAudit({ ...form, items, business_id: business?.id ?? null })
      if (!res.ok) setErr(t.scan.errorKind[res.error_kind] ? `${t.scan.errorKind[res.error_kind]}${res.marketplace ? ` ${t.scan.marketplaceTip}` : ''}` : t.siteUnreachable(res.errors?.[0] || res.url)); else setR(res)
    } catch (e2) { setErr(e2.message) } finally { setBusy(false) }
  }

  const failed = r ? r.checks.filter((c) => !c.pass).sort((a, b) => b.weight - a.weight) : []
  const grade = r ? (r.score >= 80 ? 'good' : r.score >= 55 ? 'ok' : 'low') : ''
  return (
    <div className="stack">
      <section className="hero wide">
        <h1>{t.siteHero}</h1>
        <p>{t.siteSub}</p>
      </section>

      <form className="panel stack" onSubmit={run}>
        <div className="form-grid">
          <label className="field">{t.siteUrl}<input value={form.url} onChange={set('url')} placeholder="brillocleaning.com" /></label>
          <label className="field">{t.name}<input value={form.name} onChange={set('name')} placeholder="Brillo Cleaning Co." /></label>
          <label className="field">{t.city}<input value={form.city} onChange={set('city')} placeholder="Houston, TX" /></label>
          <label className="field">{t.type}
            <select value={form.segment} onChange={set('segment')}>{SEGMENTS.map((s) => <option key={s} value={s}>{t.segment[s]}</option>)}</select>
          </label>
        </div>
        <div>
          <strong>{t.siteCsv}</strong>
          <div className="csv-row" style={{ marginTop: '0.4rem' }}>
            <label className="btn ghost small file-btn">{t.csvChoose}<input type="file" accept=".csv,text/csv" onChange={readCsv} /></label>
            <span className="faint">{fileName ? t.siteCsvLoaded(items.length, fileName) : t.siteCsvHint}</span>
          </div>
        </div>
        <div className="confirm-bar" style={{ marginTop: 0 }}>
          <button className="btn marigold" type="submit" disabled={busy}>{busy ? t.siteReading : t.siteRun}</button>
          <span className="faint">{t.siteFree}</span>
          {err && <p className="error" role="alert">{err}</p>}
        </div>
      </form>

      {r && (
        <>
          <section className={`score-card ${grade}`}>
            <div className="score-num"><b>{r.score}</b><span>/100</span></div>
            <div>
              <h2>{t.siteScoreTitle}</h2>
              <p>{t.siteScoreText(grade, failed.length)}</p>
              <div className="meter"><div style={{ width: `${r.score}%` }} /></div>
              <p className="faint">{t.sitePages(r.pages_read.length)}{r.simulated && <span className="tag">{t.simulatedTag}</span>}</p>
            </div>
          </section>

          {failed.length > 0 && (
            <section className="panel">
              <div className="panel-head"><h2>{t.siteTop}</h2><span className="faint">{t.siteTopHint}</span></div>
              <div className="top-fixes">
                {failed.slice(0, 3).map((c, i) => (
                  <div key={c.id} className="top-fix">
                    <span className="n">{i + 1}</span>
                    <div><strong>{t.siteCheck[c.id].title}</strong><p>{t.siteCheck[c.id].fix(c.detail)}</p>
                      <p className="faint">{t.siteWhy}: {t.siteCheck[c.id].why} <b>+{c.weight} {t.pts}</b></p></div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <div className="two even">
            <section className="panel">
              <div className="panel-head"><h2>{t.siteAll}</h2></div>
              <ul className="site-checks">
                {r.checks.map((c) => (
                  <li key={c.id} className={c.pass ? 'pass' : 'fail'}>
                    <span className="mark">{c.pass ? '✓' : '✕'}</span>
                    <div><strong>{t.siteCheck[c.id].title}</strong>
                      <p className="faint">{c.pass ? t.siteCheck[c.id].ok(c.detail) : t.siteCheck[c.id].why}</p></div>
                  </li>
                ))}
              </ul>
              {r.training_bots_blocked.length > 0 && <p className="note">{t.siteTraining(r.training_bots_blocked.join(', '))}</p>}
            </section>
            <section className="panel">
              <div className="panel-head"><h2>{t.siteFound}</h2><span className="faint">{t.siteFoundHint}</span></div>
              <table className="audit"><tbody>
                <tr><td>{t.siteF.phone}</td><td>{r.found.phones.join(', ') || '—'}</td></tr>
                <tr><td>{t.siteF.prices}</td><td>{r.found.prices.map((p) => `${p.label}: $${p.value}`).join(' · ') || '—'}</td></tr>
                <tr><td>{t.siteF.hours}</td><td>{r.found.hours.join(' · ') || '—'}</td></tr>
                <tr><td>{t.siteF.services}</td><td>{r.found.services.map((s) => s.label).join(', ') || '—'}</td></tr>
                <tr><td>{t.siteF.area}</td><td>{r.found.area || '—'}</td></tr>
                <tr><td>{t.siteF.trust}</td><td>{r.found.trust.map((x) => t.siteTrust[x]).join(', ') || '—'}</td></tr>
                <tr><td>{t.siteF.spanish}</td><td>{r.found.spanish ? t.yes : t.no}</td></tr>
                <tr><td>{t.siteF.structured}</td><td>{r.found.jsonld_types.slice(0, 5).join(', ') || '—'}</td></tr>
              </tbody></table>
            </section>
          </div>

          {r.facts && (
            <section className="panel">
              <div className="panel-head"><h2>{t.siteFacts}</h2><span className="faint">{t.siteFactsHint}</span></div>
              <table className="audit"><tbody>
                {r.facts.map((f) => (
                  <tr key={f.key}><td>{f.label}</td><td><strong>{f.value}</strong></td><td>{f.found ?? '—'}</td>
                    <td><span className={`verdict ${f.status === 'match' ? 'match' : f.status === 'different' ? 'wrong' : 'needs_review'}`}>{t.siteFactStatus[f.status]}</span></td></tr>
                ))}
              </tbody></table>
            </section>
          )}

          {r.items.length > 0 && (
            <section className="panel">
              <div className="panel-head"><h2>{t.siteItems}</h2><span className="faint">{t.siteItemsHint(r.items.filter((i) => !i.on_site).length, r.items.length)}</span></div>
              <table className="audit">
                <thead><tr><th>{t.siteItem}</th><th>{t.siteOnSite}</th><th>{t.sitePrice}</th><th>{t.siteEs}</th></tr></thead>
                <tbody>{r.items.map((i) => (
                  <tr key={i.name}>
                    <td>{i.name}{i.price ? ` · $${i.price}` : ''}</td>
                    <td>{i.on_site ? <span className="verdict match">{t.yes}</span> : <span className="verdict wrong">{t.siteMissing}</span>}</td>
                    <td>{i.price_matches == null ? '—' : i.price_matches ? <span className="verdict match">{t.match}</span> : <span className="verdict wrong">{t.siteDiffPrice}</span>}</td>
                    <td>{i.spanish_on_site ? <span className="verdict match">{t.yes}</span> : <span className="faint">{t.no}</span>}</td>
                  </tr>
                ))}</tbody>
              </table>
            </section>
          )}

          <section className="panel stack">
            <div className="panel-head" style={{ marginBottom: 0 }}><h2>{t.siteFixes}</h2><span className="faint">{t.siteFixesFrom[r.fixes.source]} {t.siteFixesHint}</span></div>
            <div className="two even">
              <Copyable t={t} label={t.siteFaqEn} text={r.fixes.faq_en.join('\n')} />
              <Copyable t={t} label={t.siteFaqEs} text={r.fixes.faq_es.join('\n')} />
            </div>
            <Copyable t={t} label={t.siteTitleMeta} text={`${r.fixes.title}\n${r.fixes.description}`} />
            <Copyable t={t} code label={t.siteJsonld} text={`<script type="application/ld+json">\n${JSON.stringify(r.fixes.jsonld, null, 2)}\n</script>`} />
          </section>

          {!business && (
            <section className="cta">
              <div><h2>{t.siteCtaTitle}</h2><p>{t.siteCtaText(r.suggested_facts.length)}</p></div>
              <div className="cta-actions">
                <button className="btn marigold" onClick={() => onStartTrial({ ...form, website: r.url, facts: r.suggested_facts })}>{t.siteCtaTrial}</button>
                <button className="btn ghost" onClick={() => onRunCheck({ ...form })}>{t.siteCtaCheck}</button>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
