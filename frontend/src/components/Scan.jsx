import { useEffect, useRef, useState } from 'react'
import { api, ASSISTANT_NAMES } from '../api.js'
import { Bars } from './Overview.jsx'
import { Copyable } from './SiteCheck.jsx'

const APPS = ['chatgpt', 'gemini', 'perplexity', 'copilot', 'claude']

function Ring({ value, label, tone }) {
  const R = 54, C = 2 * Math.PI * R, v = value ?? 0
  return (
    <svg viewBox="0 0 128 128" className={`ring ${tone}`} role="img" aria-label={`${value ?? '—'}% ${label}`}>
      <circle cx="64" cy="64" r={R} className="ring-bg" />
      <circle cx="64" cy="64" r={R} className="ring-fg" strokeDasharray={`${(C * v) / 100} ${C}`} transform="rotate(-90 64 64)" />
      <text x="64" y="66" textAnchor="middle" className="ring-num">{value == null ? '—' : `${value}%`}</text>
      <text x="64" y="86" textAnchor="middle" className="ring-label">{label}</text>
    </svg>
  )
}

// Free and real: the owner asks the report's questions in the free AI apps and pastes the answers back.
function RealAnswers({ S, questions, checkId, onResult, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const [f, setF] = useState({ provider: 'chatgpt', q: 0, text: '' })
  const [list, setList] = useState([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [copied, setCopied] = useState(null)
  const q = questions[f.q]
  function add() {
    if (f.text.trim().length < 10) { setErr(S.realNeed); return }
    setList([...list, { provider: f.provider, language: q.language, question: q.question, text: f.text.trim() }])
    setF({ ...f, text: '', q: Math.min(f.q + 1, questions.length - 1) }); setErr('')
  }
  async function submit() {
    setBusy(true)
    try { onResult(await api.checkAnswers(checkId, list)); setList([]); setOpen(false) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  return (
    <section className="panel real-answers">
      <div className="panel-head">
        <div><h2>{S.realTitle}</h2><p className="muted" style={{ maxWidth: '70ch', marginTop: '0.3rem' }}>{S.realHint}</p></div>
        <button className="btn small" onClick={() => setOpen(!open)}>{open ? S.hide : S.realOpen}</button>
      </div>
      {open && (
        <div className="stack" style={{ gap: '0.9rem' }}>
          <ol className="real-steps">{S.realSteps.map((x) => <li key={x}>{x}</li>)}</ol>
          <div className="q-list">
            {questions.map((x, i) => (
              <button key={x.question} className={`q-chip ${f.q === i ? 'on' : ''}`} onClick={() => setF({ ...f, q: i })}>
                <span className="lang-tag">{x.language.toUpperCase()}</span>{x.question}
              </button>
            ))}
          </div>
          <div className="copy-q">
            <strong>“{q.question}”</strong>
            <button className="linkish" onClick={() => { try { navigator.clipboard.writeText(q.question) } catch { /* no clipboard */ } setCopied(f.q) }}>{copied === f.q ? S.copied : S.copyQ}</button>
          </div>
          <div className="form-grid">
            <label className="field">{S.realApp}<select value={f.provider} onChange={(e) => setF({ ...f, provider: e.target.value })}>{APPS.map((a) => <option key={a} value={a}>{ASSISTANT_NAMES[a]}</option>)}</select></label>
          </div>
          <label className="field">{S.realPaste}<textarea rows={6} value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} placeholder={S.realPh} /></label>
          <div className="confirm-bar" style={{ marginTop: 0 }}>
            <button className="btn ghost" onClick={add}>{S.realAdd}</button>
            {list.length > 0 && <button className="btn" onClick={submit} disabled={busy}>{busy ? S.realChecking : S.realSubmit(list.length)}</button>}
            {err && <p className="error">{err}</p>}
          </div>
          {list.length > 0 && <ul className="journey-list">{list.map((a, i) => <li key={i}>{ASSISTANT_NAMES[a.provider]}: {a.question}</li>)}</ul>}
        </div>
      )}
    </section>
  )
}

// Transparency: every question exactly as asked, who named the business, and each assistant's full answer.
function PromptList({ S, c, city }) {
  const [open, setOpen] = useState(null)
  const [all, setAll] = useState(false)
  const rows = c.by_prompt || []
  const shown = all ? rows : rows.slice(0, 6)
  return (
    <section className="panel">
      <div className="panel-head"><h2>{S.promptsTitle}</h2><span className="faint">{S.promptsHint(rows.length, Object.keys(c.by_assistant || {}).length)}</span></div>
      <p className="muted" style={{ marginBottom: '0.8rem', maxWidth: '75ch' }}>{c.mode === 'pasted' ? S.promptsPasted : S.promptsHow(city)}</p>
      <div className="prompts">
        {shown.map((p, i) => (
          <div key={p.question} className="prompt">
            <button className="prompt-row" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}>
              <span className="lang-tag">{p.language.toUpperCase()}</span>
              <span className="prompt-q">“{p.question}”</span>
              <span className="prompt-who">
                {p.answers.map((a) => <span key={a.provider} className={`who ${a.mentioned ? 'yes' : 'no'}`} title={a.mentioned ? S.namedYouBy : S.notNamedBy}>{ASSISTANT_NAMES[a.provider] || a.provider}{a.mentioned && a.position ? ` #${a.position}` : ''}</span>)}
              </span>
              <b className={p.rate >= 50 ? 'up' : 'down'}>{p.rate}%</b>
            </button>
            {open === i && (
              <div className="prompt-answers">
                {p.answers.map((a) => (
                  <div key={a.provider}>
                    <p className="faint"><strong>{ASSISTANT_NAMES[a.provider] || a.provider}</strong> · {a.mentioned ? (a.position ? S.rankedAt(a.position) : S.namedYouBy) : S.notNamedBy}</p>
                    <pre>{a.text}</pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {rows.length > 6 && <button className="linkish" style={{ marginTop: '0.7rem' }} onClick={() => setAll(!all)}>{all ? S.showFewer : S.showAll(rows.length)}</button>}
    </section>
  )
}

const WIN = { 'Best in category': 'best', 'Best in town': 'best', 'Prices and reviews': 'prices', 'Open on weekends': 'hours',
  'Open late': 'hours', 'Takeout or delivery': 'delivery', 'Vegetarian options': 'menu' }

// One box → one report: what AI says, the customers you're missing, what it gets wrong, and what to do.
export default function Scan({ t, lang, initialUrl, lead, onStarted, onPlans, onWebsiteReport }) {
  const S = t.scan
  const [url, setUrl] = useState(initialUrl || '')
  const [extra, setExtra] = useState({ name: lead?.business_name || '', city: lead?.city || '', segment: lead?.segment || '' })
  const [stage, setStage] = useState('form')
  const [step, setStep] = useState(0)
  const [r, setR] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [why, setWhy] = useState(null)  // { blocked, marketplace } when the site can't be read
  const timer = useRef(null)

  async function run(u = url, more = extra) {
    if (!/\.[a-z]{2,}/i.test(u.trim())) { setErr(S.needUrl); return }
    setErr(''); setStage('loading'); setStep(0)
    timer.current = setInterval(() => setStep((s) => Math.min(s + 1, S.steps.length - 1)), 1300)
    try {
      const res = await api.quickScan({ url: u.trim(), name: more.name, city: more.city, segment: more.segment || '', lead_id: lead?.id ?? null })
      if (res.ok) { setR(res); setStage('report') }
      else if (res.need) {
        setExtra({ name: res.business?.name || more.name || '', city: res.business?.city || more.city || '', segment: res.blocked ? (more.segment || 'cleaning') : (res.business?.segment || '') })
        setWhy(res.blocked ? { blocked: true, marketplace: res.marketplace } : null); setStage('need')
      } else { setErr(S.errorKind[res.error_kind] || S.unreachable(res.errors?.[0] || res.url)); setStage('form') }
    } catch (e) { setErr(e.message); setStage('form') } finally { clearInterval(timer.current) }
  }
  useEffect(() => { if (initialUrl) run(initialUrl, extra) }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => clearInterval(timer.current), [])

  if (stage === 'loading') return (
    <div className="scan-loading">
      <h1>{S.loadingTitle}</h1>
      <ol>{S.steps.map((s, i) => <li key={s} className={i < step ? 'done' : i === step ? 'now' : ''}>{s}</li>)}</ol>
    </div>
  )

  if (stage !== 'report') return (
    <div className="stack narrow-page">
      <section className="hero wide"><h1>{stage === 'need' ? S.needTitle : S.title}</h1>
        <p>{stage !== 'need' ? S.sub : why?.blocked ? (why.marketplace ? S.blockedMarketplace : S.blockedText) : S.needText}</p></section>
      <form className="panel stack" onSubmit={(e) => { e.preventDefault(); run() }}>
        <label className="field">{t.landing.urlLabel}<input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={t.landing.urlPh} /></label>
        {stage === 'need' && (
          <div className="form-grid">
            <label className="field">{t.name}<input value={extra.name} onChange={(e) => setExtra({ ...extra, name: e.target.value })} /></label>
            <label className="field">{t.city}<input value={extra.city} onChange={(e) => setExtra({ ...extra, city: e.target.value })} placeholder="Houston, TX" /></label>
            {why?.blocked && (
              <label className="field">{t.type}
                <select value={extra.segment} onChange={(e) => setExtra({ ...extra, segment: e.target.value })}>
                  {['cleaning', 'restaurant', 'trades', 'services', 'ecommerce', 'tech'].map((s) => <option key={s} value={s}>{t.segment[s]}</option>)}
                </select>
              </label>
            )}
          </div>
        )}
        <div className="confirm-bar" style={{ marginTop: 0 }}>
          <button className="btn marigold" type="submit">{stage === 'need' ? S.continue : t.landing.cta}</button>
          {err && <p className="error" role="alert">{err}</p>}
        </div>
      </form>
    </div>
  )

  const c = r.check, b = r.business
  const pending = c.mode === 'pending'  // no real answers yet: show an estimate from real website signals
  const measured = !pending && c.mode !== 'demo'
  const site = r.blocked ? { score: null, checks: [], fixes: null, estimate: null, found: null } : r.site
  const est = site.estimate
  const pct = pending ? (est ? est.pct : null) : (c.inclusion ?? 0)
  const wrongFacts = c.facts.flatMap((f) => f.said.filter((x) => x.match === false).map((x) => ({ ...x, fact: f.label, truth: f.value })))
  const failed = site.checks.filter((x) => !x.pass).sort((a, b2) => b2.weight - a.weight)
  const impact = (w) => (w >= 10 ? 'high' : w >= 8 ? 'medium' : 'low')
  const plan = [
    ...(r.blocked ? [{ title: S.planBlockedTitle, text: S.planBlocked, impact: 'high' }] : []),
    ...wrongFacts.slice(0, 2).map((w) => ({ title: S.planWrongTitle(w.fact), text: S.planWrong(w.fact, ASSISTANT_NAMES[w.provider] || w.provider), impact: 'high' })),
    ...r.missed.filter((m) => m.offered).slice(0, 2).map((m) => ({ title: S.planServiceTitle(m.category), text: S.planService(m.category), impact: 'high' })),
    ...failed.map((x) => ({ title: t.siteCheck[x.id].title, text: t.siteCheck[x.id].fix(x.detail), why: t.siteCheck[x.id].why, impact: impact(x.weight) })),
  ].slice(0, 5)
  const F = site.found
  const readable = F ? [F.phones.length > 0, F.hours.length > 0, F.prices.length > 0, F.services.length > 0, !!F.area].filter(Boolean).length : 0
  const tone = pct == null ? 'none' : pct >= 60 ? 'good' : pct >= 40 ? 'ok' : 'low'

  return (
    <div className="report">
      {r.city_conflict && (
        <div className="city-warning" role="alert">
          <span>{S.cityConflict(r.city_conflict, b.city)}</span>
          <button className="btn small" onClick={() => run(url, { name: b.name, city: r.city_conflict, segment: b.segment })}>{S.useCity(r.city_conflict)}</button>
        </div>
      )}

      <section className="rep-head">
        <div className="rep-id">
          <p className="eyebrow">{S.eyebrow}</p>
          <h1>{b.name}</h1>
          <p className="muted">{[b.city, t.segment[b.segment]].filter(Boolean).join(' · ')}</p>
          <p className="rep-lead">{pct == null ? S.leadNone : measured ? (c.answers < 10 ? S.leadFew(pct, c.answers) : S.leadMeasured(pct, c.answers)) : S.leadEstimate(est.low, est.high)}</p>
          <span className={`src-badge ${measured ? 'real' : 'est'}`}>{measured ? S.badgeMeasured(c.answers) : S.badgeEstimate}</span>
          {!measured && est && (
            <p className="based-on">{S.basedOn}: {est.drivers.map((d) => S.driver[d.id](d)).join(' · ')}</p>
          )}
        </div>
        <Ring value={pct} label={measured ? S.ringMeasured : S.ringEstimate} tone={tone} />
      </section>

      <div className="rep-stats">
        <div><b>{site.score == null ? '—' : site.score}<small>/100</small></b><span>{S.statSite}</span></div>
        <div><b>{F ? readable : '—'}<small>/5</small></b><span>{S.statFacts}</span></div>
        {measured
          ? <div><b>{c.missed}<small>/{c.answers}</small></b><span>{S.statLost}</span></div>
          : <div><b>{c.questions?.length ?? 0}</b><span>{S.statQuestions}</span></div>}
      </div>

      <section className="rep-card">
        <div className="rep-card-head"><h2>{S.planTitle}</h2><span className="faint">{S.planHint}</span></div>
        {plan.length === 0 ? <p className="success">{S.planNone}</p> : (
          <ol className="plan-cards">
            {plan.map((p, i) => (
              <li key={p.title}>
                <span className="pc-num">{i + 1}</span>
                <div>
                  <div className="pc-head"><strong>{p.title}</strong><span className={`impact ${p.impact}`}>{S.impact[p.impact]}</span></div>
                  <p>{p.text}</p>
                  {p.why && <p className="faint">{p.why}</p>}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="rep-card">
        <div className="rep-card-head"><h2>{measured ? S.missedTitle : S.likelyTitle}</h2><span className="faint">{measured ? S.missedHint : S.likelyHint}</span></div>
        {measured ? (r.missed.length === 0 ? <p className="success">{S.missedNone}</p> : (
          <div className="miss-grid">
            {r.missed.map((m) => (
              <article key={m.category}>
                <div className="pc-head"><strong>{t.checkCategory[m.category] || m.category}</strong><span className="miss-rate">{m.rate}%</span></div>
                <p className="faint">{m.named_instead?.length ? S.namedHere(m.named_instead.join(', ')) : S.missedRate(m.rate, m.answers)}</p>
                <p>{m.offered ? S.winOffered(m.category) : S.win[WIN[m.category] || 'best']}</p>
              </article>
            ))}
          </div>
        )) : (!est || est.likely_missed.length === 0 ? <p className="success">{S.likelyNone}</p> : (
          <div className="miss-grid">
            {est.likely_missed.map((m) => (
              <article key={m.check}>
                <div className="pc-head"><strong>{m.label}</strong><span className="impact medium">{S.likelyTag}</span></div>
                <p className="faint">{t.siteCheck[m.check].why}</p>
              </article>
            ))}
          </div>
        ))}
      </section>

      {measured && <PromptList S={S} c={c} city={b.city} />}
      {measured && (
        <div className="two even">
          <section className="rep-card">
            <div className="rep-card-head"><h2>{S.wrongTitle}</h2></div>
            {wrongFacts.length === 0 ? <p className="muted">{S.wrongNone}</p> : (
              <table className="audit"><tbody>
                {wrongFacts.map((w, i) => (
                  <tr key={i}><td>{ASSISTANT_NAMES[w.provider] || w.provider}</td><td>{w.fact}</td>
                    <td><span className="verdict wrong">{w.value}</span></td><td className="faint">{S.yourSite}: {w.truth}</td></tr>
                ))}
              </tbody></table>
            )}
          </section>
          <section className="rep-card">
            <div className="rep-card-head"><h2>{S.byAssistant}</h2></div>
            <Bars items={Object.entries(c.by_assistant).map(([k, v]) => ({ label: ASSISTANT_NAMES[k] || k, value: v }))} />
          </section>
        </div>
      )}

      {site.fixes && (
        <details className="rep-card fold">
          <summary><span><strong>{S.fixesTitle}</strong><span className="faint"> · {S.fixesHint}</span></span></summary>
          <div className="two even" style={{ marginTop: '0.9rem' }}>
            <Copyable t={t} label={t.siteFaqEn} text={site.fixes.faq_en.join('\n')} />
            <Copyable t={t} label={t.siteFaqEs} text={site.fixes.faq_es.join('\n')} />
          </div>
          <p style={{ marginTop: '0.8rem' }}><button className="linkish" onClick={() => onWebsiteReport({ website: r.url || site.url, name: b.name, city: b.city, segment: b.segment })}>{S.fullSite} →</button></p>
        </details>
      )}

      {c.mode !== 'live' && c.questions && (
        <RealAnswers S={S} questions={c.questions} checkId={r.check_id}
          onResult={(res) => { setR({ ...r, check: res.check, missed: res.missed }); window.scrollTo(0, 0) }} />
      )}

      <section className="cta">
        <div><h2>{S.ctaTitle}</h2><p>{S.ctaText}</p></div>
        <div className="cta-actions">
          <button className="btn marigold" disabled={busy} onClick={async () => { setBusy(true); try { const { id } = await api.startTrial(r.check_id); await onStarted(id) } finally { setBusy(false) } }}>{t.startTrial}</button>
          <button className="btn ghost" onClick={onPlans}>{t.seePlans}</button>
        </div>
      </section>
    </div>
  )
}
