---
name: grace-diagnostics
description: "Диагностика в первую очередь: критерии надёжности живут в журнале, вердикт считается по журналу, а тест проверяет доказательство. Использовать, когда модуль или пайплайн трансформирует данные (грязные данные, фантомные записи, выпадения на JOIN), когда набор тестов зелёный, а выход повреждён, когда нужна приёмка по пунктам требований, а не процент прохождения, или когда агенту нужно понять ПОЧЕМУ прогон дал неверный результат."
---

Reliability for an agent is raised by **context that carries the criteria of reliability** — not by the number of tests. A suite can be green 6 of 6 while the output is corrupted; a failure report that only says "assert failed" tells the agent nothing. This skill makes the run itself produce the context, and makes the verdict come from that context.

## Principle

- **Tests are event generators and evidence consumers**, not the carrier of acceptance. Acceptance is the verdict computed from the journal against criteria.
- **The journal is the primary artifact.** Machine-readable, staged, with inputs and outputs of every transformation step.
- **A criterion that is not in the context cannot be checked.** If the journal lacks a field, the criterion is *unverifiable* — fix the logging, not the criterion, and not with another test.

## When to use

- data transformation pipelines — dirty keys, phantom records, dropped JOINs, silent fan-out;
- "all tests pass, but the numbers downstream are wrong";
- acceptance "did we deliver every point of the RFC / change request", not "did the suite pass";
- an agent is asked to fix something and has no idea *why* it broke;
- before adding tests: check whether the journal even carries the criteria.

Pair with `$grace-verification` (how the module is verified) and `$grace-fix` (locate → prove → fix → guard). This skill defines what the run must *leave behind* so that proving and fixing are possible.

Nothing here waives the Prove-It rule of `$grace-fix`: a bug fix still needs a failing test first. The difference is *what the failing test can tell you*. Red without a criteria-carrying journal says "something broke"; red plus staged reconciliation, offenders and evidence says **why** — which is the part an agent actually needs to make a one-shot fix.

## Prerequisites

- `docs/verification-plan.xml` with `V-M-xxx` entries — criteria are derived from it, not invented per run;
- `MODULE_CONTRACT` / function contracts / `START_BLOCK_*` and log markers `[Module][function][BLOCK_NAME]` inside the module;
- a run that can write a machine-readable journal (JSONL), ideally into the module's own directory.

## Process

### 1. Turn criteria into artifacts, not prose

Each criterion gets a record: `id`, `stage`, `rule`, `why`. Keep them next to the code that is being judged. A criterion without `why` degenerates into ritual.

```json
{"id": "crit.completeness.join", "stage": "join",
 "rule": "rows_out >= rows_in - len(orphan_keys)",
 "why": "выпадение на JOIN: любая запись с ключом из справочника обязана дойти до выхода"}
```

### 2. Make the pipeline log per stage

For every transformation stage emit one event with: `rows_in`, `rows_out`, `unmatched` **by the same predicate the code uses**, `orphan_keys`, dimension duplicates with the fan-out multiplier, key-hygiene suspects (whitespace, case, homoglyphs, leading zeros, number/string mismatch), `sum_in` / `sum_out` / `delta` per numeric column, `distinct_keys_in` / `distinct_keys_out`, and an **offenders sample with full records** — counts alone give no context.

Plus the always-needed envelope: `spec_id`, `correlation_id`, code version (commit hash), environment, timestamp, `signal`.

### 3. Evaluate from the journal only

The evaluator reads the journal and the criteria file — and has **no access to the source data**. If the verdict cannot be computed from the journal, the journal is too poor: that is a finding about observability, not a failure of the evaluator.

### 4. Use three states, never two

`ok` / `ALARM` / `unverifiable`. Unverifiable criteria are the **observability backlog** — publish the list of missing fields. Reporting `unverifiable` as `ok` is the same class of error as reporting "no data" as "no events".

### 5. Reconcile with the pipeline's own predicate

Recompute counts using exactly the code's predicate (same normalization, same types, same collation). A reconciliation that normalizes keys "correctly" while the pipeline does not will understate the loss. Then **decompose the residual** into known effects (fan-out inflation minus lost rows): a diagnosable residual is what makes a one-shot fix possible.

### 6. Attach evidence to specification points

Every requirement point gets an id (`spec.<domain>.<point>`). The run leaves an evidence line; the test asserts the evidence verdict:

```python
def test_set_params_changes_state_and_leaves_evidence(configured, trace):
    response = call("tools/call", {"name": "set_params", "arguments": {"a": 2.0}})
    assert response["result"]["isError"] is False        # business effect
    assert state.current()["a"] == 2.0                   # business effect
    assert verdict(trace(), "spec.mcp.tools")["signal"] == "ok"   # evidence
```

### 7. Keep the test three-layered

(1) drive the path and fill the journal; (2) assert the business effect; (3) assert the evidence for the spec point. Assertions read the journal, not the implementation's internal state.

### 8. Split the checking roles by cost

- **Algorithmic, per commit** (deterministic, cheap): criteria reconciliation, contract checks, linters, plus a **mutation control on the evidence assertions themselves** — remove the evidence line, the check must go red.
- **Agentic, per PR / release / event** (expensive, gives diagnosis): walk the application as a user over MCP / CLI / browser, then produce a report: steps, data slice, log lines with correlation ids, hypothesis, minimal repro, code and environment version. Target: the report alone must be enough for a one-shot fix.

Budget by consequence class: the full contour (traceability + independent evidence writer + formal invariants) where failure is expensive; the light contour (criteria in the journal + telemetry + a second agent cross-check) elsewhere.

## Evidence must not be forgeable

- the evidence line is written by a role **separated** from the author of the change (the DO-178C "with independence" analogue);
- the journal is append-only with a hash chain or signature — otherwise `"signal": "ok"` gets appended around the code;
- the verdict checks the **content** of the line (spec_id, inputs, code version, environment, time, correlation id), not its presence;
- every workaround an agent used to continue testing is reported as an open defect in a dedicated field and **blocks acceptance** until resolved — otherwise the advantage "hit a bug, worked around it, kept testing" masks defects;
- agentic acceptance needs an independent critic, or it degenerates into self-assessment — exactly the signal models learn to fake (overwritten tests, read expected outputs, `exit(0)`).

## Common Pitfalls

- **Reconciliation that normalizes "correctly"** → recompute with the pipeline's own predicate; otherwise the loss is understated (observed in a runnable demo: 7 of 8 matched and 500 lost instead of 6 of 8 and 525 lost).
- **Reporting `unverifiable` as `ok`** → keep three states and publish the unverifiable list as the backlog.
- **Criteria kept in prose** → store `id/stage/rule/why` in a file the evaluator reads; an evaluator that needs the source data hides a journal gap.
- **Evidence written by the same agent that wrote the change** → separate the writer role; self-assessment is what gets faked.
- **Agent workarounds silenced** → a mandatory `workaround` field that blocks acceptance.
- **Trusting a green suite after touching a pipeline** → run the criteria; corrupted output passes every shape assertion (file exists, table non-empty, keys known, values positive).
- **Fixing a criterion by writing another test** → if a field is missing from the journal, fix the logging.
- **Logging everything instead of staged counters** → context has a price; log counters, sums, dividers and an offenders sample.
- **Acceptance measured by pass rate** → measure the share of specification points that have valid evidence, plus a diagnostic report without open workarounds.

## Runnable example

`experiments/phantom-join/` in this repository: `demo.py` (six green happy-path tests on corrupted output), `run_log.py` (writes only the journal; `--orphan-amount` adds one field), `criteria.json`, `evaluate.py` (three-state verdict from the journal alone). `bash experiments/run_all.sh` reproduces both modes.

## See also

- `references/diagnostics-over-tests-dirty-data.md` — phantom records, dropped JOINs, LDD and the criteria experiment;
- `references/grace-tests-as-logs-and-evidence.md` — tests as journal fillers and evidence per spec point;
- `references/agentic-e2e-vs-scripted-tests.md` — what to do with scripted E2E scenarios, and the algorithmic/agentic split;
- `references/unit-test-only-reward-degradation.md` — why "tests as the goal" degrades quality even when pass rate holds.
