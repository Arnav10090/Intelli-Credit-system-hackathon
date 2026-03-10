import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'
import ThemeToggle from '../components/ThemeToggle.jsx'

const STATUS_BADGE = {
    created: { cls: 'badge-muted', label: 'Created' },
    documents_loaded: { cls: 'badge-blue', label: 'Loaded' },
    analyzed: { cls: 'badge-blue', label: 'Analyzed' },
    scored: { cls: 'badge-partial', label: 'Scored' },
    cam_generated: { cls: 'badge-approve', label: 'Complete' },
    overridden: { cls: 'badge-partial', label: 'Overridden' },
    draft: { cls: 'badge-muted', label: 'Draft' },
}

function CaseRow({ c, onClick }) {
    const sb = STATUS_BADGE[c.status] || { cls: 'badge-muted', label: c.status }
    return (
        <tr style={{ cursor: 'pointer' }} onClick={onClick}>
            <td>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{c.company_name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                    {c.company_cin || 'No CIN'}
                </div>
            </td>
            <td><span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{c.sector || '—'}</span></td>
            <td><span className={`badge ${sb.cls}`}>{sb.label}</span></td>
            <td className="mono text-sm text-muted">{new Date(c.created_at).toLocaleDateString('en-IN')}</td>
            <td>
                <span style={{ fontSize: 20, color: 'var(--text-dim)' }}>›</span>
            </td>
        </tr>
    )
}

export default function Dashboard() {
    const [cases, setCases] = useState([])
    const [loading, setLoading] = useState(true)
    const [creating, setCreating] = useState(null)
    const [error, setError] = useState('')
    const nav = useNavigate()

    useEffect(() => { loadCases() }, [])

    async function loadCases() {
        try {
            setLoading(true)
            const data = await api.listCases()
            setCases(data)
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    async function createAndOpenDemo(scenario) {
        const isAcme = scenario === 'acme'
        try {
            setCreating(scenario)
            const c = await api.createCase(isAcme ? {
                company_name: 'Acme Textiles Ltd',
                company_cin: 'U17100MH2010PLC201234',
                company_pan: 'AAACA1234B',
                sector: 'textiles',
            } : {
                company_name: 'Surya Pharmaceuticals Ltd',
                company_cin: 'U24230TG2008PLC058421',
                company_pan: 'AADCS9876C',
                sector: 'pharmaceuticals',
            })
            nav(`/demo/${scenario}`)
        } catch (e) {
            setError(e.message)
        } finally {
            setCreating(null)
        }
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
            <div className="page-body" style={{ flex: 1, overflowY: 'auto', padding: '24px 32px' }}>
                {/* Hero Banner */}
                <div className="glass-panel" style={{
                    position: 'relative',
                    background: 'var(--hero-bg)',
                    borderLeft: '4px solid var(--primary)',
                    borderRadius: 16,
                    padding: '24px 32px',
                    marginBottom: 24,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
                    overflow: 'hidden'
                }}>
                    <div style={{ position: 'absolute', top: -50, right: -50, width: 200, height: 200, background: 'radial-gradient(circle, rgba(0,242,220,0.15) 0%, transparent 70%)', borderRadius: '50%', pointerEvents: 'none' }}></div>
                    <div style={{ zIndex: 1 }}>
                        <h2 style={{ fontSize: 24, fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{ color: 'var(--primary)', textShadow: '0 0 10px var(--primary-glow)' }}>Intelli-Credit</span>
                            <span style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-muted)' }}>by Team AI APEX</span>
                        </h2>
                        <p style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 4 }}>
                            Intelligent precision appraisal and underwriting systems.
                        </p>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, zIndex: 1 }}>
                        <div style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)', padding: '8px 16px', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--primary)', boxShadow: '0 0 8px var(--primary)', animation: 'pulse 2s infinite' }}></span>
                            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>System Online</span>
                        </div>
                    </div>
                </div>

                {error && (
                    <div style={{ background: 'var(--reject-bg)', border: '1px solid var(--reject)', borderRadius: 8, padding: '12px 16px', marginBottom: 24, fontSize: 13, color: 'var(--reject)' }}>
                        {error}
                    </div>
                )}

                {/* Stats row - 4 cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
                    {[
                        { label: 'Total Cases Analyzed', value: cases.length, icon: '📊', color: 'var(--primary)', trend: ' ' },
                        { label: 'Approved Returns', value: 1, icon: '✓', color: '#00D2C0', trend: 'Surya Pharmaceuticals' },
                        { label: 'Pending in Pipeline', value: 0, icon: '⧗', color: 'var(--secondary)', trend: 'All cases resolved' },
                        { label: 'Needs Review / Alerts', value: 1, icon: '!', color: '#FF4444', trend: 'Acme Textiles flagged', isRed: true },
                    ].map(s => (
                        <div key={s.label} className={"glass-panel gold-hover"} style={{
                            borderTop: `3px solid ${s.color}`,
                            padding: '16px 20px',
                            position: 'relative',
                            overflow: 'hidden',
                            backgroundColor: s.isRed ? 'rgba(255, 68, 68, 0.05)' : undefined
                        }}>
                            <div style={{ position: 'absolute', top: 0, right: 0, width: 80, height: 80, background: `radial-gradient(circle, ${s.color}20 0%, transparent 70%)`, pointerEvents: 'none', transform: 'translate(30%, -30%)' }}></div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                                <div style={{ fontSize: 12, fontWeight: 600, color: s.isRed ? '#FF4444' : 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{s.label}</div>
                                <div style={{ fontSize: 18, color: s.color, opacity: 0.8 }}>{s.icon}</div>
                            </div>
                            <div style={{ fontSize: 32, fontWeight: 700, lineHeight: 1, fontFamily: 'var(--font-mono)', marginBottom: 8, color: s.isRed ? '#FF4444' : 'var(--text)' }}>{s.value}</div>
                            <div style={{ fontSize: 11, color: s.isRed ? 'rgba(255, 68, 68, 0.8)' : 'var(--text-dim)' }}>{s.trend}</div>
                        </div>
                    ))}
                </div>

                {/* Quick Actions Row */}
                <div style={{ marginBottom: 24 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: 1 }}>Quick Actions & Demos</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
                        <button className="btn glass-panel gold-hover" onClick={() => createAndOpenDemo('surya')} disabled={!!creating}
                            style={{ padding: '24px 20px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 10, height: 'auto', textAlign: 'left', color: 'var(--text)' }}>
                            <div style={{ fontSize: 24, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 12 }}>
                                {creating === 'surya' ? <span className="loading-spin" style={{ borderColor: 'var(--primary)', borderTopColor: 'transparent', width: 20, height: 20 }} /> : '⚡'}
                                <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--primary)' }}>Run Surya Demo</span>
                            </div>
                            <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 500 }}>Score: <span style={{ color: 'var(--text)' }}>100/100</span> | Grade <span style={{ color: 'var(--text)' }}>A+</span> | <span style={{ color: 'var(--approve)', fontWeight: 'bold' }}>APPROVE</span></span>
                        </button>

                        <button className="btn glass-panel gold-hover" onClick={() => createAndOpenDemo('acme')} disabled={!!creating}
                            style={{ padding: '24px 20px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 10, height: 'auto', textAlign: 'left', color: 'var(--text)' }}>
                            <div style={{ fontSize: 24, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 12 }}>
                                {creating === 'acme' ? <span className="loading-spin" style={{ borderColor: 'var(--reject)', borderTopColor: 'transparent', width: 20, height: 20 }} /> : <span style={{ color: 'var(--reject)' }}>✗</span>}
                                <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--reject)' }}>Run Acme Demo</span>
                            </div>
                            <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 500 }}>Score: <span style={{ color: 'var(--text)' }}>~54/100</span> | Grade <span style={{ color: 'var(--text)' }}>D</span> | <span style={{ color: 'var(--reject)', fontWeight: 'bold' }}>REJECT</span></span>
                        </button>
                    </div>
                </div>

                {/* Case table */}
                <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                    <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0, color: 'var(--text)' }}>Recent Activity Pipeline</h3>
                        <div style={{ fontSize: 12, color: 'var(--primary)', cursor: 'pointer', fontWeight: 600 }}>View All →</div>
                    </div>
                    {loading ? (
                        <div className="empty-state" style={{ padding: 40 }}>
                            <span className="loading-spin" style={{ width: 24, height: 24, borderWidth: 3, borderColor: 'var(--primary)', borderTopColor: 'transparent' }} />
                            <p style={{ marginTop: 12, color: 'var(--text-muted)' }}>Syncing pipeline...</p>
                        </div>
                    ) : cases.length === 0 ? (
                        <div className="empty-state" style={{ padding: 60 }}>
                            <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
                            <p style={{ color: 'var(--text-muted)' }}>No recent cases. Trigger a Quick Action to begin.</p>
                        </div>
                    ) : (
                        <div className="scroll-x">
                            <table className="data-table" style={{ width: '100%' }}>
                                <thead style={{ background: 'var(--surface-alt)' }}>
                                    <tr>
                                        <th style={{ padding: '12px 20px' }}>Company</th>
                                        <th>Sector</th>
                                        <th>Status</th>
                                        <th>Created</th>
                                        <th></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {cases.map(c => (
                                        <CaseRow key={c.id} c={c} onClick={() => nav(`/cases/${c.id}`)} />
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

            </div>
        </div>
    )
}