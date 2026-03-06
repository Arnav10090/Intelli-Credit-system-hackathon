import {
    ResponsiveContainer, LineChart, Line, XAxis, YAxis,
    CartesianGrid, Tooltip, Legend,
} from 'recharts'

function fmt(v) {
    if (!v && v !== 0) return '—'
    if (v >= 100) return `₹${(v / 100).toFixed(1)}Cr`
    return `₹${v.toFixed(0)}L`
}

const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    return (
        <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', padding: '10px 14px',
            boxShadow: 'var(--shadow)',
        }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600 }}>
                {label}
            </div>
            {payload.map(p => (
                <div key={p.dataKey} style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 3 }}>
                    <span style={{
                        width: 8, height: 8, borderRadius: '50%',
                        background: p.color, display: 'inline-block', flexShrink: 0,
                    }} />
                    <span style={{ fontSize: 12, color: 'var(--text)', flex: 1 }}>{p.name}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: p.color }}>
                        {fmt(p.value)}
                    </span>
                </div>
            ))}
        </div>
    )
}

export default function FinancialChart({ metrics = [] }) {
    if (!metrics.length) return (
        <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 20, textAlign: 'center' }}>
            No financial data
        </div>
    )

    const data = metrics.map(m => ({
        year: m.year,
        Revenue: m.revenue,
        EBITDA: m.ebitda,
        PAT: m.pat,
    }))

    return (
        <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                <XAxis
                    dataKey="year" tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-ui)' }}
                    axisLine={{ stroke: 'var(--border)' }} tickLine={false}
                />
                <YAxis
                    tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                    axisLine={false} tickLine={false}
                    tickFormatter={v => v >= 100 ? `${(v / 100).toFixed(0)}Cr` : `${v}L`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                    wrapperStyle={{ fontSize: 11, paddingTop: 8, fontFamily: 'var(--font-ui)' }}
                    formatter={(v) => <span style={{ color: 'var(--text-muted)' }}>{v}</span>}
                />
                <Line
                    type="monotone" dataKey="Revenue" stroke="#4D9EFF"
                    strokeWidth={2} dot={{ fill: '#4D9EFF', r: 4 }} activeDot={{ r: 6 }}
                />
                <Line
                    type="monotone" dataKey="EBITDA" stroke="#0EA97A"
                    strokeWidth={2} dot={{ fill: '#0EA97A', r: 4 }} activeDot={{ r: 6 }}
                    strokeDasharray="6 2"
                />
                <Line
                    type="monotone" dataKey="PAT" stroke="#E09B2B"
                    strokeWidth={2} dot={{ fill: '#E09B2B', r: 4 }} activeDot={{ r: 6 }}
                    strokeDasharray="2 4"
                />
            </LineChart>
        </ResponsiveContainer>
    )
}