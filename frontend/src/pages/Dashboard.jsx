import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'

const STATUS_BADGE = {
    created: { cls: 'badge-muted', label: 'Created' },
    documents_loaded: { cls: 'badge-blue', label: 'Loaded' },
    analyzed: { cls: 'badge-blue', label: 'Analyzed' },
    scored: { cls: 'badge-partial', label: 'Scored' },
    cam_generated: { cls: 'badge-approve', label: 'Complete' },
    overridden: { cls: 'badge-partial', label: 'Overridden' },
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
    const [creating, setCreating] = useState(false)
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

    async function createAndOpenDemo() {
        try {
            setCreating(true)
            const c = await api.createCase({
                company_name: 'Acme Textiles Ltd',
                company_cin: 'U17100MH2010PLC201234',
                company_pan: 'AAACA1234B',
                sector: 'textiles',
            })
            nav(`/cases/${c.id}`)
        } catch (e) {
            setError(e.message)
        } finally {
            setCreating(false)
        }
    }

    return (
        <>
            <div className="topbar">
                <span className="topbar-title">All Cases</span>
                <span className="topbar-meta">Intelli-Credit Demo v1.0</span>
            </div>
            <div className="page-body">

                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
                    <div>
                        <h2 style={{ fontSize: 20, fontWeight: 700 }}>Credit Appraisal Cases</h2>
                        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                            {cases.length} case{cases.length !== 1 ? 's' : ''} in pipeline
                        </p>
                    </div>
                    <div style={{ display: 'flex', gap: 10 }}>
                        <button className="btn btn-success" onClick={createAndOpenDemo} disabled={creating}>
                            {creating ? <span className="loading-spin" /> : '⚡'}
                            Load Acme Textiles Demo
                        </button>
                    </div>
                </div>

                {error && (
                    <div style={{ background: 'var(--reject-bg)', border: '1px solid var(--reject)', borderRadius: 6, padding: '10px 14px', marginBottom: 16, fontSize: 13, color: 'var(--reject)' }}>
                        {error}
                    </div>
                )}

                {/* Stats row */}
                <div className="stat-grid" style={{ marginBottom: 20 }}>
                    {[
                        { label: 'Total Cases', value: cases.length, sub: 'all time' },
                        { label: 'Scored', value: cases.filter(c => ['scored', 'cam_generated', 'overridden'].includes(c.status)).length, sub: 'pipeline complete' },
                        { label: 'CAMs Generated', value: cases.filter(c => c.status === 'cam_generated').length, sub: 'ready to download' },
                    ].map(s => (
                        <div key={s.label} className="stat-card blue">
                            <div className="stat-label">{s.label}</div>
                            <div className="stat-value">{s.value}</div>
                            <div className="stat-sub">{s.sub}</div>
                        </div>
                    ))}
                </div>

                {/* Case table */}
                <div className="card" style={{ padding: 0 }}>
                    {loading ? (
                        <div className="empty-state">
                            <span className="loading-spin" style={{ width: 24, height: 24, borderWidth: 3 }} />
                            <p>Loading cases…</p>
                        </div>
                    ) : cases.length === 0 ? (
                        <div className="empty-state">
                            <div style={{ fontSize: 32 }}>📋</div>
                            <p>No cases yet. Click <strong>Load Acme Textiles Demo</strong> to begin.</p>
                        </div>
                    ) : (
                        <div className="scroll-x">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Company</th>
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
        </>
    )
}