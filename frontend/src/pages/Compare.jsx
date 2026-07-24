import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import FileDropzone from '../components/FileDropzone';
import LoadingStages from '../components/LoadingStages';
import StatCard from '../components/StatCard';
import Badge from '../components/Badge';
import EmptyState from '../components/EmptyState';
import { ingestDocument, compareDocuments, getComparisonHistory } from '../lib/api';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function DeltaRow({ record, expanded, onToggle }) {
  return (
    <div className="border-b border-gray-100 dark:border-surface-700 last:border-b-0">
      <button onClick={onToggle} className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-surface-700/50 transition-colors text-left">
        <Badge variant={record.change_type}>{record.change_type}</Badge>
        <span className="text-sm text-gray-900 dark:text-white flex-1 truncate">
          {record.new_value || record.old_value || record.description}
        </span>
        <span className="text-xs text-gray-500">p{record.page}</span>
        <span className="text-xs text-gray-500">{(record.confidence * 100).toFixed(0)}%</span>
        <svg className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className="px-4 pb-3 ml-8 text-sm space-y-1">
          {record.old_value && <p><span className="text-gray-500">Old:</span> <code className="text-red-700 dark:text-red-400 font-mono text-xs bg-red-50 dark:bg-red-900/20 px-1.5 py-0.5 rounded">{record.old_value}</code></p>}
          {record.new_value && <p><span className="text-gray-500">New:</span> <code className="text-emerald-700 dark:text-emerald-400 font-mono text-xs bg-emerald-50 dark:bg-emerald-900/20 px-1.5 py-0.5 rounded">{record.new_value}</code></p>}
          <p className="text-gray-500">{record.description}</p>
        </div>
      )}
    </div>
  );
}

export default function Compare() {
  const navigate = useNavigate();
  const [uploadA, setUploadA] = useState({});
  const [uploadB, setUploadB] = useState({});
  const [comparing, setComparing] = useState(false);
  const [stageIndex, setStageIndex] = useState(-1);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const [expandedId, setExpandedId] = useState(null);
  const [history, setHistory] = useState([]);

  const stages = ['Ingesting Document A', 'Ingesting Document B', 'Detecting Changes', 'Done'];

  useEffect(() => {
    getComparisonHistory().then(d => setHistory(d.comparisons || [])).catch(() => {});
  }, [result]); // Refresh when a new comparison completes

  const handleUploadA = async ({ file, documentId, revision }) => {
    setUploadA({ loading: true });
    try {
      const res = await ingestDocument(file, documentId, revision);
      setUploadA({ done: true, format: res.format, documentId, revision });
    } catch (e) { setUploadA({ error: e.message }); }
  };

  const handleUploadB = async ({ file, documentId, revision }) => {
    setUploadB({ loading: true });
    try {
      const res = await ingestDocument(file, documentId, revision);
      setUploadB({ done: true, format: res.format, documentId, revision });
    } catch (e) { setUploadB({ error: e.message }); }
  };

  const handleCompare = async () => {
    if (!uploadA.done || !uploadB.done) return;
    setComparing(true); setError(null); setStageIndex(2);
    try {
      const res = await compareDocuments(uploadA.documentId, uploadA.revision, uploadB.documentId, uploadB.revision);
      setStageIndex(3); setResult(res);
    } catch (e) { setError(e.message || 'Comparison failed'); }
    finally { setComparing(false); }
  };

  const filteredChanges = result?.changes?.filter(c => filter === 'all' || c.change_type === filter) || [];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Document Comparison</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <FileDropzone label="Document A (Base)" onFileSelect={handleUploadA} uploadState={uploadA} />
        <FileDropzone label="Document B (Revised)" onFileSelect={handleUploadB} uploadState={uploadB} />
      </div>

      <div className="flex items-center gap-4 mb-8">
        <button onClick={handleCompare} disabled={!uploadA.done || !uploadB.done || comparing}
          className="px-6 py-2.5 rounded-lg bg-cyan-600 text-white font-semibold text-sm hover:bg-cyan-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          {comparing ? 'Comparing...' : 'Compare Documents'}
        </button>
        {comparing && <LoadingStages stages={stages} currentIndex={stageIndex} />}
      </div>

      {error && <EmptyState error title="Comparison Failed" description={error} />}

      {result && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard label="Added" value={result.summary?.added || 0} color="success" />
            <StatCard label="Removed" value={result.summary?.removed || 0} color="danger" />
            <StatCard label="Modified" value={result.summary?.modified || 0} color="warning" />
            <StatCard label="Total" value={(result.summary?.added||0)+(result.summary?.removed||0)+(result.summary?.modified||0)} color="accent" />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {['all','added','removed','modified'].map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${filter === f ? 'bg-cyan-600 text-white' : 'bg-gray-100 dark:bg-surface-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-surface-600'}`}>
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
            <div className="ml-auto flex gap-2">
              <a href={`${API}/api/compare/${uploadA.documentId}/${uploadB.documentId}/report.md`} target="_blank" rel="noopener"
                className="px-3 py-1.5 rounded text-xs font-medium bg-gray-100 dark:bg-surface-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-surface-600 transition-colors">↓ Markdown</a>
              <a href={`${API}/api/compare/${uploadA.documentId}/${uploadB.documentId}/markup?doc=a`} target="_blank" rel="noopener"
                className="px-3 py-1.5 rounded text-xs font-medium bg-gray-100 dark:bg-surface-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-surface-600 transition-colors">🖍 Markup A</a>
              <a href={`${API}/api/compare/${uploadA.documentId}/${uploadB.documentId}/markup?doc=b`} target="_blank" rel="noopener"
                className="px-3 py-1.5 rounded text-xs font-medium bg-gray-100 dark:bg-surface-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-surface-600 transition-colors">🖍 Markup B</a>
              <button onClick={() => navigate(`/chat?a=${uploadA.documentId}&b=${uploadB.documentId}`)}
                className="px-3 py-1.5 rounded text-xs font-medium bg-cyan-50 dark:bg-accent-muted text-cyan-700 dark:text-cyan-300 hover:bg-cyan-100 dark:hover:bg-cyan-900/40 transition-colors">
                Ask about these docs →
              </button>
            </div>
          </div>

          <div className="bg-white dark:bg-surface-800 border border-gray-200 dark:border-surface-600 rounded-lg overflow-hidden">
            {filteredChanges.length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-gray-500">No changes match this filter.</p>
            ) : (
              filteredChanges.slice(0, 50).map((c, i) => (
                <DeltaRow key={c.change_id || i} record={c} expanded={expandedId === (c.change_id || i)} onToggle={() => setExpandedId(expandedId === (c.change_id || i) ? null : (c.change_id || i))} />
              ))
            )}
            {filteredChanges.length > 50 && <p className="px-4 py-2 text-xs text-gray-500 text-center">Showing 50 of {filteredChanges.length}</p>}
          </div>
        </div>
      )}

      {!result && !comparing && !error && (
        <EmptyState title="Upload two documents to compare" description="Upload a base revision (A) and a newer revision (B) to detect all engineering changes." />
      )}

      {/* Previous Comparisons */}
      {history.length > 0 && (
        <div className="mt-8 border-t border-gray-200 dark:border-surface-700 pt-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Previous Comparisons</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {history.map((h, i) => (
              <div key={i} className="bg-white dark:bg-surface-800 border border-gray-200 dark:border-surface-600 rounded-lg p-4 hover:border-cyan-300 dark:hover:border-cyan-700 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-900 dark:text-white truncate">{h.document_a_id}</span>
                  <span className="text-xs text-gray-400">vs</span>
                  <span className="text-sm font-medium text-gray-900 dark:text-white truncate">{h.document_b_id}</span>
                </div>
                <div className="flex gap-2 mb-3">
                  <Badge variant="added">+{h.summary?.added || 0}</Badge>
                  <Badge variant="removed">-{h.summary?.removed || 0}</Badge>
                  <Badge variant="modified">~{h.summary?.modified || 0}</Badge>
                </div>
                <button
                  onClick={() => navigate(`/chat?a=${h.document_a_id}&b=${h.document_b_id}`)}
                  className="w-full text-xs font-medium text-cyan-700 dark:text-cyan-400 hover:underline"
                >
                  Ask questions about this pair →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
