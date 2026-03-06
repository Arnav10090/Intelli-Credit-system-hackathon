const PILLARS = [
    { key: 'character', label: 'Character', max: 60, icon: '◈' },
    { key: 'capacity', label: 'Capacity', max: 60, icon: '◉' },
    { key: 'capital', label: 'Capital', max: 45, icon: '◆' },
    { key: 'collateral', label: 'Collateral', max: 30, icon: '◇' },
    { key: 'conditions', label: 'Conditions', max: 35, icon: '◎' },
]

function barColor(pct) {
    if (pct >= 70) return 'var(--approve)'
    if (pct >= 50) return 'var(--partial)'
    return 'var(--reject)'
}

export default function PillarBars({ pillars = {} }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {PILLARS.map(p => {
                const data = pillars[p.key] || {}
                const score = data.score ?? 0
                const max = data.max ?? p.max
                const pct = max > 0 ? (score / max) * 100 : 0
                const color = barColor(pct)

                return (
                    <div key={p.key}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 5 }}>
                            <span style={{ fontSize: 12, color: 'var(--text-dim)', marginRight: 6 }}>{p.icon}</span>
                            <span style={{ fontSize: 12, color: 'var(--text)', flex: 1, fontWeight: 500 }}>
                                {p.label}
                            </span>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color }}>
                                {score} / {max}
                            </span>
                            <span style={{
                                fontFamily: 'var(--font-mono)', fontSize: 10,
                                color: 'var(--text-muted)', marginLeft: 8, width: 34, textAlign: 'right'
                            }}>
                                {pct.toFixed(0)}%
                            </span>
                        </div>
                        <div style={{
                            height: 7, background: 'var(--border)',
                            borderRadius: 4, overflow: 'hidden', position: 'relative',
                        }}>
                            <div style={{
                                position: 'absolute', left: 0, top: 0, bottom: 0,
                                width: `${pct}%`, background: color,
                                borderRadius: 4, transition: 'width 0.6s ease',
                                boxShadow: `0 0 6px ${color}55`,
                            }} />
                        </div>
                    </div>
                )
            })}
        </div>
    )
}