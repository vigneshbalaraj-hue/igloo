"use client";

import { useEffect, useRef, useCallback } from "react";
import ScrollReveal from "./ScrollReveal";

const reels = [
  "/reels/fasting-wellness.mp4",
  "/reels/hanuman-lanka.mp4",
  "/reels/spiritual-growth.mp4",
  "/reels/igloo-promo.mp4",
  "/reels/dutch-dyke.mp4",
  "/reels/index-funds.mp4",
  "/reels/kedarnath.mp4",
  "/reels/penguin-global-warming.mp4",
];

// 8 unique reels — each appears once per track copy.
// fullTrack duplication (below) handles the seamless CSS loop.
const trackItems = [
  { src: reels[0], offset: 0 },
  { src: reels[1], offset: 0 },
  { src: reels[2], offset: 0 },
  { src: reels[3], offset: 0 },
  { src: reels[4], offset: 0 },
  { src: reels[5], offset: 0 },
  { src: reels[6], offset: 0 },
  { src: reels[7], offset: 0 },
];

// Duplicate for seamless infinite CSS loop (translateX -50%)
const fullTrack = [...trackItems, ...trackItems];

export default function Showcase() {
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([]);

  const setRef = useCallback(
    (index: number) => (el: HTMLVideoElement | null) => {
      videoRefs.current[index] = el;
    },
    [],
  );

  const marqueeRef = useRef<HTMLDivElement>(null);

  /* Apply currentTime offsets for staggered playback */
  useEffect(() => {
    videoRefs.current.forEach((video, i) => {
      if (!video) return;
      const offset = fullTrack[i].offset;
      if (offset === 0) return;
      const apply = () => {
        video.currentTime = offset;
      };
      if (video.readyState >= 1) {
        apply();
      } else {
        video.addEventListener("loadedmetadata", apply, { once: true });
      }
    });
  }, []);

  /* Lazy video activation — only play/load videos when marquee is in viewport.
     Prevents iOS from choking on 16 simultaneous video decoders. */
  useEffect(() => {
    const marquee = marqueeRef.current;
    if (!marquee) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        videoRefs.current.forEach((video) => {
          if (!video) return;
          if (entry.isIntersecting) {
            video.src = video.dataset.src || "";
            video.play().catch(() => {});
          } else {
            video.pause();
            video.removeAttribute("src");
            video.load();
          }
        });
      },
      { rootMargin: "200px 0px" },
    );

    observer.observe(marquee);
    return () => observer.disconnect();
  }, []);

  return (
    <section id="showcase" className="relative z-10 py-28 md:py-40">
      <div className="max-w-[1400px] mx-auto px-6 md:px-12">
        <ScrollReveal>
          <div className="text-center max-w-2xl mx-auto">
            <span className="eyebrow mb-6 mx-auto">Showcase</span>
            <h2 className="text-3xl md:text-5xl font-light tracking-tight leading-tight mt-4 sr-only">
              Showcase
            </h2>
          </div>
        </ScrollReveal>

        {/* Reel marquee — horizontal auto-scrolling showcase */}
        <ScrollReveal className="mt-12">
          <div ref={marqueeRef} className="reel-marquee-mask overflow-hidden">
            <div className="reel-marquee-track">
              {fullTrack.map((item, i) => (
                <div
                  key={i}
                  className="shrink-0 w-[180px] md:w-[220px] aspect-[9/16] rounded-2xl overflow-hidden"
                >
                  <video
                    ref={setRef(i)}
                    data-src={item.src}
                    muted
                    loop
                    playsInline
                    className="w-full h-full object-cover"
                  />
                </div>
              ))}
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
