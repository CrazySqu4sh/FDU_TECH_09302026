import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { useStrings } from './i18n.js'
import Overview from './components/Overview.jsx'
import Matrix from './components/Matrix.jsx'
import Issues from './components/Issues.jsx'
import Answers from './components/Answers.jsx'
import Profile from './components/Profile.jsx'
import NewBusiness from './components/NewBusiness.jsx'
import Activity from './components/Activity.jsx'
import Impact from './components/Impact.jsx'
import Check from './components/Check.jsx'
import Plans from './components/Plans.jsx'
import Locked from './components/Locked.jsx'
import Growth from './components/Growth.jsx'
import Privacy from './components/Privacy.jsx'
import Perception from './components/Perception.jsx'
import Insights from './components/Insights.jsx'
import Assistant from './components/Assistant.jsx'
import ProofLab from './components/ProofLab.jsx'
import SiteCheck from './components/SiteCheck.jsx'

// Five sections instead of a long row of tabs. Each section keeps its screens one click away.
const GROUPS = [
  { id: 'home', tabs: ['overview'] },
  { id: 'see', tabs: ['perception', 'truth', 'answers'] },
  { id: 'fix', tabs: ['issues', 'profile', 'website'] },
  { id: 'results', tabs: ['works', 'growth', 'impact', 'lab'] },
  { id: 'settings', tabs: ['data', 'activity'] },
]
const TABS = GROUPS.flatMap((g) => g.tabs)

export default function App() {
  const [lang, setLang] = useState('en')
  const t = useStrings(lang)
  const [businesses, setBusinesses] = useState([])
  const params = new URLSearchParams(window.location.search)  // ?biz=2&tab=impact deep-links a pitch screen
  const [bizId, setBizId] = useState(() => Number(params.get('biz')) || null)
  const [data, setData] = useState(null)
  const [tab, setTab] = useState(() => (TABS.includes(params.get('tab')) ? params.get('tab') : 'overview'))
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)
  const [view, setView] = useState(() => (['check', 'plans', 'site'].includes(params.get('page')) ? params.get('page') : 'app'))
  const [checkPrefill, setCheckPrefill] = useState(null)

  const loadBusinesses = useCallback(async (selectId) => {
    try {
      const list = await api.businesses()
      setBusinesses(list)
      setBizId((cur) => selectId ?? cur ?? list[0]?.id ?? null)
    } catch (e) {
      setError(`Can't reach the API. Start the backend on port 8000. (${e.message})`)
    }
  }, [])

  const refresh = useCallback(async () => {
    if (!bizId) return
    try {
      setData(await api.dashboard(bizId))
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }, [bizId])

  useEffect(() => { loadBusinesses() }, [loadBusinesses])
  useEffect(() => { refresh() }, [refresh])

  async function runScan() {
    setScanning(true)
    try {
      const res = await api.scan(bizId)
      if (res.errors?.length) setError(`Some assistant calls failed: ${res.errors.slice(0, 2).join('; ')}`)
      await refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setScanning(false)
    }
  }

  const activeIssues = data?.incidents.filter((i) => ['open', 'needs_review'].includes(i.status)).length || 0
  const has = (f) => !!data?.plan.features.includes(f)
  const goPlans = () => { setView('plans'); setAdding(false) }
  const plan = data?.plan

  return (
    <>
      <header className="topbar">
        <div className="brand">aparece<span>.</span></div>
        <nav className="pages" aria-label="Pages">
          <button aria-current={view === 'app'} onClick={() => setView('app')}>{t.dashboard}</button>
          <button aria-current={view === 'site'} onClick={() => { setView('site'); setAdding(false) }}>{t.websiteCheck}</button>
          <button aria-current={view === 'check'} onClick={() => { setView('check'); setAdding(false) }}>{t.freeCheck}</button>
          <button aria-current={view === 'plans'} onClick={goPlans}>{t.plans}</button>
        </nav>
        {businesses.length > 0 && (
          <select aria-label="Business" value={bizId ?? ''} onChange={(e) => { setBizId(Number(e.target.value)); setAdding(false) }}>
            {businesses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        )}
        {data && !adding && <span className="seg-tag">{t.segment[data.business.segment]}</span>}
        {data && !adding && <span className={`plan-chip ${plan.id}`}>{t.planName[plan.id]}</span>}
        <button className="linkish" style={{ color: '#fff' }} onClick={() => { setAdding(true); setView('app') }}>+ {t.addShort}</button>

        <div className="spacer" />
        {data && <span className="mode" title={data.mode === 'demo' ? t.demoMode : t.liveMode}>{data.mode === 'demo' ? t.demoShort : t.liveShort}</span>}
        <div className="lang" role="group" aria-label="Language">
          <button aria-pressed={lang === 'en'} onClick={() => setLang('en')}>EN</button>
          <button aria-pressed={lang === 'es'} onClick={() => setLang('es')}>ES</button>
        </div>
        {bizId && !adding && view === 'app' && (
          <button className="btn marigold" onClick={runScan} disabled={scanning}>
            {scanning ? t.scanning : t.runScan}
          </button>
        )}
      </header>
      {error && <div className="banner" role="alert">{error}</div>}

      {view === 'site' ? (
        <main><SiteCheck t={t}
          onRunCheck={(p) => { setCheckPrefill({ ...p, category: t.defaultCategory[p.segment] || '' }); setView('check') }}
          onStartTrial={async (p) => {
            try {
              const { id } = await api.createBusiness({ name: p.name || p.website, category: t.defaultCategory[p.segment] || 'local business',
                category_es: '', segment: p.segment, city: p.city || '—', website: p.website, competitors: [], facts: p.facts })
              await loadBusinesses(id); setView('app'); setTab('profile')
            } catch (e) { setError(e.message) }
          }} /></main>
      ) : view === 'check' ? (
        <main><Check key={JSON.stringify(checkPrefill)} prefill={checkPrefill} t={t} lang={lang} onPlans={goPlans}
          onStarted={async (id) => { await loadBusinesses(id); setView('app'); setTab('overview') }} /></main>
      ) : view === 'plans' ? (
        <main><Plans t={t} data={data} onChanged={refresh} /></main>
      ) : adding ? (
        <main>
          <NewBusiness t={t} onCancel={() => setAdding(false)}
            onCreated={async (id) => { setAdding(false); await loadBusinesses(id); setTab('profile') }} />
        </main>
      ) : (
        <>
          <nav className="tabs" role="tablist" aria-label={t.sections}>
            {GROUPS.map((g) => (
              <button key={g.id} role="tab" aria-selected={g.tabs.includes(tab)} onClick={() => setTab(g.tabs.includes(tab) ? tab : g.tabs[0])}>
                {t.group[g.id]}{g.id === 'fix' && activeIssues > 0 && <span className="count">{activeIssues}</span>}
              </button>
            ))}
          </nav>
          {GROUPS.find((g) => g.tabs.includes(tab)).tabs.length > 1 && (
            <nav className="subtabs" aria-label={t.group[GROUPS.find((g) => g.tabs.includes(tab)).id]}>
              {GROUPS.find((g) => g.tabs.includes(tab)).tabs.map((k) => (
                <button key={k} aria-current={tab === k} onClick={() => setTab(k)}>
                  {t[k]}{k === 'issues' && activeIssues > 0 && <span className="count">{activeIssues}</span>}
                  {((k === 'impact' && data && !has('sales_basic')) || (k === 'works' && data && !has('scan_history'))) && <span className="lock" aria-label={t.lockedLabel}>🔒</span>}
                </button>
              ))}
            </nav>
          )}
          {plan?.id === 'trial' && (
            <div className="trial-bar">
              <span>{t.trialBar(plan.trial_days_left, plan.fix_drafts_used, plan.fix_drafts)}</span>
              <button className="linkish" onClick={goPlans}>{t.upgrade}</button>
            </div>
          )}
          <main>
            {!data ? <p className="empty">…</p> : (
              <>
                {tab === 'overview' && <Overview data={data} t={t} lang={lang} onUpgrade={goPlans} />}
                {tab === 'perception' && <Perception bizId={bizId} t={t} lang={lang} name={data.business.name} scanCount={data.scans.length} />}
                {tab === 'website' && <SiteCheck key={bizId} t={t} business={data.business} />}
                {tab === 'lab' && <ProofLab bizId={bizId} t={t} lang={lang} mode={data.mode} />}
                {tab === 'works' && (has('scan_history')
                  ? <Insights bizId={bizId} t={t} mode={data.mode} onChanged={refresh} />
                  : <Locked t={t} plan="silver" text={t.lockedWorks} onUpgrade={goPlans} />)}
                {tab === 'growth' && <Growth bizId={bizId} t={t} lang={lang} scanCount={data.scans.length + data.incidents.length}
                  onGo={setTab} onUpgrade={goPlans} />}
                {tab === 'data' && <Privacy data={data} t={t} lang={lang} onChanged={refresh}
                  onDeleted={async () => { setBizId(null); setData(null); await loadBusinesses(null); setTab('overview') }} />}
                {tab === 'impact' && (has('sales_basic')
                  ? <Impact data={data} t={t} lang={lang} onUpgrade={goPlans} />
                  : <Locked t={t} plan="silver" text={t.lockedSales} onUpgrade={goPlans} />)}
                {tab === 'truth' && <Matrix data={data} t={t} lang={lang} />}
                {tab === 'issues' && <Issues data={data} t={t} lang={lang} onChange={refresh} onUpgrade={goPlans} />}
                {tab === 'answers' && <Answers bizId={bizId} t={t} lang={lang} scanCount={data.scans.length} onChanged={refresh} />}
                {tab === 'profile' && <Profile data={data} t={t} lang={lang} onSaved={refresh} />}
                {tab === 'activity' && <Activity bizId={bizId} t={t} scanCount={data.scans.length} />}
              </>
            )}
          </main>
          {data && <Assistant bizId={bizId} t={t} lang={lang} onGo={setTab} />}
        </>
      )}
    </>
  )
}
