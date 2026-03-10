/**
 * DocumentUploadPanel Component
 * 
 * Provides file upload interface with drag-and-drop support for PDF, CSV, and XLSX files.
 * Displays loading state during extraction and shows extraction results.
 * 
 * Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 10.5
 */

import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import ExtractionResultCard from './ExtractionResultCard'

export default function DocumentUploadPanel({ caseId }) {
    const [uploading, setUploading] = useState(false)
    const [extractionResult, setExtractionResult] = useState(null)
    const [error, setError] = useState(null)

    const onDrop = useCallback(async (acceptedFiles) => {
        if (acceptedFiles.length === 0) return

        const file = acceptedFiles[0]
        setUploading(true)
        setError(null)
        setExtractionResult(null)

        try {
            // Create FormData with the file
            const formData = new FormData()
            formData.append('file', file)

            // POST to upload endpoint
            const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
            const response = await fetch(`${BASE}/api/v1/cases/${caseId}/upload`, {
                method: 'POST',
                body: formData,
            })

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: response.statusText }))
                throw new Error(errorData.detail || `HTTP ${response.status}`)
            }

            const result = await response.json()
            setExtractionResult(result)
        } catch (err) {
            setError(err.message || 'Upload failed. Please try again.')
        } finally {
            setUploading(false)
        }
    }, [caseId])

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            'application/pdf': ['.pdf'],
            'text/csv': ['.csv'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
        },
        multiple: false,
        disabled: uploading,
    })

    return (
        <div style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: 16,
            marginBottom: 20,
        }}>
            <h3 style={{
                fontSize: 13,
                fontWeight: 600,
                color: 'var(--text)',
                marginBottom: 12,
                textTransform: 'uppercase',
                letterSpacing: 0.8,
            }}>
                Upload Annual Report PDF — or use demo data below
            </h3>

            {/* Dropzone */}
            <div
                {...getRootProps()}
                style={{
                    border: `2px dashed ${isDragActive ? 'var(--blue-bright)' : 'var(--primary)'}`,
                    borderRadius: 'var(--radius)',
                    padding: 14,
                    textAlign: 'center',
                    cursor: uploading ? 'not-allowed' : 'pointer',
                    background: isDragActive ? 'var(--blue-dim)' : 'var(--surface-alt)',
                    transition: 'all 0.2s',
                }}
            >
                <input {...getInputProps()} />
                {uploading ? (
                    <div style={{ color: 'var(--text-muted)' }}>
                        <div style={{
                            fontSize: 32,
                            marginBottom: 8,
                            animation: 'spin 1s linear infinite',
                        }}>⏳</div>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>Extracting data...</div>
                    </div>
                ) : isDragActive ? (
                    <div style={{ color: 'var(--blue-bright)' }}>
                        <div style={{ fontSize: 32, marginBottom: 8 }}>📄</div>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>Drop file here</div>
                    </div>
                ) : (
                    <div style={{ color: 'var(--text-muted)' }}>
                        <div style={{ fontSize: 22, marginBottom: 4 }}>📤</div>
                        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>
                            Drag & drop a file here, or click to select
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                            Accepts PDF, CSV, and XLSX files
                        </div>
                    </div>
                )}
            </div>

            {/* Error display */}
            {error && (
                <div style={{
                    marginTop: 12,
                    padding: 10,
                    background: 'var(--reject-bg)',
                    border: '1px solid var(--reject)',
                    borderRadius: 'var(--radius)',
                    color: 'var(--reject)',
                    fontSize: 12,
                }}>
                    ✕ {error}
                </div>
            )}

            {/* Extraction result card */}
            {extractionResult && (
                <ExtractionResultCard extractionResult={extractionResult} />
            )}

            <style>{`
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    )
}
