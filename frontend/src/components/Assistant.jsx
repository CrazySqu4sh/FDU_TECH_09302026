import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

export default function Assistant({ bizId, t, lang, onGo }) {
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef(null)
  useEffect(() => { setMsgs([]) }, [bizId])
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [msgs, open])

  async function ask(q) {
    const question = (q ?? text).trim()
    if (!question || busy) return
    setText('')
    const history = msgs.map((m) => ({ role: m.role, content: m.content }))
    setMsgs((m) => [...m, { role: 'owner', content: question }])
    setBusy(true)
    try {
      const r = await api.chat(bizId, question, history, lang)
      setMsgs((m) => [...m, { role: 'assistant', content: r.answer, tab: r.tab }])
    } catch (e) {
      setMsgs((m) => [...m, { role: 'assistant', content: e.message }])
    } finally { setBusy(false) }
  }

  return (
    <>
      {!open && <button className="chat-fab" onClick={() => setOpen(true)} aria-label={t.chatOpen}>💬 {t.chatOpen}</button>}
      {open && (
        <section className="chat" aria-label={t.chatTitle}>
          <header>
            <div><strong>{t.chatTitle}</strong><span>{t.chatSub}</span></div>
            <button className="linkish" onClick={() => setOpen(false)} aria-label={t.chatClose}>✕</button>
          </header>
          <div className="chat-body">
            {msgs.length === 0 && (
              <div className="chat-hello">
                <p>{t.chatHello}</p>
                <div className="chat-suggest">
                  {t.chatSuggestions.map((s) => <button key={s} onClick={() => ask(s)}>{s}</button>)}
                </div>
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <p>{m.content}</p>
                {m.tab && <button className="linkish" onClick={() => onGo(m.tab)}>{t.chatOpenTab(t[m.tab] || m.tab)} →</button>}
              </div>
            ))}
            {busy && <div className="msg assistant typing"><p>…</p></div>}
            <div ref={end} />
          </div>
          <form onSubmit={(e) => { e.preventDefault(); ask() }}>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t.chatPlaceholder} maxLength={500} />
            <button className="btn small" disabled={busy || !text.trim()}>{t.chatSend}</button>
          </form>
          <p className="chat-note">{t.chatNote}</p>
        </section>
      )}
    </>
  )
}
