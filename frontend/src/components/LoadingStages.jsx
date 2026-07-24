export default function LoadingStages({ stages, currentIndex }) {
  return (
    <div className="flex flex-col gap-2 py-4">
      {stages.map((stage, i) => (
        <div key={stage} className="flex items-center gap-3">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
            i < currentIndex ? 'bg-emerald-500 text-white'
            : i === currentIndex ? 'bg-cyan-500 text-white animate-pulse'
            : 'bg-gray-200 dark:bg-surface-700 text-gray-500'
          }`}>
            {i < currentIndex ? '✓' : i + 1}
          </div>
          <span className={`text-sm ${i <= currentIndex ? 'text-gray-900 dark:text-white' : 'text-gray-400'}`}>{stage}</span>
          {i === currentIndex && <div className="ml-auto w-4 h-4 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />}
        </div>
      ))}
    </div>
  );
}
