import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FileDropzone from '../components/FileDropzone';
import LoadingStages from '../components/LoadingStages';
import StatCard from '../components/StatCard';
import Badge from '../components/Badge';
import EmptyState from '../components/EmptyState';
import { ingestDocument, compareDocuments } from '../lib/api';

function DeltaRow({ record, expanded, onToggle }) {
  return (
    <div className="border-b border-surface-700 last:border-b-0">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-700/50 transition-colors text-left"
      >
        <Badge variant={record.change_type}>{record.change_type}</Badge>
        <span className="text-sm text-text-primary flex-1 truncate">
          {record.new_value || record.old_value || record.description}
        </span>
        <span className="text-xs text-text-muted">p{record.page}</span>
        <span className="text-xs text-text-muted">
          {(record.confidence * 100).toFixed(0)}%
        </span>
        <svg className={`w-4 h-4 text-text-muted transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className="px-4 pb-3 ml-8 text-sm space-y-1">
          {record.old_value && (
            <p><span className="text-text-muted">Old:</span> <code className="text-danger font-mono text-xs bg-danger/10 px-1.5 py-0.5 rounded">{record.old_value}</code></p>
          )}
          {record.new_value && (
            <p><span className="text-text-muted">New:</span> <code className="text-success font-mono text-xs bg-success/10 px-1.5 py-0.5 rounded">{record.new_value}</code></p>
          )}
          <p className="text-text-muted">{record.description}</p>
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

  const stages = ['Ingesting Document A', 'Ingesting Document B', 'Detecting Changes', 'Done'];

  const handleUploadA = async ({ file, documentId, revision }) => {
    setUploadA({ loading: true });
    try {
      const res = await ingestDocument(file, documentId, revision);
      setUploadA({ done: true, format: res.format, documentId, revision });
    } catch (e) {
      setUploadA({ error: e.message });
    }
  };

  const handleUploadB = async ({ file, documentId, revision }) => {
    setUploadB({ loading: true });
    try {
      const res = await ingestDocument(file, documentId, revision);
      setUploadB({ done: true, format: res.format, documentId, revision });
    } catch (e) {
      setUploadB({ error: e.message });
    }
  };

  const handleCompare = async () => {
    if (!uploadA.done || !uploadB.done) return;
    setComparing(true);
    setError(null);
    setStageIndex(2);

    try {
      const res = await compareDocuments(
        uploadA.documentId, uploadA.revision,
        uploadB.documentId, uploadB.revision
      );
      setStageIndex(3);
      setResult(res);
    } catch (e) {
      setError(e.message || 'Comparison failed');
    } finally {
      setComparing(false);
    }
  };

  const filteredChanges = result?.changes?.filter(c =>
    filter === 'all' || c.change_type === filter
  ) || [];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-2xl font-bold text-text-primary mb-6">Document Comparison</h1>

      {/* Upload Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <FileDropzone label="Document A (Base)" onFileSelect={handleUploadA} uploadState={uploadA} />
        <FileDropzone label="Document B (Revised)" onFileSelect={handleUploadB} uploadState={uploadB} />
      </div>

      {/* Compare Button */}
      <div className="flex items-center gap-4 mb-8">
        <button
          onClick={handleCompare}
          disabled={!uploadA.done || !uploadB.done || comparing}
          className="px-6 py-2.5 rounded-lg bg-accent text-white font-semibold text-sm hover:bg-accent-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {comparing ? 'Comparing...' : 'Compare Documents'}
        </button>
        {comparing && <LoadingStages stages={stages} currentIndex={stageIndex} />}
      </div>

      {error && (
        <EmptyState
          error
          title="Comparison Failed"
          description={error}
          icon={<svg className="w-6 h-6 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.068 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>}
        />
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Summary Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard label="Added" value={result.summary?.added || 0} color="success" />
            <StatCard label="Removed" value={result.summary?.removed || 0} color="danger" />
            <StatCard label="Modified" value={result.summary?.modified || 0} color="warning" />
            <StatCard
              label="Total"
              value={(result.summary?.added || 0) + (result.summary?.removed || 0) + (result.summary?.modified || 0)}
              color="accent"
            />
          </div>

          {/* Filter + Download */}
          <div className="flex flex-wrap items-center gap-3">
            {['all', 'added', 'removed', 'modified'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                  filter === f ? 'bg-accent text-white' : 'bg-surface-700 text-text-secondary hover:bg-surface-600'
                }`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
            <div className="ml-auto flex gap-2">
              <a
                href={`http://localhost:8000/api/compare/${uploadA.documentId}/${uploadB.documentId}/report.md`}
                target="_blank"
                rel="noopener"
                className="px-3 py-1.5 rounded text-xs font-medium bg-surface-700 text-text-secondary hover:bg-surface-600 transition-colors"
              >
                ↓ Markdown
              </a>
              <button
                onClick={() => navigate(`/chat?a=${uploadA.documentId}&b=${uploadB.documentId}`)}
                className="px-3 py-1.5 rounded text-xs font-medium bg-accent-muted text-accent-light hover:bg-accent/30 transition-colors"
              >
                Ask about these docs →
              </button>
            </div>
          </div>

          {/* Changes List */}
          <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
            <div className="px-4 py-2 bg-surface-700/50 text-xs text-text-muted font-medium flex items-center gap-3">
              <span className="flex-1">Change</span>
              <span className="w-12">Page</span>
              <span className="w-12">Conf.</span>
              <span className="w-4"></span>
            </div>
            {filteredChanges.length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-text-muted">No changes match this filter.</p>
            ) : (
              filteredChanges.slice(0, 50).map((c, i) => (
                <DeltaRow
                  key={c.change_id || i}
                  record={c}
                  expanded={expandedId === (c.change_id || i)}
                  onToggle={() => setExpandedId(expandedId === (c.change_id || i) ? null : (c.change_id || i))}
                />
              ))
            )}
            {filteredChanges.length > 50 && (
              <p className="px-4 py-2 text-xs text-text-muted text-center">
                Showing 50 of {filteredChanges.length} changes
              </p>
            )}
          </div>
        </div>
      )}

      {!result && !comparing && !error && (
        <EmptyState
          title="Upload two documents to compare"
          description="Upload a base revision (A) and a newer revision (B) to detect all engineering changes between them."
          icon={<svg className="w-6 h-6 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>}
        />
      )}
    </div>
  );
}
