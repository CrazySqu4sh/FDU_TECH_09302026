import { useEffect, useState } from 'react'
import { api, ASSISTANT_NAMES } from '../api.js'

const APPS = ['chatgpt', 'gemini', 'perplexity', 'copilot', 'claude', 'other']
const blank = { provider: 'chatgpt', language: 'en', question: '', text: '' }

// The $0 scan: answers copied from the free consumer apps customers actually use.
export default function PasteAnswers({ bizId, t, onDone }) {
  const [open, setOpen] = useState(false)
  const [questions, setQuestions] = useState([])
  const [form, setForm] = useState(blank)
  const [list, setList] = useState([])
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  useEffect(() => { if (open) api.journeys(bizId).then(setQuestions).catch(() => {}) }, [bizId, open])
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  function add() {
    if (!form.question.trim() || form.text.trim().length < 10) { setMsg(t.pasteNeed); return }
    setList([...list, form]); setForm({ ...blank, provider: form.provider, language: form.language }); setMsg('')
  }
  async function submit() {
    setBusy(true)
    try { const r = await api.manualScan(bizId, list); setList([]); setMsg(t.pasteDone(r.answers)); await onDone() }
    catch (e) { setMsg(e.message) } finally { setBusy(false) }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.pasteTitle}</h2>
        <button className="btn ghost small" onClick={() => setOpen(!open)}>{open ? t.hide : t.pasteOpen}</button>
      </div>
      <p className="muted" style={{ maxWidth: '75ch' }}>{t.pasteHint}</p>
      {open && (
        <div className="stack" style={{ marginTop: '0.9rem', gap: '0.8rem' }}>
          <div className="form-grid">
            <label className="field">{t.pasteApp}
              <select value={form.provider} onChange={set('provider')}>{APPS.map((a) => <option key={a} value={a}>{ASSISTANT_NAMES[a]}</option>)}</select>
            </label>
            <label className="field">{t.pasteLang}
              <select value={form.language} onChange={set('language')}><option value="en">English</option><option value="es">Español</option></select>
            </label>
            <label className="field">{t.question}
              <input list="paste-questions" value={form.question} onChange={set('question')} placeholder={t.pasteQuestionPh} />
              <datalist id="paste-questions">{questions.filter((q) => q.language === form.language).map((q) => <option key={q.id} value={q.question} />)}</datalist>
            </label>
          </div>
          <label className="field">{t.pasteAnswer}
            <textarea rows={6} value={form.text} onChange={set('text')} placeholder={t.pasteAnswerPh} />
          </label>
          <div className="confirm-bar" style={{ marginTop: 0 }}>
            <button className="btn ghost" onClick={add}>{t.pasteAdd}</button>
            {list.length > 0 && <button className="btn" onClick={submit} disabled={busy}>{busy ? t.checking : t.pasteCheck(list.length)}</button>}
            {msg && <span className={msg === t.pasteNeed ? 'error' : 'success'}>{msg}</span>}
          </div>
          {list.length > 0 && (
            <ul className="journey-list">{list.map((a, i) => <li key={i}><span className="lang-tag">{a.language.toUpperCase()}</span>{ASSISTANT_NAMES[a.provider]}: {a.question}</li>)}</ul>
          )}
        </div>
      )}
    </section>
  )
}
