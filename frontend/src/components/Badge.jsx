export default function Badge({ children, variant = 'default' }) {
  const variants = {
    default: 'bg-gray-100 text-gray-700 dark:bg-surface-600 dark:text-gray-300',
    added: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    removed: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    modified: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    accent: 'bg-cyan-50 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300',
    muted: 'bg-gray-100 text-gray-500 dark:bg-surface-700 dark:text-gray-400',
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${variants[variant] || variants.default}`}>
      {children}
    </span>
  );
}
