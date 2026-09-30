import { useState } from 'react'

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
  const scanBox = (id) => (
    <form className="scan-box" onSubmit={go} id={id}>
      <label className="sr-only" htmlFor={`${id}-url`}>{L.urlLabel}</label>
      <input id={`${id}-url`} value={url} onChange={(e) => { setUrl(e.target.value); setErr('') }} placeholder={L.urlPh} inputMode="url" autoComplete="url" />
      <button className="btn marigold" type="submit">{L.cta}</button>
      {err && <p className="error" role="alert">{err}</p>}
    </form>
  )

  return (
    <div className="landing">
      <section className="l-hero">
        <div className="l-hero-copy">
          <p className="eyebrow">{L.eyebrow}</p>
          <h1>{L.title1}<br /><span>{L.title2}</span></h1>
          <p className="l-lead">{L.lead}</p>
          {scanBox('hero')}
          <p className="faint">{L.noCsv}</p>
        </div>
        <div className="l-hero-demo" aria-label={L.demoLabel}>
          <div className="demo-q"><span className="demo-who">{L.demoCustomer}</span>{L.demoQuestion}</div>
          <div className="demo-a">
            <span className="demo-who ai">{L.demoAi}</span>
            <ol>{L.demoList.map((x) => <li key={x}>{x}</li>)}</ol>
          </div>
          <div className="demo-flag"><strong>{L.demoMissing}</strong><span>{L.demoMissingText}</span></div>
          <p className="demo-note">{L.demoNote}</p>
        </div>
      </section>

      <section className="l-stats">
        {L.stats.map((s) => (
          <div key={s.n}><b>{s.n}</b><span>{s.text}</span><a href={s.url} target="_blank" rel="noreferrer">{s.source}</a></div>
        ))}
      </section>

      <section className="l-section">
        <h2>{L.problemTitle}</h2>
        <p className="l-sub">{L.problemSub}</p>
        <div className="l-cards three">
          {L.problems.map((p) => <article key={p.title}><span className="l-icon" aria-hidden="true">{p.icon}</span><h3>{p.title}</h3><p>{p.text}</p></article>)}
        </div>
      </section>

      <section className="l-section alt" id="how">
        <h2>{L.howTitle}</h2>
        <ol className="l-steps">
          {L.steps.map((s, i) => <li key={s.title}><span className="l-num">{i + 1}</span><h3>{s.title}</h3><p>{s.text}</p></li>)}
        </ol>
      </section>

      <section className="l-section">
        <h2>{L.getTitle}</h2>
        <p className="l-sub">{L.getSub}</p>
        <div className="l-cards">
          {L.features.map((f) => <article key={f.title}><h3>{f.title}</h3><p>{f.text}</p></article>)}
        </div>
      </section>

      <section className="l-section alt">
        <div className="l-split">
          <div>
            <h2>{L.whoTitle}</h2>
            <p className="l-sub">{L.whoText}</p>
            <div className="chips">{L.whoList.map((w) => <span key={w} className="chip">{w}</span>)}</div>
          </div>
          <div className="l-trust">
            <h3>{L.trustTitle}</h3>
            <ul className="checklist yes">{L.trustList.map((x) => <li key={x}>{x}</li>)}</ul>
          </div>
        </div>
      </section>

      <section className="l-section" id="pricing">
        <h2>{L.priceTitle}</h2>
        <p className="l-sub">{L.priceSub}</p>
        <div className="l-prices">
          {L.prices.map((p) => (
            <article key={p.name} className={p.featured ? 'featured' : ''}>
              <h3>{p.name}</h3><b>{p.price}</b><p>{p.text}</p>
            </article>
          ))}
        </div>
        <p className="center"><button className="btn ghost" onClick={onPlans}>{L.seePlans}</button></p>
      </section>

      <section className="l-section alt" id="about">
        <div className="l-split">
          <div>
            <h2>{L.aboutTitle}</h2>
            {L.about.map((p) => <p key={p} className="l-para">{p}</p>)}
          </div>
          <div className="l-name">
            <p className="l-word">aparece<span>.</span></p>
            <p className="faint">{L.nameMeaning}</p>
          </div>
        </div>
      </section>

      <section className="l-section">
        <h2>{L.faqTitle}</h2>
        <div className="l-faq">
          {L.faq.map((q) => <details key={q.q}><summary>{q.q}</summary><p>{q.a}</p></details>)}
        </div>
      </section>

      <section className="l-final">
        <h2>{L.finalTitle}</h2>
        <p>{L.finalText}</p>
        {scanBox('final')}
      </section>

      <footer className="l-footer">
        <span className="brand">aparece<span>.</span></span>
        <span>{L.footer}</span>
      </footer>
    </div>
  )
}
