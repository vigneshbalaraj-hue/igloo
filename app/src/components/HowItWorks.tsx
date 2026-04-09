"use client";

import { useRef, useState, useEffect } from "react";
import ScrollReveal from "./ScrollReveal";

const steps = [
  {
    number: "01",
    title: "Type your topic",
    description:
      "Your niche, your topic, your tone, your character. Fitness, finance, spirituality, parenting. Any vertical.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-accent">
        <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
      </svg>
    ),
  },
  {
    number: "02",
    title: "We make it",
    description:
      "We write the script. We generate the visuals. Don't like the voice, the character, or the script? Regenerate any of them.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-accent">
        <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
        <path d="M7 2v20" /><path d="M17 2v20" /><path d="M2 12h20" /><path d="M2 7h5" /><path d="M2 17h5" /><path d="M17 7h5" /><path d="M17 17h5" />
      </svg>
    ),
  },
  {
    number: "03",
    title: "Post it",
    description:
      "You get an MP4 in minutes. Instagram, TikTok, YouTube Shorts. Wherever your audience lives.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-accent">
        <path d="M22 2 11 13" /><path d="m22 2-7 20-4-9-9-4Z" />
      </svg>
    ),
  },
];

export default function HowItWorks() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(true);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    v.play().catch(() => {});
  }, []);

  const toggleMute = () => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = !v.muted;
    setMuted(v.muted);
    if (!v.muted) {
      v.play().catch(() => {});
    }
  };

  return (
    <section id="how-it-works" className="relative z-10 py-28 md:py-40">
      <div className="max-w-[1400px] mx-auto px-6 md:px-12">
        <ScrollReveal>
          <div className="text-center">
            <span className="eyebrow mb-6 mx-auto">How it works</span>
            <h2 className="text-3xl md:text-5xl font-light tracking-tight leading-tight mt-4 max-w-lg mx-auto">
              One topic. One video. Done.
            </h2>
          </div>
        </ScrollReveal>

        {/* Cinema block — contained video */}
        <ScrollReveal className="mt-16">
          <div className="relative aspect-video max-w-4xl mx-auto rounded-2xl border border-border-subtle overflow-hidden">
              <video
                ref={videoRef}
                className="absolute inset-0 w-full h-full object-cover"
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                poster="/hero-poster.jpg"
              >
                <source src="/igloo-ad.mp4" type="video/mp4" />
                <source src="/igloo-ad.webm" type="video/webm" />
              </video>

            {/* Mute/Unmute */}
            <button
              onClick={toggleMute}
              className="absolute bottom-4 right-4 z-20 w-10 h-10 rounded-full glass flex items-center justify-center text-foreground/70 hover:text-foreground transition-colors duration-300"
              aria-label={muted ? "Unmute" : "Mute"}
            >
              {muted ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  <line x1="23" y1="9" x2="17" y2="15" />
                  <line x1="17" y1="9" x2="23" y2="15" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                  <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                </svg>
              )}
            </button>
          </div>
        </ScrollReveal>

        {/* Step cards */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6">
          {steps.map((step, i) => (
            <ScrollReveal key={step.number}>
              <div
                className="group relative h-full rounded-[2rem] border border-border-subtle bg-surface p-8 md:p-10 transition-all duration-700 ease-[cubic-bezier(0.32,0.72,0,1)] hover:border-border-hover hover:bg-surface-elevated"
                style={{ transitionDelay: `${i * 80}ms` }}
              >
                {/* Outer shell glow on hover */}
                <div className="absolute -inset-px rounded-[2rem] bg-accent/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700 -z-10 blur-xl" />

                <div className="flex items-center gap-4 mb-6">
                  <div className="w-10 h-10 rounded-full glass flex items-center justify-center">
                    {step.icon}
                  </div>
                  <span className="font-mono text-xs text-text-muted">{step.number}</span>
                </div>

                <h3 className="text-xl font-medium tracking-tight text-foreground">
                  {step.title}
                </h3>
                <p className="mt-3 text-sm text-text-secondary leading-relaxed">
                  {step.description}
                </p>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
