/**
 * LoadingStages — shows pipeline progress with named stages.
 */
export default function LoadingStages({ stages, currentIndex }) {
  return (
    <div className="flex flex-col gap-2 py-4">
      {stages.map((stage, i) => (
        <div key={stage} className="flex items-center gap-3">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
            i < currentIndex
              ? 'bg-success text-white'
              : i === currentIndex
                ? 'bg-accent text-white animate-pulse'
                : 'bg-surface-700 text-text-muted'
          }`}>
            {i < currentIndex ? '✓' : i + 1}
          </div>
          <span className={`text-sm ${
            i <= currentIndex ? 'text-text-primary' : 'text-text-muted'
          }`}>
            {stage}
          </span>
          {i === currentIndex && (
            <div className="ml-auto">
              <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
