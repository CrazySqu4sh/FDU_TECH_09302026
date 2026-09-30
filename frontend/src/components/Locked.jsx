export default function Locked({ t, plan, text, onUpgrade, compact = false }) {
  return (
    <div className={`locked ${compact ? 'compact' : ''}`}>
      <span className={`plan-chip ${plan}`}>{t.planName[plan]}</span>
      <p>{text}</p>
      <button className="btn small" onClick={onUpgrade}>{t.seePlans}</button>
    </div>
  )
}
