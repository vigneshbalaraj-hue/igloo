# Directive: Prompt Contracts

> **Triggers:** "prompt contract", "write a contract", "define success criteria", "failure conditions", "spec this out", "what does done look like", "define the contract", "structured spec", "goal constraints format failure"

## Purpose

Define a 4-part contract before implementation: **GOAL** (quantifiable success), **CONSTRAINTS** (hard limits), **FORMAT** (exact output shape), **FAILURE** (explicit conditions that mean "not done"). Treat this as an engineering spec with zero ambiguity about what "done" means.

## Why

Agents hallucinate and over-engineer when success is undefined. They silently cut corners when failure is undefined. The FAILURE clause prevents shortcuts the agent would otherwise rationalize as acceptable.

## Execution Flow

### 1. Receive the task
- If user provides a contract → parse into 4 sections, validate (step 3)
- If user provides a plain task → help convert it into a contract (step 2)

### 2. Generate the contract

Present draft for user approval before proceeding:

```markdown
## Contract

GOAL: [What does success look like? Include a measurable metric.]

CONSTRAINTS:
- [Hard limit 1 — technology, scope, or resource constraint]
- [Hard limit 2]
- [Hard limit 3]

FORMAT:
- [Exact output shape — files, structure, what's included]
- [File naming and organization]
- [What to include — types, tests, docs]

FAILURE (any of these = not done):
- [Specific failure condition 1]
- [Specific failure condition 2]
- [Edge case that must be handled]
- [Quality bar that must be met]
```

### Writing Guidelines

**GOAL:** Include a number ("handles 50K req/sec" not "handles high traffic"). Be specific. Define the user-visible outcome.

**CONSTRAINTS:** Only hard limits — not negotiable. Technology, scope, compatibility constraints.

**FORMAT:** Exact file structure. What to include and exclude.

**FAILURE:** Think about how the task could "technically work" but actually be wrong:
- Missing edge case
- Performance miss
- Silent failure
- Incomplete handling
- Over-engineered (adds abstractions not required by GOAL)

### 3. Validate the contract
- **Complete** — all 4 sections filled
- **Consistent** — CONSTRAINTS don't contradict GOAL
- **Testable** — every FAILURE condition can be mechanically verified
- **Scoped** — GOAL is achievable within CONSTRAINTS

### 4. Implement against the contract
- GOAL = what you're optimizing for
- CONSTRAINTS = boundaries you cannot cross
- FORMAT = exact shape of output
- FAILURE = conditions you must actively prevent

### 5. Self-verify against FAILURE conditions

```markdown
## Contract Verification

- [ ] FAILURE 1: {condition} → VERIFIED: {how you confirmed it passes}
- [ ] FAILURE 2: {condition} → VERIFIED: {how you confirmed it passes}
- [ ] GOAL metric met: {evidence}
- [ ] All CONSTRAINTS respected: {confirmation}
- [ ] FORMAT matches spec: {confirmation}
```

### 6. Deliver with contract status

```
Contract status: ALL PASS

GOAL: ✓ {metric achieved — show evidence}
CONSTRAINTS: ✓ {all respected}
FORMAT: ✓ {matches spec}
FAILURE conditions: ✓ {all verified — none triggered}
```

If any condition failed:
```
Contract status: 1 FAILURE

GOAL: ✓
CONSTRAINTS: ✓
FORMAT: ✓
FAILURE conditions: 1 of 4 failed
  - FAILED: "latency <1ms on 50K requests" — achieved 1.3ms
  - Reason: {why}
  - Options: {what could fix it}
```

## When to Use
- Infrastructure code (rate limiters, caches, queues)
- API endpoints and services
- Anything hard to fix later
- Tasks where quality > speed
- Preventing "it technically works but..." outcomes

## When NOT to Use
- Quick prototypes
- Exploratory tasks with forming requirements
- Trivial changes where contract > code

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| verify | true | Run self-verification before delivering |
| strict | true | Fail the task if any FAILURE condition is triggered |
| template | standard | Contract template (standard, minimal, detailed) |

## Edge Cases
- **Incomplete contract from user:** Fill missing sections with reasonable defaults, confirm with user
- **FAILURE conflicts with GOAL:** Flag contradiction, ask which takes priority
- **Can't verify a FAILURE condition:** Note as "UNVERIFIABLE", explain why, suggest manual verification
- **Contract is overkill:** Say so. Suggest minimal version (GOAL + FAILURE only)
