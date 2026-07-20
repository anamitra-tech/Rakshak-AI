// src/Dashboard/CommandWorkSpace/DigitalArrest.jsx
import { useState } from 'react';
import { ShieldAlert, Loader2, Sparkles, Terminal, Activity, EyeOff, Radio } from 'lucide-react';
import { categoryLabel, VERDICT_STYLES } from '../fraudCategories';

const DigitalArrest = () => {
  const [transcript, setTranscript] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleAnalyze = async () => {
    if (!transcript.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: transcript,
          source_type: 'call_transcript',
          mode: 'online',
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.message || `Request failed (${res.status})`);
      }
      setResult(await res.json());
    } catch (e) {
      setError(e.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const riskPercent = result ? Math.round(result.risk_score * 100) : 0;
  
  const risk =
    riskPercent >= 67
      ? { color: 'text-red-400', ring: 'stroke-red-500', bg: 'bg-red-500/10 border-red-500/20', label: 'CRITICAL RISK / SCAM DETECTED' }
      : riskPercent >= 34
      ? { color: 'text-amber-400', ring: 'stroke-amber-500', bg: 'bg-amber-500/10 border-amber-500/20', label: 'MODERATE SUSPICION' }
      : { color: 'text-emerald-400', ring: 'stroke-emerald-500', bg: 'bg-emerald-500/10 border-emerald-500/20', label: 'LOW RISK / SECURE' };

  return (
    <div className="max-w-4xl space-y-6">
      {/* Module Header */}
      <div className="flex items-center justify-between border-b border-cyan-500/10 pb-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/10 border border-cyan-500/30 flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.15)]">
            <ShieldAlert className="h-5 w-5 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-cyan-100 tracking-wide uppercase">Digital Arrest Interceptor</h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Analyze on-device STT / OCR data for simulated authority tactics and localized extortion footprints.
            </p>
          </div>
        </div>
        
        {/* Decorative Status Bar */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#052229]/50 border border-cyan-500/10 text-[10px] text-cyan-400/80 font-mono">
          <Radio className="h-3 w-3 animate-pulse text-cyan-400" />
          STT_ENGINE // ON_LINE
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Input Workdesk */}
        <div className="lg:col-span-7 space-y-4">
          <div className="relative rounded-2xl border border-cyan-500/10 bg-[#052229]/40 backdrop-blur-md p-4 group focus-within:border-cyan-500/30 transition-all duration-300">
            <div className="flex items-center justify-between mb-2 text-xs text-slate-500 font-mono">
              <span className="flex items-center gap-1.5"><Terminal className="h-3 w-3" /> INPUT_TRANSCRIPT_RAW</span>
              <span>CHAR_COUNT: {transcript.length}</span>
            </div>
            
            <textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="Paste processed text block or call transcript logs here to evaluate scam vectoring..."
              className="w-full h-52 bg-black/20 text-slate-200 text-sm p-3 rounded-xl border border-white/[0.03] resize-none focus:outline-none focus:border-cyan-500/30 focus:ring-1 focus:ring-cyan-500/20 transition-all placeholder:text-slate-600 font-mono leading-relaxed"
            />

            <div className="mt-4 flex items-center justify-between">
              <button
                onClick={() => setTranscript('')}
                disabled={!transcript || loading}
                className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors rounded-md hover:bg-white/5 font-mono"
              >
                Clear Buffer
              </button>
              
              <button
                onClick={handleAnalyze}
                disabled={loading || !transcript.trim()}
                className="px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:from-slate-800 disabled:to-slate-800 text-white rounded-xl font-semibold shadow-[0_4px_20px_rgba(6,182,212,0.15)] hover:shadow-[0_4px_25px_rgba(6,182,212,0.3)] transition-all transform active:scale-98 disabled:opacity-40 disabled:pointer-events-none flex items-center gap-2 text-sm tracking-wide"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-cyan-200" />
                    <span className="font-mono text-xs uppercase tracking-widest animate-pulse">Processing Vector...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4 text-amber-300" />
                    Run Real-Time Audit
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Audit Results Panel */}
        <div className="lg:col-span-5">
          {error && (
            <div className="p-4 border border-red-500/20 bg-red-500/10 text-red-400 rounded-xl text-xs font-mono flex items-center gap-2 animate-in fade-in zoom-in-95 duration-200">
              <div className="h-1.5 w-1.5 rounded-full bg-red-500 animate-ping" />
              [ERROR]: {error}
            </div>
          )}

          {!result && !loading && !error && (
            <div className="h-72 border border-dashed border-cyan-500/10 rounded-2xl flex flex-col items-center justify-center text-center p-6 bg-cyan-950/[0.03]">
              <EyeOff className="h-8 w-8 text-slate-600 mb-2 stroke-1" />
              <div className="text-xs font-mono text-slate-500 uppercase tracking-wider">Awaiting Telemetry Data</div>
              <p className="text-[11px] text-slate-600 max-w-xs mt-1">
                Feed transcript parameters into the input console to spin up the tactical classifier threat breakdown.
              </p>
            </div>
          )}

          {loading && (
            <div className="h-72 border border-cyan-500/10 rounded-2xl flex flex-col items-center justify-center p-6 bg-[#041a1f]/30 backdrop-blur-sm animate-pulse">
              <Activity className="h-6 w-6 text-cyan-400/60 animate-bounce" />
              <div className="text-xs font-mono text-cyan-400/60 uppercase tracking-widest mt-3">Evaluating linguistic clusters...</div>
            </div>
          )}

          {result && !loading && (
            <div className="border border-cyan-500/15 rounded-2xl bg-gradient-to-b from-[#052229]/80 to-[#03151A]/90 backdrop-blur-md p-5 shadow-xl shadow-black/40 animate-in fade-in slide-in-from-bottom-2 duration-300 space-y-5">
              
              {/* Telemetry Indicator Metric */}
              <div className="flex items-center gap-4 bg-black/20 p-3.5 rounded-xl border border-white/[0.02]">
                <div className="relative h-16 w-16 shrink-0">
                  <svg viewBox="0 0 80 80" className="h-16 w-16 -rotate-90">
                    <circle cx="40" cy="40" r="35" fill="none" stroke="rgba(6,182,212,0.05)" strokeWidth="6" />
                    <circle
                      cx="40"
                      cy="40"
                      r="35"
                      fill="none"
                      strokeWidth="6"
                      strokeLinecap="round"
                      className={`transition-all duration-1000 ease-out ${risk.ring}`}
                      strokeDasharray={`${(riskPercent / 100) * 219.9} 219.9`}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className={`text-base font-mono font-bold ${risk.color}`}>{riskPercent}%</span>
                  </div>
                </div>
                <div className="min-w-0">
                  <span className="text-[10px] font-mono text-slate-500 block uppercase tracking-wider">THREAD ASSESSMENT MATRIX</span>
                  <div className={`mt-1 inline-flex items-center gap-1.5 px-2.5 py-0.5 border text-[10px] font-bold font-mono rounded-md ${risk.bg} ${risk.color}`}>
                    <span className="h-1 w-1 rounded-full bg-current animate-pulse" />
                    {risk.label}
                  </div>
                </div>
              </div>

              {/* Status Classification Labels */}
              <div className="space-y-2">
                <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Classification Verdict</div>
                <div className="flex flex-wrap gap-1.5">
                  <span className="px-2.5 py-1 text-xs font-mono font-bold rounded-md bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 shadow-sm uppercase">
                    {result.verdict}
                  </span>
                  {result.categories.map((c) => (
                    <span
                      key={c}
                      className="px-2.5 py-1 text-xs font-mono rounded-md bg-slate-800/60 border border-slate-700/40 text-slate-300"
                    >
                      {categoryLabel(c)}
                    </span>
                  ))}
                </div>
              </div>

              {/* Analytical Breakdown Brief */}
              <div className="pt-4 border-t border-cyan-500/10 font-sans">
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                  <span className="h-1 w-1 bg-cyan-400 rounded-full" /> Threat Assessment Logs
                </h3>
                <div className="bg-black/30 p-3.5 rounded-xl border border-white/[0.01] text-xs text-slate-300 leading-relaxed max-h-40 overflow-y-auto whitespace-pre-wrap font-mono">
                  {result.reason}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DigitalArrest;