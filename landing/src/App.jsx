import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Play, Zap, Wand2, Film, ChevronRight, ArrowRight } from 'lucide-react'
import './index.css'

gsap.registerPlugin(ScrollTrigger)

/* ═══════════════════════════════════════════
   NOISE OVERLAY
   ═══════════════════════════════════════════ */
function NoiseOverlay() {
  return (
    <div className="noise-overlay">
      <svg><filter id="noise"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="4" stitchTiles="stitch" /><feColorMatrix type="saturate" values="0" /></filter><rect width="100%" height="100%" filter="url(#noise)" /></svg>
    </div>
  )
}

/* ═══════════════════════════════════════════
   NAVBAR — Floating Island
   ═══════════════════════════════════════════ */
function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const ref = useRef()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <nav ref={ref} className={`fixed top-6 left-1/2 -translate-x-1/2 z-40 px-2 py-2 rounded-full flex items-center gap-1 transition-all duration-500 ${
      scrolled
        ? 'bg-void/70 backdrop-blur-xl border border-border-subtle shadow-[0_8px_32px_rgba(0,0,0,0.4)]'
        : 'bg-transparent'
    }`}>
      <a href="#" className="pl-3 pr-4 py-1 flex items-center gap-2">
        <img src="/igloo-mark.png" alt="Igloo" className="h-7 w-7 object-contain" />
        <span className="text-sm font-bold tracking-tight text-amber-light">Igloo</span>
      </a>
      <div className="hidden md:flex items-center gap-1">
        <a href="#features" className="px-4 py-2 text-sm text-text-secondary hover:text-text transition-colors rounded-full">Features</a>
        <a href="#how-it-works" className="px-4 py-2 text-sm text-text-secondary hover:text-text transition-colors rounded-full">How It Works</a>
        <a href="#examples" className="px-4 py-2 text-sm text-text-secondary hover:text-text transition-colors rounded-full">Examples</a>
      </div>
      <a href="http://localhost:5000" className="btn-magnetic ml-2 px-5 py-2 bg-amber text-void text-sm font-semibold rounded-full hover:bg-amber-hover">
        Create Your Reel
      </a>
    </nav>
  )
}

/* ═══════════════════════════════════════════
   HERO — The Opening Shot
   ═══════════════════════════════════════════ */
const HERO_REELS = [
  { src: '/reels/Fasting_wellness.mp4', label: 'Fasting & Wellness' },
  { src: '/reels/Screen_addiction_parenting.mp4', label: 'Screen Addiction' },
  { src: '/reels/Spiritual_growth.mp4', label: 'Spiritual Growth' },
  { src: '/reels/Hanuman_Lanka.mp4', label: 'Hanuman in Lanka' },
]

function PhoneCarousel() {
  const [active, setActive] = useState(0)
  const videoRefs = useRef([])
  const count = HERO_REELS.length

  useEffect(() => {
    const interval = setInterval(() => setActive(prev => (prev + 1) % count), 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    videoRefs.current.forEach(v => { if (v) v.play().catch(() => {}) })
  }, [])

  // 3D carousel math — position each phone on a circle
  // Active phone (index 0 from active) is at front-center (angle 0)
  const getTransform = (index) => {
    const offset = ((index - active) % count + count) % count // 0=front, 1=right, 2=back, 3=left
    const angle = (offset / count) * 360
    const rad = (angle * Math.PI) / 180
    const radius = 240 // px — how spread out the circle is
    const x = Math.sin(rad) * radius
    const z = Math.cos(rad) * radius - radius // shift so front is z=0
    const scale = 0.55 + 0.45 * ((z + radius) / (radius * 2)) // front=1.0, back=0.55
    const opacity = offset === 0 ? 1 : offset === 2 ? 0.2 : 0.45
    const zIndex = offset === 0 ? 40 : offset === 2 ? 10 : 20
    const blur = offset === 0 ? 0 : offset === 2 ? 4 : 1.5

    return {
      transform: `translateX(${x}px) translateZ(${z}px) scale(${scale})`,
      opacity,
      zIndex,
      filter: `blur(${blur}px)`,
    }
  }

  return (
    <div className="phone-carousel-stage">
      <div className="phone-carousel-ring">
        {HERO_REELS.map((reel, i) => {
          const style = getTransform(i)
          const isActive = ((i - active) % count + count) % count === 0
          return (
            <div key={i} className="phone-carousel-item" style={style}>
              <div className={`phone-frame ${isActive ? 'phone-active' : ''}`}>
                <div className="phone-notch" />
                <div className="phone-screen">
                  <video ref={el => videoRefs.current[i] = el} src={reel.src}
                    muted loop playsInline autoPlay className="w-full h-full object-cover" />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Hero() {
  const heroRef = useRef()

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from('.hero-line', {
        y: 50, opacity: 0, duration: 1,
        stagger: 0.12, ease: 'power3.out', delay: 0.3,
      })
      gsap.from('.hero-cta', {
        y: 30, opacity: 0, duration: 0.8,
        ease: 'power3.out', delay: 0.9,
      })
      gsap.from('.phone-carousel-stage', {
        y: 80, opacity: 0, duration: 1.4,
        ease: 'power3.out', delay: 0.6,
      })
    }, heroRef)
    return () => ctx.revert()
  }, [])

  return (
    <section ref={heroRef} className="relative min-h-[100dvh] flex items-end overflow-hidden">
      <div className="absolute inset-0 bg-void" />
      <div className="absolute inset-0 opacity-[0.18]">
        <img src="https://images.unsplash.com/photo-1485846234645-a62644f84728?w=1920&q=60" alt="" className="w-full h-full object-cover" style={{ filter: 'brightness(0.4) sepia(0.4)' }} />
      </div>
      <div className="hero-bg-mesh" />

      {/* Ambient glows */}
      <div className="absolute top-[10%] right-[20%] w-[700px] h-[700px] bg-amber/12 rounded-full blur-[180px] pointer-events-none" />
      <div className="absolute bottom-[10%] left-[40%] w-[500px] h-[500px] bg-amber/8 rounded-full blur-[140px] pointer-events-none" />

      {/* 3D Phone carousel — right-center */}
      <div className="absolute right-0 top-0 bottom-0 w-[55%] hidden md:flex items-center justify-center">
        <PhoneCarousel />
      </div>

      {/* Content — bottom left */}
      <div className="relative z-10 max-w-[700px] px-8 md:px-16 pb-20 md:pb-28">
        <p className="hero-line text-sm md:text-base font-mono text-amber-light tracking-widest uppercase mb-6">
          AI-Powered Video Engine
        </p>
        <h1 className="hero-line mb-2">
          <img src="/igloo-wordmark.png" alt="Igloo" className="block w-[280px] md:w-[380px] lg:w-[460px] h-auto -ml-3" />
          <span className="sr-only">Igloo</span>
        </h1>
        <p className="hero-line font-drama italic text-3xl md:text-5xl lg:text-6xl text-amber-light mb-4">
          Video that stops thumbs.
        </p>
        <p className="hero-line text-base md:text-lg text-text-secondary font-light max-w-[50ch] leading-relaxed mb-10">
          Type a topic. Pick a character. Igloo writes the script, generates visuals, composes music, and delivers your reel. All in minutes.
        </p>
        <div className="hero-cta flex flex-wrap gap-4">
          <a href="http://localhost:5000" className="btn-magnetic inline-flex items-center gap-3 px-8 py-4 bg-amber text-void font-bold rounded-2xl text-base hover:bg-amber-hover hover:shadow-[0_8px_40px_rgba(217,119,6,0.3)]">
            <Play size={18} strokeWidth={2.5} /> Create Your Reel
          </a>
          <a href="#examples" className="btn-magnetic inline-flex items-center gap-3 px-8 py-4 border border-border text-text-secondary font-medium rounded-2xl text-base hover:border-amber/40 hover:text-text">
            <Film size={18} /> Example Reels
          </a>
        </div>
      </div>

      {/* Bottom fade into next section */}
      <div className="hero-gradient" />
    </section>
  )
}

/* ═══════════════════════════════════════════
   FEATURES — Interactive Functional Artifacts
   ═══════════════════════════════════════════ */

function DiagnosticShuffler() {
  const [order, setOrder] = useState([0, 1, 2])
  const labels = ['Script Generation', 'Voice Matching', 'Scene Composition']
  const descs = ['AI writes your narration', 'Perfect voice for your content', 'Cinematic b-roll + anchor']

  useEffect(() => {
    const interval = setInterval(() => {
      setOrder(prev => {
        const next = [...prev]
        next.unshift(next.pop())
        return next
      })
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="relative h-[220px] w-full">
      {order.map((idx, pos) => (
        <div key={idx} className="absolute left-4 right-4 px-5 py-4 bg-surface-raised border border-border-subtle rounded-2xl transition-all duration-700"
          style={{
            top: `${pos * 28 + 20}px`,
            zIndex: 3 - pos,
            opacity: 1 - pos * 0.2,
            transform: `scale(${1 - pos * 0.04})`,
            transitionTimingFunction: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
          }}>
          <div className="text-sm font-semibold text-text">{labels[idx]}</div>
          <div className="text-xs text-text-muted mt-1">{descs[idx]}</div>
        </div>
      ))}
    </div>
  )
}

function TelemetryTypewriter() {
  const lines = [
    'Analyzing topic: "Benefits of cold exposure"...',
    'Generating 9-scene narration script...',
    'Selecting voice: confident, male, American...',
    'Composing ambient electronic soundtrack...',
    'Rendering cinematic b-roll sequences...',
    'Assembling final reel @ 9:16 vertical...',
  ]
  const [currentLine, setCurrentLine] = useState(0)
  const [chars, setChars] = useState(0)
  const [displayed, setDisplayed] = useState([])

  useEffect(() => {
    if (currentLine >= lines.length) {
      const timeout = setTimeout(() => {
        setCurrentLine(0)
        setChars(0)
        setDisplayed([])
      }, 2000)
      return () => clearTimeout(timeout)
    }

    const line = lines[currentLine]
    if (chars < line.length) {
      const timeout = setTimeout(() => setChars(c => c + 1), 30)
      return () => clearTimeout(timeout)
    } else {
      const timeout = setTimeout(() => {
        setDisplayed(d => [...d, line])
        setCurrentLine(l => l + 1)
        setChars(0)
      }, 800)
      return () => clearTimeout(timeout)
    }
  }, [currentLine, chars])

  return (
    <div className="px-5 py-4 h-[220px] overflow-hidden">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-2 h-2 rounded-full bg-amber pulse-dot" />
        <span className="text-xs font-mono text-amber-light">Live Feed</span>
      </div>
      <div className="font-mono text-xs text-text-muted space-y-1">
        {displayed.map((l, i) => <div key={i} className="text-text-secondary">{l}</div>)}
        {currentLine < lines.length && (
          <div className="text-amber-light">
            {lines[currentLine].slice(0, chars)}
            <span className="cursor-blink text-amber">|</span>
          </div>
        )}
      </div>
    </div>
  )
}

function CursorScheduler() {
  const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
  const [active, setActive] = useState([])
  const [cursorPos, setCursorPos] = useState(-1)

  useEffect(() => {
    let step = 0
    const sequence = [1, 3, 5] // Mon, Wed, Fri
    const interval = setInterval(() => {
      if (step < sequence.length) {
        setCursorPos(sequence[step])
        setTimeout(() => {
          setActive(prev => [...prev, sequence[step]])
          setCursorPos(-1)
        }, 400)
        step++
      } else if (step === sequence.length) {
        setCursorPos(7) // "Save" button
        setTimeout(() => setCursorPos(-1), 600)
        step++
      } else {
        step = 0
        setActive([])
      }
    }, 1200)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="px-5 py-4 h-[220px]">
      <div className="text-xs text-text-muted mb-4 font-mono">Publishing Schedule</div>
      <div className="grid grid-cols-7 gap-2 mb-6">
        {days.map((d, i) => (
          <div key={i} className={`flex items-center justify-center w-10 h-10 rounded-xl text-xs font-semibold transition-all duration-300 ${
            active.includes(i)
              ? 'bg-amber text-void scale-95'
              : cursorPos === i
              ? 'bg-amber/20 text-amber-light scale-95 ring-2 ring-amber/40'
              : 'bg-surface-raised text-text-muted'
          }`}>
            {d}
          </div>
        ))}
      </div>
      <button className={`w-full py-2.5 rounded-xl text-xs font-semibold transition-all duration-300 ${
        cursorPos === 7
          ? 'bg-amber text-void scale-[0.97]'
          : 'bg-surface-raised text-text-muted border border-border-subtle'
      }`}>
        Save Schedule
      </button>
    </div>
  )
}

function Features() {
  const ref = useRef()

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from('.feature-card', {
        scrollTrigger: { trigger: ref.current, start: 'top 80%' },
        y: 60, opacity: 0, duration: 0.8,
        stagger: 0.15, ease: 'power3.out',
      })
    }, ref)
    return () => ctx.revert()
  }, [])

  return (
    <section id="features" ref={ref} className="relative py-28 md:py-36 px-6 md:px-16 overflow-hidden">
      <div className="absolute inset-0 opacity-[0.14]">
        <img src="https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1920&q=60" alt="" className="w-full h-full object-cover" style={{ filter: 'brightness(0.35) sepia(0.3)' }} />
      </div>
      <div className="section-bg-mesh section-bg-features" />
      <div className="absolute top-0 left-1/3 w-[500px] h-[500px] bg-amber/12 rounded-full blur-[150px] pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-amber/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="max-w-[1200px] mx-auto relative">
        <p className="text-sm font-mono text-amber-light tracking-widest uppercase mb-4">What you get</p>
        <h2 className="text-3xl md:text-5xl font-bold tracking-[-0.03em] mb-16 max-w-[500px]">
          Every reel,<br /><span className="font-drama italic text-amber-light">engineered.</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1 — Shuffler */}
          <div className="feature-card card-surface overflow-hidden">
            <DiagnosticShuffler />
            <div className="px-6 pb-6">
              <h3 className="text-lg font-bold mb-1">Topic in. Script out.</h3>
              <p className="text-sm text-text-muted">AI writes, structures, and voices your narration.</p>
            </div>
          </div>

          {/* Card 2 — Typewriter */}
          <div className="feature-card card-surface overflow-hidden">
            <TelemetryTypewriter />
            <div className="px-6 pb-6">
              <h3 className="text-lg font-bold mb-1">Generated, not templated.</h3>
              <p className="text-sm text-text-muted">Lip-synced anchors. Cinematic b-roll. Original soundtrack.</p>
            </div>
          </div>

          {/* Card 3 — Scheduler */}
          <div className="feature-card card-surface overflow-hidden">
            <CursorScheduler />
            <div className="px-6 pb-6">
              <h3 className="text-lg font-bold mb-1">Hit create. Download. Post.</h3>
              <p className="text-sm text-text-muted">No timeline. No editing. Just your finished reel.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ═══════════════════════════════════════════
   PHILOSOPHY — The Manifesto
   ═══════════════════════════════════════════ */
function Philosophy() {
  const ref = useRef()

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from('.phil-line', {
        scrollTrigger: { trigger: ref.current, start: 'top 70%' },
        y: 40, opacity: 0, duration: 0.9,
        stagger: 0.2, ease: 'power3.out',
      })
    }, ref)
    return () => ctx.revert()
  }, [])

  return (
    <section ref={ref} className="relative py-28 md:py-40 px-6 md:px-16 bg-void-light overflow-hidden">
      <div className="absolute inset-0 opacity-[0.15]">
        <img src="https://images.unsplash.com/photo-1440404653325-ab127d49abc1?w=1920&q=60" alt="" className="w-full h-full object-cover" style={{ filter: 'brightness(0.3) sepia(0.4)' }} />
      </div>
      <div className="section-bg-mesh section-bg-philosophy" />
      <div className="absolute top-1/4 right-0 w-[600px] h-[600px] bg-amber/10 rounded-full blur-[160px] pointer-events-none" />

      <div className="relative max-w-[900px] mx-auto">
        <p className="phil-line text-base md:text-lg text-text-muted font-light leading-relaxed mb-8">
          Most content tools give you templates and filters.<br />
          You drag, drop, adjust, export. Hours of busywork for a 40-second clip.
        </p>
        <h2 className="phil-line text-3xl md:text-5xl lg:text-6xl font-bold tracking-[-0.03em] leading-[1.1]">
          We focus on the only thing<br />that matters:&nbsp;
          <span className="font-drama italic text-amber-light">your idea.</span>
        </h2>
        <p className="phil-line text-base text-text-secondary font-light mt-8 max-w-[55ch] leading-relaxed">
          Igloo doesn't help you edit. It removes editing entirely. You think it, describe it, and download a finished reel with professional voiceover, generated visuals, and an original score.
        </p>
      </div>
    </section>
  )
}

/* ═══════════════════════════════════════════
   PROTOCOL — How It Works (Sticky Stack)
   ═══════════════════════════════════════════ */
function Protocol() {
  const containerRef = useRef()
  const cardsRef = useRef([])

  const steps = [
    {
      num: '01',
      title: 'Describe your reel',
      desc: 'Pick a theme and topic. Optionally paste your own script, or let Gemini write one. Review the narration scene by scene.',
      visual: 'helix',
    },
    {
      num: '02',
      title: 'Choose your anchor',
      desc: 'Select from AI-suggested characters or describe your own. The system matches a voice profile and generates a photorealistic presenter.',
      visual: 'scanner',
    },
    {
      num: '03',
      title: 'Download and post',
      desc: 'Igloo generates images, video clips, voiceover, and music. Assembles everything with captions and transitions. You download the final reel.',
      visual: 'waveform',
    },
  ]

  useEffect(() => {
    const ctx = gsap.context(() => {
      cardsRef.current.forEach((card, i) => {
        if (i < steps.length - 1) {
          ScrollTrigger.create({
            trigger: card,
            start: 'top 10%',
            end: 'bottom 10%',
            onEnter: () => {
              gsap.to(card, { scale: 0.92, filter: 'blur(8px)', opacity: 0.4, duration: 0.6 })
            },
            onLeaveBack: () => {
              gsap.to(card, { scale: 1, filter: 'blur(0px)', opacity: 1, duration: 0.6 })
            },
          })
        }
      })
    }, containerRef)
    return () => ctx.revert()
  }, [])

  return (
    <section id="how-it-works" ref={containerRef} className="relative py-28 md:py-36 px-6 md:px-16 overflow-hidden">
      <div className="absolute inset-0 opacity-[0.12]">
        <img src="https://images.unsplash.com/photo-1524712245354-2c4e5e7121c0?w=1920&q=60" alt="" className="w-full h-full object-cover" style={{ filter: 'brightness(0.35) sepia(0.3)' }} />
      </div>
      <div className="section-bg-mesh section-bg-protocol" />
      <div className="absolute top-1/3 right-0 w-[600px] h-[600px] bg-amber/10 rounded-full blur-[160px] pointer-events-none" />
      <div className="absolute bottom-1/4 left-0 w-[400px] h-[400px] bg-amber/8 rounded-full blur-[140px] pointer-events-none" />
      <div className="max-w-[900px] mx-auto relative">
        <p className="text-sm font-mono text-amber-light tracking-widest uppercase mb-4">How it works</p>
        <h2 className="text-3xl md:text-5xl font-bold tracking-[-0.03em] mb-20">
          Three steps.<br /><span className="font-drama italic text-amber-light">No learning curve.</span>
        </h2>

        <div className="space-y-8">
          {steps.map((step, i) => (
            <div key={i} ref={el => cardsRef.current[i] = el}
              className="stack-card sticky top-[10vh] card-surface p-8 md:p-12">
              <div className="flex flex-col md:flex-row gap-8 items-start">
                <div className="flex-1">
                  <span className="font-mono text-sm text-amber-light">{step.num}</span>
                  <h3 className="text-2xl md:text-3xl font-bold tracking-tight mt-2 mb-4">{step.title}</h3>
                  <p className="text-base text-text-secondary font-light leading-relaxed max-w-[45ch]">{step.desc}</p>
                </div>
                <div className="w-full md:w-[280px] h-[180px] flex items-center justify-center">
                  {step.visual === 'helix' && <HelixVisual />}
                  {step.visual === 'scanner' && <ScannerVisual />}
                  {step.visual === 'waveform' && <WaveformVisual />}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ─── Step Visuals ─── */
function HelixVisual() {
  return (
    <svg viewBox="0 0 200 150" className="w-full h-full">
      {[...Array(12)].map((_, i) => {
        const x = 30 + i * 13
        const y1 = 75 + Math.sin(i * 0.6) * 35
        const y2 = 75 - Math.sin(i * 0.6) * 35
        return (
          <g key={i}>
            <circle cx={x} cy={y1} r={4} fill="#D97706" opacity={0.6 + i * 0.03}>
              <animate attributeName="cy" values={`${y1};${y2};${y1}`} dur={`${3 + i * 0.1}s`} repeatCount="indefinite" />
            </circle>
            <circle cx={x} cy={y2} r={4} fill="#F59E0B" opacity={0.4 + i * 0.03}>
              <animate attributeName="cy" values={`${y2};${y1};${y2}`} dur={`${3 + i * 0.1}s`} repeatCount="indefinite" />
            </circle>
            <line x1={x} y1={y1} x2={x} y2={y2} stroke="#D97706" strokeWidth="1" opacity="0.15">
              <animate attributeName="y1" values={`${y1};${y2};${y1}`} dur={`${3 + i * 0.1}s`} repeatCount="indefinite" />
              <animate attributeName="y2" values={`${y2};${y1};${y2}`} dur={`${3 + i * 0.1}s`} repeatCount="indefinite" />
            </line>
          </g>
        )
      })}
    </svg>
  )
}

function ScannerVisual() {
  return (
    <svg viewBox="0 0 200 150" className="w-full h-full">
      {/* Grid of dots */}
      {[...Array(7)].map((_, r) =>
        [...Array(9)].map((_, c) => (
          <circle key={`${r}-${c}`} cx={20 + c * 20} cy={20 + r * 18} r={2.5}
            fill="#3A3530" />
        ))
      )}
      {/* Scanning line */}
      <line x1="10" y1="0" x2="10" y2="150" stroke="#D97706" strokeWidth="2" opacity="0.6">
        <animate attributeName="x1" values="10;190;10" dur="4s" repeatCount="indefinite" />
        <animate attributeName="x2" values="10;190;10" dur="4s" repeatCount="indefinite" />
      </line>
      {/* Highlight dots */}
      {[[60, 56], [100, 38], [140, 74], [80, 92], [120, 110]].map(([cx, cy], i) => (
        <circle key={i} cx={cx} cy={cy} r={4} fill="#F59E0B" opacity="0">
          <animate attributeName="opacity" values="0;0.8;0" dur="4s" begin={`${i * 0.4}s`} repeatCount="indefinite" />
        </circle>
      ))}
    </svg>
  )
}

function WaveformVisual() {
  const points = [...Array(30)].map((_, i) => {
    const x = 10 + i * 6.2
    const y = 75 + Math.sin(i * 0.5) * 25 + Math.cos(i * 0.3) * 15
    return `${x},${y}`
  }).join(' ')

  return (
    <svg viewBox="0 0 200 150" className="w-full h-full">
      <polyline points={points} fill="none" stroke="#D97706" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        strokeDasharray="400" strokeDashoffset="400">
        <animate attributeName="stroke-dashoffset" values="400;0;400" dur="5s" repeatCount="indefinite" />
      </polyline>
      <polyline points={points} fill="none" stroke="#F59E0B" strokeWidth="1" strokeLinecap="round" opacity="0.3"
        strokeDasharray="400" strokeDashoffset="400" transform="translate(0, 8)">
        <animate attributeName="stroke-dashoffset" values="400;0;400" dur="5s" begin="0.3s" repeatCount="indefinite" />
      </polyline>
    </svg>
  )
}

/* ═══════════════════════════════════════════
   EXAMPLES — Reel Showcase
   ═══════════════════════════════════════════ */
function ReelPlayer({ src, title, theme }) {
  const videoRef = useRef()
  const [playing, setPlaying] = useState(false)

  const toggle = () => {
    if (videoRef.current.paused) {
      videoRef.current.play()
      setPlaying(true)
    } else {
      videoRef.current.pause()
      setPlaying(false)
    }
  }

  return (
    <div className="example-card card-surface p-3 group cursor-pointer" onClick={toggle}>
      <div className="aspect-[9/16] max-h-[320px] rounded-xl overflow-hidden relative bg-surface-raised">
        <video ref={videoRef} src={src} className="w-full h-full object-cover" loop playsInline
          onEnded={() => setPlaying(false)} />
        <div className={`absolute inset-0 flex items-center justify-center transition-opacity duration-300 ${playing ? 'opacity-0 hover:opacity-100' : 'opacity-100'}`}>
          <div className="absolute inset-0 bg-void/30" />
          <div className="w-11 h-11 rounded-full bg-amber/20 border-2 border-amber flex items-center justify-center group-hover:scale-110 group-hover:bg-amber/30 transition-all duration-300 z-10 backdrop-blur-sm">
            <Play size={18} className="text-amber-light ml-0.5" />
          </div>
        </div>
      </div>
      <h3 className="font-semibold text-sm mt-3 mb-0.5">{title}</h3>
      <span className="text-xs text-text-muted font-mono">{theme}</span>
    </div>
  )
}

function Examples() {
  const ref = useRef()
  const reels = [
    { title: 'Fasting & Wellness', theme: 'Health', src: '/reels/Fasting_wellness.mp4' },
    { title: 'Screen Addiction & Parenting', theme: 'Parenting', src: '/reels/Screen_addiction_parenting.mp4' },
    { title: 'Spiritual Growth', theme: 'Spirituality', src: '/reels/Spiritual_growth.mp4' },
    { title: 'Hanuman in Lanka', theme: 'Mythology', src: '/reels/Hanuman_Lanka.mp4' },
  ]

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from('.example-card', {
        scrollTrigger: { trigger: ref.current, start: 'top 80%' },
        y: 50, opacity: 0, duration: 0.7,
        stagger: 0.12, ease: 'power3.out',
      })
    }, ref)
    return () => ctx.revert()
  }, [])

  return (
    <section id="examples" ref={ref} className="relative py-28 md:py-36 px-6 md:px-16 bg-void-light overflow-hidden">
      <div className="absolute inset-0 opacity-[0.14]">
        <img src="https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1920&q=60" alt="" className="w-full h-full object-cover" style={{ filter: 'brightness(0.3) sepia(0.3)' }} />
      </div>
      <div className="section-bg-mesh section-bg-examples" />
      <div className="absolute top-1/4 left-0 w-[500px] h-[500px] bg-amber/10 rounded-full blur-[150px] pointer-events-none" />
      <div className="absolute bottom-1/3 right-0 w-[400px] h-[400px] bg-amber/8 rounded-full blur-[130px] pointer-events-none" />
      <div className="max-w-[1400px] mx-auto relative">
        <p className="text-sm font-mono text-amber-light tracking-widest uppercase mb-4">Example reels</p>
        <h2 className="text-3xl md:text-5xl font-bold tracking-[-0.03em] mb-16">
          Built with <span className="font-drama italic text-amber-light">Igloo.</span>
        </h2>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-5">
          {reels.map((reel, i) => (
            <ReelPlayer key={i} {...reel} />
          ))}
        </div>
      </div>
    </section>
  )
}

/* ═══════════════════════════════════════════
   CTA — Final Push
   ═══════════════════════════════════════════ */
function CTA() {
  const ref = useRef()

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from('.cta-content', {
        scrollTrigger: { trigger: ref.current, start: 'top 75%' },
        y: 40, opacity: 0, duration: 0.9, ease: 'power3.out',
      })
    }, ref)
    return () => ctx.revert()
  }, [])

  return (
    <section ref={ref} className="relative py-32 md:py-44 px-6 md:px-16 overflow-hidden">
      <div className="absolute inset-0 opacity-[0.15]">
        <img src="https://images.unsplash.com/photo-1478720568477-152d9b164e26?w=1920&q=60" alt="" className="w-full h-full object-cover" style={{ filter: 'brightness(0.3) sepia(0.4)' }} />
      </div>
      <div className="section-bg-mesh section-bg-cta" />
      {/* Ambient glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[400px] bg-amber/10 rounded-full blur-[100px] pointer-events-none" />

      <div className="cta-content relative max-w-[700px] mx-auto text-center">
        <h2 className="text-4xl md:text-6xl font-bold tracking-[-0.03em] mb-4">
          Ready to <span className="font-drama italic text-amber-light">forge?</span>
        </h2>
        <p className="text-base md:text-lg text-text-secondary font-light mb-10 max-w-[45ch] mx-auto leading-relaxed">
          Your first reel is minutes away. No account needed. No credit card. Just your idea.
        </p>
        <a href="http://localhost:5000" className="btn-magnetic inline-flex items-center gap-3 px-10 py-5 bg-amber text-void font-bold rounded-2xl text-lg hover:bg-amber-hover hover:shadow-[0_12px_48px_rgba(217,119,6,0.35)]">
          Create Your Reel <ArrowRight size={20} strokeWidth={2.5} />
        </a>
      </div>
    </section>
  )
}

/* ═══════════════════════════════════════════
   FOOTER
   ═══════════════════════════════════════════ */
function Footer() {
  return (
    <footer className="relative bg-void-light rounded-t-[3rem] md:rounded-t-[4rem] py-16 px-6 md:px-16 overflow-hidden">
      <div className="max-w-[1200px] mx-auto relative">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-16">
          <div className="md:col-span-2">
            <img src="/igloo-wordmark.png" alt="Igloo" className="block w-[200px] h-auto -ml-2 mb-3" />
            <p className="text-sm text-text-muted font-light max-w-[35ch] leading-relaxed">
              Video that stops thumbs. AI-powered reel creation from script to screen.
            </p>
          </div>
          <div>
            <h4 className="text-xs font-mono text-text-muted tracking-widest uppercase mb-4">Product</h4>
            <ul className="space-y-2">
              <li><a href="#features" className="text-sm text-text-secondary hover:text-text transition-colors">Features</a></li>
              <li><a href="#how-it-works" className="text-sm text-text-secondary hover:text-text transition-colors">How It Works</a></li>
              <li><a href="#examples" className="text-sm text-text-secondary hover:text-text transition-colors">Examples</a></li>
              <li><a href="/pricing.html" className="text-sm text-text-secondary hover:text-text transition-colors">Pricing</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-mono text-text-muted tracking-widest uppercase mb-4">Legal</h4>
            <ul className="space-y-2">
              <li><a href="/privacy.html" className="text-sm text-text-secondary hover:text-text transition-colors">Privacy</a></li>
              <li><a href="/terms.html" className="text-sm text-text-secondary hover:text-text transition-colors">Terms</a></li>
              <li><a href="/refund.html" className="text-sm text-text-secondary hover:text-text transition-colors">Refunds</a></li>
              <li><a href="/contact.html" className="text-sm text-text-secondary hover:text-text transition-colors">Contact</a></li>
            </ul>
          </div>
        </div>

        <div className="flex flex-col md:flex-row items-center justify-between pt-8 border-t border-border-subtle">
          <div className="flex items-center gap-2 text-xs font-mono text-text-muted mb-4 md:mb-0">
            <span className="w-2 h-2 rounded-full bg-success pulse-dot" />
            System Operational
          </div>
          <p className="text-xs text-text-muted">Igloo. Built with deterministic AI pipelines.</p>
        </div>
      </div>
    </footer>
  )
}

/* ═══════════════════════════════════════════
   APP
   ═══════════════════════════════════════════ */
export default function App() {
  return (
    <>
      <NoiseOverlay />
      <Navbar />
      <Hero />
      <Features />
      <Philosophy />
      <Protocol />
      <Examples />
      <CTA />
      <Footer />
    </>
  )
}
