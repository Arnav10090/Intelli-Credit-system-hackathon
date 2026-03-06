const FEATURE_LABELS = {
    litigation_risk: 'Litigation Risk',
    promoter_track_record: 'Promoter Track Record',
    gst_compliance: 'GST Compliance',
    management_quality: 'Management Quality',
    dscr: 'DSCR',
    ebitda_margin_trend: 'EBITDA Margin Trend',
    revenue_cagr_vs_sector: 'Revenue CAGR vs Sector',
    plant_utilization: 'Plant Utilization',
    de_ratio: 'D/E Ratio',
    net_worth_trend: 'Net Worth Trend',
    promoter_equity_pct: 'Promoter Equity %',
    security_cover: 'Security Cover',
    collateral_encumbrance: 'Collateral Encumbrance',
    sector_outlook: 'Sector Outlook',
    customer_concentration: 'Customer Concentration',
    regulatory_environment: 'Regulatory Environment',
}

const PILLARS = {
    litigation_risk: 'Character',
    promoter_track_record: 'Character',
    gst_compliance: 'Character',
    management_quality: 'Character',
    dscr: 'Capacity',
    ebitda_margin_trend: 'Capacity',
    revenue_cagr_vs_sector: 'Capacity',
    plant_utilization: 'Capacity',
    de_ratio: 'Capital',
    net_worth_trend: 'Capital',
    promoter_equity_pct: 'Capital',
    security_cover: 'Collateral',
    collateral_encumbrance: 'Collateral',
    sector_outlook: 'Conditions',
    customer_concentration: 'Conditions',
    regulatory_environment: 'Conditions',
}

const PILLAR_COLORS = {
    Character: '#7C8CFF',
    Capacity: '#4D9EFF',
    Capital: '#2BD9C8',
    Collateral: '#E09B2B',
    Conditions: '#A855F7',
}

function barColor(pct) {
    if (pct >= 70) return 'var(--approve)'
    if (pct >= 40) return 'var(--partial)'
    return 'var(--reject)'
}

export default function FeatureTable({ contributions = {} }) {
    const rows = Object.entries(contributions)
        .map(([key, val]) => ({
            key,
            label: FEATURE_LABELS[key] || key,
            pillar: PILLARS[key] || '',
            awarded: val.points_awarded ?? 0,
            max: val.max_points ?? 0,
            pct: val.pct ?? 0,
        }))
        .sort((a, b) => a.pct - b.pct)  // worst first

    if (!rows.length) return (
        <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '12px 0' }}>
            No contribution data available
        </div>
    )

    return (
        <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        {['Pillar', 'Feature', 'Score', 'Max', '% Achieved', 'Gap'].map(h => (
                            <th key={h} style={{
                                padding: '6px 10px', textAlign: h === 'Feature' ? 'left' : 'right',
                                fontSize: 10, fontWeight: 600, color: 'var(--text-dim)',
                                textTransform: 'uppercase', letterSpacing: 0.8,
                                fontFamily: 'var(--font-ui)',
                            }}>{h}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((r, i) => {
                        const color = barColor(r.pct)
                        const pillarColor = PILLAR_COLORS[r.pillar] || 'var(--text-muted)'
                        const gap = r.max - r.awarded

                        return (
                            <tr key={r.key} style={{
                                borderBottom: '1px solid var(--border-soft)',
                                background: i % 2 === 0 ? 'transparent' : 'var(--surface-alt)',
                            }}>
                                <td style={{ padding: '7px 10px', width: 90 }}>
                                    <span style={{
                                        fontSize: 10, fontWeight: 600, color: pillarColor,
                                        background: `${pillarColor}18`,
                                        border: `1px solid ${pillarColor}44`,
                                        borderRadius: 3, padding: '2px 6px',
                                        whiteSpace: 'nowrap',
                                    }}>{r.pillar}</span>
                                </td>
                                <td style={{ padding: '7px 10px', fontSize: 12, color: 'var(--text)' }}>
                                    {r.label}
                                </td>
                                <td style={{
                                    padding: '7px 10px', textAlign: 'right',
                                    fontFamily: 'var(--font-mono)', fontSize: 12,
                                    color, fontWeight: r.pct < 40 ? 700 : 400,
                                }}>{r.awarded}</td>
                                <td style={{
                                    padding: '7px 10px', textAlign: 'right',
                                    fontFamily: 'var(--font-mono)', fontSize: 12,
                                    color: 'var(--text-muted)',
                                }}>{r.max}</td>
                                <td style={{ padding: '7px 10px', minWidth: 120 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
                                        <div style={{
                                            flex: 1, maxWidth: 80, height: 5,
                                            background: 'var(--border)', borderRadius: 3, overflow: 'hidden',
                                        }}>
                                            <div style={{
                                                height: '100%', width: `${r.pct}%`,
                                                background: color, borderRadius: 3,
                                                transition: 'width 0.5s ease',
                                            }} />
                                        </div>
                                        <span style={{
                                            fontFamily: 'var(--font-mono)', fontSize: 11, color, width: 34, textAlign: 'right',
                                        }}>{r.pct.toFixed(0)}%</span>
                                    </div>
                                </td>
                                <td style={{
                                    padding: '7px 10px', textAlign: 'right',
                                    fontFamily: 'var(--font-mono)', fontSize: 11,
                                    color: gap > 5 ? 'var(--reject)' : 'var(--text-dim)',
                                }}>{gap > 0 ? `-${gap}` : '—'}</td>
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}