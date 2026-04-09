import ScrollReveal from "./ScrollReveal";

export default function Problem() {
  return (
    <section className="relative z-10 py-28 md:py-40">
      <div className="max-w-[1400px] mx-auto px-6 md:px-12">
        <ScrollReveal>
          <div className="text-center max-w-2xl mx-auto">
            <span className="eyebrow mb-6 mx-auto">The problem</span>
            <h2 className="text-3xl md:text-5xl font-light tracking-tight leading-tight mt-4">
              Every option is broken.
            </h2>
            <p className="mt-4 text-text-secondary text-base md:text-lg leading-relaxed">
              Every other option is either faceless, or cliched, or not photorealistic.
            </p>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
