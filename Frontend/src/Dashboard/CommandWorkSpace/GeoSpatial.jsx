// src/Dashboard/CommandWorkSpace/GeoSpatial.jsx
import { useMemo, useState } from 'react';
import { AlertTriangle, FileWarning, MapPin, Crosshair, Layers, Map as MapIcon, RefreshCw } from 'lucide-react';
import MapView from './geospatial/MapView';
import FilterPanel, { isoDaysAgo } from './geospatial/FilterPanel';
import TrendChart from './geospatial/TrendChart';
import DistrictPanel from './geospatial/DistrictPanel';
import { useGeoData, useStaticGeoResources } from './geospatial/useGeoData';

const GeoSpatial = () => {
  const [filters, setFilters] = useState({
    scamTypes: [],
    startDate: isoDaysAgo(29),
    endDate: isoDaysAgo(0),
  });
  const [activePreset, setActivePreset] = useState(30);
  const [viewMode, setViewMode] = useState('heatmap'); // 'heatmap' | 'points'
  const [showChoropleth, setShowChoropleth] = useState(true);
  const [selectedDistrictName, setSelectedDistrictName] = useState(null);

  const { districtsRaw, scamTypes } = useStaticGeoResources();
  const { complaints, districtStats, trend, loading, error } = useGeoData(filters);

  const selectedDistrict = useMemo(() => {
    if (!selectedDistrictName) return null;
    return (
      districtStats.find((d) => d.district_id === selectedDistrictName) ?? {
        district_id: selectedDistrictName,
        risk_score: -1,
        complaint_count: 0,
        top_scam_type: null,
        trend: null,
        trend_delta_pct: 0,
      }
    );
  }, [selectedDistrictName, districtStats]);

  const highRiskCount = districtStats.filter((d) => d.risk_score >= 66).length;
  const topDistrict = [...districtStats].sort((a, b) => b.risk_score - a.risk_score)[0];

  return (
    <div className="h-full flex flex-col space-y-5">
      {/* Dynamic Module Header */}
      <div className="flex items-center justify-between border-b border-cyan-500/10 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-cyan-100 tracking-wide uppercase">Geospatial Crime Intelligence</h1>
            {loading ? (
              <span className="flex items-center gap-1.5 text-[10px] text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded-md font-mono">
                <RefreshCw className="h-2.5 w-2.5 animate-spin" />
                SYNCING_LIVESTREAM
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md font-mono">
                <span className="h-1 w-1 rounded-full bg-emerald-400 animate-pulse" />
                FEED_STABLE
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">Live localized hot-spots, clusters & operational telemetry metrics.</p>
        </div>
      </div>

      {error && (
        <div className="p-3 border border-red-500/20 bg-red-500/10 text-red-400 rounded-xl text-xs font-mono flex items-center gap-2 animate-in fade-in duration-200">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          [TELEMETRY_FAILURE]: {error}
        </div>
      )}

      {/* Cybernetic Grid Matrix Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatTile
          icon={FileWarning}
          label="Complaints (selection)"
          value={complaints.length}
          tone="cyan"
        />
        <StatTile
          icon={MapPin}
          label="Districts w/ activity"
          value={districtStats.filter((d) => d.complaint_count > 0).length}
          tone="cyan"
        />
        <StatTile
          icon={AlertTriangle}
          label="High-risk zones"
          value={highRiskCount}
          tone="red"
        />
        <StatTile
          icon={Crosshair}
          label="Critical Core Sector"
          value={topDistrict?.district_id ?? '—'}
          tone="amber"
          small
        />
      </div>

      {/* Primary Analytical Split Panel */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-5 flex-1 min-h-0">
        <div className="flex flex-col gap-4 min-h-0">
          {/* Spatial Layer Controls */}
          <div className="flex items-center justify-between bg-[#041a1f]/40 backdrop-blur-md p-2 border border-cyan-500/10 rounded-xl">
            <div className="flex items-center gap-2">
              <ToggleButton active={viewMode === 'heatmap'} onClick={() => setViewMode('heatmap')} icon={Layers}>
                Heatmap Grid
              </ToggleButton>
              <ToggleButton active={viewMode === 'points'} onClick={() => setViewMode('points')} icon={Crosshair}>
                Scatter / Vectors
              </ToggleButton>
            </div>
            <ToggleButton active={showChoropleth} onClick={() => setShowChoropleth((v) => !v)} icon={MapIcon}>
              Risk Stratification Overlay
            </ToggleButton>
          </div>

          {/* Interactive Map Visualizer */}
          <div className="flex-1 min-h-[440px] rounded-2xl overflow-hidden border border-cyan-500/15 bg-[#03151A] shadow-[0_4px_30px_rgba(0,0,0,0.4)] relative">
            <MapView
              complaints={complaints}
              districtStats={districtStats}
              districtsRaw={districtsRaw}
              viewMode={viewMode}
              showChoropleth={showChoropleth}
              onSelectDistrict={setSelectedDistrictName}
            />
          </div>

          {/* Historical Delta Charts */}
          <div className="border border-cyan-500/10 rounded-2xl p-4 bg-[#052229]/30 backdrop-blur-sm">
            <TrendChart trend={trend} loading={loading} />
          </div>

          {/* Recent Activity Table */}
          <div className="border border-cyan-500/10 rounded-2xl p-4 bg-[#052229]/30 backdrop-blur-sm max-h-[300px] overflow-hidden flex flex-col">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" /> Recent Threat Activity
            </h3>
            <div className="overflow-y-auto flex-1 pr-2">
              <table className="w-full text-left text-xs font-mono text-slate-300">
                <thead className="sticky top-0 bg-[#052229] text-cyan-500/70 z-10">
                  <tr>
                    <th className="py-2 px-3 border-b border-cyan-500/10">Date</th>
                    <th className="py-2 px-3 border-b border-cyan-500/10">District</th>
                    <th className="py-2 px-3 border-b border-cyan-500/10">Scam Type</th>
                    <th className="py-2 px-3 border-b border-cyan-500/10">Risk</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cyan-500/5">
                  {complaints.slice().reverse().map((c, i) => (
                    <tr key={i} className="hover:bg-cyan-500/[0.02] transition-colors">
                      <td className="py-2 px-3 text-slate-500 whitespace-nowrap">{c.date}</td>
                      <td className="py-2 px-3">{c.district}</td>
                      <td className="py-2 px-3 text-amber-300">{c.scam_type}</td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded-md ${
                          c.risk_score >= 67 ? 'bg-red-500/10 text-red-400' :
                          c.risk_score >= 34 ? 'bg-amber-500/10 text-amber-400' :
                          'bg-emerald-500/10 text-emerald-400'
                        }`}>
                          {c.risk_score}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {complaints.length === 0 && (
                    <tr>
                      <td colSpan="4" className="py-4 text-center text-slate-500 italic">No activity logged in selected range</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Floating Parameter Controls */}
        <div className="flex flex-col gap-4 overflow-y-auto max-h-[85vh] xl:max-h-none pr-1">
          <FilterPanel
            scamTypes={scamTypes}
            filters={filters}
            onChange={setFilters}
            activePreset={activePreset}
            onPresetChange={setActivePreset}
          />
          <DistrictPanel district={selectedDistrict} onClose={() => setSelectedDistrictName(null)} />
        </div>
      </div>
    </div>
  );
};

const toneStyles = {
  cyan: { icon: 'text-cyan-400', border: 'border-cyan-500/15', glow: 'bg-cyan-500/5', bg: 'from-cyan-500/5' },
  red: { icon: 'text-red-400', border: 'border-red-500/20', glow: 'bg-red-500/5', bg: 'from-red-500/5' },
  amber: { icon: 'text-amber-400', border: 'border-amber-500/20', glow: 'bg-amber-500/5', bg: 'from-amber-500/5' },
};

const StatTile = ({ icon: Icon, label, value, tone = 'cyan', small }) => {
  const t = toneStyles[tone];
  return (
    <div
      className={`relative overflow-hidden rounded-xl border ${t.border} bg-gradient-to-br ${t.bg} to-transparent bg-[#052229]/40 backdrop-blur-md px-4 py-3.5 shadow-lg shadow-black/20 transition-all duration-300 hover:-translate-y-0.5`}
    >
      <div className={`absolute -top-10 -right-10 h-24 w-24 rounded-full blur-3xl ${t.glow} pointer-events-none`} />
      <div className="relative flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-slate-400">
        <Icon className={`h-3.5 w-3.5 ${t.icon}`} />
        {label}
      </div>
      <div className={`relative mt-2 font-mono font-bold tracking-tight text-slate-100 ${small ? 'text-xs truncate max-w-full text-cyan-300 bg-cyan-500/5 px-2 py-1 border border-cyan-500/10 rounded-md inline-block' : 'text-2xl'}`}>
        {value}
      </div>
    </div>
  );
};

const ToggleButton = ({ active, onClick, children, icon: Icon }) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-1.5 text-[11px] font-mono uppercase font-semibold px-3 py-2 rounded-lg border transition-all duration-200 ${
      active
        ? 'bg-gradient-to-r from-cyan-500/20 to-cyan-500/5 border-cyan-400/50 text-cyan-300 shadow-[0_0_10px_rgba(6,182,212,0.15)]'
        : 'border-transparent text-slate-500 hover:text-cyan-400 hover:bg-white/[0.02]'
    }`}
  >
    {Icon && <Icon className="h-3.5 w-3.5 shrink-0" />}
    {children}
  </button>
);

export default GeoSpatial;