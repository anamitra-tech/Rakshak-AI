// src/Dashboard/CommandWorkSpace/geospatial/TrendChart.jsx
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-cyan-400/30 bg-[#092930]/95 backdrop-blur-md px-3.5 py-2 text-xs font-mono text-slate-200 shadow-2xl space-y-1">
      <div className="text-slate-400 text-[10px] uppercase tracking-wider">{label}</div>
      <div className="font-bold text-sm text-cyan-300 flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
        {payload[0].value} <span className="text-[10px] font-normal text-slate-400">complaints</span>
      </div>
    </div>
  );
};

const TrendChart = ({ trend, loading }) => {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[230px] rounded-2xl border border-cyan-400/20 bg-[#062025]/40 text-xs font-mono text-cyan-400/60 tracking-widest uppercase animate-pulse">
        Initializing Trend Engine...
      </div>
    );
  }
  if (!trend?.series?.length) {
    return (
      <div className="flex items-center justify-center h-[230px] rounded-2xl border border-cyan-400/20 bg-[#062025]/40 text-xs font-mono text-slate-500 tracking-wide uppercase">
        No Trend Vector Data Found
      </div>
    );
  }

  const data = trend.series.map((p) => ({
    date: p.date.slice(5), // MM-DD
    count: p.count,
  }));

  return (
    <div className="rounded-2xl border border-cyan-400/30 bg-[#062025]/80 p-5 shadow-[0_0_20px_rgba(34,211,238,0.05)] transition-all duration-300 hover:border-cyan-400/40">
      <div className="flex items-center justify-between mb-5">
        <div className="text-xs font-bold font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
          Scam Volume Timeline
        </div>
        {trend.trending_scam_type && (
          <div className="text-[10px] font-mono font-bold uppercase tracking-wider px-3 py-1 rounded-full bg-red-500/15 text-red-400 border border-red-400/40 shadow-[0_0_10px_rgba(239,68,68,0.1)]">
            CRITICAL VECTOR: {trend.trending_scam_type}
          </div>
        )}
      </div>

      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={data} margin={{ top: 8, right: 10, left: -24, bottom: 0 }}>
          <defs>
            <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
              {/* Higher alpha fill-opacity to pop brilliantly against the background */}
              <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          
          {/* Crisper, slightly lighter horizontal reference gridlines */}
          <CartesianGrid strokeDasharray="4 4" stroke="rgba(34,211,238,0.15)" vertical={false} />
          
          <XAxis
            dataKey="date"
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
            axisLine={{ stroke: 'rgba(34,211,238,0.3)' }}
            tickLine={false}
            dy={8}
            interval="preserveStartEnd"
          />
          
          <YAxis
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
            axisLine={false}
            tickLine={false}
            width={32}
            allowDecimals={false}
          />
          
          <Tooltip 
            content={<CustomTooltip />} 
            cursor={{ stroke: 'rgba(34,211,238,0.3)', strokeWidth: 1.5, strokeDasharray: '3 3' }}
          />
          
          <Area
            type="monotone"
            dataKey="count"
            stroke="#22d3ee"
            strokeWidth={2.5} // Thicker line vector for direct clarity
            fill="url(#trendFill)"
            activeDot={{ r: 5, fill: '#fff', stroke: '#22d3ee', strokeWidth: 2, className: "shadow-lg" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TrendChart;