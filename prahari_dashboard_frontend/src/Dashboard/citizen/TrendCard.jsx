import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { SCAM_TREND_DATA, categoryLabel } from '../fraudCategories';
import { ShieldAlert, TrendingUp, AlertCircle, Eye, Globe } from 'lucide-react';

const TrendCard = ({ scamTypeKey }) => {
  const [headlines, setHeadlines] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    const fetchTrends = async () => {
      try {
        const url = scamTypeKey 
          ? `/api/trends?scam_type=${encodeURIComponent(scamTypeKey)}`
          : `/api/trends`;
          
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch trends');
        const data = await res.json();
        
        if (isMounted) {
          setHeadlines(data);
          setLoading(false);
        }
      } catch (err) {
        console.error(err);
        if (isMounted) setLoading(false);
      }
    };

    fetchTrends();

    return () => {
      isMounted = false;
    };
  }, [scamTypeKey]);

  const staticData = scamTypeKey ? SCAM_TREND_DATA[scamTypeKey] : null;

  // General State (Before Analysis)
  if (!scamTypeKey) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="p-6 border border-slate-200 rounded-2xl bg-white shadow-sm h-full flex flex-col min-h-[400px]"
      >
        <div className="flex items-center gap-3 mb-6 pb-4 border-b border-slate-100">
          <div className="p-2.5 bg-cyan-50 text-cyan-500 rounded-xl">
            <Globe className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-bold text-slate-800 tracking-tight">Live OSINT Trends</h2>
            <p className="text-sm text-slate-500 font-medium">General Cyber Fraud News</p>
          </div>
        </div>

        <div className="space-y-4 flex-1 overflow-y-auto pr-2">
          {loading ? (
            <div className="animate-pulse space-y-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-16 bg-slate-100 rounded-xl"></div>
              ))}
            </div>
          ) : (
            headlines.map((item, idx) => (
              <a 
                key={idx} 
                href={item.link} 
                target="_blank" 
                rel="noreferrer"
                className="block p-3 rounded-xl border border-slate-100 bg-slate-50 hover:bg-slate-100 transition-colors"
              >
                <h3 className="text-sm font-medium text-slate-800 line-clamp-2">{item.title}</h3>
                <p className="text-xs text-slate-500 mt-1">{item.pubDate}</p>
              </a>
            ))
          )}
          
          <div className="mt-8 text-center text-slate-400 p-4 border border-slate-200 border-dashed rounded-xl">
             <ShieldAlert className="w-8 h-8 mx-auto mb-2 opacity-50" />
             <p className="text-sm">Analyze a message to view specific threat patterns and red flags.</p>
          </div>
        </div>
      </motion.div>
    );
  }

  // Specific State (After Analysis)
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
          <h2 className="font-bold text-slate-800 tracking-tight">Contextual Intelligence</h2>
          <p className="text-sm text-slate-500 font-medium">Category: <span className="text-cyan-700">{categoryLabel(scamTypeKey)}</span></p>
        </div>
      </div>

      <div className="space-y-6 flex-1 overflow-y-auto pr-2">
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <Globe className="w-3.5 h-3.5 text-cyan-500" />
            Live Internet OSINT
          </h3>
          <div className="space-y-2">
            {loading ? (
              <div className="animate-pulse space-y-2">
                {[1, 2].map(i => (
                  <div key={i} className="h-12 bg-slate-100 rounded-lg"></div>
                ))}
              </div>
            ) : headlines.length > 0 ? (
              headlines.slice(0, 3).map((item, idx) => (
                <a 
                  key={idx} 
                  href={item.link} 
                  target="_blank" 
                  rel="noreferrer"
                  className="block text-sm text-slate-700 leading-snug bg-slate-50 hover:bg-slate-100 p-2.5 rounded-lg border border-slate-100 transition-colors"
                >
                  {item.title}
                </a>
              ))
            ) : (
              <p className="text-sm text-slate-500 p-2">No recent news found for this category.</p>
            )}
          </div>
        </div>

        {staticData && (
          <>
            <div className="space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                Common Patterns
              </h3>
              <p className="text-sm text-slate-700 leading-relaxed bg-amber-50/50 p-3 rounded-xl border border-amber-100/50">
                {staticData.patterns}
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                <Eye className="w-3.5 h-3.5 text-red-500" />
                Red Flags to Notice
              </h3>
              <ul className="space-y-2 mt-2">
                {staticData.indicators.map((indicator, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-sm text-slate-700 bg-white border border-slate-100 shadow-xs p-3 rounded-xl">
                    <span className="shrink-0 mt-0.5 text-red-500">🚩</span>
                    <span>{indicator}</span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </div>
    </motion.div>
  );
};

export default TrendCard;
