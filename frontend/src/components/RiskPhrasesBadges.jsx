/**
 * RiskPhrasesBadges Component
 * 
 * Renders grey/yellow badges for each phrase detected in the document.
 * Uses muted colors to indicate these are PDF-extracted phrases without full context verification.
 * Handles empty lists gracefully by rendering nothing.
 * 
 * Validates: Requirements 9.5
 */

export default function RiskPhrasesBadges({ risk_phrases }) {
    if (!risk_phrases || risk_phrases.length === 0) {
        return null
    }

    return (
        <div style={{ marginTop: 12 }}>
            <div style={{
                fontSize: 11,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: 0.8,
                color: 'var(--text-muted)',
                marginBottom: 8,
            }}>
                Phrases Found (context unverified)
            </div>
            <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 6,
            }}>
                {risk_phrases.map((phrase, index) => (
                    <span
                        key={index}
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            padding: '4px 10px',
                            borderRadius: '99px',
                            fontSize: 11,
                            fontWeight: 600,
                            fontFamily: 'var(--font-mono)',
                            background: '#2A2A1A',
                            color: '#D4B106',
                            border: '1px solid #4A4520',
                        }}
                    >
                        ⚠ {phrase}
                    </span>
                ))}
            </div>
        </div>
    )
}
