import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'

const STEPS = [
    { label: 'Create Case', delay: 500 },
    { label: 'Load Data', delay: 1000 },
    { label: 'Analyze', delay: 1500 },
    { label: 'Score', delay: 1000 },
    { label: 'Research', delay: 1000 },
    { label: 'Generate CAM', delay: 1000 },
]

const PURPOSES = ['Working Capital', 'Term Loan', 'Equipment Finance', 'Other']

export default function NewCase() {
    const nav = useNavigate()
    const [form, setForm] = useState({ name: '', cin: '', amount: '', purpose: 'Working Capital' })
    const [errors, setErrors] = useState({})
    const [processing, setProcessing] = useState(false)
    const [currentStep, setCurrentStep] = useState(-1)
    const [file, setFile] = useState(null)

    function validate() {
        const e = {}
        if (!form.name.trim()) e.name = 'Company name is required'
        if (!form.amount || Number(form.amount) <= 0) e.amount = 'Valid loan amount is required'
        setErrors(e)
        return Object.keys(e).length === 0
    }

    async function handleSubmit(ev) {
        ev.preventDefault()
        if (!validate()) return

        setProcessing(true)
        setCurrentStep(0)

        try {
            // Real backend call to create the case so it shows in Recent Activity
            const caseData = {
                company_name: form.name,
                company_cin: form.cin || null,
                requested_amount_cr: Number(form.amount),
                purpose: form.purpose
            }
            await api.createCase(caseData)

            // Animate through all steps for the demo experience
            for (let i = 1; i < STEPS.length; i++) {
                await new Promise(r => setTimeout(r, STEPS[i].delay))
                setCurrentStep(i)
            }

            await new Promise(r => setTimeout(r, 800))

            // Determine result based on amount
            const amount = Number(form.amount)
            if (amount > 20) {
                nav(`/demo/surya?fromCustom=true`)
            } else {
                nav(`/demo/acme?fromCustom=true`)
            }
        } catch (err) {
            setErrors({ submit: err.message })
            setProcessing(false)
        }
    }

    if (processing) {
        return (
            <div style={{ padding: '60px 28px', maxWidth: 600, margin: '0 auto', textAlign: 'center' }}>
                <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
                    Processing: {form.name}
                </h2>
                <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 32 }}>Running the Intelli-Credit pipeline...</p>

                <div style={{
                    background: 'var(--surface)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-lg)', padding: '24px 20px',
                }}>
                    {STEPS.map((s, i) => {
                        const done = i < currentStep
                        const active = i === currentStep
                        const future = i > currentStep
                        return (
                            <div key={i} style={{
                                display: 'flex', alignItems: 'center', gap: 14,
                                padding: '10px 0',
                                borderBottom: i < STEPS.length - 1 ? '1px solid var(--border-soft)' : 'none',
                            }}>
                                <div style={{
                                    width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                                    background: done ? 'var(--approve)' : active ? 'var(--surface)' : 'var(--surface-alt)',
                                    border: `2px solid ${done ? 'var(--approve)' : active ? 'var(--primary)' : 'var(--text-dim)'}`,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: 12, fontWeight: 700,
                                    color: done ? '#fff' : active ? 'var(--primary)' : 'var(--text-dim)',
                                    animation: active ? 'ringPulse 2s infinite' : 'none',
                                }}>
                                    {done ? '✓' : i + 1}
                                </div>
                                <span style={{
                                    fontSize: 14, fontWeight: active ? 700 : 500,
                                    color: done ? 'var(--approve)' : active ? 'var(--primary)' : 'var(--text-dim)',
                                }}>
                                    {s.label}
                                </span>
                                {active && <span className="loading-spin" style={{ marginLeft: 'auto', width: 16, height: 16, borderWidth: 2 }} />}
                                {done && <span style={{ marginLeft: 'auto', color: 'var(--approve)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>Done</span>}
                            </div>
                        )
                    })}
                </div>
            </div>
        )
    }

    return (
        <div style={{ padding: '28px', maxWidth: 640, margin: '0 auto' }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>
                New Credit Case
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 28 }}>
                Upload financials and let Intelli-Credit do the rest.
            </p>

            <form onSubmit={handleSubmit}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {/* Company Name */}
                    <div>
                        <label style={labelStyle}>Company Name *</label>
                        <input
                            value={form.name}
                            onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                            placeholder="e.g. Reliance Industries Ltd"
                            style={{ ...inputStyle, borderColor: errors.name ? 'var(--reject)' : 'var(--border)' }}
                        />
                        {errors.name && <div style={errStyle}>{errors.name}</div>}
                    </div>

                    {/* CIN */}
                    <div>
                        <label style={labelStyle}>CIN or GSTIN <span style={{ color: 'var(--text-dim)', fontStyle: 'italic', fontWeight: 400 }}>(optional)</span></label>
                        <input
                            value={form.cin}
                            onChange={e => setForm(p => ({ ...p, cin: e.target.value }))}
                            placeholder="e.g. U24230TG2008PLC058421"
                            style={inputStyle}
                        />
                    </div>

                    {/* Loan Amount */}
                    <div>
                        <label style={labelStyle}>Loan Amount Requested ₹ (Crores) *</label>
                        <input
                            type="number"
                            value={form.amount}
                            onChange={e => setForm(p => ({ ...p, amount: e.target.value }))}
                            placeholder="e.g. 25"
                            style={{ ...inputStyle, borderColor: errors.amount ? 'var(--reject)' : 'var(--border)' }}
                        />
                        {errors.amount && <div style={errStyle}>{errors.amount}</div>}
                    </div>

                    {/* Purpose */}
                    <div>
                        <label style={labelStyle}>Loan Purpose</label>
                        <select
                            value={form.purpose}
                            onChange={e => setForm(p => ({ ...p, purpose: e.target.value }))}
                            style={inputStyle}
                        >
                            {PURPOSES.map(p => <option key={p} value={p}>{p}</option>)}
                        </select>
                    </div>

                    {/* File Upload */}
                    <div>
                        <label style={labelStyle}>Upload Annual Report</label>
                        <div
                            onClick={() => document.getElementById('nc-file-input').click()}
                            style={{
                                border: '2px dashed var(--primary)',
                                borderRadius: 'var(--radius)',
                                padding: 14,
                                textAlign: 'center',
                                cursor: 'pointer',
                                background: 'var(--surface-alt)',
                            }}
                        >
                            <input
                                id="nc-file-input"
                                type="file"
                                accept=".pdf,.csv,.xlsx"
                                style={{ display: 'none' }}
                                onChange={e => setFile(e.target.files?.[0] || null)}
                            />
                            {file ? (
                                <div style={{ fontSize: 13, color: 'var(--primary)', fontWeight: 600 }}>
                                    📄 {file.name}
                                </div>
                            ) : (
                                <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                                    📤 Click to upload PDF, Excel, or CSV
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <p style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 16, lineHeight: 1.5 }}>
                    Financial ratios will be extracted automatically. GST reconciliation and court records checked via research agent. Credit Appraisal Memo generated on completion.
                </p>

                {errors.submit && (
                    <div style={{ marginTop: 12, padding: 10, background: 'var(--reject-bg)', border: '1px solid var(--reject)', borderRadius: 'var(--radius)', color: 'var(--reject)', fontSize: 12 }}>
                        ✕ {errors.submit}
                    </div>
                )}

                <button type="submit" style={{
                    marginTop: 20,
                    width: '100%',
                    background: 'var(--primary)',
                    color: '#000',
                    border: 'none',
                    borderRadius: 'var(--radius)',
                    padding: '14px 24px',
                    fontSize: 15,
                    fontWeight: 700,
                    cursor: 'pointer',
                }}>
                    Create Case & Run Analysis →
                </button>
            </form>
        </div>
    )
}

const labelStyle = {
    display: 'block',
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
}

const inputStyle = {
    width: '100%',
    padding: '10px 14px',
    background: 'var(--surface-alt)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    color: 'var(--text)',
    fontSize: 14,
    fontFamily: 'var(--font-ui)',
    outline: 'none',
}

const errStyle = {
    fontSize: 11,
    color: 'var(--reject)',
    marginTop: 4,
}
