import { useState } from 'react';
import Badge from './Badge';

/**
 * FileDropzone — drag-and-drop file upload area with document_id/revision inputs.
 */
export default function FileDropzone({ label, onFileSelect, uploadState }) {
  const [dragging, setDragging] = useState(false);
  const [docId, setDocId] = useState('');
  const [revision, setRevision] = useState('A');
  const [file, setFile] = useState(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  const handleSelect = (e) => {
    const f = e.target.files[0];
    if (f) setFile(f);
  };

  const handleUpload = () => {
    if (file && docId.trim()) {
      onFileSelect({ file, documentId: docId.trim(), revision: revision.trim() || 'A' });
    }
  };

  const formatBadge = uploadState?.format;

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">{label}</h3>
        {formatBadge && <Badge variant="accent">{formatBadge}</Badge>}
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
          dragging ? 'border-accent bg-accent-muted/20' : 'border-surface-600 hover:border-surface-500'
        }`}
        onClick={() => document.getElementById(`file-${label}`).click()}
      >
        <input
          id={`file-${label}`}
          type="file"
          accept=".pdf,.dwg,.dxf"
          className="hidden"
          onChange={handleSelect}
        />
        {file ? (
          <div className="text-sm">
            <p className="text-accent font-medium">{file.name}</p>
            <p className="text-text-muted text-xs mt-1">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
        ) : (
          <div>
            <svg className="w-8 h-8 mx-auto text-text-muted mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-sm text-text-muted">Drop PDF, DWG, or DXF here</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <input
          type="text"
          placeholder="Document ID"
          value={docId}
          onChange={(e) => setDocId(e.target.value)}
          className="bg-surface-700 border border-surface-600 rounded px-3 py-1.5 text-sm text-text-primary placeholder-text-muted focus:border-accent focus:outline-none"
        />
        <input
          type="text"
          placeholder="Revision"
          value={revision}
          onChange={(e) => setRevision(e.target.value)}
          className="bg-surface-700 border border-surface-600 rounded px-3 py-1.5 text-sm text-text-primary placeholder-text-muted focus:border-accent focus:outline-none"
        />
      </div>

      <button
        onClick={handleUpload}
        disabled={!file || !docId.trim() || uploadState?.loading}
        className="w-full py-2 px-4 rounded-md text-sm font-medium bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {uploadState?.loading ? 'Uploading...' : uploadState?.done ? '✓ Uploaded' : 'Upload & Ingest'}
      </button>

      {uploadState?.error && (
        <p className="text-xs text-danger">{uploadState.error}</p>
      )}
    </div>
  );
}
