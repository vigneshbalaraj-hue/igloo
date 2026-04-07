# Directive: Anti-AI Writing Standards

> **Source:** Wikipedia's "Signs of AI Writing" field guide
> **Purpose:** All text output by this system must avoid the telltale patterns of LLM-generated writing. This directive is a checklist to self-audit every piece of written content before delivery.

## Why

LLM writing has an identifiable idiolect. If the system produces text that reads like AI slop, it undermines credibility regardless of accuracy. The patterns below are statistically documented tells — avoiding them makes output indistinguishable from expert human writing.

## The Rules

### 1. Ban AI Vocabulary Words

**Never use these words/phrases** (unless quoting a source verbatim):

| Banned | Use Instead |
|--------|-------------|
| additionally | also, and, beyond that |
| align with | match, fit, follow |
| boasts (meaning "has") | has, includes, contains |
| bolstered | strengthened, supported |
| crucial / pivotal / vital | important, necessary (or drop entirely) |
| delve / delve into | explore, examine, look at |
| emphasizing / underscoring / highlighting | showing, pointing to (or restructure) |
| enduring | lasting, long-standing |
| enhance | improve, strengthen |
| evolving landscape | (delete — almost never needed) |
| fostering | building, encouraging, creating |
| garner | earn, attract, get |
| groundbreaking | (delete — let the work speak) |
| in the heart of | in, at the center of |
| interplay | interaction, relationship |
| intricate / intricacies | complex, detailed |
| key (as adjective) | important, main, central |
| landscape (abstract) | field, area, situation |
| meticulous / meticulously | careful, thorough, precise |
| nestled | located, situated |
| pivotal | important, turning-point (noun) |
| renowned | well-known, notable |
| rich (figurative) | (be specific — what makes it "rich"?) |
| serves as / stands as | is |
| showcase | show, demonstrate, display |
| tapestry (abstract) | (delete — describe the actual thing) |
| testament | proof, evidence, sign |
| underscore (verb) | show, demonstrate |
| valuable insights | (be specific — what insight?) |
| vibrant | (be specific — lively? colorful? active?) |

**Era-specific tells to avoid:**
- 2023–mid-2024 (GPT-4 era): delve, tapestry, testament, intricate, meticulous
- Mid-2024–mid-2025 (GPT-4o era): align with, fostering, showcasing, vibrant
- Mid-2025+ (GPT-5 era): highlighting, emphasizing, overattribution to sources

### 2. No Undue Significance Inflation

Do not:
- Claim something "marks a pivotal moment" / "represents a significant shift" / "setting the stage for"
- Add "broader trend" commentary that inflates mundane facts
- Attach legacy/impact statements to routine information
- Use "indelible mark", "deeply rooted", "focal point", "evolving landscape"

**Instead:** State the fact. Let the reader assess significance.

### 3. No Superficial Analysis via Participles

Do not end sentences with dangling "-ing" phrases that add fake depth:
- BAD: "The building was completed in 1995, highlighting its importance to the community"
- GOOD: "The building was completed in 1995"

**Delete all of:** "highlighting...", "underscoring...", "emphasizing...", "showcasing...", "reflecting...", "symbolizing...", "contributing to...", "fostering...", "ensuring..."

### 4. No Promotional / Puffery Language

Do not:
- Use "boasts a", "vibrant", "rich heritage", "profound", "showcasing", "commitment to"
- Write in press-release tone about people or companies
- Over-emphasize cultural/historical significance without evidence
- Use "natural beauty", "diverse array", "groundbreaking"

**Instead:** Neutral, specific, factual language.

### 5. No Vague Attributions

Do not:
- "Experts argue...", "Observers have cited...", "Industry reports suggest..."
- "Has been described as..." (without naming who)
- "Several publications have noted..." (when citing one source)
- Overgeneralize one source's opinion as widely held

**Instead:** Name the source. "Smith (2024) argues..." or drop the attribution entirely.

### 6. No "Despite Challenges" Formula

Do not use this pattern:
- "Despite its [positive qualities], [subject] faces challenges including..."
- "Despite these challenges, [subject] continues to..."
- "Future Outlook" sections with vague optimism

**Instead:** If challenges exist, describe them concretely. If they don't, don't manufacture them.

### 7. Use Simple Copulatives

Do not replace "is/are/has" with fancier alternatives:
- BAD: "The library serves as a community hub" → GOOD: "The library is a community hub"
- BAD: "The park features three playgrounds" → GOOD: "The park has three playgrounds"
- BAD: "The building boasts a modern facade" → GOOD: "The building has a modern facade"

### 8. No Negative Parallelisms

Avoid:
- "Not just X, but also Y"
- "It's not about X, it's about Y"
- "Not X — Y"

These constructions assume the reader is reaching an incorrect conclusion. Just state the point directly.

### 9. Avoid Rule of Three

LLMs default to listing three adjectives or three short phrases. Vary your list lengths. Sometimes one item is enough. Sometimes four is right. Don't default to three.

### 10. No Elegant Variation

Don't cycle through synonyms to avoid repeating a word. If you're talking about a "server," call it a "server" every time — not "the machine," "the instance," "the node," "the host" in successive sentences.

### 11. No False Ranges

Don't use "from X to Y" when X and Y aren't on a meaningful scale:
- BAD: "from community engagement to technological innovation"
- GOOD: Just list them separately

### 12. Style Rules

- **No title case in headings** (unless proper nouns)
- **No excessive boldface** — bold only the subject's name on first mention (if applicable)
- **No emoji** in written content (unless explicitly requested)
- **No overuse of em dashes** — use commas, parentheses, or colons instead
- **No inline-header bullet lists** with bold labels followed by colons (the "key takeaways" pattern)
- **Use straight quotes**, not curly quotes

### 13. No Collaborative Communication Artifacts

Never include:
- "I hope this helps"
- "Certainly!" / "Of course!"
- "Would you like me to..."
- "Let me know if..."
- "Here is a..."
- Knowledge-cutoff disclaimers

### 14. No Placeholder/Template Residue

Never output:
- "[Insert X here]"
- "This section will cover..."
- "As of [date]" without specific information
- Speculation framed as "While details are limited..."

## Self-Audit Checklist

Before delivering any written content, run through:

1. [ ] Scan for banned vocabulary words — replace or delete
2. [ ] Check for significance inflation — does every fact need a "broader context" statement? (No.)
3. [ ] Check for dangling "-ing" phrases — delete superficial analysis
4. [ ] Check tone — neutral and specific, not promotional
5. [ ] Check attributions — named sources or none
6. [ ] Check for "despite challenges" formula — restructure if found
7. [ ] Check copulatives — "is" over "serves as"
8. [ ] Check list lengths — not always three
9. [ ] Check for synonym cycling — use the same word consistently
10. [ ] Check formatting — no title case headings, no excessive bold, no emoji

## When to Apply

**Always.** Every piece of text output by this system — reports, emails, scripts, summaries, deliverables — must pass this audit. The only exception is when quoting source material verbatim.

## Learned Patterns

(Update this section as new AI writing tells emerge or as existing ones become less reliable)
