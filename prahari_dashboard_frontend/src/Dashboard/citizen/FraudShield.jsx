// src/Dashboard/citizen/FraudShield.jsx
import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { categoryLabel, VERDICT_STYLES } from '../fraudCategories';
import TrendCard from './TrendCard';

// 🛡️ Import the asset directly so the bundler can resolve and optimize it
import shieldAsset from '../../prahari copy 2.png';

const SHIELD_IMAGE_SRC = shieldAsset; 

const SOURCE_TYPES = [
  { value: 'sms', label: 'SMS' },
  { value: 'email', label: 'Email' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'payment_request', label: 'Payment Request' },
  { value: 'call_transcript', label: 'Call Transcript' },
];

const MAX_FILES = 5;
const MAX_FILE_SIZE = 8 * 1024 * 1024; // 8MB
const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'application/pdf'];

const STATUS_MESSAGES = [
  'Analyzing...',
  'Scanning content...',
  'Checking phishing indicators...',
  'Cross-checking threat intelligence...',
  'Evaluating risk...',
];

const useCountUp = (target, duration = 600) => {
  const [value, setValue] = useState(0);
  useEffect(() => {
    let start = null;
    let raf;
    const from = 0;
    const step = (ts) => {
      if (start === null) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(from + (target - from) * eased));
      if (progress < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value;
};

const FraudShield = () => {
  const [text, setText] = useState('');
  const [sourceType, setSourceType] = useState('sms');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [entities, setEntities] = useState(null);
  const [error, setError] = useState(null);

  const [showOverlay, setShowOverlay] = useState(false);
  const [statusIndex, setStatusIndex] = useState(0);
  const [isAnalysisComplete, setIsAnalysisComplete] = useState(false);

  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [fileError, setFileError] = useState(null);
  
  const [district, setDistrict] = useState('');
  const [latLng, setLatLng] = useState(null);
  const [isLocationLoading, setIsLocationLoading] = useState(false);
  const [reportSuccess, setReportSuccess] = useState(false);
  
  const dragCounter = useRef(0);
  const fileInputRef = useRef(null);

  const shouldReduceMotion = useReducedMotion();

  const riskPercent = result ? Math.round(result.risk_score * 100) : 0;
  const animatedRisk = useCountUp(riskPercent);

  useEffect(() => {
    if (!showOverlay || isAnalysisComplete) return;
    const interval = setInterval(() => {
      setStatusIndex((prev) => (prev + 1) % STATUS_MESSAGES.length);
    }, 2500);
    return () => clearInterval(interval);
  }, [showOverlay, isAnalysisComplete]);

  const addFiles = useCallback((incoming) => {
    setFileError(null);
    const valid = [];

    for (const file of incoming) {
      if (files.length + valid.length >= MAX_FILES) {
        setFileError(`You can attach up to ${MAX_FILES} files.`);
        break;
      }
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setFileError('Only images (PNG, JPG, WebP) or PDFs are supported.');
        continue;
      }
      if (file.size > MAX_FILE_SIZE) {
        setFileError('Each file must be under 8MB.');
        continue;
      }
      valid.push({
        id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
        file,
        previewUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : null,
      });
    }

    if (valid.length) setFiles((prev) => [...prev, ...valid]);
  }, [files.length]);

  const removeFile = (id) => {
    setFiles((prev) => {
      const target = prev.find((f) => f.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((f) => f.id !== id);
    });
  };

  useEffect(() => {
    return () => files.forEach((f) => f.previewUrl && URL.revokeObjectURL(f.previewUrl));
  }, []);

  const handleDragEnter = (e) => {
    e.preventDefault();
    dragCounter.current += 1;
    if (e.dataTransfer.types.includes('Files')) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  };

  const handleDragOver = (e) => e.preventDefault();

  const handleDrop = (e) => {
    e.preventDefault();
    dragCounter.current = 0;
    setIsDragging(false);
    if (e.dataTransfer.files?.length) addFiles(Array.from(e.dataTransfer.files));
  };

  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      setFileError('Geolocation is not supported by your browser.');
      return;
    }
    setIsLocationLoading(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatLng({ lat: position.coords.latitude, lng: position.coords.longitude });
        setDistrict('Current Location');
        setIsLocationLoading(false);
      },
      () => {
        setFileError('Unable to retrieve your location.');
        setIsLocationLoading(false);
      }
    );
  };

  const handleReport = async () => {
    if (!result || !district.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const payload = {
        scam_type: result.categories?.[0] || 'Unknown',
        description: text || 'Uploaded evidence',
        district,
        lat: latLng?.lat,
        lng: latLng?.lng,
        date: new Date().toISOString().split('T')[0]
      };
      
      const res = await fetch('/api/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      if (!res.ok) throw new Error('Failed to submit report');
      setReportSuccess(true);
    } catch (e) {
      setError(e.message || 'Error submitting report.');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!text.trim() && files.length === 0) return;
    setLoading(true);
    setResult(null);
    setEntities(null);
    setError(null);
    
    setIsAnalysisComplete(false);
    setStatusIndex(0);
    setShowOverlay(true);

    const startTime = Date.now();

    try {
      let analyzeRes;

      if (files.length > 0) {
        const formData = new FormData();
        formData.append('text', text);
        formData.append('source_type', sourceType);
        formData.append('mode', 'offline');
        files.forEach(({ file }) => formData.append('evidence', file));

        analyzeRes = await fetch('/api/analyze', { method: 'POST', body: formData });
      } else {
        analyzeRes = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, source_type: sourceType, mode: 'offline' }),
        });
      }

      if (!analyzeRes.ok) {
        const err = await analyzeRes.json().catch(() => null);
        throw new Error(err?.message || `Request failed (${analyzeRes.status})`);
      }
      
      const analysisData = await analyzeRes.json();

      let extractedData = null;
      if (text.trim()) {
        const entitiesRes = await fetch('/api/extract_entities', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        });
        if (entitiesRes.ok) extractedData = await entitiesRes.json();
      }

      const elapsedTime = Date.now() - startTime;
      const remainingTime = Math.max(0, 2000 - elapsedTime);
      await new Promise((resolve) => setTimeout(resolve, remainingTime));

      setIsAnalysisComplete(true);
      await new Promise((resolve) => setTimeout(resolve, 700));

      setResult(analysisData);
      if (extractedData) setEntities(extractedData);
      setShowOverlay(false);
    } catch (e) {
      setError(e.message || 'Something went wrong. Please try again.');
      setShowOverlay(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 max-w-6xl w-full items-start">
      <div className="max-w-2xl w-full flex flex-col">
      {/* Full-Screen Premium AI Guardian Overlay */}
      <AnimatePresence>
        {showOverlay && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4, ease: 'easeInOut' }}
            className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-slate-950/85 backdrop-blur-xl select-none pointer-events-auto"
          >
            {/* Background Sharp Neon HUD Circles */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
              <div className="absolute w-[600px] h-[600px] bg-cyan-500/5 blur-[140px] rounded-full" />
              
              {!shouldReduceMotion && (
                <>
                  {/* Sharp Inner HUD Ring */}
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
                    className="absolute w-[340px] h-[340px] border border-cyan-400/40 rounded-full border-dashed"
                  />
                  {/* Sharp Middle Tech Ring */}
                  <motion.div
                    animate={{ rotate: -360 }}
                    transition={{ duration: 30, repeat: Infinity, ease: 'linear' }}
                    className="absolute w-[420px] h-[420px] border-2 border-t-cyan-400/30 border-b-cyan-500/10 border-l-transparent border-r-transparent rounded-full"
                  />
                  {/* Outer Dotted Frame */}
                  <motion.div
                    animate={{ rotate: 180 }}
                    transition={{ duration: 45, repeat: Infinity, ease: 'linear' }}
                    className="absolute w-[500px] h-[500px] border border-cyan-500/20 rounded-full stroke-dasharray"
                    style={{ borderStyle: 'dotted' }}
                  />
                </>
              )}
            </div>

            {/* Central Giant Shield Container */}
            <div className="relative z-10 flex flex-col items-center">
              <motion.div
                animate={shouldReduceMotion ? {} : {
                  y: [-4, 4, -4],
                  scale: isAnalysisComplete ? [1, 1.06, 1.02] : [1, 1.02, 1]
                }}
                transition={{
                  y: { duration: 4, repeat: Infinity, ease: 'easeInOut' },
                  scale: isAnalysisComplete 
                    ? { duration: 0.4, ease: 'easeOut' }
                    : { duration: 3, repeat: Infinity, ease: 'easeInOut' }
                }}
                className="relative w-64 h-64 flex items-center justify-center rounded-full"
              >
                {/* Hyper-Brighter Layered Neon Ambient Aura directly behind the asset */}
                <div className={`absolute w-52 h-52 rounded-full blur-3xl transition-all duration-500 mix-blend-screen opacity-90 ${
                  isAnalysisComplete 
                    ? 'bg-gradient-to-r from-teal-400 to-emerald-500 scale-110 shadow-[0_0_90px_rgba(45,212,191,0.8)]' 
                    : 'bg-gradient-to-r from-cyan-400 to-blue-500 shadow-[0_0_80px_rgba(34,211,238,0.7)]'
                }`} />

                {/* Second Core Glow Ring for sharp edge illumination */}
                <div className={`absolute w-44 h-44 rounded-full blur-xl transition-colors duration-500 ${
                  isAnalysisComplete ? 'bg-teal-400/40' : 'bg-cyan-400/40'
                }`} />

                {/* Custom Scaled-up Shield Image Asset */}
                <img
                  src={SHIELD_IMAGE_SRC}
                  alt="Custom AI Guardian Shield"
                  className={`w-56 h-56 object-contain transition-all duration-500 select-none pointer-events-none relative z-10 ${
                    isAnalysisComplete 
                      ? 'drop-shadow-[0_0_35px_rgba(45,212,191,0.8)] brightness-125 scale-105' 
                      : 'drop-shadow-[0_0_25px_rgba(34,211,238,0.6)] brightness-110'
                  }`}
                  onError={(e) => {
                    const target = e.currentTarget;
                    target.style.display = 'none';
                  }}
                />
              </motion.div>

              {/* Status Message Display */}
              <div className="mt-10 h-6 flex items-center justify-center overflow-hidden">
                <AnimatePresence mode="wait">
                  {isAnalysisComplete ? (
                    <motion.p
                      key="complete"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="text-base font-semibold tracking-wide text-teal-400 flex items-center gap-1.5 drop-shadow-[0_0_8px_rgba(45,212,191,0.5)]"
                    >
                      <span className="text-lg">✔</span> Analysis Complete
                    </motion.p>
                  ) : (
                    <motion.p
                      key={statusIndex}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.3 }}
                      className="text-base font-medium tracking-wider text-cyan-300 antialiased drop-shadow-[0_0_10px_rgba(34,211,238,0.3)]"
                    >
                      {STATUS_MESSAGES[statusIndex]}
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <h1 className="text-2xl font-semibold mb-6">Citizen Fraud Shield</h1>

      <div className="mb-4 flex flex-wrap gap-2">
        {SOURCE_TYPES.map((s) => (
          <button
            key={s.value}
            type="button"
            onClick={() => setSourceType(s.value)}
            className={`px-3 py-1.5 text-xs font-medium rounded-full border transition-all duration-150 ${
              sourceType === s.value
                ? 'bg-cyan-500 text-white border-cyan-500 scale-105'
                : 'bg-white text-slate-600 border-slate-300 hover:border-cyan-300'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste a suspicious message, email, payment request, or call transcript..."
        className="w-full h-40 p-4 border border-slate-300 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-cyan-400"
      />

      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`mt-4 border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200 ${
          isDragging
            ? 'border-cyan-500 bg-cyan-50 scale-[1.01]'
            : 'border-slate-300 bg-slate-50 hover:border-cyan-300 hover:bg-cyan-50/50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES.join(',')}
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) addFiles(Array.from(e.target.files));
            e.target.value = '';
          }}
        />
        <p className="text-sm text-slate-500">
          {isDragging ? (
            <span className="text-cyan-700 font-medium">Drop screenshots here</span>
          ) : (
            <>
              Drag and drop screenshots or a PDF here, or{' '}
              <span className="text-cyan-600 font-medium">browse</span>
            </>
          )}
        </p>
        <p className="text-xs text-slate-400 mt-1">PNG, JPG, WebP, or PDF · up to {MAX_FILES} files · 8MB each</p>
      </div>

      {fileError && <p className="mt-2 text-xs text-red-500">{fileError}</p>}

      {files.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-3">
          {files.map(({ id, file, previewUrl }) => (
            <div
              key={id}
              className="relative w-20 h-20 rounded-lg overflow-hidden border border-slate-200 bg-white group"
            >
              {previewUrl ? (
                <img src={previewUrl} alt={file.name} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-[10px] text-slate-500 p-1 text-center">
                  {file.name}
                </div>
              )}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  removeFile(id);
                }}
                className="absolute top-0.5 right-0.5 h-5 w-5 rounded-full bg-black/60 text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                aria-label={`Remove ${file.name}`}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 mb-2 flex items-center gap-2">
        <input
          type="text"
          value={district}
          onChange={(e) => {
             setDistrict(e.target.value);
             setLatLng(null);
          }}
          placeholder="Enter District/City/Pincode *"
          className="flex-1 p-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-400 text-sm"
          required
        />
        <button
          type="button"
          onClick={handleGetLocation}
          disabled={isLocationLoading}
          className="px-4 py-3 bg-slate-100 text-slate-700 rounded-xl text-sm font-medium hover:bg-slate-200 transition-colors"
        >
          {isLocationLoading ? 'Locating...' : 'Use My Location'}
        </button>
      </div>

      <button
        onClick={handleAnalyze}
        disabled={loading || (!text.trim() && files.length === 0) || !district.trim()}
        className="mt-2 px-6 py-3 bg-cyan-500 text-white rounded-xl font-medium disabled:opacity-50 transition-transform active:scale-[0.98]"
      >
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>

      {error && (
        <div className="mt-4 p-4 border border-red-200 bg-red-50 text-red-600 rounded-xl text-sm animate-[fadeIn_0.2s_ease-out]">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-8 p-6 border border-slate-200 rounded-2xl bg-white shadow-sm animate-[fadeIn_0.3s_ease-out]">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm text-slate-500">Risk Score</span>
            <span className="text-3xl font-bold text-red-500 tabular-nums">{animatedRisk}%</span>
          </div>
          <div className="mb-4">
            <span
              className={`inline-block px-3 py-1 text-xs font-medium rounded-full ${
                VERDICT_STYLES[result.verdict] || 'bg-slate-100 text-slate-600'
              }`}
            >
              {result.verdict}
            </span>
          </div>
          {result.categories.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-2">
              {result.categories.map((c) => (
                <span
                  key={c}
                  className="inline-block px-3 py-1 text-xs font-medium bg-slate-100 text-slate-600 rounded-full"
                >
                  {categoryLabel(c)}
                </span>
              ))}
            </div>
          )}
          <div>
            <h3 className="text-sm font-semibold mb-2">Why this is suspicious</h3>
            <p className="text-sm text-slate-600 whitespace-pre-wrap">{result.reason}</p>
          </div>
          
          {reportSuccess ? (
             <div className="mt-6 p-4 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-xl text-sm font-medium">
               Report successfully submitted. It will appear on the map shortly.
             </div>
          ) : (
            <button
              onClick={handleReport}
              disabled={loading}
              className="mt-6 w-full py-3 bg-slate-900 text-white rounded-xl font-medium hover:bg-slate-800 transition-colors"
            >
              Submit Scam Report
            </button>
          )}
        </div>
      )}

      {entities && (
        <div className="mt-6 p-4 border border-slate-200 rounded-xl bg-slate-50 animate-[fadeIn_0.3s_ease-out]">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
            Extracted Entities
          </h3>
          <div className="grid grid-cols-2 gap-3 text-sm text-slate-600">
            <div>
              <span className="text-xs text-slate-400 block mb-1">Phone Numbers</span>
              {entities.phone_numbers.length ? entities.phone_numbers.join(', ') : '—'}
            </div>
            <div>
              <span className="text-xs text-slate-400 block mb-1">UPI IDs</span>
              {entities.upi_ids.length ? entities.upi_ids.join(', ') : '—'}
            </div>
            <div>
              <span className="text-xs text-slate-400 block mb-1">Bank Accounts</span>
              {entities.bank_accounts.length ? entities.bank_accounts.join(', ') : '—'}
            </div>
            <div>
              <span className="text-xs text-slate-400 block mb-1">URLs</span>
              {entities.urls.length ? entities.urls.join(', ') : '—'}
            </div>
          </div>
        </div>
      )}
      </div>

      <div className="w-full lg:sticky lg:top-24 h-full lg:h-[calc(100vh-8rem)]">
        <TrendCard scamTypeKey={result?.categories?.[0]} />
      </div>
    </div>
  );
};

export default FraudShield;