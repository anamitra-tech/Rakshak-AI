// src/Dashboard/CommandWorkSpace/Network.jsx
import { useEffect, useState } from 'react';
import { Network as NetIcon, Users, GitCommit, AlertTriangle, Radio, Loader2, ServerCrash } from 'lucide-react';

const Network = () => {
  const [graph, setGraph] = useState(null);
  const [clusters, setClusters] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [graphRes, clustersRes] = await Promise.all([
          fetch('/api/network/graph'),
          fetch('/api/network/clusters'),
        ]);
        if (!graphRes.ok) throw new Error(`Graph request failed (${graphRes.status})`);
        if (!clustersRes.ok) throw new Error(`Clusters request failed (${clustersRes.status})`);
        setGraph(await graphRes.json());
        setClusters(await clustersRes.json());
      } catch (e) {
        setError(e.message || 'Something went wrong. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="h-[60vh] flex flex-col items-center justify-center space-y-3">
        <Loader2 className="h-7 w-7 text-cyan-400 animate-spin" />
        <div className="text-xs font-mono text-cyan-400/70 uppercase tracking-widest">Querying Network Topology Map...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 border border-red-500/20 bg-red-500/10 text-red-400 rounded-xl text-xs font-mono flex items-center gap-3 max-w-2xl animate-in fade-in zoom-in-95 duration-200">
        <ServerCrash className="h-5 w-5 text-red-400 shrink-0" />
        <div>
          <span className="font-bold block">[TOPOLOGY_STREAM_ERROR]</span>
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl space-y-6">
      {/* Module Header */}
      <div className="flex items-center justify-between border-b border-cyan-500/10 pb-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/10 border border-cyan-500/30 flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.15)]">
            <NetIcon className="h-5 w-5 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-cyan-100 tracking-wide uppercase">Fraud Network Intelligence</h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Graph link-analysis mapping call relays, regional syndicates, and interconnected phone nodes.
            </p>
          </div>
        </div>

        {/* Telemetry Counter Strip */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#052229]/40 border border-cyan-500/10 font-mono text-[11px]">
            <Users className="h-3.5 w-3.5 text-cyan-400" />
            <span className="text-slate-400">NODES:</span>
            <span className="text-cyan-300 font-bold">{graph?.nodes?.length ?? 0}</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#052229]/40 border border-cyan-500/10 font-mono text-[11px]">
            <GitCommit className="h-3.5 w-3.5 text-amber-400" />
            <span className="text-slate-400">EDGES:</span>
            <span className="text-amber-300 font-bold">{graph?.edges?.length ?? 0}</span>
          </div>
        </div>
      </div>

      {/* Main Structural Matrix Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left Column: Inspected Entities / Nodes List */}
        <div className="lg:col-span-7 space-y-3">
          <div className="flex items-center gap-1.5 px-1 text-xs font-mono uppercase tracking-wider text-slate-400">
            <Radio className="h-3 w-3 text-cyan-400" /> Target Node Register
          </div>
          
          <div className="border border-cyan-500/10 rounded-2xl bg-[#052229]/30 backdrop-blur-md overflow-hidden max-h-[70vh] overflow-y-auto shadow-xl shadow-black/20 divide-y divide-cyan-500/5">
            {graph?.nodes?.map((node) => {
              const risk = Math.round(node.risk_score * 100);
              return (
                <div key={node.id} className="flex items-center justify-between px-4 py-3.5 hover:bg-cyan-500/[0.02] transition-colors duration-150">
                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-semibold tracking-wide text-slate-200">{node.phone_number}</span>
                      <span className="text-[10px] font-mono font-bold bg-cyan-950/60 text-cyan-400 border border-cyan-500/20 px-2 py-0.5 rounded uppercase tracking-wide">
                        {node.category}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono tracking-tight uppercase">
                      LOC_CORE: {node.region || 'UNKNOWN_MNC'}
                    </div>
                  </div>
                  
                  {/* Dynamic Risk Tag Badge */}
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-mono font-bold px-2.5 py-1 border rounded-md ${
                      risk >= 67 
                        ? 'bg-red-500/10 border-red-500/20 text-red-400' 
                        : risk >= 34 
                        ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' 
                        : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                    }`}>
                      {risk}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: High-Risk Syndicates / Cluster Panel */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center gap-1.5 px-1 text-xs font-mono uppercase tracking-wider text-slate-400">
            <AlertTriangle className="h-3 w-3 text-amber-400" /> Fraud Cluster Summaries
          </div>

          <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
            {clusters?.clusters?.map((cluster) => {
              const cRisk = Math.round(cluster.risk_score * 100);
              return (
                <div 
                  key={cluster.id} 
                  className={`p-4 border rounded-2xl bg-gradient-to-b from-[#052229]/60 to-[#03151A]/80 backdrop-blur-md shadow-lg transition-all duration-200 hover:border-cyan-500/20 ${
                    cRisk >= 67 ? 'border-red-500/15' : 'border-cyan-500/10'
                  }`}
                >
                  <div className="flex items-center justify-between mb-3 border-b border-white/[0.03] pb-2">
                    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 border rounded-md ${
                      cRisk >= 67 
                        ? 'bg-red-500/10 border-red-500/20 text-red-400 animate-pulse' 
                        : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                    }`}>
                      MATRIX_RISK: {cRisk}%
                    </span>
                    <span className="text-[11px] font-mono text-slate-500 uppercase tracking-widest">
                      {cluster.node_ids?.length ?? 0} Linked Nodes
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 font-sans leading-relaxed">
                    {cluster.summary}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

      </div>
    </div>
  );
};

export default Network;