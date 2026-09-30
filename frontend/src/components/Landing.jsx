import { useState } from 'react'
import {
  AlertTriangle, ArrowRight, Bot, CheckCircle2, ClipboardCopy, EyeOff, FlaskConical, MessageSquareText,
  Search, ShieldCheck, Shuffle, Sparkles, Target, TrendingUp, User, Wrench,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

const PROBLEM_ICONS = [EyeOff, AlertTriangle, Shuffle]
const STEP_ICONS = [Search, Sparkles, Wrench, TrendingUp]
const FEATURE_ICONS = [Target, ShieldCheck, ClipboardCopy, TrendingUp, MessageSquareText, FlaskConical]

function Section({ id, className = '', children }) {
  return <section id={id} className={`px-4 py-16 sm:px-6 md:py-24 ${className}`}><div className="mx-auto max-w-6xl">{children}</div></section>
}

function Heading({ eyebrow, title, sub, center = false }) {
  return (
    <div className={`mb-10 max-w-2xl ${center ? 'mx-auto text-center' : ''}`}>
      {eyebrow && <p className="mb-3 text-xs font-bold uppercase tracking-[0.14em] text-[#955f00]">{eyebrow}</p>}
      <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">{title}</h2>
      {sub && <p className="mt-4 text-lg text-muted-foreground">{sub}</p>}
    </div>
  )
}

// Public homepage: who Aparece is, the problem, how it works, and one box to start (a website address).
export default function Landing({ t, onScan, onPlans }) {
  const [url, setUrl] = useState('')
  const [err, setErr] = useState('')
  const L = t.landing
  function go(e) {
    e.preventDefault()
    if (!/\.[a-z]{2,}/i.test(url.trim())) { setErr(L.needUrl); return }
    onScan(url.trim())
  }
  const scanBox = (id, dark = false) => (
    <form id={id} onSubmit={go} className="w-full max-w-xl">
      <label className="sr-only" htmlFor={`${id}-url`}>{L.urlLabel}</label>
      <div className={`flex flex-col gap-2 rounded-2xl border p-2 shadow-lg sm:flex-row sm:items-center ${dark ? 'border-white/15 bg-white' : 'border-border bg-card shadow-[#17233b]/5'} focus-within:ring-2 focus-within:ring-accent`}>
        <div className="flex flex-1 items-center gap-2 px-3">
          <Search className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input id={`${id}-url`} value={url} onChange={(e) => { setUrl(e.target.value); setErr('') }} placeholder={L.urlPh}
            inputMode="url" autoComplete="url" className="h-12 w-full bg-transparent text-base text-foreground outline-none placeholder:text-muted-foreground" />
        </div>
        <Button type="submit" size="lg" className="h-12 rounded-xl bg-accent px-6 text-base font-semibold text-accent-foreground hover:bg-accent/90">
          {L.cta} <ArrowRight className="size-4" aria-hidden="true" />
        </Button>
      </div>
      {err && <p role="alert" className={`mt-2 text-sm ${dark ? 'text-red-200' : 'text-destructive'}`}>{err}</p>}
    </form>
  )

  return (
    <div className="v0 bg-background">
      {/* Hero */}
      <section className="relative overflow-hidden px-4 pb-16 pt-14 sm:px-6 md:pb-24 md:pt-20">
        <div aria-hidden="true" className="pointer-events-none absolute -right-40 -top-40 size-[520px] rounded-full bg-accent/15 blur-3xl" />
        <div aria-hidden="true" className="pointer-events-none absolute -left-32 top-64 size-[380px] rounded-full bg-[#2f63c4]/10 blur-3xl" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[1.15fr_0.85fr]">
          <div>
            <Badge variant="secondary" className="mb-6 rounded-full border border-accent/30 px-3 py-1 text-[#955f00]">
              <Sparkles className="size-3.5" aria-hidden="true" /> {L.eyebrow}
            </Badge>
            <h1 className="font-display text-5xl font-bold leading-[1.02] tracking-tight md:text-6xl lg:text-7xl">
              {L.title1}<br /><span className="text-[#b07a0b]">{L.title2}</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground md:text-xl">{L.lead}</p>
            <div className="mt-8">{scanBox('hero')}</div>
            <p className="mt-4 flex items-center gap-2 text-sm text-muted-foreground"><CheckCircle2 className="size-4 text-success" aria-hidden="true" />{L.noCsv}</p>
          </div>

          <Card className="relative gap-0 rounded-3xl border-border/70 p-0 shadow-2xl shadow-[#17233b]/10">
            <CardContent className="space-y-4 p-6" aria-label={L.demoLabel}>
              <div className="flex justify-end gap-3">
                <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-3 text-primary-foreground">
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-white/60">{L.demoCustomer}</p>
                  <p>{L.demoQuestion}</p>
                </div>
                <div className="grid size-9 shrink-0 place-items-center rounded-full bg-muted"><User className="size-4" aria-hidden="true" /></div>
              </div>
              <div className="flex gap-3">
                <div className="grid size-9 shrink-0 place-items-center rounded-full bg-[#2f63c4]/10 text-[#2f63c4]"><Bot className="size-4" aria-hidden="true" /></div>
                <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-muted px-4 py-3">
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-[#2f63c4]">{L.demoAi}</p>
                  <ol className="space-y-1">{L.demoList.map((x, i) => <li key={x}><span className="mr-2 font-semibold text-muted-foreground">{i + 1}.</span>{x}</li>)}</ol>
                </div>
              </div>
              <div className="flex gap-3 rounded-2xl border border-destructive/20 bg-destructive/5 p-4">
                <AlertTriangle className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden="true" />
                <div><p className="font-semibold text-destructive">{L.demoMissing}</p><p className="mt-1 text-sm text-muted-foreground">{L.demoMissingText}</p></div>
              </div>
              <p className="text-right text-xs text-muted-foreground">{L.demoNote}</p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Stats */}
      <section className="px-4 sm:px-6">
        <div className="mx-auto grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {L.stats.map((s) => (
            <Card key={s.n} className="gap-2 rounded-2xl p-6">
              <p className="font-display text-4xl font-bold tracking-tight">{s.n}</p>
              <p className="text-sm text-muted-foreground">{s.text}</p>
              <a href={s.url} target="_blank" rel="noreferrer" className="mt-auto text-xs font-medium text-muted-foreground underline underline-offset-4 hover:text-foreground">{s.source}</a>
            </Card>
          ))}
        </div>
      </section>

      {/* Problem */}
      <Section>
        <Heading title={L.problemTitle} sub={L.problemSub} />
        <div className="grid gap-5 md:grid-cols-3">
          {L.problems.map((p, i) => {
            const Icon = PROBLEM_ICONS[i] || AlertTriangle
            return (
              <Card key={p.title} className="gap-3 rounded-2xl p-6">
                <div className="grid size-11 place-items-center rounded-xl bg-destructive/10 text-destructive"><Icon className="size-5" aria-hidden="true" /></div>
                <h3 className="text-lg font-semibold">{p.title}</h3>
                <p className="text-muted-foreground">{p.text}</p>
              </Card>
            )
          })}
        </div>
      </Section>

      {/* How it works */}
      <Section id="how" className="border-y border-border bg-card">
        <Heading title={L.howTitle} center />
        <ol className="relative grid gap-8 md:grid-cols-4">
          <div aria-hidden="true" className="absolute left-0 right-0 top-6 hidden h-px bg-border md:block" />
          {L.steps.map((s, i) => {
            const Icon = STEP_ICONS[i]
            return (
              <li key={s.title} className="relative">
                <div className="relative mb-4 grid size-12 place-items-center rounded-full bg-accent text-accent-foreground shadow-md ring-8 ring-card"><Icon className="size-5" aria-hidden="true" /></div>
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{i + 1}</p>
                <h3 className="mt-1 text-lg font-semibold">{s.title}</h3>
                <p className="mt-2 text-muted-foreground">{s.text}</p>
              </li>
            )
          })}
        </ol>
      </Section>

      {/* What you get */}
      <Section>
        <Heading title={L.getTitle} sub={L.getSub} />
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {L.features.map((f, i) => {
            const Icon = FEATURE_ICONS[i] || Sparkles
            return (
              <Card key={f.title} className="group gap-3 rounded-2xl p-6 transition hover:-translate-y-0.5 hover:shadow-lg">
                <div className="grid size-11 place-items-center rounded-xl bg-primary text-primary-foreground transition group-hover:bg-accent group-hover:text-accent-foreground"><Icon className="size-5" aria-hidden="true" /></div>
                <h3 className="text-lg font-semibold">{f.title}</h3>
                <p className="text-muted-foreground">{f.text}</p>
              </Card>
            )
          })}
        </div>
      </Section>

      {/* Who + trust */}
      <Section className="border-y border-border bg-card">
        <div className="grid items-start gap-10 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <Heading title={L.whoTitle} sub={L.whoText} />
            <div className="-mt-4 flex flex-wrap gap-2">{L.whoList.map((w) => <Badge key={w} variant="outline" className="rounded-full px-3 py-1.5 text-sm">{w}</Badge>)}</div>
          </div>
          <Card className="gap-4 rounded-2xl bg-muted/60 p-6">
            <h3 className="flex items-center gap-2 text-lg font-semibold"><ShieldCheck className="size-5 text-success" aria-hidden="true" />{L.trustTitle}</h3>
            <ul className="space-y-3">{L.trustList.map((x) => <li key={x} className="flex gap-3"><CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" aria-hidden="true" /><span>{x}</span></li>)}</ul>
          </Card>
        </div>
      </Section>

      {/* Pricing teaser */}
      <Section id="pricing">
        <Heading title={L.priceTitle} sub={L.priceSub} center />
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {L.prices.map((p) => (
            <Card key={p.name} className={`relative gap-2 rounded-2xl p-6 ${p.featured ? 'border-accent shadow-lg ring-1 ring-accent' : ''}`}>
              {p.featured && <Badge className="absolute -top-3 left-6 rounded-full bg-accent text-accent-foreground">★</Badge>}
              <h3 className="font-semibold">{p.name}</h3>
              <p className="font-display text-3xl font-bold">{p.price}</p>
              <p className="text-sm text-muted-foreground">{p.text}</p>
            </Card>
          ))}
        </div>
        <div className="mt-8 text-center"><Button variant="outline" size="lg" className="rounded-xl" onClick={onPlans}>{L.seePlans} <ArrowRight className="size-4" aria-hidden="true" /></Button></div>
      </Section>

      {/* About */}
      <Section id="about" className="border-y border-border bg-card">
        <div className="grid items-center gap-10 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">{L.aboutTitle}</h2>
            <div className="mt-6 space-y-4 text-lg text-muted-foreground">{L.about.map((p) => <p key={p}>{p}</p>)}</div>
          </div>
          <div className="rounded-3xl bg-primary p-10 text-primary-foreground">
            <p className="font-display text-6xl font-bold tracking-tight md:text-7xl">aparece<span className="text-accent">.</span></p>
            <p className="mt-4 text-white/70">{L.nameMeaning}</p>
          </div>
        </div>
      </Section>

      {/* FAQ */}
      <Section>
        <Heading title={L.faqTitle} center />
        <div className="mx-auto max-w-3xl space-y-3">
          {L.faq.map((q) => (
            <details key={q.q} className="group rounded-2xl border border-border bg-card p-5 open:shadow-sm">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold [&::-webkit-details-marker]:hidden">
                {q.q}<span className="grid size-7 shrink-0 place-items-center rounded-full bg-muted text-lg transition group-open:rotate-45">+</span>
              </summary>
              <p className="mt-3 text-muted-foreground">{q.a}</p>
            </details>
          ))}
        </div>
      </Section>

      {/* Final CTA */}
      <section className="px-4 pb-16 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 rounded-3xl bg-primary px-6 py-14 text-center text-primary-foreground md:py-20">
          <h2 className="font-display text-3xl font-bold tracking-tight md:text-5xl">{L.finalTitle}</h2>
          <p className="text-white/70">{L.finalText}</p>
          <div className="mt-4 flex w-full justify-center">{scanBox('final', true)}</div>
        </div>
      </section>

      <footer className="border-t border-border bg-card px-4 py-6 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
          <span className="font-display text-lg font-bold text-foreground">aparece<span className="text-accent">.</span></span>
          <span>{L.footer}</span>
        </div>
      </footer>
    </div>
  )
}
