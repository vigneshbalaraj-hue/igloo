# Directive: Integrate Prompt Bank into Igloo Pipeline

> Last updated: 2026-04-07

---

## Goal

Wire `execution/prompt_bank.md` into Igloo's script generation step so that every reel script is shaped by the prompt bank's universal rules and niche-specific system prompt. The prompt bank sits between user input and script generation — it is mandatory, not optional.

---

## Pipeline Position

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐     ┌─────────────┐
│  User Input  │ ──▶ │  Prompt Bank      │ ──▶ │  Script Generation │ ──▶ │  Rest of    │
│  (niche,     │     │  (selects niche   │     │  (LLM generates    │     │  pipeline   │
│   topic,     │     │   prompt, injects │     │   reel script)     │     │  (voice,    │
│   tone,      │     │   universal rules)│     │                    │     │   image,    │
│   audience,  │     │                   │     │                    │     │   video,    │
│   CTA)       │     │                   │     │                    │     │   assembly) │
└─────────────┘     └──────────────────┘     └───────────────────┘     └─────────────┘
```

**Before (current):** User input → LLM generates script with a generic/minimal prompt → boring output.

**After (with prompt bank):** User input → prompt bank injects universal rules + niche system prompt → LLM generates contrarian, Netflix-tone script → output worth posting.

---

## Inputs (What the user provides)

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `niche` | Yes | One of: `spirituality`, `fitness`, `finance`, `parenting`, `wellness` | `fitness` |
| `topic` | Yes | The specific angle or subject for the reel | `"Why 3 sets of 12 is a waste of time"` |
| `tone` | No | Override or refine the default niche tone | `"more aggressive than usual"` |
| `audience` | No | Who the creator's audience is | `"women 25-40 who do CrossFit"` |
| `cta_target` | No | Where the CTA should drive | `"link in bio to training program"` |
| `brand_notes` | No | Any brand-specific constraints | `"never mention competitor brands"` |

---

## Process (Step by Step)

### Step 1: Load the Prompt Bank

Read the full contents of `execution/prompt_bank.md`. This file contains:
- **Part 1:** Universal rules (apply to every script, every niche)
- **Part 2:** Five niche-specific system prompts
- **Part 3:** Good/bad example scripts per niche (for few-shot reference)

### Step 2: Select the Niche Prompt

Using the user's `niche` input, extract the matching system prompt from Part 2.

```python
# Pseudocode — adapt to your actual script generation module
niche_prompts = parse_prompt_bank("execution/prompt_bank.md")
selected_prompt = niche_prompts[user_input.niche]  # e.g., niche_prompts["fitness"]
```

If the user's niche doesn't match one of the five exactly, the LLM **generates a new niche voice on the fly** using the existing prompts as style references. Do NOT reject unknown niches.

**Fallback order:**

1. **Exact match** — use the niche prompt directly (e.g., "fitness" → fitness prompt)
2. **Close match** — map to the nearest niche and note the refinement (e.g., "yoga" → spirituality prompt + "Focus on physical practice and movement, not metaphysics")
3. **No match** — trigger dynamic niche generation (see below)

**Dynamic niche generation (Step 2b):**

When the niche has no close match (e.g., "real estate," "gaming," "education," "travel"), pass ALL five existing niche prompts to the LLM as style examples and ask it to generate a new niche voice following the same pattern:

```
=== TASK: GENERATE NICHE VOICE ===
Below are 5 niche voice prompts that define Igloo's editorial style. Each one:
- Assigns a specific character with deep domain expertise
- Defines a voice (tone, cadence, attitude)
- Names an enemy (the thing this niche's mainstream gets wrong)
- Names a weapon (the specific knowledge that separates this voice from generic content)
- Lists niche-specific script rules with banned words

Study these 5 examples, then generate a new niche voice for: {user_input.niche}

Follow the exact same structure. The character must feel as distinct and authoritative
as the existing five. The enemy must be something practitioners in this niche
actually believe. The banned words must be the clichés AI defaults to in this niche.

{spirituality_prompt}
{fitness_prompt}
{finance_prompt}
{parenting_prompt}
{wellness_prompt}

Now generate the voice prompt for: {user_input.niche}
```

The generated niche voice is then used in Step 3 exactly like any of the five built-in prompts. Good/bad examples from the **closest existing niche** are still included as few-shot references (the structure and quality bar transfer even if the domain doesn't).

**Cache dynamically generated niche prompts** in `data/cache/niche_prompts/` keyed by niche name. If the same custom niche is requested again, reuse the cached prompt instead of regenerating.

### Step 3: Assemble the System Prompt

Construct the full system prompt by concatenating in this exact order:

```
1. Universal Rules (Part 1 of prompt_bank.md)
2. Niche-specific system prompt (from Step 2)
3. Brand customization block (from user input — tone, audience, brand_notes)
4. Good example script for this niche (from Part 3 — as a few-shot reference)
5. Anti-example (bad script) with annotations (from Part 3 — shows what to avoid)
```

**Template for the assembled system prompt:**

```
=== UNIVERSAL RULES ===
{Part 1 content from prompt_bank.md}

=== NICHE VOICE ===
{Selected niche system prompt from Part 2}

=== BRAND CUSTOMIZATION ===
Audience: {user_input.audience or "general audience in this niche"}
Tone override: {user_input.tone or "use niche default"}
Brand constraints: {user_input.brand_notes or "none"}
CTA target: {user_input.cta_target or "generic follow CTA"}

=== REFERENCE: GOOD SCRIPT (match this quality) ===
{Good example script for this niche from Part 3}

=== REFERENCE: BAD SCRIPT (avoid everything annotated here) ===
{Bad example script with annotations for this niche from Part 3}

=== YOUR TASK ===
Write a 40-60 second reel script about: {user_input.topic}
Follow every universal rule. Match the niche voice. Use the good example as a quality benchmark. Avoid every failure pattern shown in the bad example.
Output the script only — no preamble, no explanation, no scene labels.
```

### Step 4: Call the Script Generation LLM

Send the assembled system prompt + user topic to the LLM (currently Gemini).

```python
# Pseudocode
response = llm.generate(
    system_prompt=assembled_system_prompt,  # From Step 3
    user_prompt=f"Write a reel script about: {user_input.topic}",
    temperature=0.9,  # Higher than default — we want creative risk, not safe completion
    max_tokens=800    # 40-60 second script ≈ 150-250 words ≈ 400-700 tokens
)
```

**Temperature note:** Use 0.9 or higher. Lower temperature produces safer, more generic output — exactly what we're trying to avoid. The prompt bank's constraints prevent the model from going off-rails even at high temperature.

### Step 5: Validate the Output

Before passing the script downstream, run these checks:

```python
# Validation checklist — reject and regenerate if any fail
checks = {
    "has_hook": script_starts_with_tension(response),     # First sentence creates tension
    "has_cta": script_ends_with_cta(response),            # Last 1-2 sentences drive action
    "no_ai_tells": not contains_ai_tells(response),       # No hedging, no "in today's world"
    "word_count": 150 <= word_count(response) <= 280,     # 40-60 second range
    "no_listicle": not contains_listicle_pattern(response) # No "First... Second... Third..."
}
```

These validation functions don't need to be complex — even keyword-based checks for AI tells (`"it's important to note"`, `"in today's fast-paced world"`, `"let's dive in"`, `"here are some"`) catch the worst offenders.

If validation fails, regenerate once with an appended instruction: `"The previous attempt was rejected because: {failure_reason}. Try again — more human, more contrarian, more specific."` If it fails twice, flag for manual review.

### Step 6: Pass to Downstream Pipeline

The validated script continues to the next step in Igloo's pipeline (voice generation via ElevenLabs, then image generation, video generation, assembly).

No changes to downstream steps are needed — the prompt bank only affects the script generation step.

---

## Integration into Existing Code

The script generation step in Igloo's pipeline currently lives in the Reel Engine repo. The integration requires modifying the script generation module to:

1. **Read `prompt_bank.md`** at startup or per-request (reading at startup and caching is preferred — the file doesn't change per request)
2. **Parse niche sections** — extract the 5 system prompts and examples by section headers
3. **Accept niche as input** — add `niche` to the user input schema if not already present
4. **Assemble the system prompt** per Step 3
5. **Replace the current system prompt** in the script generation LLM call with the assembled one

**What NOT to change:**
- Voice generation step (ElevenLabs) — no changes needed
- Image/video generation — no changes needed
- Assembly/rendering — no changes needed
- The prompt bank file itself should not be modified by the pipeline at runtime

---

## File Dependencies

| File | Role | Location |
|------|------|----------|
| `execution/prompt_bank.md` | Source of truth for all script generation prompts | This repo (01_Positioning) |
| `data/reports/positioning.md` | Reference — prompt bank is derived from this | This repo (01_Positioning) |
| Script generation module | Where the integration code goes | Reel Engine repo |

**Note:** The prompt bank lives in the Positioning repo because it's a positioning artifact — it encodes Igloo's editorial voice. It should be copied or symlinked into the Reel Engine repo when integrating. If the prompt bank is updated (new niches, refined examples), the Reel Engine picks up changes automatically if symlinked, or needs a manual copy if not.

---

## Edge Cases

- **User provides a niche not in the bank:** Dynamic generation (Step 2b). The LLM creates a new niche voice using the 5 existing prompts as style references. Cache the result. Never fall back to a generic prompt — that defeats the entire purpose.
- **User provides no topic:** Reject. The LLM needs a topic to write a contrarian take. "Write a reel" is not enough input.
- **User provides conflicting tone override:** Tone override refines, never replaces. If user says "make it funny," the niche voice (e.g., Netflix documentary) still applies — it just gets dry humor instead of pure intensity.
- **Script generation LLM changes (e.g., Gemini → Claude):** The prompt bank is model-agnostic. The assembled system prompt works with any instruction-following LLM. Temperature may need adjustment per model.
- **Adding a new niche:** Add a new section to Part 2 and Part 3 of `prompt_bank.md`. Follow the existing format exactly. Update the niche mapping in Step 2.

---

## Cost

No additional API cost. The prompt bank adds ~2,000 tokens to the system prompt. At Gemini's pricing, this is <$0.01 per script generation. Negligible impact on the ~$3.19 per reel cost.

---

## Testing

After integration, generate one test script per niche and verify:

1. Hook creates tension in the first sentence
2. No AI-tell language detected
3. Specific references present (names, studies, numbers — not vague)
4. CTA is narrative-driven, not bolted on
5. Script reads like a human wrote it when spoken aloud (read it out loud — this is the real test)

Compare each test script against the good/bad examples in the prompt bank. If the test script is closer to the bad example, the integration has a bug.
