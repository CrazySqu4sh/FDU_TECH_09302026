import { useState } from 'react'
import { api, ASSISTANT_NAMES } from '../api.js'
import { pretty } from './Matrix.jsx'
import Locked from './Locked.jsx'
import Evidence from './Evidence.jsx'

const day = (iso) => (iso ? new Date(iso).toLocaleDateString() : '')

function IssueCard({ inc, fact, t, lang, onChange }) {
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const [showCode, setShowCode] = useState(false)
  const [showEv, setShowEv] = useState(false)
  const who = ASSISTANT_NAMES[inc.provider] || inc.provider
  const label = fact ? (lang === 'es' && fact.label_es ? fact.label_es : fact.label).toLowerCase() : inc.fact_key
  const product = fact?.product ? (lang === 'es' && fact.product_es ? fact.product_es : fact.product) : ''
  const factLabel = product ? (lang === 'es' ? `${label} de ${product}` : `${product} ${label}`) : label
  const title = inc.type === 'missed_opportunity'
    ? t.missedTitle(inc.category, inc.language)
    : inc.type === 'source_conflict' ? t.conflictTitle(inc.provider, factLabel)
    : inc.status === 'needs_review' ? t.reviewTitle(who, factLabel) : t.wrongFactTitle(who, factLabel)
  const fix = inc.suggested_fix
  const actionable = ['open', 'needs_review'].includes(inc.status)

  async function act(fn) {
    setBusy(true); setErr('')
    try { await fn(); await onChange() } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  function approve() {
    if (!name.trim()) { setErr(t.approverRequired); return }
    act(() => api.approve(inc.id, name))
  }

  return (
    <article className={`issue ${inc.severity === 'critical' ? 'critical' : ''}`}>
      <div className="issue-head">
        <h3>{title}</h3>
        <div className="tags">
          <span className={`tag ${inc.severity}`}>{t.severity[inc.severity]}</span>
          <span className={`tag ${inc.status}`}>{t.status[inc.status]}</span>
        </div>
      </div>

      {inc.type !== 'missed_opportunity' ? (
        <div className="compare">
          <div className="said"><small>{inc.type === 'source_conflict' ? t.listingSays(inc.provider) : t.whatAiSaid}</small>{fact ? pretty(fact.category, inc.ai_value, lang) : inc.ai_value}</div>
          <div className="true"><small>{t.verifiedValue}</small>{fact ? pretty(fact.category, inc.verified_value, lang) : inc.verified_value}</div>
        </div>
      ) : null}
      <p className="note">{inc.detail}</p>
      {inc.type === 'wrong_fact' && (
        <div className="origin-row">
          {inc.origin === 'copied' && <span className="origin copied">{t.originCopied(inc.origin_source?.replace(/^https?:\/\//, '').split('/')[0])}</span>}
          {inc.origin === 'made_up' && <span className="origin made">{t.originMadeUp}</span>}
          {inc.origin === 'unclear' && <span className="origin unclear">{t.originUnclear}</span>}
          {!inc.origin && <button className="btn ghost small" disabled={busy} onClick={() => act(() => api.checkSources(inc.id))}>{t.checkSourcesBtn}</button>}
          <button className="linkish" onClick={() => setShowEv((v) => !v)}>{showEv ? t.evHide : t.evShow}</button>
        </div>
      )}
      {inc.type === 'source_conflict' && <div className="origin-row"><button className="linkish" onClick={() => setShowEv((v) => !v)}>{showEv ? t.evHide : t.evShow}</button></div>}
      {showEv && <Evidence inc={inc} t={t} lang={lang} />}

      {fix && (
        <div className="fix">
          <p>{lang === 'es' ? fix.explanation_es : fix.explanation_en}</p>
          <div>
            <strong>{t.suggested}</strong>
            <blockquote>{lang === 'es' ? fix.website_text_es : fix.website_text_en}</blockquote>
          </div>
          <div><strong>{t.nextStep}: </strong>{fix.action}</div>
          {fix.likely_source && (
            <div className="likely-source"><strong>{t.likelySource}: </strong>{fix.likely_source.label} ({fix.likely_source.domain}). {t.likelySourceWhy(fix.likely_source.answers)}</div>
          )}
          <div>
            <button className="linkish" onClick={() => setShowCode((s) => !s)}>{t.structured}</button>
            {showCode && <pre>{`<script type="application/ld+json">\n${JSON.stringify(fix.jsonld, null, 2)}\n</script>`}</pre>}
          </div>
        </div>
      )}

      {inc.status === 'approved' && <p className="note">{t.approvedBy(inc.approved_by, day(inc.approved_at))}</p>}
      {inc.status === 'resolved' && <p className="success">{t.resolvedOn(day(inc.resolved_at))}</p>}

      {actionable && (
        <div className="approve-row">
          {!fix ? (
            <button className="btn" disabled={busy} onClick={() => act(() => api.draftFix(inc.id))}>
              {busy ? t.drafting : t.draftFix}
            </button>
          ) : (
            <>
              <div>
                <input aria-label={t.approverName} placeholder={t.approverName} value={name}
                  onChange={(e) => { setName(e.target.value); setErr('') }} />
              </div>
              <button className="btn" disabled={busy} onClick={approve}>{t.approve}</button>
              <button className="btn ghost" disabled={busy} onClick={() => act(() => api.dismiss(inc.id, name || 'owner'))}>{t.dismiss}</button>
            </>
          )}
        </div>
      )}
      {err && <p className="error" role="alert">{err}</p>}
    </article>
  )
}

export default function Issues({ data, t, lang, onChange, onUpgrade }) {
  const [filter, setFilter] = useState('active')
  const facts = Object.fromEntries(data.facts.map((f) => [f.key, f]))
  const list = data.incidents.filter((i) =>
    filter === 'all' ? true : ['open', 'needs_review', 'approved'].includes(i.status))
  return (
    <div className="stack">
      <div className="panel-head" style={{ marginBottom: 0 }}>
        <h2>{t.issues}</h2>
        <div className="filters">
          <button className={`btn small ${filter === 'active' ? '' : 'ghost'}`} onClick={() => setFilter('active')}>{t.filterActive}</button>
          <button className={`btn small ${filter === 'all' ? '' : 'ghost'}`} onClick={() => setFilter('all')}>{t.filterAll}</button>
        </div>
      </div>
      {data.locked_missed > 0 && <Locked t={t} plan="silver" text={t.lockedMissed(data.locked_missed)} onUpgrade={onUpgrade} compact />}
      {data.plan.fix_drafts != null && data.plan.fix_drafts_used >= data.plan.fix_drafts &&
        <Locked t={t} plan="silver" text={t.lockedFixes(data.plan.fix_drafts)} onUpgrade={onUpgrade} compact />}
      {list.length === 0 ? <div className="panel empty">{t.noIssues}</div> :
        list.map((inc) => <IssueCard key={inc.id} inc={inc} fact={facts[inc.fact_key]} t={t} lang={lang} onChange={onChange} />)}
    </div>
  )
}
