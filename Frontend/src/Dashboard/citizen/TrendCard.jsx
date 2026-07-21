import React from 'react';
import { motion } from 'framer-motion';
import { SCAM_TREND_DATA, categoryLabel } from '../fraudCategories';
import { ShieldAlert, TrendingUp, AlertCircle, Eye } from 'lucide-react';

const TrendCard = ({ scamTypeKey }) => {
  const data = scamTypeKey ? SCAM_TREND_DATA[scamTypeKey] : null;

  if (!scamTypeKey || !data) {
    return (
      <div className="h-full w-full flex items-center justify-center p-8 border border-slate-200 border-dashed rounded-2xl bg-slate-50/50 min-h-[400px]">
        <div className="text-center text-slate-400">
          <ShieldAlert className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="font-medium">Contextual Threat Intelligence</p>
          <p className="text-sm mt-1">Analyze a message to view live trends, patterns, and red flags for the detected threat.</p>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="p-6 border border-slate-200 rounded-2xl bg-white shadow-sm h-full flex flex-col min-h-[400px]"
    >
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-slate-100">
        <div className="p-2.5 bg-red-50 text-red-500 rounded-xl">
          <TrendingUp className="w-5 h-5" />
        </div>
        <div>
          <h2 className="font-bold text-slate-800 tracking-tight">Threat Intelligence</h2>
          <p className="text-sm text-slate-500 font-medium">Category: <span className="text-cyan-700">{categoryLabel(scamTypeKey)}</span></p>
        </div>
      </div>

      <div className="space-y-6 flex-1 overflow-y-auto pr-2">
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <TrendingUp className="w-3.5 h-3.5 text-cyan-500" />
            Current Trends
          </h3>
          <p className="text-sm text-slate-700 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100">
            {data.trends}
          </p>
        </div>

        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
            Common Patterns
          </h3>
          <p className="text-sm text-slate-700 leading-relaxed bg-amber-50/50 p-3 rounded-xl border border-amber-100/50">
            {data.patterns}
          </p>
        </div>

        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <Eye className="w-3.5 h-3.5 text-red-500" />
            Red Flags to Notice
          </h3>
          <ul className="space-y-2 mt-2">
            {data.indicators.map((indicator, idx) => (
              <li key={idx} className="flex items-start gap-2.5 text-sm text-slate-700 bg-white border border-slate-100 shadow-xs p-3 rounded-xl">
                <span className="shrink-0 mt-0.5 text-red-500">🚩</span>
                <span>{indicator}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </motion.div>
  );
};

export default TrendCard;
