---
name: grace-verification
description: "Проектирование и обеспечение тестирования, трасс и log-driven-верификации для GRACE-проекта, включая гейт реестра требований (покрытие спанов, три класса дрейфа, перезапуск чекера). Использовать, когда модулям нужны более сильные автотесты, проверки execution-trace или поддерживаемый verification-plan.xml, на который могут опираться автономные и мультиагентные сценарии."
---

Design verification that autonomous agents can trust: deterministic where possible, observable and traceable where equality checks alone are not enough.

## Prerequisites
- `docs/development-plan.xml` must exist with planned modules or module contracts
- `docs/verification-plan.xml` should exist; if it does not, create it from the GRACE init template before proceeding
- if `docs/operational-packets.xml` exists, use its `FailurePacket` shape for failure handoff output
- Read the relevant `MODULE_CONTRACT`, function contracts, semantic blocks, and existing tests first
- If no contract exists yet, route through `$grace-plan` before building verification

## Goal

Verification in GRACE is not just "did the final value match?"

It must answer:
- did the system produce the correct result?
- did it follow an acceptable execution path?
- can another agent debug the failure from the evidence left behind?

Use contracts for **expected behavior**, semantic blocks for **traceability**, and tests/logs for **evidence**.

`docs/verification-plan.xml` is the canonical place where this evidence model lives.

## Process

### Step 1: Load Verification Context
Read the smallest complete set of artifacts needed for the scope:

- `docs/requirements.xml`
- `docs/technology.xml`
- `docs/development-plan.xml`
- `docs/verification-plan.xml`
- relevant source files and nearby tests

When operating on one module, prefer that module's plan entry, verification entry, and local tests over rereading the whole repository.

If the optional `grace` CLI is available, `grace module show M-XXX --path <project-root> --with verification` is a fast way to read the shared/public module and verification context, and `grace file show <path> --path <project-root> --contracts --blocks` is a fast way to inspect the local/private contracts and semantic blocks that need evidence.

### Step 2: Derive Verification Targets from Contracts and Flows
Read the module contracts, function contracts, and linked flows. Extract:

- success scenarios
- failure scenarios
- critical invariants
- side effects
- forbidden behaviors

Turn these into a verification matrix before writing or revising tests. Keep the matrix synced into `docs/verification-plan.xml`.

Every scenario in that matrix must trace to a requirement record in the registry, not to a sentence in the spec — see **Requirements Registry Gate** below. A scenario that verifies a requirement nobody registered is a green test for a forgotten requirement.

### Step 3: Design Observability
For each critical path, define the minimum telemetry needed to debug and verify it.

At a minimum:
- important logs must reference `[ModuleName][functionName][BLOCK_NAME]`
- each critical branch should be visible in the trace
- side effects should be logged at a high-signal level
- secrets, credentials, and sensitive payloads must be redacted or omitted

Prefer stable structured logs or stable key fields over prose-heavy log lines.

### Step 4: Build or Refresh `docs/verification-plan.xml`
Update the verification artifact so it becomes execution-ready.

For each relevant module, define or refresh:
- `V-M-xxx` verification entry
- target test files
- module-local verification commands
- success and failure scenarios
- required log markers and trace assertions
- wave-level and phase-level follow-up checks

Also refresh project-wide policy when needed:
- log format
- redaction rules
- deterministic-first policy
- module/wave/phase split

### Step 5: Choose Evidence Types Per Scenario
For each scenario, decide which evidence type to use:

- **Deterministic assertions** for stable outputs, return values, state transitions, and exact invariants
- **Trace assertions** for required execution paths, branch decisions, retries, and failure handling
- **Integration or smoke checks** for end-to-end viability
- **Semantic evaluation of traces** only when domain correctness cannot be expressed reliably with exact asserts alone

If an exact assert works, use it. Do not replace strong deterministic checks with fuzzy evaluation.

### Step 6: Implement AI-Friendly Tests and Evidence Hooks
Write tests and harnesses that:

1. execute the scenario
2. collect the relevant trace, logs, or telemetry
3. verify both:
   - outcome correctness
   - trajectory correctness

Typical trace checks:
- required block markers appeared
- forbidden block markers did not appear
- events occurred in the expected order
- retries stayed within allowed bounds
- failure mode matched the contract

Substantial test files may also use MODULE_CONTRACT, MODULE_MAP, semantic blocks, and CHANGE_SUMMARY if that makes them easier for future agents to navigate.

### Step 7: Use Semantic Verification Carefully
When strict equality is too weak or too brittle, use bounded semantic checks.

Allowed pattern:
- provide the evaluator with:
  - the contract
  - the scenario description
  - the observed trace or structured logs
  - an explicit rubric
- ask whether the evidence satisfies the contract and why

Disallowed pattern:
- asking a model to "judge if this feels correct"
- using raw hidden reasoning as evidence
- relying on unconstrained free-form log dumps without a rubric

### Step 8: Apply Verification Levels
Match the verification depth to the execution stage.

- **Module level**: worker-local typecheck, lint, unit tests, deterministic assertions, and local trace checks
- **Wave level**: integration checks only for the merged surfaces touched in the wave
- **Phase level**: full suite, broad traceability checks, and final confidence checks before marking the phase done

Do not require full-repository verification after every clean module if the wave and phase gates already cover that risk.

Make these levels explicit in `docs/verification-plan.xml` so execution packets can reuse them.

Run the registry gates (span coverage, three-way drift diff, checker replay — see **Requirements Registry Gate**) at module level for the touched requirement IDs only, and at wave and phase level across the whole registry.

### Step 9: Failure Triage
When verification fails, produce a concise failure packet:

- contract or scenario that failed
- expected evidence
- observed evidence
- first divergent module/function/block
- suggested next action

Use this packet to drive `$grace-fix` or to hand off the issue to another agent without losing context.

If `docs/operational-packets.xml` exists, align the handoff to its canonical `FailurePacket` fields.

## Requirements Registry Gate

The registry (`docs/requirements-registry.xml` or `.jsonl`) is the source of truth for "what was asked". The spec, the development plan, module contracts and the evidence log are **derived views**: each carries `req_id` plus the hash of the requirement text it was derived from.

Each record keeps `raw_text` verbatim with a source anchor — `file`, `sha256`, `span[start,end]`, `channel` (chat, letter, document, call), `speaker`, `date`. An artifact cites the span; a paraphrase is never a valid citation, because a paraphrase cannot be diffed against the source.

Three gates, all mechanical:

1. **Span coverage.** Every span of every source document has a verdict: `requirement` | `constraint` | `question` | `decision` | `background` | `duplicate`. Zero unclassified spans. A span containing a modal obligation ("must", "не должен", "shall", "at least N") marked `background` is a finding, not a judgement call.
2. **Three-way drift diff** at module, wave and phase level:
   - `evidence.req_hash` ≠ current requirement hash → **stale evidence** → block;
   - requirement present, `evidence[]` empty → **unproven requirement** → block;
   - requirement removed or superseded, but evidence, tests or code still reference it → **orphaned evidence** → block.

   The third class is the invisible half of drift: the requirement left the registry, the code and tests kept it and still count it as satisfied.
3. **Checker replay.** Acceptance re-runs the invariant checker over `(req_id, code_hash)` instead of trusting the log. The invariant must be an executable predicate that neither the coding agent nor the reviewer can edit. Two LLM opinions are not a chain of proofs; the strength lives in the checker, as in Lean's small trusted kernel.

Statuses are first-class: `elicited` | `assumed` | `open` | `rejected` | `superseded`. `open` covers both unresolved questions and fragments the agent did not understand — it carries an owner and a deadline, and it is never paraphrased away into a confident requirement. The count of `open` records at baseline is the risk metric, not an embarrassment.

The mechanics are implemented, not left to prose: `python3 registry/grace.py --root <project> parse|coverage|drift|replay` (stdlib only, no install). Exit codes: `0` clean, `1` blocking findings, `2` bad input, `3` refuse to run — a predicate whose sha256 differs from the recorded version, or an invariant with no transitions. An `open` verdict without a verbatim quote from the span is rejected at write time. If the tool is available, run it instead of judging the registry by reading it: "I looked and it seems covered" is exactly the claim this gate exists to replace.

Every evidence record names its checker and checker version, and states the observation that would falsify it. If no such observation can be named, the record is decoration.

The machine-readable spec is a **cache**: regenerable from `raw_text` plus derivation rules, never a second source of truth. Discarding it is fine; losing the ability to regenerate it is not.

## Verification Rules
- Deterministic assertions first, semantic trace evaluation second
- Logs are evidence, not decoration
- Every important log should map back to a semantic block
- Do not log chain-of-thought or hidden reasoning
- Do not assert on unstable wording if stable fields are available
- Prefer high-signal traces over verbose noise
- Keep `docs/verification-plan.xml` synchronized with real test files and commands
- Prefer source-adjacent tests and narrow fakes over giant opaque harnesses
- If verification is weak, improve observability before adding more agents
- Prefer module-level checks during worker execution and reserve broader suites for wave or phase gates

## Deliverables
When using this skill, produce:

1. an updated `docs/verification-plan.xml`
2. a verification matrix for the scoped modules or flows
3. the telemetry/logging requirements
4. the tests or harness changes needed
5. the recommended verification level split across module, wave, and phase
6. a brief assessment of whether the module is safe for autonomous or multi-agent execution
7. the registry gate result: span coverage, the three drift classes, and which evidence records were replayed through their checker

## When to Use It
- Before a first serious `$grace-execute` or `$grace-multiagent-execute` run
- Before enabling autonomous execution for a module
- When multi-agent workflows need trustworthy checks
- When tests are too brittle or too shallow
- When bugs recur and logs are not actionable
- When business logic is hard to verify with plain equality asserts alone

## Common Rationalizations

Thoughts that mean STOP — you are about to ship verification that autonomous agents cannot trust.

| Rationalization | Reality |
|---|---|
| "This branch is critical but log markers slow things down, skip them" | A critical branch without a stable log marker is invisible to every future agent debugging a failure. The marker IS the trace anchor — skipping it turns trace assertions into guesses. |
| "After the refactor I'll just reuse the old log-marker names, they're close enough" | Reused marker names after a refactor silently redirect trace assertions to the wrong block. If the block moved or split, mint a new name and update every `V-M-xxx` and test reference in the same commit. |
| "Module-level tests cover everything, phase-level gates are bureaucracy" | Module-level tests cannot observe cross-module state, merged surfaces, or wave-to-wave regression. Without phase-level gates, cross-wave drift ships undetected. |
| "The tests read like good documentation, that's enough" | A test with no assertions is a doc comment that allocates memory. Trajectory or outcome must be asserted — otherwise the test passes forever, including when the code is deleted. |
| "Verification-plan entry is a bit thin but it's good enough for now" | "Good enough" verification is how autonomous runs produce silent failures. Either the plan names concrete tests, commands, log markers, and scenarios, or it is not ready for `$grace-execute`. |
| "Deterministic asserts are too strict, a semantic evaluator will be more flexible" | Flexible means "unfalsifiable". If an exact assertion is possible, use it. Semantic evaluation is the last resort, never the default. |
| "Logging the full reasoning trace makes debugging easier" | Logging chain-of-thought or hidden reasoning is forbidden — it leaks into evidence and corrupts the rubric. Log stable structured fields, not monologue. |
| "The spec is the requirement; re-tracking the original notes is overhead" | The spec is a compiled, lossy view. Once it is the only source, there is nothing left to diff against and drift becomes invisible by construction — the requirement disappears without any artifact noticing. |
| "The agent read every note before writing the spec, so nothing is missing" | Reading is not coverage. Only span-level verdicts show what was classified as non-requirement, and the interesting defects are exactly the spans that were silently classified. |
| "The model checks the invariant, then a reviewer checks it again — that's independent verification" | Two opinions are not a proof chain; the reviewer's check is as unfalsifiable as the first. Strength comes from an executable checker that neither of them can edit, replayed at acceptance. |
| "Open questions can wait until the requirements settle" | `open` is a first-class status with an owner and a deadline, not a deferred item. Unregistered, unanswered questions are the single largest source of mathematically correct work on the wrong problem. |

## Red Flags

Stop immediately if any of the below apply — your verification plan is unsafe for autonomous or multi-agent execution:

- A `V-M-xxx` entry references a test file or command that does not exist on disk.
- A critical branch has no `[Module][function][BLOCK_NAME]` log marker or no trace assertion covering it.
- A refactor renamed semantic blocks but the verification-plan still references the old marker names.
- Phase-level gates are missing entirely, and wave-level checks are doing phase-level work.
- Test files contain scenario names and setup code but no `expect(...)` / `assert` statements.
- The verification-plan says "see tests" instead of naming scenarios, commands, markers, and expected evidence.
- A semantic evaluation is used where an exact assertion would have worked.
- A requirement record cites a paraphrase, a summary or a spec sentence instead of a source span (`file` + `sha256` + offsets).
- Evidence, tests or code reference a requirement that is no longer in the registry — orphaned evidence surviving a supersede.
- A source document has spans with no verdict, or an obligation-bearing span ("must", "не должен", "at least N") labelled `background`.
- An invariant is "verified" by asking a model whether it holds, with no executable checker named and replayed.
- Logs in critical paths contain redaction-violating data (tokens, PII, credentials) or raw model reasoning.

## When NOT to Use

- The project has no `docs/development-plan.xml` or module contracts yet — run `$grace-plan` first; verification without contracts is guessing.
- You are fixing a single reproducible bug — use `$grace-fix` (which writes its own RED-GREEN test) rather than redesigning the whole verification plan.
- The codebase is a throwaway spike that will be deleted — verification-plan overhead is not justified.
- The user wants project health status, not evidence design — route to `$grace-status`.
- The change is outside GRACE governance (e.g. lockfile update, typo in a comment) — regular code review is enough.
- You are mid-execution in a wave and the caller needs a worker-local check only — use the module-level entry that already exists; do not rewrite the plan mid-wave.

## Verification

Before claiming this skill is complete, confirm every box:

- [ ] `docs/verification-plan.xml` updated and still well-formed (verification: open the file and confirm each touched `V-M-xxx` has targets, commands, scenarios, and markers)
- [ ] Every critical branch has a stable log marker (verification: `grep -rn "\[.*\]\[.*\]\[.*\]" src/` matches the markers named in the plan)
- [ ] Marker names in the plan exist in code AND match the block names (verification: for each marker `X`, `grep -rn "START_BLOCK_X" src/` returns exactly one match)
- [ ] Module-, wave-, and phase-level commands are explicit and runnable (verification: each listed command executes, e.g. `bun test <path>` returns a real exit code)
- [ ] Tests contain real assertions, not just scenario setup (verification: `grep -rEn "expect\(|assert(Equal|That|True|False)?\(" tests/` for each target test file)
- [ ] No chain-of-thought or sensitive payloads logged (verification: `grep -rnE "reasoning|thought|password|token|secret" src/` in logged strings returns no hits that escape redaction)
- [ ] Failure packet shape matches `docs/operational-packets.xml` when that file exists (verification: grep the packet fields against the canonical `FailurePacket`)
- [ ] Span coverage gate passes: no source span without a verdict (verification: the project's coverage check prints zero unclassified spans, and zero obligation-bearing spans labelled `background`)
- [ ] Three-way drift diff is clean (verification: the drift check prints 0 stale evidence, 0 unproven requirements, 0 orphaned evidence across the registry)
- [ ] Every evidence record names a checker and checker version, and is replayed at acceptance rather than read (verification: run the checker for three sampled `(req_id, code_hash)` pairs and compare with the logged result)
- [ ] `grace lint --path <project-root>` (if CLI available) passes after the plan update, and its exit code is cited in the deliverable
