export default function StatCard({ label, value, sub, color = 'accent' }) {
  const borderColors = {
    accent: 'border-cyan-200 dark:border-cyan-800',
    success: 'border-emerald-200 dark:border-emerald-800',
    warning: 'border-amber-200 dark:border-amber-800',
    danger: 'border-red-200 dark:border-red-800',
  };
  const textColors = {
    accent: 'text-cyan-700 dark:text-cyan-400',
    success: 'text-emerald-700 dark:text-emerald-400',
    warning: 'text-amber-700 dark:text-amber-400',
    danger: 'text-red-700 dark:text-red-400',
  };

  return (
    <div className={`bg-white dark:bg-surface-800 border ${borderColors[color] || borderColors.accent} rounded-lg p-4`}>
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${textColors[color] || textColors.accent}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}
