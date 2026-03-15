import React, { useState, useEffect } from 'react'
import ThemeToggle from './ThemeToggle.jsx'

export default function Topbar() {
    const [currentTime, setCurrentTime] = useState(new Date())

    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentTime(new Date())
        }, 1000)

        return () => clearInterval(timer)
    }, [])

    return (
        <div className="topbar" style={{ flexShrink: 0 }}>
            <div style={{ position: 'relative' }}>
                <input type="text" placeholder="Search cases, borrowers..." style={{ background: 'var(--surface-alt)', border: '1px solid var(--border-soft)', padding: '6px 16px 6px 36px', borderRadius: 20, color: 'var(--text)', fontSize: 13, width: 280, outline: 'none' }} />
                <span style={{ position: 'absolute', left: 12, top: 4, color: 'var(--text-muted)', fontSize: 16 }}>⌕</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                <ThemeToggle />
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(0, 242, 220, 0.1)', padding: '6px 12px', borderRadius: 20, color: 'var(--primary)', fontSize: 11, fontWeight: 700, border: '1px solid rgba(0, 242, 220, 0.3)' }}>
                    <span style={{ fontSize: 14 }}>📈</span> Portfolio Health: Excellent
                </div>
                <div style={{ fontSize: 13, color: 'var(--text)', fontFamily: 'var(--font-mono)' }}>
                    {currentTime.toLocaleTimeString()}
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: 18, cursor: 'pointer' }}>🔔</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, borderLeft: '1px solid var(--border)', paddingLeft: 20 }}>
                    <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg, #00F2DC, #00B8A9)', color: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 14 }}>
                        A
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                        <div style={{ fontWeight: 600, fontSize: 13, lineHeight: '14px' }}>Admin User</div>
                        <div style={{ fontSize: 11, color: 'var(--secondary)' }}>Credit Analyst</div>
                    </div>
                </div>
            </div>
        </div>
    )
}
