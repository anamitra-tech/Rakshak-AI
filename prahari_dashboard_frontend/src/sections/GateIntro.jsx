import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Play } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import ModulesShowcase from './ModulesShowcase';
// ==========================================
// 1. TECH-TEAL CITADEL DUST & ATMOSPHERE
// ==========================================
const CitadelAtmosphere = ({ particleCount = 60 }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const particles = Array.from({ length: particleCount }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 1.5 + 0.4,
      speedX: (Math.random() - 0.5) * 0.1,
      speedY: -(Math.random() * 0.2 + 0.05),
      alpha: Math.random() * 0.35 + 0.15,
      wobble: Math.random() * 100,
      wobbleSpeed: Math.random() * 0.01 + 0.005
    }));

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach((p) => {
        p.y += p.speedY;
        p.x += p.speedX + Math.sin(p.wobble) * 0.05;
        p.wobble += p.wobbleSpeed;

        if (p.y < 0) {
          p.y = canvas.height;
          p.x = Math.random() * canvas.width;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(34, 211, 238, ${p.alpha})`;
        ctx.fill();
      });
      animationFrameId = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', resizeCanvas);
    };
  }, [particleCount]);

  return (
    <div className="absolute inset-0 z-10 pointer-events-none overflow-hidden select-none">
      <div className="absolute inset-0 bg-[#041E24]" />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[80vw] h-[80vh] bg-[radial-gradient(circle,rgba(0,255,230,0.14),transparent_65%)] blur-2xl opacity-90" />
      <canvas ref={canvasRef} className="absolute inset-0 opacity-40" />
    </div>
  );
};

// ==========================================
// 2. CHISELED CORNER BRACKETS (TINTED TO THEME)
// ==========================================
const ThreeDCornerBracket = () => {
  return (
    <svg className="w-28 h-28 drop-shadow-[0_6px_12px_rgba(0,0,0,0.85)] filter brightness-90" viewBox="0 0 100 100" fill="none">
      <path d="M 5 95 L 5 5 L 95 5" stroke="#021114" strokeWidth="6" strokeLinecap="square" />
      <path d="M 6 94 L 6 6 L 94 6" stroke="#0d3842" strokeWidth="4" strokeLinecap="square" />
      <path d="M 7 93 L 7 7 L 93 7" stroke="#22d3ee" strokeWidth="1.2" strokeLinecap="square" strokeDasharray="85 6 85" className="opacity-30" />
      
      <circle cx="16" cy="16" r="4.5" fill="#021114" />
      <circle cx="16" cy="16" r="3.5" fill="#041E24" stroke="#0d3842" strokeWidth="0.5" />
      
      <circle cx="48" cy="14" r="3.5" fill="#021114" />
      <circle cx="48" cy="14" r="2.5" fill="#041E24" stroke="#0d3842" strokeWidth="0.5" />

      <circle cx="14" cy="48" r="3.5" fill="#021114" />
      <circle cx="14" cy="48" r="2.5" fill="#041E24" stroke="#0d3842" strokeWidth="0.5" />
    </svg>
  );
};

// ==========================================
// 3. HORIZONTAL STRAPS (WITH TEAL UNDERTONES)
// ==========================================
const ThreeDStrap = () => {
  return (
    <div 
      className="relative w-full h-12 rounded shadow-[0_14px_28px_rgba(4,30,36,0.9),_inset_0_1px_2px_rgba(255,255,255,0.04),_inset_0_-2px_4px_rgba(0,0,0,0.95)] border-y border-cyan-950/40 flex items-center justify-around px-8"
      style={{
        backgroundImage: `
          linear-gradient(to bottom, #072A32 0%, #041E24 50%, #021114 100%),
          radial-gradient(circle at 20% 30%, rgba(34, 211, 238, 0.15) 0%, transparent 40%)
        `
      }}
    >
      {[...Array(4)].map((_, i) => (
        <div key={i} className="w-2.5 h-2.5 rounded-full bg-[#021114] shadow-[0_2px_4px_rgba(0,0,0,0.7)] flex items-center justify-center">
          <div className="w-1.5 h-1.5 rounded-full bg-gradient-to-t from-[#041E24] to-cyan-500 opacity-60" />
        </div>
      ))}
    </div>
  );
};

// ==========================================
// 4. TECH-TEAL INTEGRATED CITADEL PORTAL
// ==========================================
const FortressDoor = ({ side, stage, children }) => {
  const isLeft = side === 'left';

  return (
    <motion.div
      className={`relative w-1/2 h-full overflow-hidden flex items-center shadow-[0_0_80px_rgba(4,30,36,0.9)] ${
        isLeft ? 'justify-end border-r-[3px] border-[#072A32]' : 'justify-start border-l-[3px] border-[#072A32]'
      }`}
      style={{
        backgroundImage: `
          linear-gradient(${isLeft ? '90deg' : '-90deg'}, rgba(4,30,36,0.6) 0%, transparent 25%, transparent 75%, rgba(4,30,36,0.9) 100%),
          linear-gradient(to bottom, #072A32 0%, #041E24 50%, #021114 100%)
        `,
        transformOrigin: isLeft ? 'left center' : 'right center',
      }}
      animate={{
        x: stage === 'opening' || stage === 'revealed' ? (isLeft ? '-102%' : '102%') : '0%',
        rotateY: stage === 'opening' || stage === 'revealed' ? (isLeft ? -22 : 22) : 0,
        z: stage === 'opening' ? -80 : 0
      }}
      exit={{ opacity: 0, transition: { duration: 0.4 } }}
      transition={{
        duration: 2.8,
        ease: [0.76, 0, 0.24, 1],
        delay: 0.2
      }}
    >
      {/* Horizontal laser light effect matching the landing dashboard theme */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-400/5 to-transparent pointer-events-none mix-blend-screen" />

      {/* Cyber-Teal Ambient Core Behind Shield Asset */}
      <div className={`absolute ${isLeft ? 'right-0' : 'left-0'} top-1/2 -translate-y-1/2 w-96 h-96 bg-[radial-gradient(circle,rgba(34,211,238,0.18),transparent_70%)] pointer-events-none z-10`} />

      {/* High-Fidelity Cyber-Iron Textured Patina Engine */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-[0.22] mix-blend-overlay">
        <filter id="cyberiron">
          <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="4" result="noise" />
          <feColorMatrix type="matrix" values="
            0.1   0   0   0   0.02
            0     1   0   0   0.14
            0     0   1   0   0.16
            0     0   0  0.85  0
          " />
        </filter>
        <rect width="100%" height="100%" filter="url(#cyberiron)" />
      </svg>

      {/* Beveled frame structure */}
      <div className="absolute inset-6 border border-cyan-500/15 pointer-events-none rounded-sm shadow-[inset_0_0_60px_rgba(4,30,36,0.85)]" />

      {/* Structured Brackets */}
      <div className={`absolute top-8 ${isLeft ? 'left-8' : 'right-8 scale-x-[-1]'} opacity-80 mix-blend-luminosity`}>
        <ThreeDCornerBracket />
      </div>
      <div className={`absolute bottom-8 ${isLeft ? 'left-8 scale-y-[-1]' : 'right-8 scale-x-[-1] scale-y-[-1]'} opacity-80 mix-blend-luminosity`}>
        <ThreeDCornerBracket />
      </div>

      {/* Horizontal Heavy Plates */}
      <div className={`absolute left-0 right-0 top-[28%] px-12 pointer-events-none z-20 ${isLeft ? 'translate-x-4' : '-translate-x-4'}`}>
        <ThreeDStrap />
      </div>
      <div className={`absolute left-0 right-0 bottom-[28%] px-12 pointer-events-none z-20 ${isLeft ? 'translate-x-4' : '-translate-x-4'}`}>
        <ThreeDStrap />
      </div>

      {/* Inner Door Split Seam Shading */}
      <div className={`absolute top-0 bottom-0 w-24 bg-gradient-to-r from-transparent via-[#041E24]/50 to-[#021114]/90 pointer-events-none ${isLeft ? 'right-0' : 'left-0 rotate-180'}`} />

      {/* Centered Graphic Container Asset */}
      <div className="relative flex items-center h-full z-30 filter drop-shadow-[0_20px_50px_rgba(4,30,36,0.95)]">
        {children}
      </div>
    </motion.div>
  );
};

// ==========================================
// 5. THEME-MATCHED CENTRAL SYSTEM DEADBOLTS
// ==========================================
const DynamicCitadelLocks = ({ stage }) => {
  const isUnlocked = stage === 'unlocking' || stage === 'opening' || stage === 'revealed';

  return (
    <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 z-40 w-32 pointer-events-none flex flex-col justify-between py-24 items-center">
      <motion.div
        className="w-10 h-44 rounded shadow-[0_24px_40px_rgba(0,0,0,0.95)] border-x border-cyan-900/40 relative"
        style={{
          backgroundImage: 'linear-gradient(to right, #041E24 0%, #0d3842 50%, #021114 100%)'
        }}
        animate={{ y: isUnlocked ? -190 : 0, scaleY: isUnlocked ? 0.8 : 1, opacity: isUnlocked ? 0 : 1 }}
        transition={{ duration: 1.4, ease: [0.6, -0.28, 0.735, 0.045] }}
      >
        <div className="absolute top-4 inset-x-1 h-3 bg-black/40 border-y border-cyan-500/20" />
        <div className="absolute bottom-4 inset-x-1 h-8 bg-gradient-to-b from-[#072A32] to-[#041E24]" />
      </motion.div>

      <motion.div
        className="w-10 h-44 rounded shadow-[0_-24px_40px_rgba(0,0,0,0.95)] border-x border-cyan-900/40 relative"
        style={{
          backgroundImage: 'linear-gradient(to right, #041E24 0%, #0d3842 50%, #021114 100%)'
        }}
        animate={{ y: isUnlocked ? 190 : 0, scaleY: isUnlocked ? 0.8 : 1, opacity: isUnlocked ? 0 : 1 }}
        transition={{ duration: 1.4, ease: [0.6, -0.28, 0.735, 0.045] }}
      >
        <div className="absolute bottom-4 inset-x-1 h-3 bg-black/40 border-y border-cyan-500/20" />
        <div className="absolute top-4 inset-x-1 h-8 bg-gradient-to-t from-[#072A32] to-[#041E24]" />
      </motion.div>
    </div>
  );
};

// ==========================================
// 6. PRAHARI PLATFORM CORE LANDING SECTION
// ==========================================
const Landing = ({ isVisible }) => {
  if (!isVisible) return null;
  const navigate = useNavigate();
  return (
    <motion.section 
      initial={{ scale: 0.98, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 1.2, ease: [0.25, 1, 0.5, 1] }}
      className="absolute inset-0 h-screen overflow-hidden bg-[#041E24] z-20"
    >
      {/* Background Graphic Asset */}
      <img
        src="src/tealbk.jpg"
        alt=""
        className="absolute inset-0 h-full w-full object-cover object-center scale-105"
      />

      {/* Dark Cover Overlay */}
      <div className="absolute inset-0 bg-[#072A32]/45" />

      {/* Radial Glow Matrix */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_55%_25%,rgba(0,255,230,0.18),transparent_65%)]" />

      {/* Horizontal Vector Light Accent */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-300/10 to-transparent" />

      {/* Floating Network Node Arrays */}
      <div className="absolute left-[13%] top-[34%] h-2.5 w-2.5 rounded-full bg-cyan-300 shadow-[0_0_30px_10px_rgba(34,211,238,.8)] animate-pulse" />
      <div className="absolute left-[38%] top-[20%] h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_25px_8px_rgba(34,211,238,.8)] animate-pulse" />
      <div className="absolute right-[20%] top-[24%] h-3 w-3 rounded-full bg-cyan-300 shadow-[0_0_35px_10px_rgba(34,211,238,.8)] animate-pulse" />
      <div className="absolute right-[10%] bottom-[35%] h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_25px_8px_rgba(34,211,238,.8)] animate-pulse" />
      <div className="absolute left-[18%] bottom-[28%] h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_25px_8px_rgba(34,211,238,.8)] animate-pulse" />

      {/* Atmospheric Fog Layers */}
      <div className="absolute bottom-20 left-1/2 -translate-x-1/2 w-[150%] h-64 bg-cyan-300/10 blur-[170px]" />
      <div className="absolute bottom-0 left-0 w-full h-80 bg-gradient-to-t from-[#041E24] via-[#072A32]/90 via-30% to-transparent" />
      <div className="absolute bottom-0 left-0 w-full h-40 bg-gradient-to-b from-transparent to-[#041E24]" />
      {/* ================= NAVBAR ================= */}
      <nav className="absolute top-0 left-0 w-full z-50">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-10">

          {/* Logo */}
          <div className="inline-flex items-center gap-3 rounded-full border border-cyan-300/30 bg-white/5 backdrop-blur-xl px-5 py-2">
                  <div className="h-2 w-2 rounded-full bg-cyan-300 animate-pulse"></div>
                  <span className="text-sm font-medium text-cyan-100">
                    AI Powered • PRAHARI
                  </span>
                </div>


        {/* Navigation */}
        <div className="hidden md:flex items-center gap-12 rounded-full border border-cyan-300/15 bg-white/5 px-8 py-3 backdrop-blur-xl">

          <a
            href="#modules"
            className="text-slate-300 transition hover:text-cyan-300"
          >
            Modules
          </a>

          <a
            href="#mvp"
            className="text-slate-300 transition hover:text-cyan-300"
          >
            MVP
          </a>

        <Link to="/login" className="text-slate-300 transition hover:text-cyan-300">
      Login
    </Link>

        </div>

        {/* CTA */}
        <button
        onClick={() => navigate('/walkthrough')}
        className="rounded-xl border border-cyan-400 bg-cyan-400 px-6 py-2.5 ..."
      >
        Get Started
      </button>

      </div>
    </nav>
      {/* Primary Landing Content Hero */}
      <div className="relative z-20 flex h-full items-center">
        <div className="max-w-3xl ml-24 -mt-12">
          
          {/* Badge Alert */}
         
          {/* Heading Elements */}
          <h1 className="mt-8 text-7xl  font-bebas tracking-wide font-black leading-[1.05] tracking-tight text-white">
            Protect Every Citizen.<br />
            <span className="text-cyan-300">Detect Every Scam.</span>
          </h1>

          {/* Platform Explainer */}
          <p className="mt-8 max-w-2xl font-montenegrin text-xl leading-9 text-slate-100">
            Prahari is India's AI-powered fraud intelligence platform helping
            citizens, villages, farmers and senior citizens stay protected from
            digital fraud. Whether online or offline, Prahari empowers everyone
            to report scams, detect fraud networks, identify crime hotspots and
            generate intelligence for law enforcement.
          </p>

          {/* Trigger CTAs */}
          <div className="mt-12 flex items-center gap-6">
           <button
              onClick={() => navigate('/citizen/report')}
              className="rounded-xl bg-cyan-400 px-10 py-4 text-lg font-semibold text-slate-900 ..."
            >
              Report a Scam
            </button>
            <button className="rounded-xl border border-white/20 bg-white/10 backdrop-blur-xl px-10 py-4 text-lg font-medium text-white transition duration-300 hover:bg-white/20">
              <Play />
            </button>
          </div>

          {/* Metrics Footer */}
          <div className="mt-16 flex gap-16">
            <div>
              <h2 className="text-4xl font-bold text-cyan-300">24/7</h2>
              <p className="mt-2 text-sm uppercase tracking-widest text-slate-300">AI Monitoring</p>
            </div>
            <div>
              <h2 className="text-4xl font-bold text-cyan-300">Offline</h2>
              <p className="mt-2 text-sm uppercase tracking-widest text-slate-300">Village Support</p>
            </div>
            <div>
              <h2 className="text-4xl font-bold text-cyan-300"> Modules</h2>
              <p className="mt-2 text-sm uppercase tracking-widest text-slate-300">Connected Intelligence</p>
            </div>
          </div>
        </div>
       
      </div>
    </motion.section>
  );
};

// ==========================================
// 7. MAIN TIMELINE COORDINATION COMPONENT
// ==========================================
const GateIntro = () => {
  const [stage, setStage] = useState('initial');
  const [gateTremor, setGateTremor] = useState(false);

  useEffect(() => {
    const unlockTimer = setTimeout(() => {
      setStage('unlocking');
      setGateTremor(true);
    }, 1200);

    const stopTremorTimer = setTimeout(() => setGateTremor(false), 2100);

    const openTimer = setTimeout(() => {
      setStage('opening');
    }, 2600);

    const finishedTimer = setTimeout(() => setStage('revealed'), 5400);

    return () => {
      clearTimeout(unlockTimer);
      clearTimeout(stopTremorTimer);
      clearTimeout(openTimer);
      clearTimeout(finishedTimer);
    };
  }, []);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black text-white select-none [perspective:1400px]">
      {/* Atmosphere particles colored explicitly cyan */}
      <CitadelAtmosphere particleCount={stage === 'opening' ? 95 : 45} />

      {/* Your Landing Content is nested cleanly underneath to pick up light streams */}
      <Landing isVisible={stage === 'opening' || stage === 'revealed'} />

      <AnimatePresence>
        {stage !== 'revealed' && (
          <motion.div
            key="citadel-gate-wrapper"
            className="absolute inset-0 z-30 flex"
            animate={gateTremor ? {
              x: [0, -2, 2.5, -2.5, 1.5, -0.5, 0],
              y: [0, 1.5, -1, 2, -1.5, 0.5, 0]
            } : {}}
            transition={{ duration: 0.7, repeat: 1 }}
          >
            {/* Left Hand Portal Layer */}
            <FortressDoor side="left" stage={stage}>
              <img
                src="src/prahari.png"
                alt="Shield Left Wing"
                className="h-64 md:h-96 w-auto object-contain select-none"
              />
            </FortressDoor>

            {/* Centered Mechanized Systems */}
            <DynamicCitadelLocks stage={stage} />

            {/* Right Hand Portal Layer */}
            <FortressDoor side="right" stage={stage}>
              <img
                src="src/prahari copy.png"
                alt="Shield Right Wing"
                className="h-64 md:h-96 w-auto object-contain select-none"
              />
            </FortressDoor>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default GateIntro;