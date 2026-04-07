# Directive: Reverse Prompting

> **Triggers:** "reverse prompt", "ask me questions first", "what questions do you have", "clarify before starting", "surface assumptions", "don't start until you ask me", "what do you need to know", "ask before building"

## Purpose

Before touching anything, ask the user exactly 5 clarifying questions that would most change your approach. Do not proceed until they answer. Surface your own assumptions, let the user disambiguate, then build with high-quality context.

## Why

The most expensive agent failures are silent assumption failures — confidently building the wrong thing because you assumed REST when they meant GraphQL, or assumed a new file when they wanted to extend an existing one. The 5-question constraint forces you to prioritize which unknowns matter most.

## Execution Flow

### 1. Receive the task
Read the user's task description. Do NOT start implementing. Analyze what you'd need to know to do this well.

### 2. Check for existing context (optional)
- Check `directives/` for relevant prior decisions
- Check `CLAUDE.md` for project conventions
- Check existing code for patterns that answer questions implicitly
- Narrow questions to things NOT already answered by the codebase

### 3. Generate your 5 questions

Turn your silent assumptions into questions. Prioritize by impact — ask where a different answer would most change implementation.

**Categories to consider:**
- **Scope** — what's in vs out?
- **Tech choices** — which tools/patterns?
- **Edge cases** — what happens when things break?
- **Performance** — what scale?
- **Integration** — what touches this?
- **UX** — what does the user see?
- **Existing patterns** — follow or diverge?

**Question format:**
```
Q1 (highest impact): [question]
My default assumption: [what you'd do if not asked]
Why it matters: [how the answer changes implementation]
```

### 4. Wait for answers
Do not proceed until user answers all 5. If they skip a question, use your default assumption and note it.

### 5. Record answers (optional but recommended)
If the project uses experience docs, append Q&A:

```markdown
## {Task Name} — Decisions ({date})

Q: {question}
A: {user's answer}
Rationale: {why this matters for future tasks}
```

### 6. Proceed with implementation
Reference user's answers as requirements. If you find yourself making a new assumption during implementation, pause and ask.

## Accumulated Experience (Advanced)

For repeat task domains, use experience docs to avoid re-asking:

```
1. Read directives/ for decisions from past builds
2. Ask 5 questions NOT already answered by experience
3. After answers, append to experience doc for next time
4. Proceed with implementation
```

This creates a flywheel: each task adds context, future tasks need fewer questions.

## When to Use
- Tasks where you'd normally spend 10+ minutes writing a detailed spec
- Complex features with multiple valid approaches
- Tasks touching unfamiliar parts of the codebase
- Anything where getting it wrong means significant rework

## When NOT to Use
- Trivial tasks ("fix this typo", "add a log line")
- Tasks with extremely detailed specs already provided
- Urgent hotfixes where speed > perfection
- Follow-up tasks where questions were already answered

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| question_count | 5 | Number of questions (3-7 range) |
| experience_doc | none | Path to experience doc for accumulated learning |
| priority_order | impact | Sort questions by implementation impact |

## Edge Cases
- **User says "just do it":** Respect it. List assumptions as a comment, proceed.
- **All questions answered by context:** Skip to implementation. Note no ambiguities found.
- **User answers are contradictory:** Flag contradiction. Ask one follow-up to resolve.
- **Task changes after questions:** Re-assess. Ask 1-2 new questions if scope shifted significantly.
