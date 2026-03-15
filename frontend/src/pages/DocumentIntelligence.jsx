import { useState } from 'react'
import { api } from '../api/client.js'

const DOCUMENT_TYPES = [
    { id: 'alm', label: 'ALM Report', icon: '📊' },
    { id: 'shareholding', label: 'Shareholding Pattern', icon: '👥' },
    { id: 'borrowing', label: 'Borrowing Profile', icon: '💰' },
    { id: 'annual_report', label: 'Annual Report', icon: '📈' },
    { id: 'portfolio', label: 'Portfolio Performance', icon: '📁' },
]

export default function DocumentIntelligence() {
    const [uploadedDocs, setUploadedDocs] = useState([])
    const [uploading, setUploading] = useState(false)
    const [selectedFile, setSelectedFile] = useState(null)
    const [classificationResult, setClassificationResult] = useState(null)
    const [error, setError] = useState(null)

    async function handleFileUpload(file) {
        if (!file) return
        
        setUploading(true)
        setSelectedFile(file)
        setError(null)
        
        try {
            // Use demo case ID for testing
            const caseId = 'demo-doc-intelligence'
            const docSlot = 'annual_report' // Default slot
            
            // Call real backend API
            const result = await api.uploadDocument(caseId, file, docSlot)
            
            // Transform API response to match our UI format
            const transformedResult = {
                filename: result.filename,
                classified_type: result.classified_as,
                confidence: result.classification_confidence,
                needs_review: result.requires_human_review,
                matched_patterns: result.matched_patterns || [],
                extracted_data: result.suggested_schema || {},
                raw_preview: result.raw_text_preview || '',
                page_count: result.page_count,
                extraction_method: result.extraction_method,
            }
            
            setClassificationResult(transformedResult)
            setUploadedDocs(prev => [...prev, transformedResult])
        } catch (err) {
            console.error('Upload failed:', err)
            setError(err.message || 'Upload failed')
        } finally {
            setUploading(false)
        }
    }

    async function handleApprove(doc) {
        try {
            const caseId = 'demo-doc-intelligence'
            const docId = doc.filename.replace(/[^a-zA-Z0-9]/g, '_')
            
            await api.approveClassification(caseId, docId, doc.classified_type, null)
            alert('✓ Document classification approved!')
        } catch (err) {
            alert('Failed to approve: ' + err.message)
        }
    }

    function handleReject(doc) {
        const newType = prompt(
            `Current classification: ${doc.classified_type}\n\nEnter correct document type:\n` +
            '- alm\n- shareholding\n- borrowing\n- annual_report\n- portfolio'
        )
        
        if (newType && DOCUMENT_TYPES.find(t => t.id === newType)) {
            // Update classification
            setClassificationResult(prev => ({
                ...prev,
                classified_type: newType,
                needs_review: false
            }))
            alert('✓ Classification updated to: ' + newType)
        }
    }

    return (
        <div style={{ padding: '28px', maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ marginBottom: 32 }}>
                <h2 style={{ fontSize: 24, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
                    📄 Document Intelligence (Stage 3)
                </h2>
                <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>
                    Upload documents for automatic classification, schema mapping, and human-in-the-loop approval
                </p>
                {error && (
                    <div style={{
                        marginTop: 12,
                        padding: 12,
                        background: 'var(--reject-bg)',
                        border: '1px solid var(--reject)',
                        borderRadius: 'var(--radius)',
                        color: 'var(--reject)',
                        fontSize: 13
                    }}>
                        ✕ {error}
                    </div>
                )}
            </div>

            <div style={{
                background: 'var(--surface)',
                border: '2px dashed var(--primary)',
                borderRadius: 'var(--radius-lg)',
                padding: 40,
                textAlign: 'center',
                marginBottom: 32,
                cursor: 'pointer'
            }}
            onClick={() => document.getElementById('doc-upload').click()}
            >
                <input
                    id="doc-upload"
                    type="file"
                    accept=".pdf,.xlsx,.csv"
                    style={{ display: 'none' }}
                    onChange={e => handleFileUpload(e.target.files?.[0])}
                />
                {uploading ? (
                    <div>
                        <div className="loading-spin" style={{ margin: '0 auto 16px', width: 32, height: 32, borderWidth: 3 }} />
                        <p style={{ color: 'var(--primary)', fontWeight: 600 }}>Classifying document...</p>
                    </div>
                ) : (
                    <div>
                        <div style={{ fontSize: 48, marginBottom: 12 }}>📤</div>
                        <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>
                            Upload Financial Document
                        </p>
                        <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                            Supports: ALM, Shareholding, Borrowing, Annual Reports, Portfolio Data
                        </p>
                    </div>
                )}
            </div>

            <div style={{ marginBottom: 32 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 16 }}>
                    Supported Document Types
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                    {DOCUMENT_TYPES.map(type => (
                        <div key={type.id} style={{
                            background: 'var(--surface)',
                            border: '1px solid var(--border)',
                            borderRadius: 'var(--radius)',
                            padding: 12,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 10
                        }}>
                            <span style={{ fontSize: 24 }}>{type.icon}</span>
                            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{type.label}</span>
                        </div>
                    ))}
                </div>
            </div>

            {classificationResult && (
                <div style={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: 24,
                    marginBottom: 32
                }}>
                    <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', marginBottom: 16 }}>
                        🤖 Classification Result
                    </h3>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                        <div>
                            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Filename</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
                                {classificationResult.filename}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Classified As</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--primary)' }}>
                                {DOCUMENT_TYPES.find(t => t.id === classificationResult.classified_type)?.label || 'Unknown'}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Confidence</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: classificationResult.confidence > 0.7 ? 'var(--approve)' : 'var(--warning)' }}>
                                {(classificationResult.confidence * 100).toFixed(1)}%
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Review Status</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: classificationResult.needs_review ? 'var(--warning)' : 'var(--approve)' }}>
                                {classificationResult.needs_review ? '⚠️ Needs Review' : '✓ Auto-Approved'}
                            </div>
                        </div>
                    </div>

                    <div style={{
                        background: 'var(--surface-alt)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        padding: 16,
                        marginBottom: 16
                    }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 12 }}>
                            📋 Document Details
                        </div>
                        <div style={{ display: 'grid', gap: 8 }}>
                            {classificationResult.page_count && (
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                                    <span style={{ color: 'var(--text-muted)' }}>PAGE COUNT:</span>
                                    <span style={{ color: 'var(--text)', fontWeight: 600 }}>{classificationResult.page_count}</span>
                                </div>
                            )}
                            {classificationResult.extraction_method && (
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                                    <span style={{ color: 'var(--text-muted)' }}>EXTRACTION METHOD:</span>
                                    <span style={{ color: 'var(--text)', fontWeight: 600 }}>{classificationResult.extraction_method}</span>
                                </div>
                            )}
                            {classificationResult.matched_patterns && classificationResult.matched_patterns.length > 0 && (
                                <div style={{ fontSize: 12, marginTop: 8 }}>
                                    <span style={{ color: 'var(--text-muted)' }}>MATCHED PATTERNS:</span>
                                    <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                        {classificationResult.matched_patterns.map((pattern, idx) => (
                                            <span key={idx} style={{
                                                background: 'var(--surface)',
                                                padding: '4px 8px',
                                                borderRadius: 'var(--radius)',
                                                fontSize: 11,
                                                color: 'var(--primary)'
                                            }}>
                                                {pattern}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    <div style={{ display: 'flex', gap: 12 }}>
                        <button
                            onClick={() => handleApprove(classificationResult)}
                            style={{
                                flex: 1,
                                background: 'var(--approve)',
                                color: '#fff',
                                border: 'none',
                                borderRadius: 'var(--radius)',
                                padding: '12px 20px',
                                fontSize: 14,
                                fontWeight: 700,
                                cursor: 'pointer'
                            }}
                        >
                            ✓ Approve Classification
                        </button>
                        <button
                            onClick={() => handleReject(classificationResult)}
                            style={{
                                flex: 1,
                                background: 'var(--surface-alt)',
                                color: 'var(--text)',
                                border: '1px solid var(--border)',
                                borderRadius: 'var(--radius)',
                                padding: '12px 20px',
                                fontSize: 14,
                                fontWeight: 700,
                                cursor: 'pointer'
                            }}
                        >
                            ✕ Reject & Reclassify
                        </button>
                    </div>
                </div>
            )}

            {uploadedDocs.length > 0 && (
                <div>
                    <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', marginBottom: 16 }}>
                        📚 Document History
                    </h3>
                    <div style={{ display: 'grid', gap: 12 }}>
                        {uploadedDocs.map((doc, idx) => (
                            <div key={idx} style={{
                                background: 'var(--surface)',
                                border: '1px solid var(--border)',
                                borderRadius: 'var(--radius)',
                                padding: 16,
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center'
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <span style={{ fontSize: 24 }}>
                                        {DOCUMENT_TYPES.find(t => t.id === doc.classified_type)?.icon || '📄'}
                                    </span>
                                    <div>
                                        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
                                            {doc.filename}
                                        </div>
                                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                                            {DOCUMENT_TYPES.find(t => t.id === doc.classified_type)?.label} • {(doc.confidence * 100).toFixed(0)}% confidence
                                        </div>
                                    </div>
                                </div>
                                <div style={{
                                    padding: '6px 12px',
                                    background: 'var(--approve-bg)',
                                    color: 'var(--approve)',
                                    borderRadius: 'var(--radius)',
                                    fontSize: 12,
                                    fontWeight: 700
                                }}>
                                    ✓ Processed
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div style={{
                marginTop: 40,
                padding: 24,
                background: 'var(--surface-alt)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)'
            }}>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 16 }}>
                    ✨ Stage 3 Extended Objectives
                </h3>
                <div style={{ display: 'grid', gap: 12 }}>
                    <div style={{ display: 'flex', gap: 10 }}>
                        <span style={{ color: 'var(--approve)', fontSize: 18 }}>✓</span>
                        <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Automatic Document Classification</div>
                            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Pattern-based classification with 37 rules across 5 document types</div>
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: 10 }}>
                        <span style={{ color: 'var(--approve)', fontSize: 18 }}>✓</span>
                        <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Dynamic Schema Mapping</div>
                            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Configurable schemas with field transformations and validation</div>
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: 10 }}>
                        <span style={{ color: 'var(--approve)', fontSize: 18 }}>✓</span>
                        <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Human-in-the-Loop Approval</div>
                            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Review and approve/reject classifications with confidence thresholds</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
