import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const steps = [
  {
    eyebrow: 'Welcome to Prahari',
    title: 'India’s AI-Powered Fraud Shield',
    description:
      'Prahari helps citizens, villages, farmers and senior citizens stay protected from digital fraud — whether online or offline. Here’s a quick look at how the four modules work together.',
  },
  {
    eyebrow: 'Module 01',
    title: 'Citizen Fraud Shield',
    description:
      'Paste a suspicious message, email, WhatsApp chat, or payment request. AI classifies the fraud type, assigns a risk score, explains why it’s suspicious, and gives you safety recommendations — in seconds.',
  },
  {
    eyebrow: 'Module 02',
    title: 'Digital Arrest Scam Detector',
    description:
      'Upload a call recording or transcript. Speech-to-text generates a transcript, then AI detects authority impersonation, fear tactics, and money-transfer demands — returning a fraud score and a timeline of suspicious moments.',
  },
  {
    eyebrow: 'Module 03',
    title: 'Fraud Network Intelligence',
    description:
      'Phone numbers, bank accounts, UPI IDs, victims and devices become nodes in a live graph. Graph analysis surfaces fraud rings and shared infrastructure, with AI-generated summaries of each cluster.',
  },
  {
    eyebrow: 'Module 04',
    title: 'Geospatial Crime Intelligence',
    description:
      'Complaint locations plotted on an interactive map with heatmaps and clustering. Spot fraud hotspots, track scam trends over time, and filter by scam type, district, or date range.',
  },
  {
    eyebrow: 'You’re ready',
    title: 'Let’s protect the next citizen.',
    description:
      'Sign in with Google to start using the Fraud Shield and Command Workspace — your account is created automatically the first time you sign in.',
  },
];

const Walkthrough = () => {
  const [step, setStep] = useState(0);
  const navigate = useNavigate();
  const { user } = useAuth();

  const isLast = step === steps.length - 1;
  const current = steps[step];

  const handleNext = () => {
    if (isLast) {
      navigate(user ? '/citizen/fraud-shield' : '/login');
      return;
    }
    setStep((s) => s + 1);
  };

  const handleBack = () => setStep((s) => Math.max(0, s - 1));

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-[#041E24] flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,rgba(0,255,230,0.16),transparent_65%)]" />
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-300/5 to-transparent" />
      <div className="absolute bottom-0 left-0 w-full h-64 bg-gradient-to-t from-[#041E24] via-[#072A32]/60 to-transparent" />

      <Link
        to="/"
        className="absolute top-8 left-8 inline-flex items-center gap-3 rounded-full border border-cyan-300/30 bg-white/5 backdrop-blur-xl px-5 py-2 z-10"
      >
        <div className="h-2 w-2 rounded-full bg-cyan-300 animate-pulse" />
        <span className="text-sm font-medium text-cyan-100">PRAHARI</span>
      </Link>

      <button
        onClick={() => navigate(user ? '/citizen/fraud-shield' : '/login')}
        className="absolute top-8 right-8 z-10 text-sm text-slate-300 hover:text-cyan-300 transition"
      >
        Skip
      </button>

      <div className="relative z-10 w-full max-w-xl rounded-2xl border border-cyan-300/20 bg-white/5 backdrop-blur-2xl px-10 py-12 shadow-[0_0_80px_rgba(4,30,36,0.9)]">
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
          >
            <p className="uppercase tracking-[0.35em] text-cyan-400 text-xs font-semibold">
              {current.eyebrow}
            </p>
            <h1 className="mt-4 text-4xl font-bebas font-black leading-tight text-white tracking-tight">
              {current.title}
            </h1>
            <div className="mt-4 h-[3px] w-16 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
            <p className="mt-6 text-base leading-relaxed text-slate-300">
              {current.description}
            </p>
          </motion.div>
        </AnimatePresence>

        {/* Progress dots */}
        <div className="mt-10 flex items-center justify-center gap-2">
          {steps.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i === step ? 'w-8 bg-cyan-400' : 'w-1.5 bg-cyan-900/60'
              }`}
            />
          ))}
        </div>

        <div className="mt-8 flex items-center justify-between">
          <button
            onClick={handleBack}
            disabled={step === 0}
            className="text-sm text-slate-400 hover:text-cyan-300 transition disabled:opacity-0 disabled:pointer-events-none"
          >
            &larr; Back
          </button>
          <button
            onClick={handleNext}
            className="rounded-xl bg-cyan-400 px-8 py-3 text-sm font-semibold text-slate-900 hover:bg-cyan-300 transition"
          >
            {isLast ? 'Get Started' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Walkthrough;
