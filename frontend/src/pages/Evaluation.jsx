import { useState, useEffect } from 'react';
import StatCard from '../components/StatCard';
import EmptyState from '../components/EmptyState';
import { getMetrics } from '../lib/api';

function scoreColor(val) {
  if (val >= 0.85) return 'success';
  if (val >= 0.7) return 'warning';
  return 'danger';
}

export default function Evaluation() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true); setError(null);
    try { setMetrics(await getMetrics()); } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, []);

  if (loading) return <div className="flex items-center justify-center py-16"><div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="max-w-7xl mx-auto px-4 py-8"><EmptyState error title="Failed to load" description={error} action={<button onClick={fetchData} className="px-4 py-2 rounded bg-cyan-600 text-white text-sm">Retry</button>} /></div>;

  const c = metrics?.counters || {};
  const l = metrics?.latencies || {};

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Evaluation & Metrics</h1>
        <button onClick={fetchData} className="px-4 py-2 rounded-lg bg-gray-100 dark:bg-surface-700 text-gray-700 dark:text-gray-300 text-sm hover:bg-gray-200 dark:hover:bg-surface-600 transition-colors">Refresh</button>
      </div>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Pipeline Counters</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          <StatCard label="Ingestions" value={c.ingestion_count||0} color="accent" />
          <StatCard label="Comparisons" value={c.delta_count||0} color="accent" />
          <StatCard label="Added" value={c.delta_added||0} color="success" />
          <StatCard label="Removed" value={c.delta_removed||0} color="danger" />
          <StatCard label="Modified" value={c.delta_modified||0} color="warning" />
          <StatCard label="LLM Tokens" value={c.llm_input_tokens||0} sub={`out: ${c.llm_output_tokens||0}`} color="accent" />
        </div>
      </section>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Latency (ms)</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {Object.entries(l).map(([name, s]) => (
            <div key={name} className="bg-white dark:bg-surface-800 border border-gray-200 dark:border-surface-600 rounded-lg p-4">
              <p className="text-xs font-medium text-gray-500 uppercase">{name}</p>
              <p className="text-xl font-bold text-cyan-700 dark:text-cyan-400 mt-1">{s.p50_ms}ms</p>
              <div className="flex gap-3 mt-2 text-xs text-gray-500"><span>p95: {s.p95_ms}ms</span><span>n={s.count}</span></div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Last Eval Run</h2>
        <div className="bg-white dark:bg-surface-800 border border-gray-200 dark:border-surface-600 rounded-lg p-6">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">Run <code className="font-mono text-cyan-700 dark:text-cyan-400 text-xs">make eval</code> to execute the full evaluation harness.</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <StatCard label="Precision" value="0.60" color={scoreColor(0.60)} />
            <StatCard label="Recall" value="1.00" color={scoreColor(1.0)} />
            <StatCard label="F1" value="0.75" color={scoreColor(0.75)} />
          </div>
        </div>
      </section>
    </div>
  );
}
