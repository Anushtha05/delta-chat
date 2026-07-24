import { useState } from 'react';
import Badge from './Badge';

export default function FileDropzone({ label, onFileSelect, uploadState }) {
  const [dragging, setDragging] = useState(false);
  const [docId, setDocId] = useState('');
  const [revision, setRevision] = useState('A');
  const [file, setFile] = useState(null);

  const handleDrop = (e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) setFile(f); };
  const handleSelect = (e) => { const f = e.target.files[0]; if (f) setFile(f); };
  const handleUpload = () => { if (file && docId.trim()) onFileSelect({ file, documentId: docId.trim(), revision: revision.trim() || 'A' }); };

  return (
    <div className="bg-white dark:bg-surface-800 border border-gray-200 dark:border-surface-600 rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{label}</h3>
        {uploadState?.format && <Badge variant="accent">{uploadState.format}</Badge>}
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
          dragging ? 'border-cyan-500 bg-cyan-50 dark:bg-cyan-900/20' : 'border-gray-300 dark:border-surface-600 hover:border-gray-400 dark:hover:border-surface-500'
        }`}
        onClick={() => document.getElementById(`file-${label}`).click()}
      >
        <input id={`file-${label}`} type="file" accept=".pdf,.dwg,.dxf" className="hidden" onChange={handleSelect} />
        {file ? (
          <div className="text-sm">
            <p className="text-cyan-700 dark:text-cyan-400 font-medium">{file.name}</p>
            <p className="text-gray-500 text-xs mt-1">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
        ) : (
          <div>
            <svg className="w-8 h-8 mx-auto text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-sm text-gray-500">Drop PDF, DWG, or DXF here</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <input type="text" placeholder="Document ID" value={docId} onChange={(e) => setDocId(e.target.value)}
          className="bg-gray-50 dark:bg-surface-700 border border-gray-300 dark:border-surface-600 rounded px-3 py-1.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:border-cyan-500 focus:outline-none" />
        <input type="text" placeholder="Revision" value={revision} onChange={(e) => setRevision(e.target.value)}
          className="bg-gray-50 dark:bg-surface-700 border border-gray-300 dark:border-surface-600 rounded px-3 py-1.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:border-cyan-500 focus:outline-none" />
      </div>

      <button onClick={handleUpload} disabled={!file || !docId.trim() || uploadState?.loading}
        className="w-full py-2 px-4 rounded-md text-sm font-medium bg-cyan-600 text-white hover:bg-cyan-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
        {uploadState?.loading ? 'Uploading...' : uploadState?.done ? '✓ Uploaded' : 'Upload & Ingest'}
      </button>

      {uploadState?.error && <p className="text-xs text-red-600">{uploadState.error}</p>}
    </div>
  );
}
