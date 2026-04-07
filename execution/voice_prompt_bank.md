# Igloo Voice Prompt Bank

> **Purpose:** This document is the mandatory reference for generating ElevenLabs voice prompts. It sits between the validated script and the TTS API calls. Every reel's voice generation reads this file. The LLM that constructs voice prompts must internalize these rules before generating any voice direction.
>
> **Scope:** Controls ElevenLabs Voice Design (text-to-voice) prompts and per-section TTS parameters. Does NOT select voice IDs — it creates voice descriptions from scratch per section.
>
> **Last updated:** 2026-04-07

---

## Part 1 — Universal Voice Rules (Apply to ALL sections, ALL niches)

These rules are non-negotiable. Every voice prompt the system generates must satisfy all of them. If a rule conflicts with a phase-specific instruction, the universal rule wins unless explicitly overridden.

### The Narrator

One narrator across all niches. The voice identity stays constant — what changes is the *performance*.

| Rule | Why |
|------|-----|
| **Single narrator identity across niches** | Brand consistency. The viewer should recognize Igloo's voice the way they recognize a Netflix narrator. The *content* changes per niche, not the voice. |
| **Netflix documentary tone is the baseline** | Authoritative, measured, slightly intense. Every section starts from this baseline and modulates up or down. If in doubt, return to documentary narrator. |
| **Male, 30s-40s, neutral accent with slight warmth** | The default casting. Specific enough to be consistent, broad enough to work across spirituality, finance, fitness, parenting, wellness. Adjust only if user explicitly overrides. |
| **Never robotic, never over-performed** | The voice should sound like a real human narrating — not a text-to-speech engine, and not a stage actor. The sweet spot is "someone telling you something important in a quiet room." |
| **Emotion is conveyed through pacing and weight, not volume** | ElevenLabs Voice Design responds better to pacing/cadence descriptions than to "loud" or "soft." Describe delivery rhythm, not amplitude. |

### Base Voice Design Prompt (The Casting)

This is the foundation prompt that establishes the narrator's identity. Every per-section voice prompt starts by inheriting this, then adds emotional modifiers.

```
A male narrator in his mid-30s with a composed, authoritative voice. Slight natural warmth underneath a serious tone. Speaks like a documentary narrator — measured, deliberate, never rushed. Neutral accent with clear diction. The kind of voice that makes you stop scrolling and listen. Not a broadcaster, not a podcaster — a storyteller with gravitas.
```

**Why this specific description:**
- "Mid-30s" — avoids the too-young TikTok energy and the too-old lecture tone
- "Composed, authoritative" — Netflix documentary baseline
- "Slight natural warmth underneath a serious tone" — prevents cold/robotic delivery
- "Measured, deliberate, never rushed" — pacing anchor that each section modulates
- "Neutral accent with clear diction" — consistent across niches without sounding generic
- "Storyteller with gravitas" — the key identity. Not informing — narrating

### Voice Generation Parameters

These ElevenLabs TTS settings apply universally. Phase-specific overrides are in Part 2.

| Parameter | Default Value | Why |
|-----------|---------------|-----|
| **Stability** | `0.40` | Lower than default (0.50). We want expressive variation, not monotone consistency. The script's emotional range requires the voice to breathe. |
| **Similarity Boost** | `0.75` | High enough to maintain narrator identity across sections. Not maxed — leave room for emotional coloring. |
| **Style** | `0.60` | Above midpoint. Pushes toward more expressive, emotionally colored delivery. Below 0.50 sounds flat. Above 0.80 becomes theatrical. |
| **Speaker Boost** | `true` | Enhances clarity and presence. Non-negotiable for short-form content competing with thumb-scrolling. |

### Anti-Flat-Voice Checklist

Before finalizing any voice prompt, verify:

- [ ] Does the prompt describe *how* the narrator delivers, not just *what* they sound like?
- [ ] Is pacing explicitly specified (not just "speaks naturally")?
- [ ] Is there at least one emotional descriptor beyond "authoritative"?
- [ ] Does the prompt avoid vague terms like "engaging," "dynamic," or "professional"?
- [ ] Would a voice director reading this prompt know exactly what performance to ask for?
- [ ] Does the prompt include at least one physical delivery cue (pause placement, breath, weight on specific words)?

---

## Part 2 — Phase-Specific Voice Prompts (The Performance Map)

Each script has 4 phases. Each phase gets its own ElevenLabs TTS call with a tailored voice prompt. The narrator identity stays the same — the delivery shifts.

**How to read this section:** Each phase has:
- **Emotional intent** — what the viewer should feel
- **Voice prompt modifier** — appended to the base voice design prompt
- **TTS parameter overrides** — phase-specific settings that override Part 1 defaults
- **Text annotation rules** — how to mark up the script text for this phase
- **What to avoid** — common failure modes

---

### Phase 1: HOOK (0-3 seconds)

**Emotional intent:** Pattern interrupt. Tension. The viewer's internal response should be "wait, what?"

**Voice prompt modifier:**
```
Delivering an opening line that stops someone mid-scroll. Slightly lower pitch than normal speaking voice. Deliberate, weighted pacing — every word lands with intention. A half-beat pause after the first clause. Not aggressive, not shouting — controlled intensity. Like a prosecutor's opening statement. The kind of delivery where silence between words carries as much meaning as the words themselves.
```

**TTS parameter overrides:**

| Parameter | Value | Why |
|-----------|-------|-----|
| Stability | `0.35` | Slightly lower — we want the voice to commit to the emotional weight, not play it safe |
| Style | `0.70` | Higher expressiveness for the hook. This is the most performative moment in the reel |

**Text annotation rules for hook:**
- Add `...` after the first clause if the hook is a contrarian claim (creates the "wait" beat)
- Use em dashes (`—`) for abrupt pivots: "Every guru tells you to meditate — they're wrong."
- Keep sentences short. One idea per sentence. The voice needs room to land each one.
- NO exclamation marks. Intensity comes from the voice prompt, not punctuation. Exclamation marks make TTS sound like an infomercial.

**What to avoid:**
- "Excited" or "energetic" — this is tension, not excitement. Excitement sounds like YouTube, not Netflix.
- "Whisper" — too quiet for a scroll-stopping hook. The voice needs presence.
- "Fast-paced" — speed kills gravitas. The hook is slow and heavy, not quick.

---

### Phase 2: AGITATION (3-20 seconds)

**Emotional intent:** Building unease. Deepening the problem. The viewer should feel the ground shifting under something they believed.

**Voice prompt modifier:**
```
Building a case with mounting intensity. Pacing gradually increases from the hook's deliberate weight — not fast, but gaining momentum like a documentary building to a revelation. Tone carries controlled frustration, like someone who's seen the truth and can't believe no one's talking about it. Emphasis lands on specific details — names, numbers, dates — these words get slightly more weight. Pauses shorten between sentences as the argument builds. Still measured, still authoritative, but now there's an undercurrent of urgency.
```

**TTS parameter overrides:**

| Parameter | Value | Why |
|-----------|-------|-----|
| Stability | `0.40` | Back to default — we want steady build, not wild variation |
| Style | `0.65` | Slightly above default — the controlled frustration needs room to breathe |

**Text annotation rules for agitation:**
- Use commas liberally to create natural breath points: "Not a study, not a trial, a magazine article from 1974."
- Em dashes for revelatory pivots: "They call it a wellness practice — it's a $4.2 billion industry."
- Place specific details (names, numbers, studies) at the END of sentences — this is where emphasis naturally falls in speech, and it gives the voice prompt room to weight them.
- Shorten sentence length as the phase progresses. First agitation sentence: 15-20 words. Last agitation sentence: 5-10 words. This creates accelerating rhythm the TTS will follow.

**What to avoid:**
- "Angry" or "frustrated" — too hot. This is controlled concern, not rage. Anger alienates the viewer.
- "Questioning" or "uncertain" — the narrator is not unsure. They know exactly what they're revealing. Uncertainty kills authority.
- "Conversational" — this phase is not casual. It's a building argument.

---

### Phase 3: REFRAME (20-40 seconds)

**Emotional intent:** The reveal. The paradigm shift. The viewer should feel the "oh" moment — the insight that recontextualizes everything before it.

**Voice prompt modifier:**
```
Delivering the core revelation with the weight it deserves. Pacing slows noticeably from the agitation — this is the moment the documentary score drops out and the narrator says the thing that changes everything. Tone shifts from building urgency to calm, absolute authority. Like a teacher who just said the one sentence that will stay with you for years. Pauses are longer and more deliberate here — let the insight land. Voice carries quiet conviction. Not triumphant, not smug — just certain. The gravity is in the stillness.
```

**TTS parameter overrides:**

| Parameter | Value | Why |
|-----------|-------|-----|
| Stability | `0.30` | Lowest point in the reel. The reframe needs maximum emotional expression — this is the payload |
| Style | `0.75` | Highest expressiveness. This section carries the entire reel's reason to exist |

**Text annotation rules for reframe:**
- Begin the reframe with a transitional pause: "And here's what nobody explains..." or place `...` before the key insight.
- The single most important sentence in the reframe gets its own line — no compound clauses, no qualifiers. Just the insight. Alone. The TTS will naturally weight a short isolated sentence more heavily.
- Use periods instead of commas to force full stops between ideas. "It wasn't the method. It wasn't the dosage. It was the timing." — each period creates a beat the voice will honor.
- After the key insight, one longer sentence (20-25 words) that expands it. This breathing room prevents the reframe from feeling like a list of punches.

**What to avoid:**
- "Dramatic" or "cinematic" — these are vague. Describe the specific quality: slow, weighted, certain, still.
- "Emotional" without specifying which emotion — the reframe emotion is *quiet certainty*, not sadness or joy.
- "Pause for effect" — too theatrical. The pauses come from the text structure (periods, ellipses), not from telling the voice to perform pauses.

---

### Phase 4: CTA (40-60 seconds)

**Emotional intent:** Bridge from insight to action. The viewer should feel invited, not sold to. The tone shifts from "narrator" to "someone who just shared something real and is pointing you toward more."

**Voice prompt modifier:**
```
Transitioning from the weight of the revelation to a warmer, more direct address. Pacing returns to a natural, slightly relaxed tempo — the intensity has passed, and now the narrator is speaking to you personally. Tone is warm but not soft — still carries authority, but the edge is gone. Like the moment after a documentary's climax when the narrator offers a quiet closing thought. Delivery feels like a genuine recommendation from someone who has no reason to lie to you. Measured, unhurried, definitive.
```

**TTS parameter overrides:**

| Parameter | Value | Why |
|-----------|-------|-----|
| Stability | `0.50` | Higher than any other section. The CTA must sound natural and consistent — vocal wobble here sounds like uncertainty, which kills conversion |
| Style | `0.55` | Pulled back slightly. The CTA should feel real, not performed. Lower style = more natural = more trustworthy |

**Text annotation rules for CTA:**
- The CTA opens with a callback to the reframe insight — this bridges the transition: "If that changed how you think about fasting..."
- One sentence for the callback. One sentence for the action. Maximum two sentences total.
- Use a period between the callback and the action, not a comma. The period creates a beat that makes the action feel like a separate, considered recommendation — not a tacked-on pitch.
- NO ellipses in the CTA. Ellipses create uncertainty. The CTA is definitive.
- Final word of the script should be concrete (a noun or action), not abstract. "...the full breakdown is in the link." not "...there's more to explore."

**What to avoid:**
- "Enthusiastic" or "upbeat" — this is warm authority, not sales energy. Enthusiasm in a CTA sounds like an ad.
- "Call to action tone" — if you have to describe it as a CTA, the TTS will make it sound like one. Describe the *human quality* instead: warm, direct, unhurried.
- "Urgent" — urgency in a CTA is a scarcity tactic. This narrator is above that. The insight speaks for itself.

---

## Part 3 — Script Text Annotation Reference

These rules govern how the script text itself is modified before being sent to ElevenLabs TTS. The voice prompt controls the *voice*. The text annotations control the *performance of specific words and phrases*.

**Principle:** Voice prompt sets the emotional frame. Text annotations fine-tune the delivery within that frame. Both are required. A great voice prompt with unannotated text produces generic delivery. Annotated text with a generic voice prompt produces erratic delivery. They work together.

### Annotation Toolkit

| Annotation | What it does | When to use | Example |
|------------|-------------|-------------|---------|
| `...` (ellipsis) | Creates a 0.5-1s breath pause | Before a revelation, after a hook's first clause | `"Gratitude journaling... is spiritual bypassing."` |
| `—` (em dash) | Creates an abrupt tonal pivot | When the sentence changes direction mid-thought | `"Every trainer says 3 sets of 12 — that's not a program."` |
| `.` (period between short sentences) | Forces full stop + micro-pause | When stacking punches for rhythm | `"It wasn't toys. It wasn't curriculum. It was presence."` |
| `,` (comma clusters) | Creates breath-point pacing | When listing specifics that need individual weight | `"Not a study, not a trial, a magazine article."` |
| Single-sentence paragraph | Forces the TTS to weight the sentence heavily | The key insight in the reframe | `"The window had closed."` |
| Short sentence after long sentence | Creates rhythmic contrast | Throughout — prevents monotone cadence | `"The studies used 2,000mg of curcumin with piperine to boost absorption by 2,000%. Your latte has 200mg."` |

### What NOT to use

| Don't | Why |
|-------|-----|
| `!` (exclamation marks) | Makes TTS sound like an infomercial or children's show host. Intensity comes from the voice prompt, not punctuation |
| ALL CAPS | Unpredictable in TTS — sometimes creates shouting, sometimes ignored. Use voice prompt emphasis descriptions instead |
| `*asterisks*` or `_underscores_` | Markdown formatting. TTS engines ignore or mispronounce them |
| `(parentheses)` | TTS reads them as asides with dropped volume. Destroys authority |
| `;` (semicolons) | Too formal. Creates an awkward pause that sounds like a reading error, not a natural breath |
| `""` (quotes within speech) | TTS may shift to a "quoting" voice. Rephrase as indirect speech instead |

### Annotation by Phase

| Phase | Primary annotations | Rhythm pattern |
|-------|-------------------|----------------|
| **Hook** | `...` after first clause, `—` for pivots | Slow, heavy, spaced |
| **Agitation** | `,` clusters, shortening sentences | Accelerating, building |
| **Reframe** | `.` between punches, isolated key sentence | Slow, weighted, then one long breath |
| **CTA** | `.` between callback and action, concrete final word | Natural, even, definitive |

---

## Part 4 — Examples

### Format

Each phase has one **GOOD** voice prompt and one **BAD** voice prompt. Good examples follow every rule in this document. Bad examples are annotated with exactly why they fail.

**Note:** These examples show the FULL voice prompt sent to ElevenLabs — the base narrator prompt + the phase modifier combined.

---

### HOOK — GOOD Example

**Script line:** `"Gratitude journaling... is the most popular form of spiritual bypassing on the planet."`

**Full voice prompt:**
```
A male narrator in his mid-30s with a composed, authoritative voice. Slight natural warmth underneath a serious tone. Neutral accent with clear diction. Delivering an opening line that stops someone mid-scroll. Slightly lower pitch than normal speaking voice. Deliberate, weighted pacing — every word lands with intention. A half-beat pause after "journaling." Not aggressive, not shouting — controlled intensity. Like a prosecutor's opening statement. The silence between words carries as much meaning as the words themselves.
```

**Why this works:**
- Inherits the base narrator identity (mid-30s, composed, authoritative)
- Adds hook-specific performance (lower pitch, weighted pacing, prosecutor's opening)
- References the specific text ("half-beat pause after journaling") — ties the voice prompt to the actual script
- Physical delivery cues ("silence between words") give the TTS engine concrete direction
- No vague descriptors — every adjective maps to an audible quality

---

### HOOK — BAD Example

**Script line:** `"Gratitude journaling is the most popular form of spiritual bypassing on the planet."`

**Full voice prompt:**
```
❌ An engaging male narrator with a dynamic and professional voice. Speaks clearly and confidently. Good energy and pacing. Sounds interesting and attention-grabbing.
```

**Why this fails:**
- **"Engaging"** — meaningless. Every voice prompt should be engaging. This tells the TTS nothing about HOW to engage
- **"Dynamic and professional"** — contradictory mush. Dynamic implies variation. Professional implies restraint. Which one?
- **"Good energy and pacing"** — what energy? Fast? Slow? Intense? Measured? "Good" is not a direction
- **"Sounds interesting and attention-grabbing"** — describing the desired EFFECT, not the CAUSE. Don't tell the voice to be interesting. Tell it HOW to be interesting (pacing, pitch, pause placement)
- **No reference to the script text** — the hook word "journaling" needs a pause after it. This prompt doesn't know the script exists
- **No emotional specificity** — the hook needs tension, controlled intensity, prosecutorial weight. This prompt asks for "confidence" — the blandest possible performance
- **Script text has no ellipsis** — "journaling is" runs together. The pause that creates the hook's tension is missing

---

### AGITATION — GOOD Example

**Script line:** `"Three sets of twelve became the default because it showed up in a 1974 bodybuilding magazine. Not a study, not a trial, a magazine. And the entire commercial gym industry copy-pasted it for fifty years."`

**Full voice prompt:**
```
A male narrator in his mid-30s with a composed, authoritative voice. Slight natural warmth underneath a serious tone. Neutral accent with clear diction. Building a case with mounting intensity. Pacing gradually increases — not fast, but gaining momentum. Tone carries controlled frustration, like someone who's seen the truth and can't believe no one talks about it. Extra weight on "1974," "magazine," and "fifty years" — these are the evidence. Pauses shorten between sentences as the argument builds. Still measured, still authoritative, but now there's an undercurrent of urgency.
```

**Why this works:**
- Base narrator identity intact
- Calls out specific words that need emphasis ("1974," "magazine," "fifty years")
- Describes emotional quality precisely ("controlled frustration" not "angry" or "passionate")
- Pacing direction is relative ("gradually increases," "pauses shorten") — gives the TTS a trajectory, not a fixed state
- The metaphor ("like someone who's seen the truth") gives the TTS an actable intention

---

### AGITATION — BAD Example

**Script line:** `"Three sets of twelve became the default because it showed up in a 1974 bodybuilding magazine. Not a study not a trial a magazine. And the entire commercial gym industry copy-pasted it for fifty years."`

**Full voice prompt:**
```
❌ Narrator sounds frustrated and passionate about this topic. Speaking faster now to build excitement. Voice gets louder as the argument progresses. Energetic and persuasive delivery.
```

**Why this fails:**
- **"Frustrated and passionate"** — too hot. Controlled frustration ≠ audible anger. This produces a ranting delivery
- **"Speaking faster"** — faster ≠ building intensity. Speed without weight sounds breathless, not authoritative
- **"Voice gets louder"** — volume-based direction doesn't work well in TTS. Pacing and weight are the levers
- **"Energetic and persuasive"** — this is YouTube energy, not documentary energy. The agitation should feel like evidence mounting, not a sales pitch building
- **No specific word emphasis** — the numbers and dates ("1974," "fifty years") are the anchors of the argument. Without calling them out, they get the same weight as filler words
- **Script text is missing commas** — "Not a study not a trial a magazine" runs together as one thought. With commas ("Not a study, not a trial, a magazine.") each item gets individual weight

---

### REFRAME — GOOD Example

**Script line:** `"And here's the finding that should rewrite every parenting book on your shelf... The children who were moved to foster care before age two? Most of them recovered. After age two? The window had largely closed."`

**Full voice prompt:**
```
A male narrator in his mid-30s with a composed, authoritative voice. Slight natural warmth underneath a serious tone. Neutral accent with clear diction. Delivering the core revelation with the weight it deserves. Pacing slows noticeably — this is the moment the documentary score drops out. Tone shifts to calm, absolute authority. Longer, more deliberate pauses between sentences. Voice carries quiet conviction — not triumphant, not smug, just certain. Extra weight on "before age two" and "the window had largely closed." The gravity is in the stillness between those phrases.
```

**Why this works:**
- Explicit pacing direction ("slows noticeably") — tells TTS exactly how this section differs from agitation
- Cinematic metaphor ("the moment the documentary score drops out") — gives the TTS an actable scene
- Emotional precision ("quiet conviction — not triumphant, not smug, just certain") — three things it's NOT prevents overcorrection
- Calls out the two phrases that carry the payload ("before age two" and "the window had largely closed")
- "The gravity is in the stillness" — tells TTS that pauses are intentional and should be honored, not filled

---

### REFRAME — BAD Example

**Script line:** `"And here's the finding that should rewrite every parenting book on your shelf. The children who were moved to foster care before age two, most of them recovered, after age two the window had largely closed."`

**Full voice prompt:**
```
❌ Now the narrator reveals the big insight. Voice becomes very dramatic and emotional. Slow, cinematic delivery. Pause for effect before the key line. This should feel like a movie moment.
```

**Why this fails:**
- **"Very dramatic and emotional"** — which emotion? This produces melodrama. The reframe needs quiet certainty, not theatrical weight
- **"Slow, cinematic delivery"** — vague. How slow? Slower than what? "Cinematic" means nothing to a TTS engine
- **"Pause for effect"** — theatrical direction. Pauses should come from text structure (ellipses, periods), not from telling the voice to perform
- **"This should feel like a movie moment"** — describing the effect, not the cause. The GOOD prompt describes specific delivery qualities that PRODUCE the feeling
- **Script text uses commas instead of periods** — "most of them recovered, after age two the window had largely closed" is one run-on thought. The periods in the good version ("Most of them recovered. After age two? The window had largely closed.") create the beats that make the reframe land
- **No specific word emphasis** — "before age two" is the hinge of the entire insight. Without calling it out, it's just another phrase

---

### CTA — GOOD Example

**Script line:** `"One study. One variable. If that changes how you think about what your kid actually needs, the deeper research is in the link."`

**Full voice prompt:**
```
A male narrator in his mid-30s with a composed, authoritative voice. Slight natural warmth underneath a serious tone. Neutral accent with clear diction. Transitioning from the weight of the revelation to a warmer, more direct address. Pacing returns to a natural, slightly relaxed tempo — the intensity has passed. Tone is warm but not soft — still carries authority, but the edge is gone. Delivery feels like a genuine recommendation from someone with no reason to lie. Measured, unhurried. The final phrase lands with quiet confidence, not urgency.
```

**Why this works:**
- Explicit transition from previous phase ("the intensity has passed")
- Emotional quality is precise ("warm but not soft," "genuine recommendation")
- Describes what the voice is NOT ("no reason to lie," "not urgency") — prevents sales-pitch delivery
- Pacing is relative to previous section ("returns to natural") — the TTS understands the shift
- "Quiet confidence" for the final phrase — the last thing the viewer hears should feel definitive

---

### CTA — BAD Example

**Script line:** `"If that changes how you think about what your kid actually needs, the deeper research is in the link!"`

**Full voice prompt:**
```
❌ Upbeat and friendly narrator wrapping up the video. Encouraging tone, like inviting the viewer to take action. Clear call to action with enthusiasm. Warm and inviting.
```

**Why this fails:**
- **"Upbeat and friendly"** — tonal whiplash from a documentary reframe about Romanian orphans. The CTA must feel continuous, not like a different show started
- **"Encouraging tone"** — patronizing. The narrator is not your cheerleader. They're someone who shared something real
- **"Clear call to action with enthusiasm"** — if you describe it as a CTA, the TTS will deliver it like an ad. Describe the human quality instead
- **"Warm and inviting"** — too soft. The narrator still carries authority. "Warm but not soft" is the target
- **Script text ends with `!`** — the exclamation mark will make the TTS spike in energy on the final word. The CTA should land with quiet confidence, not enthusiasm. Period, not exclamation
- **No reference to the tonal shift from reframe** — without explicit transition guidance, the TTS may either maintain reframe intensity (too heavy) or snap to a completely different voice (jarring)

---

## Part 5 — Voice Prompt Assembly Checklist

Before sending any voice prompt to ElevenLabs, verify against this checklist:

### Per-Section Checks

- [ ] Voice prompt starts with the base narrator description (Part 1)
- [ ] Phase-specific modifier is appended (Part 2)
- [ ] At least 2 specific words from the script are called out for emphasis
- [ ] Pacing is described relative to the previous section (except hook, which is absolute)
- [ ] Emotional quality uses precise descriptors, not vague ones ("controlled frustration" not "passionate")
- [ ] At least one "not X" descriptor to prevent overcorrection
- [ ] TTS parameters match the phase-specific overrides (Part 2)

### Script Text Checks

- [ ] Hook has `...` or `—` creating the pattern-interrupt beat
- [ ] Agitation sentences shorten progressively
- [ ] Reframe's key insight is an isolated short sentence
- [ ] CTA has no ellipses and no exclamation marks
- [ ] No `!`, `ALL CAPS`, `*asterisks*`, `(parentheses)`, or `;` anywhere
- [ ] Numbers and names are spelled out if mispronunciation is likely ("$4.2 billion" not "$4.2B")

### Cross-Section Checks

- [ ] Emotional arc progresses: tension → building unease → quiet certainty → warm authority
- [ ] Pacing arc follows: slow/heavy → accelerating → slowest → natural
- [ ] Style parameter rises through hook/agitation/reframe, then drops for CTA
- [ ] Stability parameter is lowest at reframe (most expressive) and highest at CTA (most natural)
- [ ] No section's voice prompt contradicts the narrator's base identity
