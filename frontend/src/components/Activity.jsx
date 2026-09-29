import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Activity({ bizId, t, scanCount }) {
  const [log, setLog] = useState([])
  useEffect(() => { api.audit(bizId).then(setLog).catch(() => setLog([])) }, [bizId, scanCount])
  return (
    <section className="panel">
      <div className="panel-head"><h2>{t.activity}</h2></div>
      <table className="audit">
        <tbody>
          {log.map((e) => (
            <tr key={e.id}>
              <td className="faint" style={{ whiteSpace: 'nowrap' }}>{new Date(e.at).toLocaleString()}</td>
              <td><strong>{e.action.replaceAll('_', ' ')}</strong></td>
              <td>{t.actor} {e.actor}</td>
              <td className="faint">{e.detail && e.detail !== 'null' ? e.detail : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
