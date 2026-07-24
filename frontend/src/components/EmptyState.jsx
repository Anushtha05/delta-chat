export default function EmptyState({ icon, title, description, action, error = false }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {icon && (
        <div className={`w-12 h-12 rounded-full flex items-center justify-center mb-4 ${error ? 'bg-red-50 dark:bg-red-900/20' : 'bg-gray-100 dark:bg-surface-700'}`}>
          {icon}
        </div>
      )}
      <h3 className={`text-lg font-medium ${error ? 'text-red-700 dark:text-red-400' : 'text-gray-900 dark:text-white'}`}>
        {title}
      </h3>
      {description && (
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 max-w-md">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
