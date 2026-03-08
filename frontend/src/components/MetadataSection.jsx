/**
 * MetadataSection Component
 * 
 * Displays extraction metadata including:
 * - Page count as "{count} pages processed"
 * - Company name or "Not detected" in grey
 * - Financial figures count as "{count} financial figures detected"
 * 
 * Validates: Requirements 9.3, 9.4, 9.8
 */

export default function MetadataSection({ page_count, company_name, figures_count }) {
    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            marginTop: 12,
        }}>
            {/* Page count */}
            {page_count !== undefined && page_count !== null && (
                <div style={{
                    fontSize: 13,
                    color: 'var(--text)',
                }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {page_count}
                    </span>
                    {' pages processed'}
                </div>
            )}

            {/* Company name */}
            <div style={{
                fontSize: 13,
                color: company_name ? 'var(--text)' : 'var(--text-muted)',
            }}>
                <span style={{ color: 'var(--text-muted)' }}>Company name: </span>
                {company_name || 'Not detected'}
            </div>

            {/* Financial figures count */}
            {figures_count !== undefined && figures_count !== null && (
                <div style={{
                    fontSize: 13,
                    color: 'var(--text)',
                }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {figures_count}
                    </span>
                    {' financial figures detected'}
                </div>
            )}
        </div>
    )
}
