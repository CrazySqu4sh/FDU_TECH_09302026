import { useEffect, useState } from 'react'
import { api } from '../api.js'
import CsvImport, { TEMPLATES, downloadText, parseCsv } from './CsvImport.jsx'
import ReferralLog from './ReferralLog.jsx'

const DATA_EVENTS = ['facts_confirmed', 'data_exported', 'sales_imported', 'plan_changed', 'fact_deleted', 'business_created', 'trial_started', 'evidence_exported', 'manual_scan', 'referrals_logged', 'facts_verified']

export default function Privacy({ data, t, lang, onChanged, onDeleted }) {
  const biz = data.business
  const [name, setName] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [confirm, setConfirm] = useState('')
  const [events, setEvents] = useState([])
  useEffect(() => { api.audit(biz.id).then((a) => setEvents(a.filter((e) => DATA_EVENTS.includes(e.action)).slice(0, 8))).catch(() => {}) }, [biz.id, data])

  const done = (m) => { setMsg(m); setErr('') }
  async function addFacts(rows) {
    if (!name.trim()) { setErr(t.approverRequired); return }
    // Reuse the existing fact when the same thing is already in the profile, so imports update instead of duplicating.
    const norm = (s) => (s || '').toLowerCase().replace(/\(.*?\)/g, '').replace(/[^a-z0-9áéíóúñ]+/g, ' ').trim()
    const facts = rows.map((f) => {
      const same = data.facts.find((x) => x.category === f.category && norm(x.product) === norm(f.product)
        && (norm(x.label) === norm(f.label) || x.key === f.key))
      return same ? { ...f, key: same.key, label: same.label, label_es: same.label_es || f.label_es } : f
    })
    try { await api.confirmFacts(biz.id, facts, name); done(t.csvSaved(facts.length)); await onChanged() } catch (e) { setErr(e.message) }
  }
  async function importSales(e) {
    const file = e.target.files?.[0]; if (!file) return
    e.target.value = ''
    const [head, ...body] = parseCsv(await file.text())
    const cols = head.map((h) => h.toLowerCase())
    const need = ['search_sessions', 'ai_sessions', 'ai_orders', 'ai_revenue']
    if (!need.every((c) => cols.includes(c))) { setErr(t.salesCsvColumns(need.join(', '))); return }
    const weeks = body.map((r) => ({
      phase: r[cols.indexOf('phase')] === 'before' ? 'before' : 'after',
      ...Object.fromEntries(need.map((c) => [c, Number(r[cols.indexOf(c)]) || 0])),
    }))
    try { await api.importSales(biz.id, weeks); done(t.salesCsvSaved(weeks.length)); await onChanged() } catch (e2) { setErr(e2.message) }
  }
  async function exportAll() {
    const all = await api.exportData(biz.id)
    downloadText(`aparece-${biz.name.replace(/\W+/g, '-').toLowerCase()}.json`, JSON.stringify(all, null, 2), 'application/json')
    await onChanged()
  }
  async function remove() {
    try { await api.deleteBusiness(biz.id, confirm); await onDeleted() } catch (e) { setErr(e.message) }
  }

  return (
    <div className="stack">
      <section className="hero wide">
        <h1>{t.privacyHero}</h1>
        <p>{t.privacySub}</p>
      </section>

      <div className="two even">
        <section className="panel">
          <div className="panel-head"><h2>{t.weAsk}</h2></div>
          <ul className="checklist yes">{t.weAskList.map((x) => <li key={x}>{x}</li>)}</ul>
        </section>
        <section className="panel">
          <div className="panel-head"><h2>{t.weNever}</h2></div>
          <ul className="checklist no">{t.weNeverList.map((x) => <li key={x}>{x}</li>)}</ul>
        </section>
      </div>

      <section className="panel">
        <div className="panel-head"><h2>{t.whereTitle}</h2></div>
        <div className="matrix-wrap">
          <table className="audit flow">
            <thead><tr><th>{t.flowData}</th><th>{t.flowWhere}</th><th>{t.flowWho}</th></tr></thead>
            <tbody>{t.flows.map((f) => <tr key={f[0]}><td><strong>{f[0]}</strong></td><td>{f[1]}</td><td>{f[2]}</td></tr>)}</tbody>
          </table>
        </div>
      </section>

      <ReferralLog bizId={biz.id} t={t} lang={lang} rows={data.referrals} onChanged={onChanged} />

      <section className="panel stack">
        <div className="panel-head" style={{ marginBottom: 0 }}><h2>{t.connectTitle}</h2></div>
        <label className="field narrow">{t.confirmedBy}<input value={name} onChange={(e) => { setName(e.target.value); setErr('') }} /></label>
        <div>
          <h3>{biz.segment === 'ecommerce' || biz.segment === 'tech' ? t.importProducts : t.importServices}</h3>
          <CsvImport t={t} segment={biz.segment} onFacts={addFacts} />
        </div>
        <div>
          <h3>{t.importSales}</h3>
          <div className="csv-row">
            <label className="btn ghost small file-btn">{t.csvChoose}<input type="file" accept=".csv,text/csv" onChange={importSales} /></label>
            <button className="linkish" type="button" onClick={() => downloadText('aparece-sales-template.csv', TEMPLATES.sales)}>{t.csvTemplate}</button>
          </div>
          <p className="faint">{t.salesCsvHint}</p>
        </div>
        {msg && <p className="success">{msg}</p>}
        {err && <p className="error" role="alert">{err}</p>}
      </section>

      <div className="two even">
        <section className="panel stack">
          <div className="panel-head" style={{ marginBottom: 0 }}><h2>{t.exportTitle}</h2></div>
          <p className="muted">{t.exportText}</p>
          <div><button className="btn" onClick={exportAll}>{t.exportBtn}</button></div>
        </section>
        <section className="panel stack danger">
          <div className="panel-head" style={{ marginBottom: 0 }}><h2>{t.deleteTitle}</h2></div>
          <p className="muted">{t.deleteText}</p>
          <label className="field">{t.deleteConfirm(biz.name)}<input value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>
          <div><button className="btn danger" disabled={confirm !== biz.name} onClick={remove}>{t.deleteBtn}</button></div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-head"><h2>{t.dataEvents}</h2></div>
        {events.length === 0 ? <p className="muted">–</p> : (
          <table className="audit"><tbody>
            {events.map((e) => <tr key={e.id}><td>{new Date(e.at).toLocaleString()}</td><td>{t.dataAction[e.action] || e.action}</td><td>{e.actor}</td></tr>)}
          </tbody></table>
        )}
      </section>

      <section className="panel">
        <div className="panel-head"><h2>{t.securityTitle}</h2><span className="faint">{t.securityHint}</span></div>
        <table className="audit"><tbody>
          {t.security.map(([item, status]) => (
            <tr key={item}><td>{item}</td><td><span className={`tag ${status === 'now' ? 'resolved' : 'approved'}`}>{status === 'now' ? t.inDemo : t.beforeLaunch}</span></td></tr>
          ))}
        </tbody></table>
      </section>
    </div>
  )
}
