import Badge from './Badge';

/**
 * ChatBubble — message bubble for user or assistant.
 */
export default function ChatBubble({ role, content, citations, tokens, cost }) {
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[85%] sm:max-w-[70%] ${isUser ? 'order-1' : 'order-1'}`}>
        <div className={`rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-accent-muted text-text-primary rounded-br-sm'
            : 'bg-surface-700 text-text-primary rounded-bl-sm'
        }`}>
          <p className="text-sm whitespace-pre-wrap">{content}</p>
        </div>

        {!isUser && citations && citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="text-xs text-text-muted mr-1">Sources:</span>
            {citations.map((cit, i) => (
              <Badge key={i} variant="accent">{cit}</Badge>
            ))}
          </div>
        )}

        {!isUser && tokens != null && (
          <p className="text-xs text-text-muted mt-1.5">
            {tokens} tokens · ~${cost?.toFixed(4) || '0.0000'}
          </p>
        )}
      </div>
    </div>
  );
}
