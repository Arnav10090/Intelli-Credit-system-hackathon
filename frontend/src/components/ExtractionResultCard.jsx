/**
 * ExtractionResultCard Component
 * 
 * Composes all extraction result display components into a unified card.
 * Displays extraction method, metadata, risk phrases, key sections, and raw text preview.
 * 
 * Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
 */

import ExtractionMethodBadge from './ExtractionMethodBadge'
import MetadataSection from './MetadataSection'
import RiskPhrasesBadges from './RiskPhrasesBadges'
import KeySectionsBadges from './KeySectionsBadges'
import CollapsiblePreview from './CollapsiblePreview'

export default function ExtractionResultCard({ extractionResult }) {
    if (!extractionResult) {
        return null
    }

    return (
        <div style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: 16,
            marginTop: 16,
        }}>
            {/* Extraction method badge at the top */}
            <ExtractionMethodBadge
                extraction_method={extractionResult.extraction_method}
                confidence_score={extractionResult.confidence_score}
            />

            {/* Metadata section */}
            <MetadataSection
                page_count={extractionResult.page_count}
                company_name={extractionResult.company_name_detected}
                figures_count={extractionResult.financial_figures_found}
            />

            {/* Risk phrases badges */}
            <RiskPhrasesBadges
                risk_phrases={extractionResult.risk_phrases_found}
            />

            {/* Key sections badges */}
            <KeySectionsBadges
                key_sections={extractionResult.key_sections_detected}
            />

            {/* Collapsible raw text preview */}
            <CollapsiblePreview
                raw_text_preview={extractionResult.raw_text_preview}
            />
        </div>
    )
}
