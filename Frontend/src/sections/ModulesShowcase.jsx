import React, { useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger);

const modules = [
  {
    title: "Citizen Fraud Shield",
    image: "src/prahari tl.png",
    description:
      "Analyze suspicious messages, emails, links, and screenshots using AI-powered fraud detection. Instantly identify scams, understand the risk level, and receive actionable guidance to stay protected from cyber threats.",
  },
  {
    title: "Digital Arrest Scam Detector",
    image: "src/prahari tr.png",
    description:
      "Upload suspicious call recordings or live conversations. AI transcribes the audio, detects fake government officials and digital arrest scams, and alerts users before they become victims.",
  },
  {
    title: "Fraud Network Intelligence",
    image: "src/prahari bl.png",
    description:
      "Visualize hidden relationships between phone numbers, bank accounts, UPI IDs, email addresses, and devices using an interactive intelligence graph that uncovers organized fraud networks.",
  },
  {
    title: "Cyber Crime Heatmap",
    image: "src/prahari br.png",
    description:
      "Explore cybercrime trends across India through an interactive heatmap displaying fraud hotspots, recent incidents, and regional insights to spread awareness and improve preparedness.",
  },
  // --- NEW 5TH CARD ADDED HERE ---
  {
    title: "Offline Guard & Senior Safety",
    image: null, // No unique piece, shield is already full
    isOfflineSection: true,
    description:
      "Zero internet? No tech skills? No problem. Built specifically to protect senior citizens and offline users, our local AI engine monitors incoming telecom patterns instantly. If a matching scam footprint is detected, the device emits a distinct, loud buzzer noise—providing an unmistakable sensory alert before anyone can answer.",
  },
];

const ModulesShowcase = () => {
  const containerRef = useRef(null);
  const shieldRef = useRef(null);

  useGSAP(() => {
    const pieces = gsap.utils.toArray(".shield-piece");
    const textCards = gsap.utils.toArray(".text-card");
    const introTitle = document.querySelector(".intro-title");

    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: containerRef.current,
        start: "top top",
        end: "+=650%", // Increased slightly to give the final card breathing room
        scrub: 1,
        pin: true,
      },
    });

    // --- INITIAL STATES ---
    gsap.set(pieces[0], { x: -400, y: -400, opacity: 0 }); 
    gsap.set(pieces[1], { x: 400, y: -400, opacity: 0 });  
    gsap.set(pieces[2], { x: -400, y: 400, opacity: 0 });  
    gsap.set(pieces[3], { x: 400, y: 400, opacity: 0 });   

    // All text modules start hidden below the screen
    gsap.set(textCards, { y: "100vh", opacity: 0 });

    // --- ANIMATION SEQUENCE ---

    // 1. Fade out the Intro Title
    tl.to(introTitle, {
      y: "-50vh",
      opacity: 0,
      duration: 1.5,
      ease: "power2.inOut",
    }, "start");

    // 2. Loop through all 5 screens
    modules.forEach((module, index) => {
      const positionLabel = `step-${index}`;

      // Bring in the current text card
      tl.to(textCards[index], {
        y: "0vh",
        opacity: 1,
        duration: 2,
        ease: "power2.out",
      }, positionLabel);

      // Bring in the shield piece ONLY if it's one of the first 4 modules
      if (index < 4) {
        tl.to(pieces[index], {
          x: 0,
          y: 0,
          opacity: 1,
          duration: 2,
          ease: "power2.out",
        }, positionLabel);
      }

      // Trigger the Epic Shield Assembly glow during Module 4's reveal
      if (index === 3) {
        tl.to(shieldRef.current, {
          scale: 1.05,
          filter: "drop-shadow(0 0 45px rgba(34,211,238,0.6))",
          duration: 2,
          ease: "power2.out",
        }, positionLabel);
      }

      // If this is the offline section, maybe add a slight pulse to the shield to match the "buzzer alert" concept
      if (module.isOfflineSection) {
        tl.to(shieldRef.current, {
          scale: 0.98,
          filter: "drop-shadow(0 0 55px rgba(239, 68, 68, 0.5))", // Shifts red/crimson to look like a warning trigger
          duration: 0.5,
          yoyo: true,
          repeat: 3,
        }, positionLabel);
      }

      // Slide this text card away IF there is another module coming up next
      if (index < modules.length - 1) {
        tl.to(textCards[index], {
          y: "-100vh",
          opacity: 0,
          duration: 1.5,
          ease: "power2.in",
        }, `${positionLabel}+=2.5`); // Added extra delay buffer so text stays readable longer
      }
    });

  }, { scope: containerRef });

  return (
    <div ref={containerRef} className="relative h-screen w-full overflow-hidden bg-[#041E24]">
      {/* Dynamic Background Layout */}
      <img
        src="src/tealbk.jpg"
        alt="Background"
        className="absolute inset-0 h-full w-full object-cover"
      />
      <div className="absolute inset-0 bg-[#041E24]/85 z-10" />

      {/* INTRO TITLE LAYER */}
      <div className="intro-title absolute inset-0 z-30 flex flex-col items-center justify-center text-center px-4 pointer-events-none">
        <h2 className="text-xs md:text-sm font-bold tracking-[0.5em] text-cyan-400 uppercase mb-4 animate-pulse">
          Securing The Digital Frontier
        </h2>
        <h1 className="text-6xl md:text-8xl font-black text-transparent bg-clip-text bg-gradient-to-b from-white via-gray-200 to-gray-500 tracking-tight max-w-4xl leading-none">
          FOUR POWERFUL MODULES
        </h1>
        <p className="text-gray-400 mt-6 text-lg md:text-xl tracking-wide max-w-xl font-light">
          Scroll down to watch the dynamic tactical shield assemble piece by piece.
        </p>
      </div>

      {/* CORE WORKSPACE FRAME */}
      <div className="relative z-20 mx-auto flex h-full max-w-7xl items-center justify-between px-8 md:px-16">
        
        {/* LEFT COMPONENT: The Seamless Shield Framework */}
        <div className="w-[45%] flex justify-center items-center">
          <div 
            ref={shieldRef} 
            className="relative w-[340px] h-[340px] md:w-[400px] md:h-[400px] transition-all duration-300"
          >
            {/* Render the 4 shield pieces explicitly using static array layout indexes */}
            <img
              src={modules[0].image}
              alt="Shield Top Left"
              className="shield-piece absolute top-0 left-0 w-1/2 h-1/2 object-right-bottom object-contain"
            />
            <img
              src={modules[1].image}
              alt="Shield Top Right"
              className="shield-piece absolute top-0 right-0 w-1/2 h-1/2 object-left-bottom object-contain"
            />
            <img
              src={modules[2].image}
              alt="Shield Bottom Left"
              className="shield-piece absolute bottom-0 left-0 w-1/2 h-1/2 object-right-top object-contain"
            />
            <img
              src={modules[3].image}
              alt="Shield Bottom Right"
              className="shield-piece absolute bottom-0 right-0 w-1/2 h-1/2 object-left-top object-contain"
            />
          </div>
        </div>

        {/* RIGHT COMPONENT: Scroll-Bound Sequential Content */}
        <div className="relative w-[50%] h-[500px] flex items-center">
          {modules.map((module, index) => (
            <div
              key={index}
              className="text-card absolute inset-0 flex flex-col justify-center"
            >
              <p className="uppercase tracking-[0.35em] text-cyan-400 text-xs md:text-sm font-semibold">
                {module.isOfflineSection ? "Universal Accessibility" : `Module 0${index + 1}`}
              </p>

              <h1 className="mt-3 text-4xl font-bebas md:text-5xl lg:text-6xl font-extrabold leading-tight text-white tracking-tight">
                {module.title}
              </h1>

              {/* Dynamic color underline for the offline/warning screen */}
              <div 
                className={`mt-5 h-[3px] w-24 rounded-full transition-all duration-300 ${
                  module.isOfflineSection 
                    ? "bg-red-500 shadow-[0_0_8px_#ef4444]" 
                    : "bg-cyan-400 shadow-[0_0_8px_#22d3ee]"
                }`}
              />

              <p className="mt-6 text-sm font-montenegrin md:text-base lg:text-lg leading-relaxed text-gray-300 font-light">
                {module.description}
              </p>
            </div>
          ))}
        </div>

      </div>
      <div className="absolute bottom-0 left-0 h-32 w-full bg-gradient-to-t from-[#041E24] via-[#041E24]/40 to-transparent z-20 pointer-events-none" />
    </div>
  );
};

 export default ModulesShowcase;