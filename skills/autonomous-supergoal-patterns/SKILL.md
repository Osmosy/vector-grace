---
name: autonomous-supergoal-patterns
description: Use when the user needs autonomous end-to-end work without active supervision — overnight runs, busy days, hands-off task delivery. Triggers on "автономно", "ночью", "у меня нет времени", "сделай и не спрашивай", "babysit", "run it overnight", "autonomous loop", "fire and forget", "всё сам", "поставь на ночь". Adapted from robzilla1738/supergoal patterns (self-critique, pre-flight smoke, cleanliness grep, final audit, 3-strike self-healing) to work in Hermes/CLI without depending on /goal slash command.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Autonomous, Self-Healing, Planning, Overnight, Hands-Off, Workflow, Superpowers-Pattern]
    related_skills: [github-repo-research, api-tokens-in-chat, kanban-orchestrator, writing-plans]
---

# Autonomous Supergoal Patterns (Hermes adaptation)

Patterns from `robzilla1738/supergoal` (544⭐, MIT) adapted for **Hermes Agent / CLI environments** without `/goal` slash command. Source: https://github.com/robzilla1738/supergoal — v0.7.0.

**What's the same:** self-critique before plan dispatch, pre-flight smoke check, cleanliness grep (debug / TODO / dead imports), 3-strike self-healing, final audit with working-tree-vs-baseline deliverable check.

**What's adapted:** instead of "single /goal paste handoff", use the existing Hermes workflow (plan → confirm → act with explicit "Стою, жду" gates). Instead of memory writeback inside the host, write directly to the run's STATE.md. Instead of `/plugin marketplace`, install via copying to `~/.hermes/skills/`.

## When to Use

- "поставь задачу на ночь" / "run this overnight" / "автономно"
- User says "у меня нет времени" / "сделай всё сам" / "не спрашивай"
- Task is well-defined, multi-step, and would normally need babysitting
- Goal is verifiable (acceptance criteria can be made falsifiable)
- User explicitly accepts reduced interactivity

## When NOT to Use

- Task is ambiguous and needs user input mid-flight — autonomous mode makes that expensive (agent commits to a wrong path before user notices)
- Regulatory / compliance work (Меркурий, ЧЗ, financial docs) — always human-in-the-loop at the commit gate, see `vector-meat-stack-v1` principle
- Destructive operations (rm -rf, force push to main, schema migrations on prod) — never autonomous without explicit pre-authorized scope
- Single-step tasks — overhead not worth it
- User said "обязательно спрашивай перед каждым шагом" — opposite workflow

## Core Principle

**Autonomous ≠ unsupervised.** Autonomous = the agent decides execution details, but the user has approved a plan + acceptance criteria upfront. The plan is the contract. The audit is the proof. The user reviews the proof, not the journey.

## The 4 Patterns (in execution order)

### Pattern 1 — Self-Critique Pass (before committing to action)

After writing the plan, before asking for confirmation, run ONE self-critique turn answering exactly three questions:

1. **Falsifiability** — Is every acceptance criterion a yes/no test, not a vibe?
   Flag any that say "works", "good", "ready", "correct" without a measurable predicate.
   Rewrite in place before showing the plan.

2. **Phase atomicity** — Is any phase secretly two coherent units packed into one?
   (deliverables that don't share a verify gate, names containing "and",
   split-able dependency lines). Split if needed.

3. **Weakest dependency** — Where would a partial failure cascade worst?
   (e.g., phase 2 unblocks 3, 4, and 5 — if 2 ships shaky, three phases
   inherit the bug). Add mitigation.

**Honesty check:** this pass must produce findings OR a "clean" verdict. If it silently always says "clean" on real plans, remove it. (From Supergoal Stage 6a.)

**In Hermes:** write the self-critique output to the run's STATE.md or a dedicated `self-critique.md` so it's auditable later, not just in transcript context.

### Pattern 2 — Pre-Flight Smoke Check (after plan approval, before action)

After user approves the plan and BEFORE the first code/file action:

1. Read every phase spec, union their "Mandatory commands" into a deduplicated set.
2. Run each once. Capture exit code and last ~5 lines.
3. If all green → proceed.
4. If any red → STOP. Surface failures. Re-show plan with revised menu:
   - "Skip pre-flight, dispatch anyway" (baseline being broken IS the point)
   - Adjust an assumption
   - Tweak a phase
   - Restructure phases

**Why this matters:** catches "agent tries to fix phase 1 work that was never the cause" (the broken baseline was). Saves the entire 3-strike loop from wasted retries on pre-existing failures.

**In Hermes:** use the existing `terminal(command=...)` with `nice -n 19` for CPU-heavy ones. Don't `subprocess.run` inside `execute_code` for shell commands — terminal tool handles approval prompts correctly when something needs sudo / network / writes to restricted paths.

### Pattern 3 — Cleanliness Grep (per-phase verify)

Per phase, before declaring DONE, run a cleanliness pass on the **complete working-tree changes** since baseline:

```bash
# Example: catch debug prints added in this phase
git diff --unified=0 <baseline_sha>..HEAD | grep -E '^\+' | grep -E 'console\.log|print\(|TODO|FIXME|XXX' | head -20

# Or for unstaged/untracked work (use repo-state.sh if available):
bash repo-state.sh added-lines <baseline_sha>
```

Counts:
- `console.log` / debug prints (in production code, not tests)
- `TODO` / `FIXME` / `XXX` without ticket reference
- Dead imports (grep for `import X` then `grep -c "X" .` for usage)
- Session-only markers (e.g., `// temp`, `// REMOVE BEFORE MERGE`)

Non-zero counts trigger either a fix-up or explicit "Cleanliness override:" in the phase spec.

**Why this matters:** catches "agent said done but added 47 debug prints" before it goes to user review. Catches uncommitted work too if `repo-state.sh` covers working tree, not just HEAD.

### Pattern 4 — Final Audit (after last phase, before completion)

After the last phase's `SUPERGOAL_PHASE_DONE`-equivalent, run a **final audit** that re-validates against the **original plan**, not against per-phase self-reports:

1. **Re-read the original plan** — pull every acceptance criterion fresh.
2. **Re-run aggregated mandatory commands** (build, typecheck, lint, full test suite).
3. **Spot-check each acceptance criterion**:
   - File exists / Function exported / Config key set → re-check via ls/grep/cat.
   - Screenshot / manual smoke test / other non-deterministic → mark `trust-prior-verify`, do not re-run.
4. **Deliverable check** vs baseline:
   ```bash
   # Files declared in plan deliverables that should exist now
   for path in $(grep -oP 'Deliverables?:\s*\K.*' plan.md | tr ',' ' '); do
     test -e "$path" || echo "MISSING: $path"
   done
   # Working-tree diff vs baseline (includes uncommitted)
   git diff --stat <baseline_sha>
   git status --porcelain
   ```
5. **Compute audit coverage** = `re_verified / (re_verified + trust_prior)` as %.
6. If any gaps → write `audit-fix-N.md`, execute inline. Cap at 3 audit rounds.
7. On clean → report:
   - "AUDIT_COMPLETE" with phases verified, commands re-run, criteria pass/trust-prior counts, deliverables present/missing counts, coverage %.
   - If `trust_prior / (re_verified + trust_prior) > 30%`, prepend honesty banner: "⚠ Audit coverage: X re-verified, Y trust-prior (Z%). Eyeball UI/UX before merging."

**Why this matters:** per-phase VERIFY is self-reported. A phase can pass its own check while a later phase silently breaks it (type added in phase 2 violated in phase 5; tests that passed mid-run break after refactor). The audit closes that loophole.

## Optional Pattern 5 — 3-Strike Self-Healing

**Use only when user has explicitly pre-authorized retries** (typical for overnight runs). Default behavior in Hermes should still be "Стою, жду" on first failure.

1. First failure of any acceptance criterion → auto-retry once with diagnostic probe.
2. Second failure → write focused fix spec, execute inline.
3. Third failure → STOP, hand off with full probe history, do NOT auto-continue.

**Why opt-in:** self-healing eats tokens and time, and the user might prefer to wake up to "blocked, here's what happened" rather than "I tried 47 things and broke it more". Default is transparency over throughput.

**In Hermes:** mark `3_strike_authorized: true` in the plan file if user opts in. Default false.

## Overnight-Run Specifics

For runs that span "I go to sleep → I wake up":

- **Single notification, not per-phase.** Configure the terminal background pattern to only notify on completion, BLOCKED, or final audit gaps. Don't wake the user for each phase done.
- **STATE.md is the morning reading.** Write enough that "wake up, read STATE.md, decide if anything needs my attention" is the user's whole morning ritual.
- **Token economy matters.** Overnight = unattended = unmonitored token burn. Don't run heavy exploration. Plan first, then execute.
- **Pin the model.** Per AGENTS.md §1: never switch models mid-process. For overnight runs, explicitly set `model.default` in the run spec so the agent doesn't accidentally trigger an auto-router.
- **No network surprises.** Pre-flight smoke check should confirm key endpoints (e.g., git remote, registry, internal API). If an overnight run hits "git remote unreachable" at 3 AM, that's a hard BLOCKED, not a retry.
- **Daily log into memory.** After completion, write a one-line summary to MEMORY.md (or session_search next morning) so the user can grep "what did the agent do overnight" without reading the whole STATE.md.

## Recommended Workflow (Hermes-specific)

For overnight / hands-off runs:

1. **Pre-plan with user** — even for autonomous runs, you still need:
   - Goal (one sentence)
   - Acceptance criteria (falsifiable, per Pattern 1)
   - Phase list (per Pattern 1)
   - Whether 3-strike is authorized (Pattern 5)
   - Notification policy (which events wake the user)
   - Hard blockers list (what counts as "stop and ask", not "retry")

2. **Write STATE.md** at the run root (e.g., `.runs/2026-06-20-add-dark-mode/STATE.md`):
   - Goal
   - Phases (each with criteria + mandatory commands + cleanliness overrides)
   - Baseline ref (`git rev-parse HEAD` at start)
   - Notification policy
   - Hard blockers

3. **Run pre-flight** (Pattern 2). Block on any red.

4. **Execute phases sequentially** with per-phase verify + cleanliness grep (Pattern 3). Update STATE.md after each.

5. **Run final audit** (Pattern 4). Block on gaps (3 rounds max).

6. **Report once** with full audit summary. User reads in the morning.

## Anti-Patterns

1. **"Autonomous" without a plan.** "Just do X" with no acceptance criteria = the agent will do something and call it done. Always start with the plan, even for 5-minute tasks.
2. **3-strike self-healing by default.** Most users want to know about failures, not have them auto-retried. Make 3-strike opt-in.
3. **Trust-prior-verify > 30%.** If the audit can't re-verify most criteria, the plan was probably wrong. Rewrite, don't ship.
4. **Overnight runs without pre-flight.** Waking up to "agent tried for 4 hours, baseline was broken" is worse than 5 minutes of pre-flight.
5. **Per-phase notifications during overnight.** Defeats the purpose. Notify on completion, BLOCKED, or final audit gap only.
6. **Suppressing STATE.md updates to save tokens.** STATE.md is the morning report. Keep it dense but complete.
7. **Reusing Supergoal terminology without the patterns.** Printing "SUPERGOAL_PHASE_DONE" without the discipline (verify + cleanliness + memory writeback) is theater.

## Verification Checklist

- [ ] Plan has falsifiable acceptance criteria (Pattern 1 applied)
- [ ] Pre-flight smoke check passed before any state-changing action (Pattern 2)
- [ ] Cleanliness grep run per phase (Pattern 3)
- [ ] Final audit re-runs mandatory commands and spot-checks criteria (Pattern 4)
- [ ] Audit coverage computed and reported
- [ ] If `trust_prior > 30%`: honesty banner shown to user
- [ ] If 3-strike used: was it pre-authorized by user?
- [ ] STATE.md at run root is the morning reading
- [ ] No model switch mid-run (AGENTS.md §1)
- [ ] User notified only on completion / BLOCKED / audit gap

## What's NOT in this skill (use other skills instead)

- **Memory writeback patterns** → see `using-superpowers` and the host's standard memory system
- **Plan writing itself** → see `writing-plans` (superpowers)
- **Code review of finished work** → see `requesting-code-review` (superpowers)
- **TDD per phase** → see `test-driven-development` (superpowers)
- **Multi-agent delegation** → see `subagent-driven-development` (superpowers)
- **Dispatching parallel work** → see `dispatching-parallel-agents`

## Related Skills

- `github-repo-research` — used to evaluate the original Supergoal repo
- `api-tokens-in-chat` — apply before any overnight run that handles API tokens
- `kanban-orchestrator` / `kanban-worker` — alternative parallel-task pattern (different shape from Supergoal)
- `writing-plans` (superpowers) — the planning phase this skill assumes you've already done

## Source & Credits

- Original: https://github.com/robzilla1738/supergoal (v0.7.0, MIT)
- Author: robzilla1738
- What was preserved: self-critique pass (Stage 6a), pre-flight smoke check (Stage 6.5), cleanliness grep, 3-strike self-healing, final audit with deliverable check vs baseline.
- What was adapted: removed `/goal` dependency, replaced slash-command dispatch with "Стою, жду" gates, removed plugin marketplace install, kept all patterns usable in Hermes/CLI.
- License: MIT (Supergoal) + MIT (this adaptation).