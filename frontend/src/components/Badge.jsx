/**
 * Badge — small colored label for types, statuses, etc.
 */
export default function Badge({ children, variant = 'default' }) {
  const variants = {
    default: 'bg-surface-600 text-text-secondary',
    added: 'bg-success/20 text-success',
    removed: 'bg-danger/20 text-danger',
    modified: 'bg-warning/20 text-warning',
    accent: 'bg-accent-muted text-accent-light',
    muted: 'bg-surface-700 text-text-muted',
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${variants[variant] || variants.default}`}>
      {children}
    </span>
  );
}
