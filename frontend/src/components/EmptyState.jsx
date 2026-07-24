/**
 * EmptyState — displays a message when there's no data or an error occurred.
 */
export default function EmptyState({ icon, title, description, action, error = false }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {icon && (
        <div className={`w-12 h-12 rounded-full flex items-center justify-center mb-4 ${error ? 'bg-danger/10' : 'bg-surface-700'}`}>
          {icon}
        </div>
      )}
      <h3 className={`text-lg font-medium ${error ? 'text-danger' : 'text-text-primary'}`}>
        {title}
      </h3>
      {description && (
        <p className="text-sm text-text-muted mt-2 max-w-md">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
