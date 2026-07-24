import { Link } from 'react-router-dom';

function StepIcon({ step, label }) {
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <div className="w-12 h-12 rounded-full bg-accent-muted border border-accent/30 flex items-center justify-center text-accent font-bold text-lg">
        {step}
      </div>
      <span className="text-sm font-medium text-text-primary">{label}</span>
    </div>
  );
}

function Arrow() {
  return (
    <svg className="w-8 h-4 text-text-muted hidden sm:block" fill="none" viewBox="0 0 32 16">
      <path d="M0 8h28M22 2l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function FeatureCard({ icon, title, description }) {
  return (
    <div className="bg-surface-800 border border-surface-600 rounded-lg p-6 hover:border-accent/40 transition-colors">
      <div className="w-10 h-10 rounded-lg bg-accent-muted flex items-center justify-center text-accent mb-4">
        {icon}
      </div>
      <h3 className="text-base font-semibold text-text-primary mb-2">{title}</h3>
      <p className="text-sm text-text-secondary leading-relaxed">{description}</p>
    </div>
  );
}

export default function Landing() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Hero */}
      <section className="py-20 sm:py-28 text-center">
        <h1 className="text-4xl sm:text-5xl font-bold text-text-primary leading-tight">
          Engineering Document
          <span className="text-accent"> Delta Intelligence</span>
        </h1>
        <p className="mt-6 text-lg text-text-secondary max-w-2xl mx-auto leading-relaxed">
          Compare engineering document revisions, see exactly what changed, and ask questions grounded in the evidence.
        </p>
        <div className="mt-8">
          <Link
            to="/compare"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-accent text-white font-semibold text-sm hover:bg-accent-dark transition-colors shadow-lg shadow-accent/20"
          >
            Start Comparing
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
        </div>
      </section>

      {/* Pipeline Visualization */}
      <section className="py-12 border-t border-surface-700">
        <h2 className="text-center text-sm font-semibold text-text-muted uppercase tracking-wider mb-8">
          How It Works
        </h2>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-6">
          <StepIcon step="1" label="Ingest" />
          <Arrow />
          <StepIcon step="2" label="Delta Engine" />
          <Arrow />
          <StepIcon step="3" label="Report" />
          <Arrow />
          <StepIcon step="4" label="Grounded Chat" />
        </div>
      </section>

      {/* Feature Cards */}
      <section className="py-16 border-t border-surface-700">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <FeatureCard
            icon={<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>}
            title="Deterministic Delta Engine"
            description="Element-level comparison with fuzzy matching. Every detected change is traceable to exact coordinates in the source document."
          />
          <FeatureCard
            icon={<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>}
            title="Grounded Citations"
            description="Every AI answer cites specific chunks from your documents. No hallucination — if the evidence isn't there, the system says so."
          />
          <FeatureCard
            icon={<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>}
            title="Full Observability & Eval"
            description="Per-request tracing, structured logs, latency metrics, and a built-in precision/recall evaluation harness against ground-truth datasets."
          />
        </div>
      </section>
    </div>
  );
}
