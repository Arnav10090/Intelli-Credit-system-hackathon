/**
 * KeySectionsBadges Component
 * 
 * Renders grey badges for each key section detected in the document.
 * Handles empty lists gracefully by rendering nothing.
 * 
 * Validates: Requirements 9.6
 */

export default function KeySectionsBadges({ key_sections }) {
    if (!key_sections || key_sections.length === 0) {
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
                Key Sections Found
            </div>
            <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 6,
            }}>
                {key_sections.map((section, index) => (
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
                            background: 'var(--surface-alt)',
                            color: 'var(--text-muted)',
                            border: '1px solid var(--border)',
                        }}
                    >
                        {section}
                    </span>
                ))}
            </div>
        </div>
    )
}
