import { useState, useEffect } from 'react'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export default function InsightPanel({ caseId, onInsightsSaved, externalNotes, onNotesChange }) {
  const [notes, setNotes] = useState('')
  const [adjustments, setAdjustments] = useState([])
  const [totalDelta, setTotalDelta] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)

  const charCount = notes.length
  const charLimit = 5000
  const isOverLimit = charCount > charLimit

  // Load existing insights on mount
  useEffect(() => {
    if (!caseId) return

    const loadInsights = async () => {
      try {
        const response = await fetch(`${BASE}/api/v1/cases/${caseId}/insights`)
        if (response.ok) {
          const data = await response.json()
          if (data.notes) {
            setNotes(data.notes)
            setAdjustments(data.adjustments || [])
            setTotalDelta(data.total_delta || 0)
          }
        }
      } catch (err) {
        console.error('Failed to load insights:', err)
      }
    }

    loadInsights()
  }, [caseId])

  // Sync internal notes with externalNotes when they change
  useEffect(() => {
    if (externalNotes !== undefined && externalNotes !== notes) {
      setNotes(externalNotes)
    }
  }, [externalNotes])

  // Call onNotesChange when local notes change
  const handleNotesLocalChange = (newVal) => {
    setNotes(newVal)
    if (onNotesChange) {
      onNotesChange(newVal)
    }
  }

  const handleSaveNotes = async () => {
    if (isOverLimit) {
      setError('Notes cannot exceed 5000 characters')
      return
    }

    setLoading(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const response = await fetch(`${BASE}/api/v1/cases/${caseId}/insights`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          notes: notes,
          created_by: 'analyst@nbfc.com'
        })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      const data = await response.json()
      setAdjustments(data.adjustments || [])
      setTotalDelta(data.total_delta || 0)
      setSuccessMessage(data.message || 'Insights saved successfully')

      if (onInsightsSaved) {
        onInsightsSaved(data.adjustments || [])
      }

      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      setError(err.message || 'Failed to save notes. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const renderAdjustmentPreview = () => {
    if (!adjustments || adjustments.length === 0) return null

    return (
      <div style={{
        marginTop: 16,
        padding: 14,
        background: 'var(--surface-alt)',
        border: '1px solid var(--border-soft)',
        borderRadius: 'var(--radius)',
        animation: 'slideIn 0.3s ease-out',
      }}>
        <style>{`
          @keyframes slideIn {
            from {
              opacity: 0;
              transform: translateY(-10px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
          
          @keyframes fadeIn {
            from {
              opacity: 0;
              transform: scale(0.95);
            }
            to {
              opacity: 1;
              transform: scale(1);
            }
          }
          
          .adjustment-item {
            animation: fadeIn 0.2s ease-out backwards;
          }
        `}</style>

        <div style={{
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--text-muted)',
          marginBottom: 10,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}>
          Score Impact Preview
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {adjustments.map((adj, i) => {
            const isNegative = adj.delta < 0
            const icon = isNegative ? '⚠️' : '✅'
            const color = isNegative ? '#ef4444' : '#10b981'
            const bgColor = isNegative ? '#fef2f2' : '#f0fdf4'
            const borderColor = isNegative ? '#fecaca' : '#bbf7d0'

            return (
              <div
                key={i}
                className="adjustment-item"
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  padding: '10px 12px',
                  background: bgColor,
                  border: `1px solid ${borderColor}`,
                  borderRadius: 6,
                  animationDelay: `${i * 0.05}s`,
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateX(4px)'
                  e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateX(0)'
                  e.currentTarget.style.boxShadow = 'none'
                }}
              >
                <span style={{
                  fontSize: 16,
                  lineHeight: '20px',
                  flexShrink: 0,
                }}>{icon}</span>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: 'var(--text)',
                    marginBottom: 3,
                  }}>
                    {adj.pillar}: <span style={{
                      color: color,
                      fontFamily: 'var(--font-mono)',
                      fontSize: 14,
                    }}>
                      {adj.delta > 0 ? '+' : ''}{adj.delta} pts
                    </span>
                  </div>
                  <div style={{
                    fontSize: 12,
                    color: 'var(--text-muted)',
                    lineHeight: 1.5,
                  }}>
                    {adj.reason}
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <div style={{
          marginTop: 14,
          paddingTop: 14,
          borderTop: '2px solid var(--border-soft)',
          fontSize: 14,
          fontWeight: 700,
          color: 'var(--text)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <span>Net Score Impact:</span>
          <span style={{
            color: totalDelta < 0 ? '#ef4444' : '#10b981',
            fontFamily: 'var(--font-mono)',
            fontSize: 16,
            padding: '4px 12px',
            background: totalDelta < 0 ? '#fef2f2' : '#f0fdf4',
            borderRadius: 6,
            border: `1px solid ${totalDelta < 0 ? '#fecaca' : '#bbf7d0'}`,
          }}>
            {totalDelta > 0 ? '+' : ''}{totalDelta} pts
          </span>
        </div>
      </div>
    )
  }

  const loadDemoScenario = () => {
    const demoNotes = `Site visit observations from manufacturing facility:

Factory operating at 40% capacity due to reduced demand. Management was evasive when asked about order book details and refused to share customer contracts.

Positive developments:
- Secured new export order worth $2M with 3-year contract
- Promoter infusion of $500K equity completed last month
- Experienced management team with second generation now involved

Concerns:
- Litigation pending with former supplier (court notice received)
- Key man risk - single promoter handles all major decisions
- Collateral disputed by third party claiming prior encumbrance

Overall: Mixed signals requiring careful evaluation.`

    handleNotesLocalChange(demoNotes)
    setError(null)
    setSuccessMessage(null)
  }

  return (
    <div style={{
      padding: '16px 0',
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 12,
      }}>
        <div>
          <div style={{
            fontSize: 14,
            fontWeight: 600,
            color: 'var(--text)',
            marginBottom: 4,
          }}>
            Analyst Notes
          </div>
          <div style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--primary)',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}>
            ✨ AI-Powered Insight Analysis
          </div>
        </div>

        <button
          onClick={loadDemoScenario}
          disabled={loading}
          style={{
            padding: '6px 12px',
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--primary)',
            background: 'transparent',
            border: '1px solid var(--primary)',
            borderRadius: 'var(--radius)',
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            opacity: loading ? 0.5 : 1,
          }}
          onMouseEnter={(e) => {
            if (!loading) {
              e.target.style.background = 'var(--primary)'
              e.target.style.color = 'var(--text-inverse)'
            }
          }}
          onMouseLeave={(e) => {
            if (!loading) {
              e.target.style.background = 'transparent'
              e.target.style.color = 'var(--primary)'
            }
          }}
        >
          Load Demo Scenario
        </button>
      </div>

      <textarea
        value={notes}
        onChange={(e) => handleNotesLocalChange(e.target.value)}
        placeholder="Enter your observations from site visit or management meeting (e.g. Factory operating at 40% capacity)"
        disabled={loading}
        style={{
          width: '100%',
          minHeight: 100,
          padding: 12,
          fontSize: 13,
          lineHeight: 1.5,
          color: 'var(--text)',
          background: 'var(--surface)',
          border: `1px solid ${isOverLimit ? 'var(--critical)' : 'var(--border)'}`,
          borderRadius: 'var(--radius)',
          resize: 'vertical',
          fontFamily: 'inherit',
          outline: 'none',
          transition: 'border-color 0.2s',
        }}
        onFocus={(e) => {
          if (!isOverLimit) {
            e.target.style.borderColor = 'var(--primary)'
          }
        }}
        onBlur={(e) => {
          if (!isOverLimit) {
            e.target.style.borderColor = 'var(--border)'
          }
        }}
      />

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginTop: 8,
      }}>
        <div style={{
          fontSize: 12,
          color: isOverLimit ? 'var(--critical)' : 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
        }}>
          {charCount} / {charLimit}
        </div>

        <button
          onClick={handleSaveNotes}
          disabled={loading || isOverLimit}
          style={{
            padding: '8px 16px',
            fontSize: 13,
            fontWeight: 600,
            color: loading || isOverLimit ? 'var(--text-dim)' : 'var(--text-inverse)',
            background: loading || isOverLimit ? 'var(--border)' : 'var(--primary)',
            border: 'none',
            borderRadius: 'var(--radius)',
            cursor: loading || isOverLimit ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            opacity: loading || isOverLimit ? 0.5 : 1,
          }}
          onMouseEnter={(e) => {
            if (!loading && !isOverLimit) {
              e.target.style.opacity = '0.9'
            }
          }}
          onMouseLeave={(e) => {
            if (!loading && !isOverLimit) {
              e.target.style.opacity = '1'
            }
          }}
        >
          {loading ? 'Saving...' : 'Save Notes'}
        </button>
      </div>

      {isOverLimit && (
        <div style={{
          marginTop: 8,
          padding: '8px 12px',
          fontSize: 12,
          color: '#ef4444',
          background: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: 4,
          animation: 'fadeIn 0.3s ease-out',
        }}>
          ⚠️ Notes cannot exceed 5000 characters
        </div>
      )}

      {error && (
        <div style={{
          marginTop: 8,
          padding: '8px 12px',
          fontSize: 12,
          color: '#ef4444',
          background: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: 4,
          animation: 'fadeIn 0.3s ease-out',
        }}>
          ⚠️ {error}
        </div>
      )}

      {successMessage && (
        <div style={{
          marginTop: 8,
          padding: '8px 12px',
          fontSize: 12,
          color: '#10b981',
          background: '#f0fdf4',
          border: '1px solid #bbf7d0',
          borderRadius: 4,
          animation: 'fadeIn 0.3s ease-out',
        }}>
          ✓ {successMessage}
        </div>
      )}

      {renderAdjustmentPreview()}
    </div>
  )
}
