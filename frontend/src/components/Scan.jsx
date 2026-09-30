import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, ArrowRight, CheckCircle2, Circle, ClipboardCopy, Globe, Info, ListChecks, Loader2, MapPin,
  MessageSquareText, TrendingDown, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { api, ASSISTANT_NAMES } from '../api.js'
import { Bars } from './Overview.jsx'
import { Copyable } from './SiteCheck.jsx'

const APPS = ['chatgpt', 'gemini', 'perplexity', 'copilot', 'claude']

function Ring({ value, label, tone }) {
  const R = 54, C = 2 * Math.PI * R, v = value ?? 0
  return (
    <svg viewBox="0 0 128 128" className={`score-ring ${tone}`} role="img" aria-label={`${value ?? '—'}% ${label}`}>
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
    <div className="v0 mx-auto max-w-lg py-10">
      <Card className="gap-6 rounded-3xl p-8 shadow-xl shadow-[#17233b]/5">
        <div className="flex items-center gap-3"><Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" /><h1 className="font-display text-2xl font-bold">{S.loadingTitle}</h1></div>
        <ol className="space-y-3">
          {S.steps.map((x, i) => (
            <li key={x} className={`flex items-center gap-3 ${i < step ? 'text-muted-foreground' : i === step ? 'font-semibold text-foreground' : 'text-muted-foreground/60'}`}>
              {i < step ? <CheckCircle2 className="size-5 text-success" aria-hidden="true" /> : i === step ? <Loader2 className="size-5 animate-spin text-accent" aria-hidden="true" /> : <Circle className="size-5" aria-hidden="true" />}
              {x}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )

  const field = 'h-11 w-full rounded-xl border border-input bg-card px-3 text-base outline-none focus:ring-2 focus:ring-accent'
  if (stage !== 'report') return (
    <div className="v0 mx-auto max-w-2xl py-6">
      <h1 className="font-display text-4xl font-bold tracking-tight">{stage === 'need' ? S.needTitle : S.title}</h1>
      <p className="mt-3 text-lg text-muted-foreground">{stage !== 'need' ? S.sub : why?.blocked ? (why.marketplace ? S.blockedMarketplace : S.blockedText) : S.needText}</p>
      <Card className="mt-6 gap-5 rounded-3xl p-6">
        <form className="space-y-5" onSubmit={(e) => { e.preventDefault(); run() }}>
          <label className="block space-y-1.5 text-sm font-medium">{t.landing.urlLabel}<input className={field} value={url} onChange={(e) => setUrl(e.target.value)} placeholder={t.landing.urlPh} /></label>
          {stage === 'need' && (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block space-y-1.5 text-sm font-medium">{t.name}<input className={field} value={extra.name} onChange={(e) => setExtra({ ...extra, name: e.target.value })} /></label>
              <label className="block space-y-1.5 text-sm font-medium">{t.city}<input className={field} value={extra.city} onChange={(e) => setExtra({ ...extra, city: e.target.value })} placeholder="Houston, TX" /></label>
              {why?.blocked && (
                <label className="block space-y-1.5 text-sm font-medium">{t.type}
                  <select className={field} value={extra.segment} onChange={(e) => setExtra({ ...extra, segment: e.target.value })}>
                    {['cleaning', 'restaurant', 'trades', 'services', 'ecommerce', 'tech'].map((x) => <option key={x} value={x}>{t.segment[x]}</option>)}
                  </select>
                </label>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" size="lg" className="h-12 rounded-xl bg-accent px-6 text-base font-semibold text-accent-foreground hover:bg-accent/90">
              {stage === 'need' ? S.continue : t.landing.cta} <ArrowRight className="size-4" aria-hidden="true" />
            </Button>
            {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          </div>
        </form>
      </Card>
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

  const IMPACT = { high: 'bg-destructive/10 text-destructive', medium: 'bg-accent/15 text-[#955f00]', low: 'bg-success/10 text-success' }
  const stats = [
    { icon: Globe, value: site.score == null ? '—' : site.score, of: '/100', label: S.statSite },
    { icon: ListChecks, value: F ? readable : '—', of: '/5', label: S.statFacts },
    measured
      ? { icon: Users, value: c.missed, of: `/${c.answers}`, label: S.statLost }
      : { icon: MessageSquareText, value: c.questions?.length ?? 0, of: '', label: S.statQuestions },
  ]

  return (
    <div className="v0 mx-auto max-w-5xl space-y-6 pb-6">
      {r.city_conflict && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-accent/40 bg-accent/10 px-5 py-4 text-sm font-medium text-[#955f00]">
          <span className="flex items-center gap-2"><AlertTriangle className="size-4 shrink-0" aria-hidden="true" />{S.cityConflict(r.city_conflict, b.city)}</span>
          <Button size="sm" className="rounded-lg" onClick={() => run(url, { name: b.name, city: r.city_conflict, segment: b.segment })}>{S.useCity(r.city_conflict)}</Button>
        </div>
      )}

      <Card className="grid items-center gap-8 rounded-3xl p-6 shadow-xl shadow-[#17233b]/5 md:grid-cols-[1fr_210px] md:p-9">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#955f00]">{S.eyebrow}</p>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">{b.name}</h1>
          <p className="mt-2 flex items-center gap-1.5 text-muted-foreground"><MapPin className="size-4" aria-hidden="true" />{[b.city, t.segment[b.segment]].filter(Boolean).join(' · ')}</p>
          <p className="mt-5 max-w-xl text-lg">{pct == null ? S.leadNone : measured ? (c.answers < 10 ? S.leadFew(pct, c.answers) : S.leadMeasured(pct, c.answers)) : S.leadEstimate(est.low, est.high)}</p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Badge className={`rounded-full px-3 py-1 ${measured ? 'bg-success text-success-foreground' : 'bg-[#2f63c4]/10 text-[#1f4ea3]'}`}>{measured ? S.badgeMeasured(c.answers) : S.badgeEstimate}</Badge>
          </div>
          {!measured && est && (
            <p className="mt-3 flex items-start gap-1.5 text-sm text-muted-foreground"><Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />{S.basedOn}: {est.drivers.map((d) => S.driver[d.id](d)).join(' · ')}</p>
          )}
        </div>
        <div className="mx-auto w-full max-w-[210px]"><Ring value={pct} label={measured ? S.ringMeasured : S.ringEstimate} tone={tone} /></div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-3">
        {stats.map(({ icon: Icon, value, of, label }) => (
          <Card key={label} className="flex-row items-start gap-4 rounded-2xl p-5">
            <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground"><Icon className="size-5" aria-hidden="true" /></div>
            <div><p className="font-display text-3xl font-bold leading-none">{value}<span className="text-base font-medium text-muted-foreground">{of}</span></p><p className="mt-1.5 text-sm text-muted-foreground">{label}</p></div>
          </Card>
        ))}
      </div>

      <Card className="gap-5 rounded-3xl p-6 md:p-7">
        <div className="flex flex-wrap items-baseline justify-between gap-2"><h2 className="font-display text-2xl font-bold">{S.planTitle}</h2><span className="text-sm text-muted-foreground">{S.planHint}</span></div>
        {plan.length === 0 ? <p className="font-medium text-success">{S.planNone}</p> : (
          <ol className="space-y-3">
            {plan.map((p, i) => (
              <li key={p.title} className="flex gap-4 rounded-2xl border border-border p-4 transition hover:border-accent/50 hover:bg-muted/40">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary font-bold text-primary-foreground">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">{p.title}</p><span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${IMPACT[p.impact]}`}>{S.impact[p.impact]}</span></div>
                  <p className="mt-1">{p.text}</p>
                  {p.why && <p className="mt-1.5 text-sm text-muted-foreground">{p.why}</p>}
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>

      <Card className="gap-5 rounded-3xl p-6 md:p-7">
        <div className="flex flex-wrap items-baseline justify-between gap-2"><h2 className="font-display text-2xl font-bold">{measured ? S.missedTitle : S.likelyTitle}</h2><span className="text-sm text-muted-foreground">{measured ? S.missedHint : S.likelyHint}</span></div>
        {(measured ? r.missed.length === 0 : !est || est.likely_missed.length === 0)
          ? <p className="font-medium text-success">{measured ? S.missedNone : S.likelyNone}</p>
          : (
            <div className="grid gap-3 sm:grid-cols-2">
              {(measured ? r.missed.map((m) => ({ key: m.category, title: t.checkCategory[m.category] || m.category, tag: `${m.rate}%`,
                sub: m.named_instead?.length ? S.namedHere(m.named_instead.join(', ')) : S.missedRate(m.rate, m.answers),
                text: m.offered ? S.winOffered(m.category) : S.win[WIN[m.category] || 'best'] }))
                : est.likely_missed.map((m) => ({ key: m.check, title: m.label, tag: S.likelyTag, sub: t.siteCheck[m.check].why }))
              ).map((m) => (
                <div key={m.key} className="rounded-2xl border border-border p-4">
                  <div className="flex items-start justify-between gap-3"><p className="flex items-center gap-2 font-semibold"><TrendingDown className="size-4 shrink-0 text-destructive" aria-hidden="true" />{m.title}</p>
                    <span className="shrink-0 rounded-full bg-accent/15 px-2.5 py-0.5 text-xs font-semibold text-[#955f00]">{m.tag}</span></div>
                  <p className="mt-2 text-sm text-muted-foreground">{m.sub}</p>
                  {m.text && <p className="mt-2 text-sm">{m.text}</p>}
                </div>
              ))}
            </div>
          )}
      </Card>

      {measured && <PromptList S={S} c={c} city={b.city} />}
      {measured && (
        <div className="grid gap-6 md:grid-cols-2">
          <Card className="gap-4 rounded-3xl p-6">
            <h2 className="font-display text-xl font-bold">{S.wrongTitle}</h2>
            {wrongFacts.length === 0 ? <p className="text-muted-foreground">{S.wrongNone}</p> : (
              <ul className="space-y-2">{wrongFacts.map((w, i) => (
                <li key={i} className="rounded-xl bg-destructive/5 p-3 text-sm"><span className="font-semibold">{ASSISTANT_NAMES[w.provider] || w.provider}</span> · {w.fact}: <span className="font-semibold text-destructive">{w.value}</span> <span className="text-muted-foreground">({S.yourSite}: {w.truth})</span></li>
              ))}</ul>
            )}
          </Card>
          <Card className="gap-4 rounded-3xl p-6">
            <h2 className="font-display text-xl font-bold">{S.byAssistant}</h2>
            <Bars items={Object.entries(c.by_assistant).map(([k, v]) => ({ label: ASSISTANT_NAMES[k] || k, value: v }))} />
          </Card>
        </div>
      )}

      {site.fixes && (
        <details className="group rounded-3xl border border-border bg-card p-6 shadow-sm">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 [&::-webkit-details-marker]:hidden">
            <span className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-muted"><ClipboardCopy className="size-5" aria-hidden="true" /></span>
              <span><span className="block font-semibold">{S.fixesTitle}</span><span className="text-sm text-muted-foreground">{S.fixesHint}</span></span></span>
            <span className="grid size-8 shrink-0 place-items-center rounded-full bg-muted text-lg transition group-open:rotate-45">+</span>
          </summary>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <Copyable t={t} label={t.siteFaqEn} text={site.fixes.faq_en.join('\n')} />
            <Copyable t={t} label={t.siteFaqEs} text={site.fixes.faq_es.join('\n')} />
          </div>
          <button className="mt-4 text-sm font-medium underline underline-offset-4" onClick={() => onWebsiteReport({ website: r.url || site.url, name: b.name, city: b.city, segment: b.segment })}>{S.fullSite} →</button>
        </details>
      )}

      {c.mode !== 'live' && c.questions && (
        <RealAnswers S={S} questions={c.questions} checkId={r.check_id}
          onResult={(res) => { setR({ ...r, check: res.check, missed: res.missed }); window.scrollTo(0, 0) }} />
      )}

      <div className="flex flex-col items-start justify-between gap-5 rounded-3xl bg-primary p-7 text-primary-foreground md:flex-row md:items-center md:p-9">
        <div><h2 className="font-display text-2xl font-bold md:text-3xl">{S.ctaTitle}</h2><p className="mt-2 text-white/70">{S.ctaText}</p></div>
        <div className="flex shrink-0 flex-wrap gap-3">
          <Button size="lg" disabled={busy} className="h-12 rounded-xl bg-accent px-6 font-semibold text-accent-foreground hover:bg-accent/90"
            onClick={async () => { setBusy(true); try { const { id } = await api.startTrial(r.check_id); await onStarted(id) } finally { setBusy(false) } }}>{t.startTrial}</Button>
          <Button size="lg" variant="outline" className="h-12 rounded-xl border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white" onClick={onPlans}>{t.seePlans}</Button>
        </div>
      </div>
    </div>
  )
}
