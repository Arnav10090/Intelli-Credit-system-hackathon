/**
 * CollapsiblePreview Component
 * 
 * Displays the first 300 characters of raw text with expand/collapse toggle.
 * Handles null/empty preview gracefully by rendering nothing.
 * 
 * Validates: Requirements 9.7
 */

import { useState } from 'react'

export default function CollapsiblePreview({ raw_text_preview }) {
    const [isExpanded, setIsExpanded] = useState(false)

    if (!raw_text_preview) {
        return null
    }

    const previewText = raw_text_preview.slice(0, 300)
    const hasMore = raw_text_preview.length > 300

    return (
        <div style={{ marginTop: 12 }}>
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 8,
            }}>
                <div style={{
                    fontSize: 11,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: 0.8,
                    color: 'var(--text-muted)',
                }}>
                    Raw Text Preview
                </div>
                {hasMore && (
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--blue-bright)',
                            fontSize: 11,
                            fontWeight: 600,
                            cursor: 'pointer',
                            padding: '2px 6px',
                            fontFamily: 'var(--font-ui)',
                        }}
                    >
                        {isExpanded ? '▲ Collapse' : '▼ Expand'}
                    </button>
                )}
            </div>
            <div style={{
                background: 'var(--surface-alt)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: 12,
                fontSize: 12,
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-muted)',
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                maxHeight: isExpanded ? 'none' : '120px',
                overflow: isExpanded ? 'visible' : 'hidden',
            }}>
                {isExpanded ? raw_text_preview : previewText}
                {!isExpanded && hasMore && '...'}
            </div>
        </div>
    )
}
