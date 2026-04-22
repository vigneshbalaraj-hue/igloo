import "@/styles/landing.css";
import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Problem from "@/components/Problem";
import HowItWorks from "@/components/HowItWorks";
import Features from "@/components/Features";
import Showcase from "@/components/Showcase";
import FinalCTA from "@/components/FinalCTA";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <div className="landing-theme">
      {/* Background layers */}
      <div className="mesh-gradient" />
      <div className="noise-overlay" />

      {/* Navigation */}
      <Navbar />

      {/* Sections */}
      <main className="relative z-10">
        <Hero />
        <Problem />

        <HowItWorks />
        <Features />
        <Showcase />
        <FinalCTA />
      </main>

      <Footer />
    </div>
  );
}
