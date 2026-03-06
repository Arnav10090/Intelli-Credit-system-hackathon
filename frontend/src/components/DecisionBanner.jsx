export default function DecisionBanner({ decision, grade, score, trigger, counter }) {
    if (!decision) return null

    const map = {
        APPROVE: { color: 'var(--approve)', bg: 'var(--approve-bg)', icon: '✓', label: 'APPROVED' },
        PARTIAL: { color: 'var(--partial)', bg: 'var(--partial-bg)', icon: '⚡', label: 'PARTIAL APPROVAL' },
        REJECT: { color: 'var(--reject)', bg: 'var(--reject-bg)', icon: '✕', label: 'REJECTED' },
    }
    const d = map[decision] || map.REJECT

    return (
        <div style={{
            background: d.bg,
            border: `1px solid ${d.color}`,
            borderRadius: 'var(--radius-lg)',
            padding: '16px 20px',
            marginBottom: 20,
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: trigger ? 8 : 0 }}>
                <span style={{
                    width: 36, height: 36, borderRadius: '50%',
                    background: d.color, color: '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 18, fontWeight: 700, flexShrink: 0,
                }}>{d.icon}</span>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontSize: 18, fontWeight: 700, color: d.color, letterSpacing: 1 }}>
                            {d.label}
                        </span>
                        {grade && (
                            <span style={{
                                fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700,
                                color: d.color, background: d.bg,
                                border: `1px solid ${d.color}`, borderRadius: 4,
                                padding: '2px 8px',
                            }}>
                                Grade {grade} · {score}/100
                            </span>
                        )}
                    </div>
                    {trigger && (
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>
                            Primary trigger: {trigger}
                        </div>
                    )}
                </div>
            </div>
            {counter && (
                <div style={{
                    marginTop: 8, paddingTop: 8,
                    borderTop: `1px solid ${d.color}33`,
                    fontSize: 12, color: 'var(--text-muted)',
                    fontStyle: 'italic',
                }}>
                    ℹ️ {counter}
                </div>
            )}
        </div>
    )
}