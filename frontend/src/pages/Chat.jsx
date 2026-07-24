import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import ChatBubble from '../components/ChatBubble';
import EmptyState from '../components/EmptyState';
import { sendChatMessage } from '../lib/api';

const EXAMPLE_QUESTIONS = [
  'What changed between the two documents?',
  'Did the discharge pressure change?',
  'Were any instruments added or removed?',
];

export default function Chat() {
  const [searchParams] = useSearchParams();
  const [docA, setDocA] = useState(searchParams.get('a') || '');
  const [docB, setDocB] = useState(searchParams.get('b') || '');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (question) => {
    const q = question || input.trim();
    if (!q || !docA || !docB) return;

    setInput('');
    setError(null);
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setLoading(true);

    try {
      const res = await sendChatMessage(q, docA, docB);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.answer,
        citations: res.citations || [],
        tokens: (res.input_tokens || 0) + (res.output_tokens || 0),
        cost: ((res.input_tokens || 0) / 1000 * 0.00015) + ((res.output_tokens || 0) / 1000 * 0.0006),
      }]);
    } catch (e) {
      setError(e.message);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${e.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const pairSelected = docA && docB;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col h-[calc(100vh-8rem)]">
      <h1 className="text-2xl font-bold text-text-primary mb-4">Grounded Chat</h1>

      {/* Document Pair Selector */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4 p-3 bg-surface-800 border border-surface-600 rounded-lg">
        <div className="flex-1">
          <label className="text-xs text-text-muted block mb-1">Document A</label>
          <input
            type="text"
            value={docA}
            onChange={(e) => setDocA(e.target.value)}
            placeholder="e.g. PID-EGC-001"
            className="w-full bg-surface-700 border border-surface-600 rounded px-3 py-1.5 text-sm text-text-primary placeholder-text-muted focus:border-accent focus:outline-none"
          />
        </div>
        <div className="flex-1">
          <label className="text-xs text-text-muted block mb-1">Document B</label>
          <input
            type="text"
            value={docB}
            onChange={(e) => setDocB(e.target.value)}
            placeholder="e.g. PID-LGC-001"
            className="w-full bg-surface-700 border border-surface-600 rounded px-3 py-1.5 text-sm text-text-primary placeholder-text-muted focus:border-accent focus:outline-none"
          />
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto min-h-0 mb-4 px-1">
        {!pairSelected && (
          <EmptyState
            title="Select a document pair"
            description="Enter the document IDs for the two P&IDs you want to ask questions about."
            icon={<svg className="w-6 h-6 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>}
          />
        )}

        {pairSelected && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full">
            <p className="text-sm text-text-muted mb-4">Ask a question about these documents:</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {EXAMPLE_QUESTIONS.map(q => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  className="px-3 py-2 rounded-lg bg-surface-700 border border-surface-600 text-sm text-text-secondary hover:border-accent hover:text-accent transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatBubble
            key={i}
            role={msg.role}
            content={msg.content}
            citations={msg.citations}
            tokens={msg.tokens}
            cost={msg.cost}
          />
        ))}

        {loading && (
          <div className="flex justify-start mb-4">
            <div className="bg-surface-700 rounded-lg px-4 py-3 rounded-bl-sm">
              <div className="flex gap-1.5">
                <div className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!pairSelected || loading}
          placeholder={pairSelected ? 'Ask about these documents...' : 'Select documents first'}
          className="flex-1 bg-surface-800 border border-surface-600 rounded-lg px-4 py-2.5 text-sm text-text-primary placeholder-text-muted focus:border-accent focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={() => handleSend()}
          disabled={!input.trim() || !pairSelected || loading}
          className="px-4 py-2.5 rounded-lg bg-accent text-white font-medium text-sm hover:bg-accent-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  );
}
