/**
 * StatCard — displays a single metric with label, value, and optional color coding.
 */
export default function StatCard({ label, value, sub, color = 'accent' }) {
  const colorMap = {
    accent: 'border-accent/30 text-accent',
    success: 'border-success/30 text-success',
    warning: 'border-warning/30 text-warning',
    danger: 'border-danger/30 text-danger',
  };

  return (
    <div className={`bg-surface-800 border ${colorMap[color]?.split(' ')[0] || 'border-surface-600'} rounded-lg p-4`}>
      <p className="text-xs font-medium text-text-muted uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${colorMap[color]?.split(' ')[1] || 'text-text-primary'}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-text-muted mt-1">{sub}</p>}
    </div>
  );
}
