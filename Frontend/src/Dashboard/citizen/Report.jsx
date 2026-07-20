import { useState } from 'react';

const Report = () => {
  const [scamType, setScamType] = useState('');
  const [description, setDescription] = useState('');
  const [contactInfo, setContactInfo] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    if (!scamType.trim() || !description.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await fetch('/api/citizen/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scam_type: scamType,
          description,
          contact_info: contactInfo || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.message || `Request failed (${res.status})`);
      }
      const data = await res.json();
      setResult(data);
      setScamType('');
      setDescription('');
      setContactInfo('');
    } catch (e) {
      setError(e.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold mb-6">Report a Scam</h1>

      <div className="space-y-4">
        <input
          value={scamType}
          onChange={(e) => setScamType(e.target.value)}
          placeholder="Scam type (e.g. UPI Scam, Digital Arrest, Phishing)"
          className="w-full p-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-400"
        />
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe what happened..."
          className="w-full h-32 p-4 border border-slate-300 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-cyan-400"
        />
        <input
          value={contactInfo}
          onChange={(e) => setContactInfo(e.target.value)}
          placeholder="Scammer's phone/UPI/account (optional)"
          className="w-full p-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-400"
        />
      </div>

      <button
        onClick={handleSubmit}
        disabled={loading}
        className="mt-4 px-6 py-3 bg-cyan-500 text-white rounded-xl font-medium disabled:opacity-50"
      >
        {loading ? 'Submitting...' : 'Submit Report'}
      </button>

      {error && (
        <div className="mt-4 p-4 border border-red-200 bg-red-50 text-red-600 rounded-xl text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 p-4 border border-emerald-200 bg-emerald-50 text-emerald-700 rounded-xl text-sm">
          <div className="font-medium mb-1">Report {result.report_id} — {result.status}</div>
          <div>{result.message}</div>
        </div>
      )}
    </div>
  );
};

export default Report;
