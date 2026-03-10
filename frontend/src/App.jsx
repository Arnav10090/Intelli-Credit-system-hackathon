import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import CaseDetail from './pages/CaseDetail.jsx'
import NewCase from './pages/NewCase.jsx'
import Topbar from './components/Topbar.jsx'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, color: 'red', fontFamily: 'monospace' }}>
          <h2>Something went wrong.</h2>
          <pre>{this.state.error?.toString()}</pre>
          <pre style={{ fontSize: 12, marginTop: 10 }}>{this.state.errorInfo?.componentStack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

// Icons matching the screenshot roughly
const IconSparkles = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.5 4.5l1.5 5 5 1.5-5 1.5-1.5 5-1.5-5-5-1.5 5-1.5z" />
    <path d="M17.5 4.5l.5 2 2 .5-2 .5-.5 2-.5-2-2-.5 2-.5z" />
  </svg>
)

const IconGrid = () => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></svg>
const IconBarChart = () => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M18 20V10" /><path d="M12 20V4" /><path d="M6 20v-6" /></svg>
const IconUsers = () => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 00-3-3.87" /><path d="M16 3.13a4 4 0 010 7.75" /></svg>
const IconFileText = () => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg>
const IconTrending = () => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18" /><polyline points="17 6 23 6 23 12" /></svg>
const IconInfo = () => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></svg>
const IconSettings = () => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" /></svg>
const IconHelp = () => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>

function Sidebar({ isOpen, setIsOpen }) {
  const nav = useNavigate()

  return (
    <aside className={`sidebar ${isOpen ? '' : 'collapsed'}`}>
      <div className="sidebar-logo" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: 'linear-gradient(135deg, var(--primary), var(--blue-bright))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#000', flexShrink: 0,
            boxShadow: '0 0 16px var(--primary-glow)',
          }}>
            <IconSparkles />
          </div>
          <div>
            <h1 className="sidebar-logo-text" style={{ fontSize: 20, letterSpacing: -0.5, color: 'var(--primary)', margin: 0 }}>Intelli-Credit  </h1>
            <p style={{ color: 'var(--secondary)', fontSize: 11, fontWeight: 700, marginTop: 2, margin: 0 }}>
              Team: AI APEX
            </p>
          </div>
        </div>
        <button onClick={() => setIsOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 24, padding: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          ×
        </button>
      </div>

      {/* AI Engine Active Box */}
      <div style={{ padding: '0 20px', marginTop: 16, marginBottom: 8 }}>
        <div style={{
          border: '1px solid var(--border)',
          borderRadius: 10,
          padding: '12px 16px',
          background: 'var(--surface-alt)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--primary)', boxShadow: '0 0 8px var(--primary)' }}></span>
            AI Engine Active
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            🛡 99.8% Accuracy
          </div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <span className="sidebar-icon"><IconGrid /></span> Dashboard
          {/* Active dot removed to match screenshot style better */}
        </NavLink>
        <NavLink to="/demo/surya" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <span className="sidebar-icon" style={{ color: 'var(--approve)' }}>✓</span> Surya Pharma (Demo)
        </NavLink>
        <NavLink to="/demo/acme" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <span className="sidebar-icon" style={{ color: 'var(--reject)' }}>✕</span> Acme Textiles (Demo)
        </NavLink>

        <div style={{ margin: '16px 0', borderTop: '1px solid var(--border)', width: '100%' }}></div>

        {/* Dummy Links Removed */}
        <div style={{ flexGrow: 1 }}></div>

        <NavLink to="/new" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} style={{ color: 'var(--primary)', marginTop: '20px', borderTop: '1px solid var(--border)' }}>
          <span className="sidebar-icon" style={{ fontSize: 18, fontWeight: 'bold' }}>+</span> New Case (Custom)
        </NavLink>
      </nav>

    </aside>
  )
}

export default function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <BrowserRouter>
      {/* Animated Glowing Background Orbs */}
      <div className="bg-orbs">
        <div className="orb orb-1"></div>
        <div className="orb orb-2"></div>
      </div>

      <div className="app-layout">
        {!isSidebarOpen && (
          <button
            onClick={() => setIsSidebarOpen(true)}
            style={{
              position: 'fixed', top: 14, left: 16, zIndex: 60,
              background: 'var(--surface)', border: '1px solid var(--border)',
              color: 'var(--primary)', padding: '8px 12px', borderRadius: 'var(--radius)',
              cursor: 'pointer', boxShadow: 'var(--glass-shadow)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)'
            }}
          >
            <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" /></svg>
          </button>
        )}

        <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />

        <div className={`main-content ${isSidebarOpen ? '' : 'expanded'}`}>
          <Topbar />
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/demo/surya" element={<CaseDetail demoScenario="surya" />} />
              <Route path="/demo/acme" element={<CaseDetail demoScenario="acme" />} />
              <Route path="/demo" element={<CaseDetail demoScenario="acme" />} />
              <Route path="/cases/:id" element={<CaseDetail />} />
              <Route path="/new" element={<NewCase />} />
            </Routes>
          </ErrorBoundary>
        </div>
      </div>
    </BrowserRouter>
  )
}