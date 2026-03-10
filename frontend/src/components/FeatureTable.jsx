import { useState } from 'react'

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
    const [search, setSearch] = useState('')
    const [pillarFilter, setPillarFilter] = useState('All')
    const [currentPage, setCurrentPage] = useState(1)
    const [rowsPerPage] = useState(6)

    const allRows = Object.entries(contributions)
        .map(([key, val]) => ({
            key,
            label: FEATURE_LABELS[key] || key,
            pillar: PILLARS[key] || '',
            awarded: val.points_awarded ?? 0,
            max: val.max_points ?? 0,
            pct: val.pct ?? 0,
        }))
        .sort((a, b) => a.pct - b.pct)  // worst first

    // Filtering logic
    const filteredRows = allRows.filter(r => {
        const matchesSearch = r.label.toLowerCase().includes(search.toLowerCase())
        const matchesPillar = pillarFilter === 'All' || r.pillar === pillarFilter
        return matchesSearch && matchesPillar
    })

    // Pagination logic
    const totalPages = Math.ceil(filteredRows.length / rowsPerPage)
    const startIndex = (currentPage - 1) * rowsPerPage
    const paginatedRows = filteredRows.slice(startIndex, startIndex + rowsPerPage)

    const handleSearch = (e) => {
        setSearch(e.target.value)
        setCurrentPage(1)
    }

    const handlePillarChange = (p) => {
        setPillarFilter(p)
        setCurrentPage(1)
    }

    if (!allRows.length) return (
        <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '12px 0' }}>
            No contribution data available
        </div>
    )

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Toolbar */}
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
                    <input
                        type="text"
                        placeholder="Search features..."
                        value={search}
                        onChange={handleSearch}
                        style={{
                            width: '100%',
                            background: 'var(--surface-alt)',
                            border: '1px solid var(--border)',
                            borderRadius: 'var(--radius)',
                            padding: '8px 12px',
                            color: 'var(--text)',
                            fontSize: 12,
                            outline: 'none',
                        }}
                    />
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {['All', ...new Set(Object.values(PILLARS))].map(p => (
                        <button
                            key={p}
                            onClick={() => handlePillarChange(p)}
                            style={{
                                background: pillarFilter === p ? 'var(--blue-bright)' : 'var(--surface-alt)',
                                color: pillarFilter === p ? '#fff' : 'var(--text-dim)',
                                border: '1px solid var(--border)',
                                borderRadius: 'var(--radius)',
                                padding: '4px 10px',
                                fontSize: 10,
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                            }}
                        >{p}</button>
                    ))}
                </div>
            </div>

            {/* Table */}
            <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-alt)' }}>
                            {['Pillar', 'Feature', 'Score', 'Max', '% Achieved', 'Gap'].map(h => (
                                <th key={h} style={{
                                    padding: '10px 12px', textAlign: h === 'Feature' ? 'left' : 'right',
                                    fontSize: 10, fontWeight: 700, color: 'var(--text-dim)',
                                    textTransform: 'uppercase', letterSpacing: 0.8,
                                    fontFamily: 'var(--font-ui)',
                                }}>{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {paginatedRows.length === 0 ? (
                            <tr>
                                <td colSpan="6" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                                    No features matches your filters
                                </td>
                            </tr>
                        ) : paginatedRows.map((r, i) => {
                            const color = barColor(r.pct)
                            const pillarColor = PILLAR_COLORS[r.pillar] || 'var(--text-muted)'
                            const gap = r.max - r.awarded

                            return (
                                <tr key={r.key} style={{
                                    borderBottom: '1px solid var(--border-soft)',
                                    background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                                }}>
                                    <td style={{ padding: '9px 12px', width: 90 }}>
                                        <span style={{
                                            fontSize: 10, fontWeight: 700, color: pillarColor,
                                            background: `${pillarColor}18`,
                                            border: `1px solid ${pillarColor}44`,
                                            borderRadius: 3, padding: '2px 6px',
                                            whiteSpace: 'nowrap',
                                            textTransform: 'uppercase',
                                        }}>{r.pillar}</span>
                                    </td>
                                    <td style={{ padding: '9px 12px', fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>
                                        {r.label}
                                    </td>
                                    <td style={{
                                        padding: '9px 12px', textAlign: 'right',
                                        fontFamily: 'var(--font-mono)', fontSize: 12,
                                        color, fontWeight: 700,
                                    }}>{r.awarded}</td>
                                    <td style={{
                                        padding: '9px 12px', textAlign: 'right',
                                        fontFamily: 'var(--font-mono)', fontSize: 12,
                                        color: 'var(--text-dim)',
                                    }}>{r.max}</td>
                                    <td style={{ padding: '9px 12px', minWidth: 140 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'flex-end' }}>
                                            <div style={{
                                                flex: 1, maxWidth: 80, height: 6,
                                                background: 'var(--border)', borderRadius: 4, overflow: 'hidden',
                                                boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.2)',
                                            }}>
                                                <div style={{
                                                    height: '100%', width: `${r.pct}%`,
                                                    background: color, borderRadius: 4,
                                                    transition: 'width 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
                                                    boxShadow: `0 0 8px ${color}66`,
                                                }} />
                                            </div>
                                            <span style={{
                                                fontFamily: 'var(--font-mono)', fontSize: 11, color, width: 34, textAlign: 'right', fontWeight: 600
                                            }}>{r.pct.toFixed(0)}%</span>
                                        </div>
                                    </td>
                                    <td style={{
                                        padding: '9px 12px', textAlign: 'right',
                                        fontFamily: 'var(--font-mono)', fontSize: 11,
                                        color: gap > 5 ? 'var(--reject)' : 'var(--text-dim)',
                                        fontWeight: gap > 5 ? 600 : 400,
                                    }}>{gap > 0 ? `-${gap}` : '—'}</td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 4px' }}>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                        Showing <span style={{ color: 'var(--text)', fontWeight: 600 }}>{startIndex + 1}</span> to <span style={{ color: 'var(--text)', fontWeight: 600 }}>{Math.min(startIndex + rowsPerPage, filteredRows.length)}</span> of <span style={{ color: 'var(--text)', fontWeight: 600 }}>{filteredRows.length}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                        <button
                            disabled={currentPage === 1}
                            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                            style={{
                                background: 'var(--surface-alt)',
                                color: 'var(--text)',
                                border: '1px solid var(--border)',
                                borderRadius: 'var(--radius)',
                                padding: '6px 12px',
                                fontSize: 11,
                                fontWeight: 600,
                                cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                                opacity: currentPage === 1 ? 0.5 : 1,
                            }}
                        >Prev</button>
                        <div style={{ display: 'flex', gap: 4 }}>
                            {[...Array(totalPages)].map((_, i) => (
                                <button
                                    key={i}
                                    onClick={() => setCurrentPage(i + 1)}
                                    style={{
                                        width: 28, height: 28,
                                        background: currentPage === i + 1 ? 'var(--blue-bright)' : 'var(--surface-alt)',
                                        color: currentPage === i + 1 ? '#fff' : 'var(--text-dim)',
                                        border: '1px solid var(--border)',
                                        borderRadius: 'var(--radius)',
                                        fontSize: 11,
                                        fontWeight: 600,
                                        cursor: 'pointer',
                                    }}
                                >{i + 1}</button>
                            ))}
                        </div>
                        <button
                            disabled={currentPage === totalPages}
                            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                            style={{
                                background: 'var(--surface-alt)',
                                color: 'var(--text)',
                                border: '1px solid var(--border)',
                                borderRadius: 'var(--radius)',
                                padding: '6px 12px',
                                fontSize: 11,
                                fontWeight: 600,
                                cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                                opacity: currentPage === totalPages ? 0.5 : 1,
                            }}
                        >Next</button>
                    </div>
                </div>
            )}
        </div>
    )
}