// src/Dashboard/citizen/Chat.jsx
import { useState, useRef, useEffect } from 'react';

const SESSION_KEY = 'prahari_chat_session_id';

const getOrCreateSessionId = () => {
  let id = sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
};

const formatScamType = (scamType) =>
  scamType
    ? scamType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : null;

const SUGGESTIONS = [
  'Someone called claiming to be CBI and asked me to pay money',
  'I got an SMS saying my KYC will expire, what should I do?',
  'What is a digital arrest scam?',
];

const Chat = () => {
  const sessionIdRef = useRef(getOrCreateSessionId());
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, loading]);

  const send = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: 'user', text: trimmed }]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionIdRef.current, message: trimmed }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.message || `Request failed (${res.status})`);
      }
      const data = await res.json();
      setMessages((prev) => [...prev, { role: 'assistant', ...data }]);
    } catch (e) {
      setError(e.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div className="max-w-3xl w-full mx-auto flex flex-col">
      <h1 className="text-2xl font-semibold mb-1">Ask Prahari</h1>
      <p className="text-sm text-slate-500 mb-6">
        Describe what happened, paste a suspicious message, or ask a question — Prahari will explain
        the risk in plain language.
      </p>

      <div
        ref={scrollRef}
        className="border border-slate-200 rounded-2xl bg-white shadow-sm h-[28rem] overflow-y-auto p-5 flex flex-col gap-4"
      >
        {messages.length === 0 && (
          <div className="m-auto text-center max-w-sm">
            <p className="text-sm text-slate-500 mb-4">
              Try asking about a call, message, or scam pattern you're unsure about.
            </p>
            <div className="flex flex-col gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="text-left text-xs px-3 py-2 rounded-xl border border-slate-200 bg-slate-50 text-slate-600 hover:bg-cyan-50 hover:border-cyan-300 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, idx) =>
          m.role === 'user' ? (
            <div key={idx} className="flex justify-end">
              <div className="max-w-[80%] bg-cyan-500 text-white text-sm px-4 py-2.5 rounded-2xl rounded-br-sm">
                {m.text}
              </div>
            </div>
          ) : (
            <div key={idx} className="flex justify-start">
              <div className="max-w-[85%] bg-slate-50 border border-slate-200 text-slate-800 text-sm px-4 py-3 rounded-2xl rounded-bl-sm whitespace-pre-wrap">
                {(m.scam_type || m.confidence != null) && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {m.scam_type && (
                      <span className="inline-block px-2.5 py-0.5 text-[11px] font-medium bg-red-50 text-red-600 rounded-full">
                        {formatScamType(m.scam_type)}
                      </span>
                    )}
                    {m.confidence != null && (
                      <span className="inline-block px-2.5 py-0.5 text-[11px] font-medium bg-slate-100 text-slate-600 rounded-full">
                        {Math.round(m.confidence * 100)}% confidence
                      </span>
                    )}
                  </div>
                )}
                {m.answer}
                {m.source_name && (
                  <div className="mt-2 pt-2 border-t border-slate-200 text-[11px] text-slate-400">
                    Source:{' '}
                    {m.source_url ? (
                      <a href={m.source_url} target="_blank" rel="noreferrer" className="text-cyan-600 hover:underline">
                        {m.source_name}
                      </a>
                    ) : (
                      m.source_name
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-50 border border-slate-200 text-slate-400 text-sm px-4 py-3 rounded-2xl rounded-bl-sm">
              Thinking...
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-3 p-3 border border-red-200 bg-red-50 text-red-600 rounded-xl text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-4 flex items-center gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message..."
          className="flex-1 p-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-400 text-sm"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-6 py-3 bg-cyan-500 text-white rounded-xl font-medium disabled:opacity-50 transition-transform active:scale-[0.98]"
        >
          Send
        </button>
      </form>
    </div>
  );
};

export default Chat;
