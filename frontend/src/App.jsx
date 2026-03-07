import { BrowserRouter, Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import CaseDetail from './pages/CaseDetail.jsx'

function Sidebar() {
  const nav = useNavigate()
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>⚡ Intelli-Credit</h1>
        <p>AI Credit Appraisal</p>
      </div>
      <nav className="sidebar-nav">
        <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>
          <span className="sidebar-icon">▦</span> Dashboard
        </NavLink>
        <div style={{ padding: '6px 18px 2px', fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1, marginTop: 4 }}>
          Demo Scenarios
        </div>
        <NavLink to="/demo/surya" className={({ isActive }) => isActive ? 'active' : ''}>
          <span className="sidebar-icon" style={{ color: 'var(--approve)' }}>✓</span> Surya Pharma
        </NavLink>
        <NavLink to="/demo/acme" className={({ isActive }) => isActive ? 'active' : ''}>
          <span className="sidebar-icon" style={{ color: 'var(--reject)' }}>✕</span> Acme Textiles
        </NavLink>
      </nav>
      <div style={{ padding: '16px 18px', borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: 1 }}>
          API Status
        </div>
        <div style={{ fontSize: 11, color: 'var(--approve)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
          ● Backend Connected
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 6 }}>
          localhost:8000
        </div>
      </div>
    </aside>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <div className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/demo/surya" element={<CaseDetail demoScenario="surya" />} />
            <Route path="/demo/acme" element={<CaseDetail demoScenario="acme" />} />
            <Route path="/demo" element={<CaseDetail demoScenario="acme" />} />
            <Route path="/cases/:id" element={<CaseDetail />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  )
}