/**
 * ExtractionMethodBadge Component
 * 
 * Displays a badge indicating the PDF extraction method used.
 * - Green badge for "digital" extraction with confidence percentage
 * - Orange badge for "ocr" extraction with warning text
 * - Grey badge for "ocr_unavailable"
 * 
 * Validates: Requirements 9.1, 9.2
 */

export default function ExtractionMethodBadge({ extraction_method, confidence_score }) {
    if (!extraction_method) return null

    const badgeStyles = {
        digital: {
            background: 'var(--approve-bg)',
            color: 'var(--approve)',
            border: '1px solid #0A4030',
            icon: '✓',
            text: `Digital PDF — ${Math.round(confidence_score * 100)}% confidence`
        },
        ocr: {
            background: 'var(--partial-bg)',
            color: 'var(--partial)',
            border: '1px solid #4A2A05',
            icon: '⚠',
            text: 'OCR Mode — lower accuracy'
        },
        ocr_unavailable: {
            background: 'var(--surface-alt)',
            color: 'var(--text-muted)',
            border: '1px solid var(--border)',
            icon: '○',
            text: 'OCR Unavailable'
        }
    }

    const style = badgeStyles[extraction_method] || badgeStyles.ocr_unavailable

    return (
        <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 12px',
            borderRadius: '99px',
            fontSize: 12,
            fontWeight: 600,
            fontFamily: 'var(--font-mono)',
            background: style.background,
            color: style.color,
            border: style.border,
        }}>
            <span style={{ fontSize: 14 }}>{style.icon}</span>
            <span>{style.text}</span>
        </div>
    )
}
