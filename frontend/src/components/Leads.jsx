import { Fragment, useEffect, useState } from 'react'
import { api } from '../api.js'

const STATUS = ['new', 'contacted', 'trial', 'customer', 'not_fit']

// Internal: everyone who signed up for a free scan, why they came, and what their scan found.
export default function Leads({ t }) {
  const S = t.leads
  const [list, setList] = useState(null)
  const [open, setOpen] = useState(null)
  const [filter, setFilter] = useState('all')
  const load = () => api.leads().then(setList).catch(() => setList([]))
  useEffect(() => { load() }, [])
  if (!list) return <p className="empty">…</p>
  const shown = filter === 'all' ? list : list.filter((l) => l.status === filter)
  const count = (key, field) => list.reduce((m, l) => { l[field].forEach((x) => { m[x] = (m[x] || 0) + 1 }); return m }, {})[key] || 0
  const top = (field, labels) => Object.keys(labels).map((k) => [k, count(k, field)]).filter(([, n]) => n).sort((a, b) => b[1] - a[1]).slice(0, 4)
  async function setStatus(l, status) { await api.updateLead(l.id, status, l.note || ''); load() }

  return (
    <div className="stack">
      <div className="panel-head" style={{ marginBottom: 0 }}>
        <h2>{S.title} ({list.length})</h2>
        <a className="btn ghost small" href="/api/leads.csv">{S.csv}</a>
      </div>
      <p className="note">{S.hint}</p>
      {list.length > 0 && (
        <div className="two even">
          <section className="panel"><div className="panel-head"><h3>{S.topReasons}</h3></div>
            <ul className="journey-list">{top('reasons', t.signup.reasons).map(([k, n]) => <li key={k}>{t.signup.reasons[k]} · <strong>{n}</strong></li>)}</ul></section>
          <section className="panel"><div className="panel-head"><h3>{S.topIssues}</h3></div>
            <ul className="journey-list">{top('issues', t.signup.issues).map(([k, n]) => <li key={k}>{t.signup.issues[k]} · <strong>{n}</strong></li>)}</ul></section>
        </div>
      )}
      <div className="filters">
        {['all', ...STATUS].map((s) => <button key={s} className={`btn small ${filter === s ? '' : 'ghost'}`} onClick={() => setFilter(s)}>{s === 'all' ? S.all : S.status[s]}</button>)}
      </div>
      {shown.length === 0 ? <div className="panel empty">{S.none}</div> : (
        <div className="matrix-wrap panel" style={{ padding: 0 }}>
          <table className="audit leads-table">
            <thead><tr><th>{S.who}</th><th>{S.business}</th><th>{S.why}</th><th>{S.result}</th><th>{S.statusCol}</th></tr></thead>
            <tbody>
              {shown.map((l) => (
                <Fragment key={l.id}>
                  <tr className="lead-row" onClick={() => setOpen(open === l.id ? null : l.id)}>
                    <td><strong>{l.contact_name}</strong><br /><span className="faint">{l.email}{l.phone ? ` · ${l.phone}` : ''}</span></td>
                    <td>{l.business_name}<br /><span className="faint">{l.city}{l.segment ? ` · ${t.segment[l.segment]}` : ''}</span></td>
                    <td><div className="chips small">{l.reasons.map((r) => <span key={r} className="chip">{t.signup.reasons[r]}</span>)}</div></td>
                    <td>{l.scan && l.scan.inclusion == null ? <span className="faint">{S.notMeasured}</span> : l.scan ? <>{S.named(l.scan.inclusion)}<br /><span className="faint">{S.lost(l.scan.missed)}{l.scan.mode === 'demo' ? ` · ${t.simulatedTag}` : ''}</span></> : <span className="faint">{S.noScan}</span>}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <select value={l.status} onChange={(e) => setStatus(l, e.target.value)}>{STATUS.map((s) => <option key={s} value={s}>{S.status[s]}</option>)}</select>
                    </td>
                  </tr>
                  {open === l.id && (
                    <tr className="lead-detail"><td colSpan={5}>
                      <div className="two even">
                        <div>
                          <p><strong>{S.problems}:</strong> {l.issues.map((i) => t.signup.issues[i]).join(', ') || '—'}</p>
                          {l.issue_text && <p><strong>{S.tellMore}:</strong> “{l.issue_text}”</p>}
                          {l.help_text && <p><strong>{S.howHelp}:</strong> “{l.help_text}”</p>}
                        </div>
                        <div>
                          <p><strong>{S.website}:</strong> {l.website}</p>
                          <p><strong>{S.role}:</strong> {t.signup.roles[l.role] || l.role} · <strong>{S.signed}:</strong> {new Date(l.created_at).toLocaleString()}</p>
                          {l.scan && <p><strong>{S.scanLine}:</strong> {S.scanDetail(l.scan)}</p>}
                        </div>
                      </div>
                    </td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
