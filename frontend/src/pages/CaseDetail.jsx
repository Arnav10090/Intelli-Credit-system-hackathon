import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'
import DecisionBanner from '../components/DecisionBanner.jsx'
import ScoreGauge from '../components/ScoreGauge.jsx'
import PillarBars from '../components/PillarBars.jsx'
import FeatureTable from '../components/FeatureTable.jsx'
import FinancialChart from '../components/FinancialChart.jsx'
import ResearchTable from '../components/ResearchTable.jsx'

/* ── helpers ─────────────────────────────────────────────────── */
function fmt(v, unit = 'L') {
    if (v == null) return '—'
    const n = Number(v)
    if (unit === 'Cr') return `₹${n.toFixed(2)} Cr`
    if (unit === 'x') return `${n.toFixed(2)}x`
    if (unit === '%') return `${n.toFixed(1)}%`
    if (unit === 'd') return `${n.toFixed(0)}d`
    return `₹${n.toFixed(0)}L`
}

function Stat({ label, value, sub, color }) {
    return (
        <div style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '12px 14px' }}>
            <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4 }}>{label}</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 700, color: color || 'var(--blue-bright)' }}>{value}</div>
            {sub && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>}
        </div>
    )
}

function Badge({ label, color }) {
    return (
        <span style={{
            fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)',
            color, background: color + '20', border: `1px solid ${color}55`,
            borderRadius: 3, padding: '2px 7px', textTransform: 'uppercase',
        }}>{label}</span>
    )
}

const STEPS = [
    { id: 'create', label: 'Create Case' },
    { id: 'demo', label: 'Load Data' },
    { id: 'analyze', label: 'Analyze' },
    { id: 'score', label: 'Score' },
    { id: 'research', label: 'Research' },
    { id: 'cam', label: 'Generate CAM' },
]

const STATUS_STEP = {
    draft: 0,
    ingested: 1,
    analyzed: 2,
    scored: 3,
    researched: 4,
    cam_generated: 5,
}

const TABS = ['Pipeline', 'Scorecard', 'Financials', 'Research', 'CAM']

/* ── main component ──────────────────────────────────────────── */
export default function CaseDetail({ demo }) {
    const { id } = useParams()
    const navigate = useNavigate()

    const [caseId, setCaseId] = useState(null)
    const [caseData, setCaseData] = useState(null)
    const [score, setScore] = useState(null)
    const [research, setResearch] = useState([])
    const [resSummary, setResSummary] = useState(null)
    const [camStatus, setCamStatus] = useState(null)
    const [wc, setWc] = useState(null)   // yearly_metrics from score
    const [flags, setFlags] = useState([])
    const [tab, setTab] = useState('Pipeline')
    const [loading, setLoading] = useState({})
    const [errors, setErrors] = useState({})
    const [stepDone, setStepDone] = useState(0)      // highest completed step index
    const [log, setLog] = useState([])

    /* ── boot: load or create demo case ─────────────────────── */
    useEffect(() => {
        if (demo) {
            // check if demo case already exists via listing
            api.listCases().then(cases => {
                const existing = cases.find(c => c.company_name === 'Acme Textiles Ltd')
                if (existing) {
                    setCaseId(existing.id)
                    setCaseData(existing)
                    refreshAll(existing.id, existing.status)
                } else {
                    api.createCase({
                        company_name: 'Acme Textiles Ltd',
                        company_cin: 'U17100MH2010PLC201234',
                        company_pan: 'AAACA1234B',
                        requested_amount_cr: 20,
                        requested_tenor_yr: 7,
                        purpose: 'Working Capital + Term Loan for capacity expansion',
                    }).then(res => {
                        setCaseId(res.case_id)
                        setCaseData({ company_name: res.company_name, status: 'draft' })
                        addLog('Case created: ' + res.case_id)
                    }).catch(err => addLog('Error: ' + err.message))
                }
            })
        } else if (id) {
            setCaseId(id)
            refreshAll(id)
        }
    }, [demo, id])

    function addLog(msg) {
        setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`])
    }

    async function refreshAll(cid, status) {
        const caseRes = await api.listCases().then(cs => cs.find(c => c.id === cid)).catch(() => null)
        if (caseRes) {
            setCaseData(caseRes)
            const step = STATUS_STEP[caseRes.status] ?? 0
            setStepDone(step)
        }
        // Try loading score
        try {
            const sc = await api.getScore(cid)
            setScore(sc)
            // Extract yearly metrics from scoring data if embedded
        } catch { }
        // Try loading research
        try {
            const rs = await api.getResearch(cid)
            setResearch(rs)
        } catch { }
        try {
            const rsum = await api.getResearchSummary(cid)
            setResSummary(rsum)
        } catch { }
        // CAM status
        try {
            const cs = await api.getCamStatus(cid)
            setCamStatus(cs)
            if (cs.exists) setStepDone(s => Math.max(s, 5))
        } catch { }
        // Flags
        try {
            const fl = await api.listFlags(cid)
            setFlags(fl)
        } catch { }
    }

    function setLoad(key, val) { setLoading(p => ({ ...p, [key]: val })) }
    function setErr(key, val) { setErrors(p => ({ ...p, [key]: val })) }
    function clearErr(key) { setErrors(p => ({ ...p, [key]: null })) }

    /* ── pipeline steps ──────────────────────────────────────── */
    async function doLoadDemo() {
        if (!caseId) return
        setLoad('demo', true); clearErr('demo')
        try {
            const r = await api.loadDemo(caseId)
            addLog(`Demo loaded: ${r.documents_loaded} docs, ${r.flags_raised} flags`)
            setStepDone(s => Math.max(s, 1))
            setCaseData(p => ({ ...p, status: 'ingested' }))
        } catch (e) { setErr('demo', e.message) }
        setLoad('demo', false)
    }

    async function doAnalyze() {
        if (!caseId) return
        setLoad('analyze', true); clearErr('analyze')
        try {
            const r = await api.analyze(caseId)
            addLog(`Analysis: ${r.total_flags} flags | DSCR ${r.avg_dscr?.toFixed(2)}x | D/E ${r.latest_de_ratio?.toFixed(2)}x`)
            setStepDone(s => Math.max(s, 2))
            setCaseData(p => ({ ...p, status: 'analyzed' }))
            const fl = await api.listFlags(caseId)
            setFlags(fl)
        } catch (e) { setErr('analyze', e.message) }
        setLoad('analyze', false)
    }

    async function doScore() {
        if (!caseId) return
        setLoad('score', true); clearErr('score')
        try {
            const r = await api.runScore(caseId)
            addLog(`Scored: ${r.normalised_score}/100 Grade ${r.risk_grade} → ${r.decision}`)
            // fetch full score detail
            const sc = await api.getScore(caseId)
            setScore(sc)
            setStepDone(s => Math.max(s, 3))
            setCaseData(p => ({ ...p, status: 'scored' }))
        } catch (e) { setErr('score', e.message) }
        setLoad('score', false)
    }

    async function doResearch() {
        if (!caseId) return
        setLoad('research', true); clearErr('research')
        try {
            const r = await api.loadResearch(caseId)
            addLog(`Research: ${r.articles_saved} findings | Delta ${r.aggregate?.total_risk_delta}`)
            const rs = await api.getResearch(caseId)
            setResearch(rs)
            try {
                const rsum = await api.getResearchSummary(caseId)
                setResSummary(rsum)
            } catch { }
            setStepDone(s => Math.max(s, 4))
            setCaseData(p => ({ ...p, status: 'researched' }))
        } catch (e) { setErr('research', e.message) }
        setLoad('research', false)
    }

    async function doGenCam() {
        if (!caseId) return
        setLoad('cam', true); clearErr('cam')
        try {
            const r = await api.generateCam(caseId, 'Demo Analyst')
            addLog(`CAM generated: ${r.filename} (~${r.pages_est} pages) via ${r.model_used}`)
            const cs = await api.getCamStatus(caseId)
            setCamStatus(cs)
            setStepDone(s => Math.max(s, 5))
            setCaseData(p => ({ ...p, status: 'cam_generated' }))
        } catch (e) { setErr('cam', e.message) }
        setLoad('cam', false)
    }

    /* ── sidebar metrics ─────────────────────────────────────── */
    const decisionColor = !score?.decision ? 'var(--text-muted)'
        : score.decision === 'APPROVE' ? 'var(--approve)'
            : score.decision === 'PARTIAL' ? 'var(--partial)'
                : 'var(--reject)'

    /* ── render ──────────────────────────────────────────────── */
    return (
        <div style={{ padding: '24px 28px', maxWidth: 1200 }}>

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
                <button
                    onClick={() => navigate('/')}
                    style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '5px 10px', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 12 }}
                >← Back</button>
                <div>
                    <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', marginBottom: 2 }}>
                        {caseData?.company_name || '—'}
                    </h2>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <Badge
                            label={caseData?.status || 'draft'}
                            color={caseData?.status === 'cam_generated' ? 'var(--approve)' : caseData?.status === 'scored' ? 'var(--blue-bright)' : 'var(--text-muted)'}
                        />
                        {caseId && (
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>
                                {caseId.slice(0, 8).toUpperCase()}
                            </span>
                        )}
                    </div>
                </div>

                {/* Score quick-view */}
                {score && (
                    <div style={{ marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' }}>
                        <div style={{ textAlign: 'right' }}>
                            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 700, color: decisionColor }}>
                                {score.normalised_score}
                                <span style={{ fontSize: 12, color: 'var(--text-dim)', marginLeft: 2 }}>/100</span>
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                                Grade {score.risk_grade}
                            </div>
                        </div>
                        <div style={{
                            padding: '6px 14px', borderRadius: 'var(--radius)',
                            background: decisionColor + '20', border: `1px solid ${decisionColor}`,
                            fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, color: decisionColor,
                        }}>{score.decision}</div>
                    </div>
                )}
            </div>

            {/* Stepper */}
            <div style={{
                display: 'flex', alignItems: 'center', gap: 0,
                background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)', padding: '12px 16px',
                marginBottom: 20, overflowX: 'auto',
            }}>
                {STEPS.map((s, i) => {
                    const done = i < stepDone
                    const current = i === stepDone
                    const future = i > stepDone
                    const color = done ? 'var(--approve)' : current ? 'var(--blue-bright)' : 'var(--text-dim)'
                    return (
                        <div key={s.id} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, minWidth: 80 }}>
                                <div style={{
                                    width: 26, height: 26, borderRadius: '50%',
                                    background: done ? 'var(--approve)' : current ? 'var(--blue-dim)' : 'var(--border)',
                                    border: `2px solid ${color}`,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: 10, fontWeight: 700, color: done ? '#fff' : color,
                                    fontFamily: 'var(--font-mono)',
                                }}>{done ? '✓' : i + 1}</div>
                                <span style={{ fontSize: 9, color, fontWeight: current ? 700 : 400, textAlign: 'center' }}>
                                    {s.label}
                                </span>
                            </div>
                            {i < STEPS.length - 1 && (
                                <div style={{
                                    width: 24, height: 1, flexShrink: 0,
                                    background: i < stepDone ? 'var(--approve)' : 'var(--border)',
                                    margin: '0 2px', marginTop: -12,
                                }} />
                            )}
                        </div>
                    )
                })}
            </div>

            {/* Tabs */}
            <div style={{
                display: 'flex', gap: 2, borderBottom: '1px solid var(--border)', marginBottom: 20,
            }}>
                {TABS.map(t => (
                    <button key={t} onClick={() => setTab(t)} style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        padding: '9px 16px', fontSize: 12, fontWeight: tab === t ? 700 : 400,
                        color: tab === t ? 'var(--blue-bright)' : 'var(--text-muted)',
                        borderBottom: tab === t ? '2px solid var(--blue-bright)' : '2px solid transparent',
                        transition: 'all 0.15s',
                    }}>{t}</button>
                ))}
            </div>

            {/* Tab: Pipeline */}
            {tab === 'Pipeline' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20 }}>
                    <div>
                        {/* Decision banner (if scored) */}
                        {score?.decision && (
                            <DecisionBanner
                                decision={score.decision}
                                grade={score.risk_grade}
                                score={score.normalised_score}
                                trigger={score.primary_rejection_trigger}
                                counter={score.counter_factual}
                            />
                        )}

                        {/* Action cards */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            {[
                                {
                                    step: 1, key: 'demo', label: 'Load Demo Data',
                                    desc: 'Loads Acme Textiles demo data: financials, GST, research cache.',
                                    action: doLoadDemo,
                                    done: stepDone >= 1,
                                    available: !!caseId,
                                },
                                {
                                    step: 2, key: 'analyze', label: 'Run Analysis',
                                    desc: 'Working capital cycle + related party detection. Raises flags.',
                                    action: doAnalyze,
                                    done: stepDone >= 2,
                                    available: stepDone >= 1,
                                },
                                {
                                    step: 3, key: 'score', label: 'Run Scoring Engine',
                                    desc: 'Five Cs scorecard (200 pts) → risk grade + loan sizing + ML validation.',
                                    action: doScore,
                                    done: stepDone >= 3,
                                    available: stepDone >= 2,
                                },
                                {
                                    step: 4, key: 'research', label: 'Load Research Cache',
                                    desc: 'Loads Acme Textiles news, eCourts, MCA findings into DB.',
                                    action: doResearch,
                                    done: stepDone >= 4,
                                    available: stepDone >= 2,
                                },
                                {
                                    step: 5, key: 'cam', label: 'Generate CAM',
                                    desc: 'Builds the full Credit Appraisal Memo as a Word document.',
                                    action: doGenCam,
                                    done: stepDone >= 5,
                                    available: stepDone >= 3,
                                },
                            ].map(item => {
                                const isLoad = loading[item.key]
                                return (
                                    <div key={item.key} style={{
                                        display: 'flex', alignItems: 'center', gap: 14,
                                        background: 'var(--surface)', border: '1px solid var(--border)',
                                        borderRadius: 'var(--radius)', padding: '14px 16px',
                                        opacity: item.available ? 1 : 0.5,
                                    }}>
                                        <div style={{
                                            width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                                            background: item.done ? 'var(--approve)' : 'var(--border)',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            fontSize: 13, color: item.done ? '#fff' : 'var(--text-dim)',
                                        }}>{item.done ? '✓' : item.step}</div>
                                        <div style={{ flex: 1 }}>
                                            <div style={{ fontSize: 13, fontWeight: 600, color: item.done ? 'var(--approve)' : 'var(--text)', marginBottom: 2 }}>
                                                {item.label}
                                            </div>
                                            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.desc}</div>
                                            {errors[item.key] && (
                                                <div style={{ fontSize: 11, color: 'var(--reject)', marginTop: 4 }}>
                                                    ✕ {errors[item.key]}
                                                </div>
                                            )}
                                        </div>
                                        {!item.done && (
                                            <button
                                                onClick={item.action}
                                                disabled={!item.available || isLoad}
                                                style={{
                                                    background: item.available && !isLoad ? 'var(--blue)' : 'var(--border)',
                                                    color: item.available && !isLoad ? '#fff' : 'var(--text-dim)',
                                                    border: 'none', borderRadius: 'var(--radius)',
                                                    padding: '7px 16px', fontSize: 12, fontWeight: 600,
                                                    cursor: item.available && !isLoad ? 'pointer' : 'not-allowed',
                                                    flexShrink: 0, minWidth: 90,
                                                }}
                                            >{isLoad ? '…' : item.available ? 'Run' : 'Locked'}</button>
                                        )}
                                        {item.done && item.key === 'cam' && camStatus?.exists && (
                                            <a
                                                href={api.camDownloadUrl(caseId)}
                                                download
                                                style={{
                                                    background: 'var(--approve)', color: '#fff',
                                                    border: 'none', borderRadius: 'var(--radius)',
                                                    padding: '7px 14px', fontSize: 12, fontWeight: 600,
                                                    cursor: 'pointer', textDecoration: 'none', flexShrink: 0,
                                                }}
                                            >⬇ Download</a>
                                        )}
                                    </div>
                                )
                            })}
                        </div>
                    </div>

                    {/* Log + flags sidebar */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                        {/* Activity log */}
                        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 14 }}>
                            <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 }}>
                                Activity Log
                            </div>
                            <div style={{
                                fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)',
                                maxHeight: 180, overflowY: 'auto', lineHeight: 1.7,
                            }}>
                                {log.length === 0
                                    ? <div style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>Waiting for actions…</div>
                                    : [...log].reverse().map((l, i) => <div key={i}>{l}</div>)
                                }
                            </div>
                        </div>

                        {/* Flags */}
                        {flags.length > 0 && (
                            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 14 }}>
                                <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 }}>
                                    Recon Flags ({flags.length})
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                    {flags.slice(0, 6).map((f, i) => {
                                        const col = f.severity === 'CRITICAL' ? 'var(--critical)' : f.severity === 'HIGH' ? 'var(--high)' : f.severity === 'MEDIUM' ? 'var(--medium)' : 'var(--text-muted)'
                                        return (
                                            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                                                <span style={{ fontSize: 8, color: col, flexShrink: 0, fontWeight: 700, marginTop: 2 }}>●</span>
                                                <div>
                                                    <div style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.3 }}>{f.title}</div>
                                                    <div style={{ fontSize: 10, color: col }}>{f.severity}</div>
                                                </div>
                                            </div>
                                        )
                                    })}
                                    {flags.length > 6 && <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>+{flags.length - 6} more</div>}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Tab: Scorecard */}
            {tab === 'Scorecard' && (
                <div>
                    {!score ? (
                        <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>
                            Run the scoring engine first (Pipeline tab → Step 3)
                        </div>
                    ) : (
                        <>
                            <DecisionBanner
                                decision={score.decision}
                                grade={score.risk_grade}
                                score={score.normalised_score}
                                trigger={score.primary_rejection_trigger}
                                counter={score.counter_factual}
                            />

                            <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 20, marginBottom: 20 }}>
                                {/* Gauge */}
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                                    <ScoreGauge
                                        score={score.normalised_score}
                                        grade={score.risk_grade}
                                        decision={score.decision}
                                    />
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, width: '100%' }}>
                                        <Stat label="Raw Score" value={score.total_raw_score + '/200'} color="var(--text)" />
                                        <Stat label="Norm Score" value={score.normalised_score + '/100'} color={score.decision === 'APPROVE' ? 'var(--approve)' : score.decision === 'PARTIAL' ? 'var(--partial)' : 'var(--reject)'} />
                                    </div>
                                </div>

                                {/* Pillar bars */}
                                <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '16px 18px' }}>
                                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 14 }}>
                                        Five Cs Breakdown
                                    </div>
                                    <PillarBars pillars={score.pillar_scores} />

                                    {/* Knockout flags */}
                                    {(score.knockout_flags || []).length > 0 && (
                                        <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
                                            <div style={{ fontSize: 10, color: 'var(--reject)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 }}>
                                                Knockout Flags
                                            </div>
                                            {score.knockout_flags.map((f, i) => (
                                                <div key={i} style={{ fontSize: 11, color: 'var(--reject)', marginBottom: 3, display: 'flex', gap: 6 }}>
                                                    <span style={{ flexShrink: 0 }}>⚠</span>{f}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Loan sizing quick stats */}
                            {score.loan_sizing && (
                                <div style={{ marginBottom: 20 }}>
                                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 10 }}>
                                        Loan Sizing
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
                                        <Stat label="Recommended" value={fmt(score.loan_sizing?.recommendation?.recommended_cr, 'Cr')} color="var(--blue-bright)" />
                                        <Stat label="DSCR Limit" value={fmt(score.loan_sizing?.limits?.dscr_based_cr, 'Cr')} color="var(--text)" />
                                        <Stat label="Coll. Limit" value={fmt(score.loan_sizing?.limits?.collateral_based_cr, 'Cr')} color="var(--text)" />
                                        <Stat label="Rate" value={fmt(score.loan_sizing?.rate?.recommended_rate_pct, '%')} color="var(--partial)" />
                                        <Stat label="Binding" value={score.loan_sizing?.recommendation?.binding_constraint || '—'} color="var(--text-muted)" />
                                    </div>
                                </div>
                            )}

                            {/* ML Validation */}
                            {score.ml_validation && (
                                <div style={{
                                    background: 'var(--surface)', border: '1px solid var(--border)',
                                    borderRadius: 'var(--radius)', padding: '12px 16px', marginBottom: 20,
                                    display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap',
                                }}>
                                    <span style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.8 }}>
                                        ML Validator
                                    </span>
                                    <Badge
                                        label={score.ml_validation.predicted_label || '?'}
                                        color={score.ml_validation.predicted_label === 'low_risk' ? 'var(--approve)' : score.ml_validation.predicted_label === 'medium_risk' ? 'var(--partial)' : 'var(--reject)'}
                                    />
                                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>
                                        Default prob: {((score.ml_validation.default_probability || 0) * 100).toFixed(0)}%
                                    </span>
                                    <Badge
                                        label={score.ml_validation.agrees_with_scorecard ? '✓ Agrees' : '⚠ Divergent'}
                                        color={score.ml_validation.agrees_with_scorecard ? 'var(--approve)' : 'var(--partial)'}
                                    />
                                    <span style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1 }}>
                                        via {score.ml_validation.model_used}
                                    </span>
                                    {score.ml_validation.divergence_note && (
                                        <div style={{ width: '100%', fontSize: 11, color: 'var(--partial)', marginTop: 4 }}>
                                            {score.ml_validation.divergence_note}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Feature contribution waterfall */}
                            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '16px 18px' }}>
                                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 14 }}>
                                    Feature Contribution Waterfall
                                </div>
                                <FeatureTable contributions={score.contributions || {}} />
                            </div>
                        </>
                    )}
                </div>
            )}

            {/* Tab: Financials */}
            {tab === 'Financials' && (
                <div>
                    {!score?.loan_sizing && (
                        <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>
                            Run scoring engine first to see financial analysis
                        </div>
                    )}

                    {/* We load WC metrics via score's feature_values */}
                    <WCMetricsPanel caseId={caseId} score={score} />
                </div>
            )}

            {/* Tab: Research */}
            {tab === 'Research' && (
                <div>
                    {/* Summary stats */}
                    {resSummary && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 16 }}>
                            <Stat label="Total Findings" value={resSummary.total_articles} color="var(--text)" />
                            <Stat label="Risk Delta" value={resSummary.total_risk_delta} color={resSummary.total_risk_delta < -30 ? 'var(--reject)' : 'var(--partial)'} />
                            <Stat label="Tier 1 Critical" value={resSummary.tier1_count} color="var(--critical)" />
                            <Stat label="Tier 2 High" value={resSummary.tier2_count} color="var(--high)" />
                            <Stat label="Overall Risk" value={resSummary.overall_label} color={
                                resSummary.overall_label === 'CRITICAL' ? 'var(--critical)' :
                                    resSummary.overall_label === 'HIGH' ? 'var(--high)' : 'var(--text-muted)'
                            } />
                        </div>
                    )}

                    {resSummary?.knockout && (
                        <div style={{
                            background: 'var(--reject-bg)', border: '1px solid var(--reject)',
                            borderRadius: 'var(--radius)', padding: '10px 14px', marginBottom: 16,
                            display: 'flex', gap: 10, alignItems: 'flex-start',
                        }}>
                            <span style={{ color: 'var(--reject)', fontSize: 16, flexShrink: 0 }}>⚠</span>
                            <div>
                                <div style={{ fontWeight: 700, color: 'var(--reject)', fontSize: 13, marginBottom: 2 }}>
                                    KNOCKOUT FLAG — Litigation Risk
                                </div>
                                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                                    {resSummary.primary_trigger}
                                </div>
                            </div>
                        </div>
                    )}

                    {research.length === 0 ? (
                        <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>
                            Load research cache first (Pipeline tab → Step 4)
                        </div>
                    ) : (
                        <ResearchTable items={research} />
                    )}
                </div>
            )}

            {/* Tab: CAM */}
            {tab === 'CAM' && (
                <div>
                    <div style={{
                        background: 'var(--surface)', border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-lg)', padding: 28, textAlign: 'center',
                    }}>
                        {!camStatus?.exists ? (
                            <>
                                <div style={{ fontSize: 48, marginBottom: 12 }}>📄</div>
                                <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>
                                    Credit Appraisal Memo
                                </div>
                                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20, maxWidth: 480, margin: '0 auto 20px' }}>
                                    Generate a full 10-section CAM document as a Word file. Requires scoring to be completed first.
                                </div>
                                {errors.cam && (
                                    <div style={{ color: 'var(--reject)', fontSize: 12, marginBottom: 12 }}>
                                        ✕ {errors.cam}
                                    </div>
                                )}
                                <button
                                    onClick={doGenCam}
                                    disabled={stepDone < 3 || loading.cam}
                                    style={{
                                        background: stepDone >= 3 ? 'var(--blue)' : 'var(--border)',
                                        color: stepDone >= 3 ? '#fff' : 'var(--text-dim)',
                                        border: 'none', borderRadius: 'var(--radius)',
                                        padding: '10px 28px', fontSize: 14, fontWeight: 600, cursor: stepDone >= 3 ? 'pointer' : 'not-allowed',
                                    }}
                                >{loading.cam ? 'Generating…' : stepDone < 3 ? 'Score Required First' : 'Generate CAM'}</button>
                            </>
                        ) : (
                            <>
                                <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
                                <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--approve)', marginBottom: 8 }}>
                                    CAM Generated
                                </div>
                                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                                    {camStatus.filename}
                                </div>
                                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>
                                    {camStatus.size_kb?.toFixed(0)} KB · Generated {camStatus.generated_at?.slice(0, 10)}
                                </div>
                                <a
                                    href={api.camDownloadUrl(caseId)}
                                    download
                                    style={{
                                        display: 'inline-block',
                                        background: 'var(--approve)', color: '#fff',
                                        border: 'none', borderRadius: 'var(--radius)',
                                        padding: '10px 28px', fontSize: 14, fontWeight: 600,
                                        textDecoration: 'none', cursor: 'pointer',
                                    }}
                                >⬇ Download Word Document</a>
                                <div style={{ marginTop: 16 }}>
                                    <button
                                        onClick={doGenCam}
                                        disabled={loading.cam}
                                        style={{
                                            background: 'none', border: '1px solid var(--border)',
                                            color: 'var(--text-muted)', borderRadius: 'var(--radius)',
                                            padding: '7px 16px', fontSize: 12, cursor: 'pointer',
                                        }}
                                    >{loading.cam ? 'Regenerating…' : 'Regenerate'}</button>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Sections reference */}
                    <div style={{ marginTop: 20, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '14px 18px' }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 12 }}>
                            CAM Sections
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6 }}>
                            {[
                                '1. Cover Page — Decision + metadata',
                                '2. Executive Summary — AI narrative',
                                '3. Company Profile — Promoters + shareholding',
                                '4. Proposed Facility — Loan terms + security',
                                '5. Financial Summary — 3-yr P&L + WC ratios',
                                '6. GST Reconciliation — Flag table',
                                '7. Research Findings — Litigation + news',
                                '8. Five Cs Scorecard — Waterfall + pillars',
                                '9. Risk Factors — AI risk register',
                                '10. Recommendation + Audit Trail',
                            ].map((s, i) => (
                                <div key={i} style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 0', borderBottom: '1px solid var(--border-soft)', display: 'flex', gap: 8 }}>
                                    <span style={{ color: 'var(--blue-bright)', flexShrink: 0 }}>›</span>
                                    {s}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

/* ── WC Metrics sub-panel ─────────────────────────────────────── */
function WCMetricsPanel({ caseId, score }) {
    const [wc, setWc] = useState(null)
    const [loading, setLoading] = useState(false)

    // Try to load WC data from API when caseId is set
    useEffect(() => {
        if (!caseId) return
        setLoading(true)
        // We fetch the balance_sheet document embedded in score feature_values
        // The yearly_metrics are available via the /analyze output stored in the financial doc
        // We'll fetch from /cases/:id/flags which has WC info, or infer from score
        // Best approach: call a dedicated working capital endpoint. Since we don't have one,
        // we reconstruct from score feature_values if available.
        if (score) {
            // Try fetching from a hypothetical endpoint, otherwise use score data
            setLoading(false)
        }
    }, [caseId, score])

    // Extract what we can from the score object
    if (!score) return (
        <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>
            Run scoring engine first to see financial analysis
        </div>
    )

    // Build placeholder metrics from score raw values if yearly not available
    const fv = score  // score already has pillar_scores, loan_sizing etc.

    return (
        <WCMetricsFetcher caseId={caseId} score={score} />
    )
}

function WCMetricsFetcher({ caseId, score }) {
    const [metrics, setMetrics] = useState(null)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        if (!caseId) return
        setLoading(true)
        // Fetch working capital data by calling the analyze endpoint output.
        // We get it from the financial document. Since there's no direct endpoint,
        // we'll fetch from /cases/:id/flags and reconstruct or use the score loan_sizing hints.
        // The cleanest approach: call /analyze again for a re-fetch — but that re-runs analysis.
        // Instead, we'll display what's in the score and supplement with a dedicated fetch.
        setLoading(false)
    }, [caseId])

    const ratioRows = [
        { label: 'DSCR', key: null, value: score?.loan_sizing ? null : null },
    ]

    // Display score-derived stats + chart placeholder
    return (
        <div>
            {/* Quick financial stats from loan sizing */}
            {score?.loan_sizing && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 20 }}>
                    {[
                        { label: 'Recommended', value: `₹${(score.loan_sizing?.recommendation?.recommended_cr || 0).toFixed(2)} Cr` },
                        { label: 'DSCR Limit', value: `₹${(score.loan_sizing?.limits?.dscr_based_cr || 0).toFixed(2)} Cr` },
                        { label: 'Drawing Pwr', value: `₹${(score.loan_sizing?.limits?.drawing_power_cr || 0).toFixed(2)} Cr` },
                        { label: 'Rate', value: `${(score.loan_sizing?.rate?.recommended_rate_pct || 0).toFixed(2)}% p.a.` },
                    ].map(s => (
                        <div key={s.label} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '12px 14px' }}>
                            <div style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4 }}>{s.label}</div>
                            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 700, color: 'var(--blue-bright)' }}>{s.value}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Rate breakdown */}
            {score?.loan_sizing?.rate && (
                <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '14px 18px', marginBottom: 20 }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 12 }}>
                        Interest Rate Build-Up
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {[
                            { label: 'RBI Repo + NBFC Spread (Base Rate)', value: `${score.loan_sizing.rate.base_rate_pct}%` },
                            { label: 'Risk Premium', value: `+${score.loan_sizing.rate.risk_premium_pct}%` },
                            { label: 'Tenor Premium', value: `+${score.loan_sizing.rate.tenor_premium_pct}%` },
                            { label: 'Collateral Discount', value: `−${score.loan_sizing.rate.collateral_discount_pct}%` },
                            { label: 'Recommended Rate', value: `${score.loan_sizing.rate.recommended_rate_pct}%`, bold: true },
                        ].map(r => (
                            <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: 6, borderBottom: '1px solid var(--border-soft)' }}>
                                <span style={{ fontSize: 12, color: r.bold ? 'var(--text)' : 'var(--text-muted)', fontWeight: r.bold ? 700 : 400 }}>{r.label}</span>
                                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: r.bold ? 'var(--partial)' : 'var(--text-muted)', fontWeight: r.bold ? 700 : 400 }}>{r.value}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Sizing notes */}
            {(score?.loan_sizing?.sizing_notes || []).length > 0 && (
                <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '14px 18px' }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 10 }}>
                        Sizing Notes
                    </div>
                    {score.loan_sizing.sizing_notes.map((n, i) => (
                        <div key={i} style={{ fontSize: 12, color: 'var(--text-muted)', padding: '5px 0', borderBottom: '1px solid var(--border-soft)', display: 'flex', gap: 8 }}>
                            <span style={{ color: 'var(--blue-bright)', flexShrink: 0 }}>›</span>
                            {n}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}