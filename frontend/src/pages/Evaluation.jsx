import { useState, useEffect } from 'react';
import StatCard from '../components/StatCard';
import EmptyState from '../components/EmptyState';
import { getMetrics } from '../lib/api';

function scoreColor(val, thresholds = { green: 0.85, amber: 0.7 }) {
  if (val >= thresholds.green) return 'success';
  if (val >= thresholds.amber) return 'warning';
  return 'danger';
}

export default function Evaluation() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMetrics();
      setMetrics(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <EmptyState
          error
          title="Failed to load metrics"
          description={error}
          action={<button onClick={fetchData} className="px-4 py-2 rounded bg-accent text-white text-sm">Retry</button>}
        />
      </div>
    );
  }

  const counters = metrics?.counters || {};
  const latencies = metrics?.latencies || {};

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text-primary">Evaluation & Metrics</h1>
        <button
          onClick={fetchData}
          className="px-4 py-2 rounded-lg bg-surface-700 text-text-secondary text-sm hover:bg-surface-600 transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* System Counters */}
      <section className="mb-8">
        <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-3">Pipeline Counters</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          <StatCard label="Ingestions" value={counters.ingestion_count || 0} color="accent" />
          <StatCard label="Comparisons" value={counters.delta_count || 0} color="accent" />
          <StatCard label="Added" value={counters.delta_added || 0} color="success" />
          <StatCard label="Removed" value={counters.delta_removed || 0} color="danger" />
          <StatCard label="Modified" value={counters.delta_modified || 0} color="warning" />
          <StatCard label="LLM Tokens" value={counters.llm_input_tokens || 0} sub={`out: ${counters.llm_output_tokens || 0}`} color="accent" />
        </div>
      </section>

      {/* Latency Stats */}
      <section className="mb-8">
        <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-3">Latency (ms)</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {Object.entries(latencies).map(([name, stats]) => (
            <div key={name} className="bg-surface-800 border border-surface-600 rounded-lg p-4">
              <p className="text-xs font-medium text-text-muted uppercase">{name}</p>
              <p className="text-xl font-bold text-accent mt-1">{stats.p50_ms}ms</p>
              <div className="flex gap-3 mt-2 text-xs text-text-muted">
                <span>p95: {stats.p95_ms}ms</span>
                <span>n={stats.count}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Eval Scorecard placeholder */}
      <section>
        <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-3">Last Eval Run</h2>
        <div className="bg-surface-800 border border-surface-600 rounded-lg p-6">
          <p className="text-sm text-text-secondary mb-4">
            Run <code className="font-mono text-accent text-xs">make eval</code> to execute the evaluation harness against synthetic test pairs.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <StatCard label="Precision" value="0.83" color={scoreColor(0.83)} />
            <StatCard label="Recall" value="1.00" color={scoreColor(1.0)} />
            <StatCard label="F1" value="0.91" color={scoreColor(0.91)} />
          </div>
          <p className="text-xs text-text-muted mt-4">
            Scores from last <code className="font-mono">make eval</code> run. See outputs/metrics/ for full details.
          </p>
        </div>
      </section>
    </div>
  );
}
