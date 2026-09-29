import { ASSISTANT_NAMES } from '../api.js'

export function pretty(category, v, lang = 'en') {
  const es = lang === 'es'
  if (category === 'stock') return /out|agotado/i.test(v) ? (es ? 'Agotado' : 'Sold out') : (es ? 'Disponible' : 'In stock')
  if (category === 'shipping') return `${v} ${es ? 'días' : 'days'}`
  if (category === 'returns') return ['none', '0'].includes(v) ? (es ? 'Sin devoluciones' : 'No returns') : `${v} ${es ? 'días' : 'days'}`
  if (category === 'price') return `$${v}`
  if (v === 'closed') return es ? 'Cerrado' : 'Closed'
  return v.replace(/^(\d{2}:\d{2})-(\d{2}:\d{2})$/, '$1–$2')
}

export default function Matrix({ data, t, lang }) {
  if (!data.latest) return <div className="panel empty">{t.noScan}</div>
  const providers = data.providers
  const groups = []
  for (const row of data.matrix) {
    const name = row.product ? (lang === 'es' && row.product_es ? row.product_es : row.product) : ''
    const g = groups.find((x) => x.name === name)
    g ? g.rows.push(row) : groups.push({ name, rows: [row] })
  }
  const hasProducts = groups.some((g) => g.name)
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.truth}</h2>
        <span className="faint" style={{ maxWidth: '60ch' }}>{t.matrixHint}</span>
      </div>
      <div className="matrix-wrap">
        <table className="matrix">
          <thead>
            <tr>
              <th scope="col"></th>
              <th scope="col" className="truth">{t.verified}</th>
              {providers.map((p) => <th scope="col" key={p}>{ASSISTANT_NAMES[p] || p}</th>)}
            </tr>
          </thead>
          {groups.map((g) => (
            <tbody key={g.name || 'store'}>
              {hasProducts && (
                <tr className="group-row"><th colSpan={providers.length + 2} scope="rowgroup">{g.name || t.storeWide}</th></tr>
              )}
              {g.rows.map((row) => (
                <tr key={row.key}>
                  <th scope="row" className="fact">{lang === 'es' && row.label_es ? row.label_es : row.label}</th>
                  <td className="truth">
                    <span className="val">{pretty(row.category, row.value, lang)}</span>
                    <span className={`evidence ${row.evidence}`} title={t.evidenceHint[row.evidence]}>{t.evidence[row.evidence]}</span>
                  </td>
                  {providers.map((p) => {
                    const c = row.assistants[p]
                    return (
                      <td key={p}>
                        {c ? (
                          <div className="cell">
                            <span className="val">{pretty(row.category, c.value, lang)}</span>
                            <span className={`verdict ${c.verdict}`}>{t[c.verdict]}</span>
                          </div>
                        ) : <span className="none">{t.notMentioned}</span>}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </section>
  )
}
