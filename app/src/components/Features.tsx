"use client";

import { useRef, useEffect, useState, useCallback } from "react";

const TOTAL_FRAMES = 59;
const FRAME_PATH = "/features-frames/frame_";

const features = [
  {
    number: "01",
    title: "Unscrollable",
    description:
      "Hooks that make someone pause mid-scroll. Not summaries. Not listicles. Every script challenges a belief.",
  },
  {
    number: "02",
    title: "Cinematic",
    description:
      "Every frame generated from scratch. No stock footage. Narration that sounds like a Netflix doc.",
  },
  {
    number: "03",
    title: "Niche-proof",
    description:
      "Fitness, finance, parenting, spirituality, wellness. One engine, any brand.",
  },
];

function padFrame(n: number): string {
  return String(n).padStart(4, "0");
}

export default function Features() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imagesRef = useRef<HTMLImageElement[]>([]);
  const currentFrameRef = useRef(0);
  const targetFrameRef = useRef(0);
  const rafRef = useRef<number>(0);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loaded, setLoaded] = useState(false);

  /* Preload all frames */
  useEffect(() => {
    let mounted = true;
    const images: HTMLImageElement[] = [];
    let loadedCount = 0;

    for (let i = 1; i <= TOTAL_FRAMES; i++) {
      const img = new Image();
      img.src = `${FRAME_PATH}${padFrame(i)}.jpg`;
      img.onload = () => {
        loadedCount++;
        if (loadedCount === TOTAL_FRAMES && mounted) {
          imagesRef.current = images;
          setLoaded(true);
          drawFrame(0);
        }
      };
      images.push(img);
    }

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const drawFrame = useCallback((index: number) => {
    const canvas = canvasRef.current;
    const images = imagesRef.current;
    if (!canvas || !images.length) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const clampedIndex = Math.max(0, Math.min(TOTAL_FRAMES - 1, index));
    const img = images[clampedIndex];
    if (!img) return;

    if (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
    }

    ctx.drawImage(img, 0, 0);
  }, []);

  /* Lerp animation loop — smoothly interpolates between current and target frame */
  useEffect(() => {
    let animating = true;

    const tick = () => {
      if (!animating) return;

      const current = currentFrameRef.current;
      const target = targetFrameRef.current;
      const diff = target - current;

      /* Lerp factor: 0.12 gives ~8 frames to converge, smooth but responsive */
      if (Math.abs(diff) > 0.3) {
        const next = current + diff * 0.12;
        currentFrameRef.current = next;
        drawFrame(Math.round(next));
      } else if (Math.round(current) !== Math.round(target)) {
        currentFrameRef.current = target;
        drawFrame(Math.round(target));
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      animating = false;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [drawFrame]);

  /* Scroll handler — sets target frame + active text index */
  useEffect(() => {
    const onScroll = () => {
      const section = sectionRef.current;
      if (!section) return;

      const rect = section.getBoundingClientRect();
      const scrollable = section.offsetHeight - window.innerHeight;
      const scrolled = -rect.top;
      const progress = Math.max(0, Math.min(1, scrolled / scrollable));

      /* Set target frame for lerp */
      targetFrameRef.current = progress * (TOTAL_FRAMES - 1);

      /* Cycle through the 3 specialties */
      setActiveIndex(progress >= 1 ? 2 : Math.floor(progress * 3));
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <section
      ref={sectionRef}
      id="features"
      className="relative z-10"
      style={{ height: "300vh" }}
    >
      <div className="sticky top-0 h-screen flex flex-col items-center justify-center px-4 md:px-12">
        {/* Section heading */}
        <div className="text-center mb-6 md:mb-10">
          <span className="eyebrow mx-auto">What makes Igloo different</span>
          <h2 className="text-2xl md:text-4xl lg:text-5xl font-light tracking-tight leading-tight mt-3">
            Videos with a point of view.
          </h2>
        </div>

        {/* Canvas + text container — mask fades edges to transparent */}
        <div className="relative w-full max-w-[1100px] aspect-video features-vignette">
          {/* Canvas element — draws preloaded frames on scroll */}
          <canvas
            ref={canvasRef}
            className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-500 ${
              loaded ? "opacity-100" : "opacity-0"
            }`}
            style={{ objectFit: "cover" }}
          />

          {/* Loading placeholder */}
          {!loaded && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
            </div>
          )}

          {/* Left gradient — text readability over image */}
          <div className="absolute inset-0 bg-gradient-to-r from-black/70 via-black/25 to-transparent pointer-events-none" />

          {/* Text overlay — bottom on mobile, left-center on desktop */}
          <div className="absolute inset-0 flex items-end md:items-center p-5 pb-6 md:p-12">
            <div className="w-full md:max-w-sm">
              {/* Grid stacks all items in the same cell for crossfade */}
              <div className="grid [&>*]:col-start-1 [&>*]:row-start-1">
                {features.map((feat, i) => (
                  <div
                    key={feat.title}
                    className="features-text-block"
                    style={{
                      opacity: activeIndex === i ? 1 : 0,
                      transform: `translateY(${
                        activeIndex === i ? 0 : i < activeIndex ? -20 : 20
                      }px)`,
                      pointerEvents: activeIndex === i ? "auto" : "none",
                    }}
                  >
                    <span className="text-accent-bright font-mono text-xs md:text-sm tracking-widest">
                      {feat.number}
                    </span>
                    <h3 className="text-xl md:text-3xl lg:text-4xl font-light tracking-tight text-white mt-1 md:mt-2 features-text-glow">
                      {feat.title}
                    </h3>
                    <p className="text-xs md:text-sm text-white/90 mt-2 md:mt-3 leading-relaxed max-w-[38ch] features-text-glow">
                      {feat.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Progress dots */}
        <div className="flex items-center gap-2 mt-6">
          {features.map((feat, i) => (
            <div
              key={feat.title}
              className="features-dot"
              style={{
                width: activeIndex === i ? 24 : 6,
                background:
                  activeIndex === i
                    ? "var(--accent)"
                    : "rgba(255,255,255,0.15)",
              }}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
