/**
 * MLValidationPanel.jsx
 * Full ML second-opinion panel — shows default probability, risk label,
 * agreement with scorecard, feature importances, and divergence alerts.
 */

export default function MLValidationPanel({ ml }) {
    if (!ml) return null

    const prob = ml.default_probability ?? 0
    const probPct = Math.round(prob * 100)
    const label = ml.predicted_label ?? 'unknown'
    const agrees = ml.agrees_with_scorecard
    const divergence = ml.divergence_flag
    const note = ml.divergence_note
    const modelUsed = ml.model_used
    const confidence = Math.round((ml.confidence ?? 0) * 100)
    const importances = ml.feature_importances ?? {}

    // Color maps
    const labelColor = label === 'low_risk'
        ? 'var(--approve)'
        : label === 'medium_risk'
            ? 'var(--partial)'
            : 'var(--reject)'

    const probColor = prob < 0.25
        ? 'var(--approve)'
        : prob < 0.55
            ? 'var(--partial)'
            : 'var(--reject)'

    // Sort importances descending, take top 5
    const topFeatures = Object.entries(importances)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)

    const maxImportance = topFeatures.length > 0
        ? Math.max(...topFeatures.map(([, v]) => Math.abs(v)))
        : 1

    const FEATURE_LABELS = {
        dscr: 'DSCR',
        de_ratio: 'D/E Ratio',
        litigation_risk: 'Litigation Risk',
        security_cover: 'Security Cover',
        promoter_track_record: 'Promoter Track Record',
        gst_compliance: 'GST Compliance',
        ebitda_margin_trend: 'EBITDA Margin Trend',
        net_worth_trend: 'Net Worth Trend',
        promoter_equity_pct_norm: 'Promoter Equity',
        collateral_encumbrance: 'Collateral Encumbrance',
        revenue_cagr_vs_sector: 'Revenue CAGR vs Sector',
        plant_utilization: 'Plant Utilization',
        management_quality: 'Mgmt Quality',
        sector_outlook: 'Sector Outlook',
        customer_concentration: 'Customer Concentration',
        regulatory_environment: 'Regulatory Environment',
    }

    return (
        <div style={{
            background: 'var(--surface)',
            border: `1px solid ${divergence ? 'var(--partial)' : 'var(--border)'}`,
            borderRadius: 'var(--radius)',
            overflow: 'hidden',
            marginBottom: 20,
        }}>
            {/* Header bar */}
            <div style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 16px',
                background: divergence ? 'var(--partial-bg)' : 'var(--surface-alt)',
                borderBottom: `1px solid ${divergence ? 'var(--partial)33' : 'var(--border)'}`,
            }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', letterSpacing: 0.3 }}>
                    🤖 ML Second Opinion
                </span>
                <span style={{
                    fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
                    background: 'var(--border)', borderRadius: 3, padding: '2px 6px',
                    textTransform: 'uppercase', letterSpacing: 0.5,
                }}>
                    {modelUsed === 'sklearn_hgb' ? 'HistGradientBoosting' : 'Rule Fallback'}
                </span>
                <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-dim)' }}>
                    Confidence: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{confidence}%</span>
                </span>
            </div>

            <div style={{ padding: '14px 16px' }}>

                {/* Divergence alert */}
                {divergence && note && (
                    <div style={{
                        background: 'var(--partial-bg)',
                        border: '1px solid var(--partial)',
                        borderRadius: 'var(--radius)',
                        padding: '10px 14px',
                        marginBottom: 14,
                        fontSize: 12,
                        color: 'var(--text)',
                        lineHeight: 1.6,
                    }}>
                        {note}
                    </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>

                    {/* Default probability */}
                    <div style={{
                        background: 'var(--surface-alt)', border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)', padding: '12px 14px',
                    }}>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 }}>
                            Default Probability
                        </div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 700, color: probColor, marginBottom: 8 }}>
                            {probPct}%
                        </div>
                        {/* Probability bar */}
                        <div style={{ height: 5, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                            <div style={{
                                width: `${probPct}%`,
                                height: '100%',
                                background: probColor,
                                borderRadius: 3,
                                transition: 'width 0.8s ease',
                                boxShadow: `0 0 6px ${probColor}55`,
                            }} />
                        </div>
                        <div style={{ fontSize: 9, color: 'var(--text-dim)', marginTop: 4, display: 'flex', justifyContent: 'space-between' }}>
                            <span>0% (safe)</span>
                            <span>100% (default)</span>
                        </div>
                    </div>

                    {/* Risk label */}
                    <div style={{
                        background: 'var(--surface-alt)', border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)', padding: '12px 14px',
                    }}>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 }}>
                            ML Risk Label
                        </div>
                        <div style={{
                            fontSize: 14, fontWeight: 700, color: labelColor,
                            fontFamily: 'var(--font-mono)', textTransform: 'uppercase',
                            letterSpacing: 0.5, marginBottom: 8,
                        }}>
                            {label.replace('_', ' ')}
                        </div>
                        <div style={{
                            fontSize: 10, color: labelColor,
                            background: labelColor + '15',
                            border: `1px solid ${labelColor}40`,
                            borderRadius: 3, padding: '3px 8px', display: 'inline-block',
                        }}>
                            {prob < 0.25 ? 'Low default risk' : prob < 0.55 ? 'Moderate risk' : 'High default risk'}
                        </div>
                    </div>

                    {/* Scorecard agreement */}
                    <div style={{
                        background: 'var(--surface-alt)', border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)', padding: '12px 14px',
                    }}>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 }}>
                            Scorecard Agreement
                        </div>
                        <div style={{
                            fontSize: 18, fontWeight: 700,
                            color: agrees ? 'var(--approve)' : 'var(--partial)',
                            fontFamily: 'var(--font-mono)', marginBottom: 6,
                        }}>
                            {agrees ? '✓ Agrees' : '⚠ Divergent'}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>
                            {agrees
                                ? 'ML consistent with scorecard decision'
                                : 'ML directionally disagrees — review recommended'}
                        </div>
                    </div>

                </div>

                {/* Feature importances */}
                {topFeatures.length > 0 && (
                    <div>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 10 }}>
                            Top Predictive Features (permutation importance)
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                            {topFeatures.map(([feat, val]) => {
                                const barPct = (Math.abs(val) / maxImportance) * 100
                                const label = FEATURE_LABELS[feat] ?? feat
                                return (
                                    <div key={feat} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                        <div style={{ width: 140, fontSize: 11, color: 'var(--text-muted)', flexShrink: 0, textAlign: 'right' }}>
                                            {label}
                                        </div>
                                        <div style={{ flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                                            <div style={{
                                                width: `${barPct}%`, height: '100%',
                                                background: 'var(--blue-bright)',
                                                borderRadius: 3,
                                                transition: 'width 0.6s ease',
                                                boxShadow: '0 0 4px var(--blue-bright)44',
                                            }} />
                                        </div>
                                        <div style={{ width: 48, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', textAlign: 'right' }}>
                                            {val.toFixed(4)}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 8, fontStyle: 'italic' }}>
                            Permutation importance: how much AUC drops when this feature is shuffled. Higher = more important.
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}