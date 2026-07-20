import { riskColor, riskLabel, trendColor } from './constants';

const DistrictPanel = ({ district, onClose }) => {
  if (!district) {
    return (
      <div className="rounded-xl border border-cyan-900/40 bg-[#06272E]/60 p-4 text-xs text-slate-500">
        Click a district on the map to see details.
      </div>
    );
  }

  const noData = district.risk_score < 0;

  return (
    <div className="rounded-xl border border-cyan-900/40 bg-[#06272E]/60 p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm font-semibold text-cyan-300">{district.district_id}</div>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-cyan-300 text-xs">
          ✕
        </button>
      </div>

      {noData ? (
        <div className="mt-3 text-xs text-slate-500">No complaint data for this district.</div>
      ) : (
        <div className="mt-3 space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Risk score</span>
            <span
              className="px-2 py-0.5 rounded-full font-medium"
              style={{ color: riskColor(district.risk_score), backgroundColor: `${riskColor(district.risk_score)}22` }}
            >
              {riskLabel(district.risk_score)} · {district.risk_score.toFixed(1)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Total complaints</span>
            <span className="text-slate-200">{district.complaint_count}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Top scam type</span>
            <span className="text-slate-200">{district.top_scam_type ?? '—'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Trend vs previous period</span>
            <span style={{ color: trendColor(district.trend) }} className="font-medium">
              {district.trend === 'up' ? '▲' : district.trend === 'down' ? '▼' : '—'}{' '}
              {Math.abs(district.trend_delta_pct)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default DistrictPanel;
