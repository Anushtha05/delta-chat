import Badge from './Badge';

export default function ChatBubble({ role, content, citations, tokens, cost }) {
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className="max-w-[85%] sm:max-w-[70%]">
        <div className={`rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-cyan-600 text-white rounded-br-sm'
            : 'bg-gray-100 dark:bg-surface-700 text-gray-900 dark:text-white rounded-bl-sm'
        }`}>
          <p className="text-sm whitespace-pre-wrap">{content}</p>
        </div>

        {!isUser && citations && citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="text-xs text-gray-500 mr-1">Sources:</span>
            {citations.map((cit, i) => (
              <Badge key={i} variant="accent">{cit}</Badge>
            ))}
          </div>
        )}

        {!isUser && tokens != null && (
          <p className="text-xs text-gray-400 mt-1.5">
            {tokens} tokens · ~${cost?.toFixed(4) || '0.0000'}
          </p>
        )}
      </div>
    </div>
  );
}
