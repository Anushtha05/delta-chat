import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import ChatBubble from '../components/ChatBubble';
import EmptyState from '../components/EmptyState';
import { sendChatMessage } from '../lib/api';

const EXAMPLES = ['What changed between the two documents?', 'Did the discharge pressure change?', 'Were any instruments added or removed?'];

export default function Chat() {
  const [searchParams] = useSearchParams();
  const [docA, setDocA] = useState(searchParams.get('a') || '');
  const [docB, setDocB] = useState(searchParams.get('b') || '');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async (q) => {
    const question = q || input.trim();
    if (!question || !docA || !docB) return;
    setInput(''); setMessages(p => [...p, { role: 'user', content: question }]); setLoading(true);
    try {
      const res = await sendChatMessage(question, docA, docB);
      setMessages(p => [...p, { role: 'assistant', content: res.answer, citations: res.citations || [], tokens: (res.input_tokens||0)+(res.output_tokens||0), cost: ((res.input_tokens||0)/1000*0.00015)+((res.output_tokens||0)/1000*0.0006) }]);
    } catch (e) {
      setMessages(p => [...p, { role: 'assistant', content: `Error: ${e.message}` }]);
    } finally { setLoading(false); }
  };

  const pairSelected = docA && docB;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col h-[calc(100vh-8rem)]">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Grounded Chat</h1>

      <div className="flex flex-col sm:flex-row gap-3 mb-4 p-3 bg-white dark:bg-surface-800 border border-gray-200 dark:border-surface-600 rounded-lg">
        <div className="flex-1">
          <label className="text-xs text-gray-500 block mb-1">Document A</label>
          <input type="text" value={docA} onChange={e => setDocA(e.target.value)} placeholder="e.g. PID-EGC-001"
            className="w-full bg-gray-50 dark:bg-surface-700 border border-gray-300 dark:border-surface-600 rounded px-3 py-1.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:border-cyan-500 focus:outline-none" />
        </div>
        <div className="flex-1">
          <label className="text-xs text-gray-500 block mb-1">Document B</label>
          <input type="text" value={docB} onChange={e => setDocB(e.target.value)} placeholder="e.g. PID-LGC-001"
            className="w-full bg-gray-50 dark:bg-surface-700 border border-gray-300 dark:border-surface-600 rounded px-3 py-1.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:border-cyan-500 focus:outline-none" />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 mb-4 px-1">
        {!pairSelected && <EmptyState title="Select a document pair" description="Enter document IDs to start asking questions." />}
        {pairSelected && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full">
            <p className="text-sm text-gray-500 mb-4">Try one of these questions:</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {EXAMPLES.map(q => (
                <button key={q} onClick={() => send(q)} className="px-3 py-2 rounded-lg bg-gray-100 dark:bg-surface-700 border border-gray-200 dark:border-surface-600 text-sm text-gray-700 dark:text-gray-300 hover:border-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-400 transition-colors">{q}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => <ChatBubble key={i} role={m.role} content={m.content} citations={m.citations} tokens={m.tokens} cost={m.cost} />)}
        {loading && (
          <div className="flex justify-start mb-4"><div className="bg-gray-100 dark:bg-surface-700 rounded-lg px-4 py-3"><div className="flex gap-1.5">
            <div className="w-2 h-2 rounded-full bg-cyan-500 animate-bounce" /><div className="w-2 h-2 rounded-full bg-cyan-500 animate-bounce" style={{animationDelay:'150ms'}} /><div className="w-2 h-2 rounded-full bg-cyan-500 animate-bounce" style={{animationDelay:'300ms'}} />
          </div></div></div>
        )}
        <div ref={endRef} />
      </div>

      <div className="flex gap-2">
        <input type="text" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send(); }}} disabled={!pairSelected || loading} placeholder={pairSelected ? 'Ask about these documents...' : 'Select documents first'}
          className="flex-1 bg-white dark:bg-surface-800 border border-gray-300 dark:border-surface-600 rounded-lg px-4 py-2.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:border-cyan-500 focus:outline-none disabled:opacity-50" />
        <button onClick={() => send()} disabled={!input.trim() || !pairSelected || loading}
          className="px-4 py-2.5 rounded-lg bg-cyan-600 text-white font-medium text-sm hover:bg-cyan-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">Send</button>
      </div>
    </div>
  );
}
