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

const TABS = ['overview', 'truth', 'issues', 'answers', 'profile', 'activity']

export default function App() {
  const [lang, setLang] = useState('en')
  const t = useStrings(lang)
  const [businesses, setBusinesses] = useState([])
  const [bizId, setBizId] = useState(null)
  const [data, setData] = useState(null)
  const [tab, setTab] = useState('overview')
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)

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

  return (
    <>
      <header className="topbar">
        <div className="brand">aparece<span>.</span></div>
        {businesses.length > 0 && (
          <select aria-label="Business" value={bizId ?? ''} onChange={(e) => { setBizId(Number(e.target.value)); setAdding(false) }}>
            {businesses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        )}
        {data && !adding && <span className="seg-tag">{t.segment[data.business.segment]}</span>}
        <button className="linkish" style={{ color: '#fff' }} onClick={() => setAdding(true)}>{t.addBusiness}</button>
        <div className="spacer" />
        {data && <span className="mode">{data.mode === 'demo' ? t.demoMode : t.liveMode}</span>}
        <div className="lang" role="group" aria-label="Language">
          <button aria-pressed={lang === 'en'} onClick={() => setLang('en')}>EN</button>
          <button aria-pressed={lang === 'es'} onClick={() => setLang('es')}>ES</button>
        </div>
        {bizId && !adding && (
          <button className="btn marigold" onClick={runScan} disabled={scanning}>
            {scanning ? t.scanning : t.runScan}
          </button>
        )}
      </header>
      {error && <div className="banner" role="alert">{error}</div>}

      {adding ? (
        <main>
          <NewBusiness t={t} onCancel={() => setAdding(false)}
            onCreated={async (id) => { setAdding(false); await loadBusinesses(id); setTab('profile') }} />
        </main>
      ) : (
        <>
          <nav className="tabs" role="tablist">
            {TABS.map((k) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>
                {t[k]}{k === 'issues' && activeIssues > 0 && <span className="count">{activeIssues}</span>}
              </button>
            ))}
          </nav>
          <main>
            {!data ? <p className="empty">…</p> : (
              <>
                {tab === 'overview' && <Overview data={data} t={t} lang={lang} />}
                {tab === 'truth' && <Matrix data={data} t={t} lang={lang} />}
                {tab === 'issues' && <Issues data={data} t={t} lang={lang} onChange={refresh} />}
                {tab === 'answers' && <Answers bizId={bizId} t={t} scanCount={data.scans.length} />}
                {tab === 'profile' && <Profile data={data} t={t} onSaved={refresh} />}
                {tab === 'activity' && <Activity bizId={bizId} t={t} scanCount={data.scans.length} />}
              </>
            )}
          </main>
        </>
      )}
    </>
  )
}
