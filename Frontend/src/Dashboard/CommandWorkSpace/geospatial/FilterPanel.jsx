import { useState } from 'react';
import { DATE_PRESETS, FALLBACK_SCAM_TYPES, SCAM_TYPE_COLORS } from './constants';

const isoDaysAgo = (days) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
};

const FilterPanel = ({ scamTypes, filters, onChange, activePreset, onPresetChange }) => {
  const [customOpen, setCustomOpen] = useState(false);
  const options = scamTypes.length ? scamTypes : FALLBACK_SCAM_TYPES;

  const toggleScamType = (type) => {
    const set = new Set(filters.scamTypes);
    if (set.has(type)) set.delete(type);
    else set.add(type);
    onChange({ ...filters, scamTypes: Array.from(set) });
  };

  const applyPreset = (days) => {
    onPresetChange(days);
    setCustomOpen(false);
    onChange({ ...filters, startDate: isoDaysAgo(days - 1), endDate: isoDaysAgo(0) });
  };

  const applyCustomRange = (field, value) => {
    onPresetChange('custom');
    onChange({ ...filters, [field]: value });
  };

  return (
    <div className="rounded-xl border border-cyan-900/40 bg-[#06272E]/60 p-4 space-y-4">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-cyan-400 mb-2">
          Scam Type
        </div>
        <div className="flex flex-wrap gap-2">
          {options.map((type) => {
            const active = filters.scamTypes.includes(type);
            const color = SCAM_TYPE_COLORS[type] || '#22d3ee';
            return (
              <button
                key={type}
                onClick={() => toggleScamType(type)}
                className={`text-xs px-2.5 py-1 rounded-full border transition ${
                  active
                    ? 'text-[#041E24] font-medium'
                    : 'text-slate-400 border-cyan-900/50 hover:text-cyan-300'
                }`}
                style={active ? { backgroundColor: color, borderColor: color } : undefined}
              >
                {type}
              </button>
            );
          })}
          {filters.scamTypes.length > 0 && (
            <button
              onClick={() => onChange({ ...filters, scamTypes: [] })}
              className="text-xs px-2.5 py-1 rounded-full text-slate-500 hover:text-cyan-300"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-cyan-400 mb-2">
          Date Range
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {DATE_PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => applyPreset(p.days)}
              className={`text-xs px-3 py-1 rounded-lg border transition ${
                activePreset === p.days
                  ? 'bg-cyan-500/20 border-cyan-500/60 text-cyan-300'
                  : 'border-cyan-900/50 text-slate-400 hover:text-cyan-300'
              }`}
            >
              Last {p.label}
            </button>
          ))}
          <button
            onClick={() => setCustomOpen((v) => !v)}
            className={`text-xs px-3 py-1 rounded-lg border transition ${
              activePreset === 'custom'
                ? 'bg-cyan-500/20 border-cyan-500/60 text-cyan-300'
                : 'border-cyan-900/50 text-slate-400 hover:text-cyan-300'
            }`}
          >
            Custom
          </button>
        </div>
        {customOpen && (
          <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
            <input
              type="date"
              value={filters.startDate}
              max={filters.endDate}
              onChange={(e) => applyCustomRange('startDate', e.target.value)}
              className="bg-[#04161a] border border-cyan-900/50 rounded px-2 py-1 text-slate-200"
            />
            <span>to</span>
            <input
              type="date"
              value={filters.endDate}
              min={filters.startDate}
              onChange={(e) => applyCustomRange('endDate', e.target.value)}
              className="bg-[#04161a] border border-cyan-900/50 rounded px-2 py-1 text-slate-200"
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default FilterPanel;
export { isoDaysAgo };
