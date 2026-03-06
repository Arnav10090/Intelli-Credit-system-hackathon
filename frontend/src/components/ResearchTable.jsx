const TIER_META = {
    1: { label: 'T1', color: 'var(--critical)', bg: 'var(--reject-bg)', title: 'Critical' },
    2: { label: 'T2', color: 'var(--high)', bg: 'var(--partial-bg)', title: 'High Risk' },
    3: { label: 'T3', color: 'var(--medium)', bg: '#1A1500', title: 'Monitor' },
}

const SOURCE_ICON = {
    'Economic Times': 'ET',
    'Business Standard': 'BS',
    'MoneyControl': 'MC',
    'Mint': 'MI',
    'MCA21': 'MCA',
    'eCourts India': 'EC',
    'BSE India': 'BSE',
}

export default function ResearchTable({ items = [] }) {
    if (!items.length) return (
        <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '16px 0', textAlign: 'center' }}>
            No research findings loaded
        </div>
    )

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {items.map((item, i) => {
                const tier = item.risk_tier
                const meta = TIER_META[tier] || { label: '+', color: 'var(--approve)', bg: 'var(--approve-bg)', title: 'Positive' }
                const delta = item.risk_score_delta ?? 0
                const srcAbbr = SOURCE_ICON[item.source_name] || (item.source_name || '').slice(0, 3).toUpperCase()

                return (
                    <div key={i} style={{
                        display: 'flex', alignItems: 'flex-start', gap: 12,
                        background: tier === 1 ? meta.bg : 'var(--surface-alt)',
                        border: `1px solid ${tier === 1 ? meta.color + '44' : 'var(--border-soft)'}`,
                        borderRadius: 'var(--radius)',
                        padding: '10px 14px',
                        transition: 'border-color 0.2s',
                    }}>
                        {/* Tier badge */}
                        <div style={{ flexShrink: 0, paddingTop: 1 }}>
                            <span style={{
                                display: 'inline-block',
                                width: 28, height: 28, borderRadius: '50%',
                                background: meta.color + '22',
                                border: `1px solid ${meta.color}`,
                                color: meta.color,
                                fontSize: 9, fontWeight: 700,
                                fontFamily: 'var(--font-mono)',
                                textAlign: 'center', lineHeight: '26px',
                                ...(tier === 1 && { boxShadow: `0 0 8px ${meta.color}66` }),
                            }}>{meta.label}</span>
                        </div>

                        {/* Content */}
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.4, marginBottom: 4 }}>
                                {item.title}
                            </div>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                                {/* Source */}
                                <span style={{
                                    fontSize: 10, fontWeight: 700,
                                    color: 'var(--text-dim)',
                                    background: 'var(--border)',
                                    borderRadius: 3, padding: '1px 6px',
                                    fontFamily: 'var(--font-mono)',
                                }}>{srcAbbr}</span>
                                {/* Keywords */}
                                {(item.matched_keywords || []).slice(0, 2).map((kw, j) => (
                                    <span key={j} style={{
                                        fontSize: 10, color: meta.color,
                                        background: meta.bg,
                                        border: `1px solid ${meta.color}33`,
                                        borderRadius: 3, padding: '1px 6px',
                                    }}>{kw}</span>
                                ))}
                            </div>
                        </div>

                        {/* Delta */}
                        <div style={{
                            flexShrink: 0, fontFamily: 'var(--font-mono)',
                            fontSize: 12, fontWeight: 700, paddingTop: 4,
                            color: delta < 0 ? meta.color : 'var(--approve)',
                        }}>
                            {delta > 0 ? `+${delta}` : delta}
                        </div>
                    </div>
                )
            })}
        </div>
    )
}