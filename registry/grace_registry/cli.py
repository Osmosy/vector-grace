"""CLI реестра требований GRACE.

Команды:
  parse         источники → спаны (кэш, пересобирается)
  verdict       вердикт по спану, кроме requirement/constraint
  add-req       спан → запись требования (вердикт + REQ-NNNN)
  revise        новая ревизия требования (запись не правится)
  invariant-add инвариант с обязательным списком переходов
  evidence      запись доказательства с defeater
  coverage      гейт покрытия спанов
  drift         гейт дрейфа, три класса
  replay        перезапуск чекеров по (req_id, code_hash)
  status        сводка

Коды выхода: 0 — чисто, 1 — блокирующие находки, 2 — плохой вход, 3 — чекер
не тот (подмена версии, инвариант без переходов).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import gates, measure as measure_mod, model, replay, spans as spans_mod

_CHOICES_NON_REQ = ("question", "decision", "background", "duplicate", "open")


class Layout:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.docs = self.root / "docs"
        self.registry_dir = self.docs / "registry"
        self.sources = self.registry_dir / "sources.json"
        self.spans = self.registry_dir / "spans.jsonl"
        self.verdicts = self.registry_dir / "verdicts.jsonl"
        self.evidence = self.registry_dir / "evidence.jsonl"
        self.invariants = self.registry_dir / "invariants.jsonl"
        self.measurements = self.registry_dir / "measurements.jsonl"
        self.requirements = self.docs / "requirements-registry.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fail(message: str, code: int = 2) -> int:
    print(f"ошибка: {message}", file=sys.stderr)
    return code


def _load_sources(lay: Layout) -> list[dict]:
    if not lay.sources.exists():
        raise ValueError(f"нет {lay.sources.relative_to(lay.root)}")
    payload = json.loads(lay.sources.read_text("utf-8"))
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("sources.json: пустой список sources")
    return sources


def _span_index(lay: Layout) -> dict[str, dict]:
    return {rec["span_id"]: rec for rec in model.load_jsonl(lay.spans)}


def _need_span(lay: Layout, span_id: str) -> dict:
    span = _span_index(lay).get(span_id)
    if span is None:
        raise ValueError(
            f"спан {span_id} не найден; сначала пересоберите: grace.py parse"
        )
    return span


def _print_findings(findings: list[gates.Finding], as_json: bool, title: str) -> int:
    blocked = gates.has_block(findings)
    if as_json:
        print(
            json.dumps(
                {
                    "gate": title,
                    "ok": not blocked,
                    "blocking": sum(1 for f in findings if f.severity == gates.BLOCK),
                    "warnings": sum(1 for f in findings if f.severity != gates.BLOCK),
                    "findings": [f.as_dict() for f in findings],
                },
                ensure_ascii=False,
                indent=1,
            )
        )
    else:
        for finding in findings:
            print(finding.line())
        blocking = sum(1 for f in findings if f.severity == gates.BLOCK)
        warnings = len(findings) - blocking
        verdict = "ЧИСТО" if not blocked and not warnings else (
            "БЛОК" if blocked else "предупреждения"
        )
        print(f"{title}: {verdict} — блокирующих {blocking}, предупреждений {warnings}")
    return 1 if blocked else 0


# ---------------------------------------------------------------- команды


def cmd_parse(args, lay: Layout) -> int:
    sources = _load_sources(lay)
    lay.registry_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    for src in sources:
        rel = str(src.get("file", ""))
        path = lay.root / rel
        if not path.is_file():
            return _fail(f"источник не найден: {rel}")
        data = path.read_bytes()
        file_records = list(spans_mod.records(data, rel))
        records.extend(file_records)
        modal = sum(
            1 for rec in file_records if spans_mod.obligations(rec["text"])
        )
        print(f"{rel}: спанов {len(file_records)}, с модальностью {modal}")
    tmp = lay.spans.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(lay.spans)
    print(f"всего спанов: {len(records)} → {lay.spans.relative_to(lay.root)}")
    return 0


def cmd_verdict(args, lay: Layout) -> int:
    span = _need_span(lay, args.span_id)
    if args.kind == "open":
        quote = (args.quote or "").strip()
        if not quote and not (args.note or "").strip():
            return _fail("open требует дословную цитату (--quote) или прямую пометку")
        if quote and quote not in span["text"]:
            return _fail("цитата не найдена в тексте спана: пересказ не цитата")
    record = {
        "span_id": span["span_id"],
        "file": span["file"],
        "span": span["span"],
        "span_sha256": span["sha256"],
        "kind": args.kind,
        "quote": args.quote,
        "note": args.note,
        "by": args.by,
        "at": _now(),
    }
    model.append_jsonl(lay.verdicts, record)
    print(f"вердикт: {span['span_id']} → {args.kind}")
    return 0


def cmd_add_req(args, lay: Layout) -> int:
    span = _need_span(lay, args.span_id)
    sources = {str(s.get("file")): s for s in _load_sources(lay)}
    src = sources.get(span["file"])
    if src is None:
        return _fail(f"источник {span['file']} не объявлен в sources.json")
    existing = model.load_jsonl(lay.requirements)
    req_id = args.req_id or model.next_req_id(existing)
    if any(rec.get("req_id") == req_id for rec in existing):
        return _fail(f"{req_id} уже существует")
    record = {
        "req_id": req_id,
        "rev": 1,
        "source": {
            "file": span["file"],
            "sha256": span["file_sha256"],
            "span": span["span"],
            "channel": src.get("channel"),
            "speaker": src.get("speaker"),
            "date": src.get("date"),
        },
        "raw_text": span["text"],
        "req_hash": model.req_hash(span["text"]),
        "kind": args.kind,
        "strength": args.strength,
        "status": args.status,
        "supersedes": None,
        "superseded_by": None,
        "invariants": [],
        "owner": args.owner,
        "deadline": args.deadline,
        "created_by": args.by,
        "at": _now(),
    }
    problems = model.problems(record)
    if problems:
        return _fail(f"{req_id}: " + "; ".join(problems))
    model.append_jsonl(lay.requirements, record)
    model.append_jsonl(
        lay.verdicts,
        {
            "span_id": span["span_id"],
            "file": span["file"],
            "span": span["span"],
            "span_sha256": span["sha256"],
            "kind": args.kind,
            "note": f"→ {req_id}",
            "by": args.by,
            "at": _now(),
        },
    )
    print(f"{req_id}: {args.kind}/{args.strength}/{args.status} ← {span['span_id']}")
    return 0


def cmd_revise(args, lay: Layout) -> int:
    records = model.load_jsonl(lay.requirements)
    live = model.live_requirements(records)
    current = live.get(args.req)
    if current is None:
        return _fail(f"{args.req} не найден")
    new = dict(current)
    new["rev"] = int(current.get("rev", 1)) + 1
    new["revised_by"] = args.by
    new["at"] = _now()
    if args.status:
        new["status"] = args.status
    if args.owner is not None:
        new["owner"] = args.owner
    if args.deadline is not None:
        new["deadline"] = args.deadline
    if args.superseded_by:
        new["status"] = "superseded"
        new["superseded_by"] = args.superseded_by
        new["supersedes"] = current.get("supersedes")
    problems = model.problems(new)
    if problems:
        return _fail(f"{args.req} rev {new['rev']}: " + "; ".join(problems))
    model.append_jsonl(lay.requirements, new)
    print(f"{args.req}: ревизия {new['rev']} → {new['status']}")
    return 0


def cmd_invariant_add(args, lay: Layout) -> int:
    records = model.load_jsonl(lay.requirements)
    live = model.live_requirements(records)
    if args.req not in live:
        return _fail(f"{args.req} не найден")
    predicate = Path(args.predicate)
    if not (lay.root / predicate).is_file():
        return _fail(f"предикат не найден: {args.predicate}")
    transitions = [t.strip() for t in args.transitions.split(",") if t.strip()]
    if not transitions:
        return _fail(
            "инвариант без списка переходов — снимок, а не свойство системы",
            replay.INTEGRITY_EXIT,
        )
    existing = model.load_jsonl(lay.invariants)
    inv_id = args.inv or f"INV-{len(existing) + 1:04d}"
    record = {
        "inv_id": inv_id,
        "req_id": args.req,
        "kind": args.kind,
        "transition_scope": "переходы, на которых проверяется сохранение",
        "transitions": transitions,
        "predicate": {
            "path": predicate.as_posix(),
            "sha256": spans_mod.sha256_file(lay.root / predicate),
        },
        "checker_version": str(args.checker_version),
        "measured": {"false_accept": args.fa, "false_reject": args.fr, "n": args.n},
        "by": args.by,
        "at": _now(),
    }
    model.append_jsonl(lay.invariants, record)
    if inv_id not in (live[args.req].get("invariants") or []):
        new = dict(live[args.req])
        new["rev"] = int(live[args.req].get("rev", 1)) + 1
        new["invariants"] = sorted((new.get("invariants") or []) + [inv_id])
        new["at"] = _now()
        model.append_jsonl(lay.requirements, new)
    print(f"{inv_id}: предикат {predicate.as_posix()} → {args.req}, переходов {len(transitions)}")
    return 0


def cmd_evidence(args, lay: Layout) -> int:
    records = model.load_jsonl(lay.requirements)
    live = model.live_requirements(records)
    rec = live.get(args.req)
    if rec is None:
        return _fail(f"{args.req} не найден")
    invariants = {i["inv_id"]: i for i in model.load_jsonl(lay.invariants) if "inv_id" in i}
    inv = invariants.get(args.inv)
    if inv is None:
        return _fail(f"{args.inv} не найден")
    if args.transition not in (inv.get("transitions") or []):
        return _fail(f"переход {args.transition} не объявлен у {args.inv}")
    predicate = lay.root / inv["predicate"]["path"]
    if not predicate.is_file():
        return _fail(f"предикат не найден: {inv['predicate']['path']}")
    actual = spans_mod.sha256_file(predicate)
    if actual != inv["predicate"]["sha256"]:
        return _fail(
            "версия предиката не совпадает с записанной в инварианте",
            replay.INTEGRITY_EXIT,
        )
    if not (args.defeater or "").strip():
        return _fail("без defeater запись доказательства — декорация")
    code_root = Path(args.code_root).resolve() if args.code_root else lay.root
    measured = None
    for item in model.load_jsonl(lay.measurements):
        if item.get("inv_id") == args.inv and item.get("checker_sha256") == actual:
            measured = {
                "source": "measure",
                "at": item.get("at"),
                "bench": item.get("bench"),
                "mutants": item.get("mutants"),
                "detected": item.get("detected"),
                "false_accept": item.get("false_accept"),
                "false_reject": item.get("false_reject"),
            }
    record = {
        "req_id": args.req,
        "req_hash": rec.get("req_hash"),
        "inv_id": args.inv,
        "transition": args.transition,
        "checker": inv["predicate"]["path"],
        "checker_sha256": actual,
        "checker_version": inv.get("checker_version"),
        "code_hash": replay.code_hash(code_root),
        "result": args.result,
        "defeater": args.defeater,
        "detail": args.detail,
        "measured": measured,
        "by": args.by,
        "at": _now(),
    }
    model.append_jsonl(lay.evidence, record)
    tail = ""
    if measured:
        tail = f" (замер: пропуск {measured['false_accept']}, ложное отклонение {measured['false_reject']}, n={measured['mutants']})"
    print(f"доказательство: {args.req} / {args.inv} / {args.transition} → {args.result}{tail}")
    return 0


def cmd_measure(args, lay: Layout) -> int:
    invariants = {
        rec["inv_id"]: rec for rec in model.load_jsonl(lay.invariants) if "inv_id" in rec
    }
    inv = invariants.get(args.inv)
    if inv is None:
        return _fail(f"{args.inv} не найден")
    predicate = (
        (lay.root / args.predicate) if args.predicate else (lay.root / inv["predicate"]["path"])
    )
    if not predicate.is_file():
        return _fail(f"предикат не найден: {predicate}")
    bench_path = lay.root / (args.bench or "bench/bench.json")
    try:
        bench = measure_mod.load_bench(bench_path)
    except measure_mod.BenchError as exc:
        return _fail(str(exc))
    transition = args.transition or bench.get("transition") or (inv.get("transitions") or [""])[0]
    if not transition:
        return _fail("переход не задан ни в bench, ни в инварианте")
    report = measure_mod.measure(predicate, lay.root, bench, transition)
    report["inv_id"] = args.inv
    report["bench"] = bench_path.relative_to(lay.root).as_posix()
    report["registered"] = report["checker_sha256"] == inv["predicate"]["sha256"]

    if args.out:
        out_path = lay.root / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        state = "зарегистрированный" if report["registered"] else "кандидат, не записан в инвариант"
        print(f"{args.inv}: предикат {Path(report['checker']).name} ({state}), переход {transition}")
        print(f"чистый код: {'проходит' if report['clean_ok'] else 'ОТКЛОНЁН'}")
        for item in report["results"]:
            mark = "поймал " if item["detected"] else "пропустил"
            print(f"  {mark} {item['class']}: {item['name']}")
        print(
            f"обнаружено {report['detected']} из {report['mutants']}"
            f" (пропуск {report['false_accept']}), ложных отклонений на чистом коде"
            f" {report['false_reject']} при {report['clean_runs']} прогоне"
        )

    if args.predicate:
        # Кандидата не фиксируем: в инвариант он попадает только новой версией
        # чекера, а это уже отдельная запись с новым sha256.
        return 0 if report["clean_ok"] else 1

    model.append_jsonl(
        lay.measurements,
        {
            "inv_id": args.inv,
            "checker_sha256": report["checker_sha256"],
            "bench": report["bench"],
            "transition": transition,
            "mutants": report["mutants"],
            "detected": report["detected"],
            "false_accept": report["false_accept"],
            "false_reject": report["false_reject"],
            "by_class": report["by_class"],
            "by": args.by,
            "at": _now(),
        },
    )
    if not args.json:
        print(f"замер записан: {lay.measurements.relative_to(lay.root)}")
    return 0 if report["clean_ok"] else 1


def cmd_coverage(args, lay: Layout) -> int:
    spans = model.load_jsonl(lay.spans)
    if not spans:
        return _fail("спаны не собраны: сначала grace.py parse")
    findings = gates.coverage_gate(spans, model.load_jsonl(lay.verdicts))
    return _print_findings(findings, args.json, "coverage")


def cmd_drift(args, lay: Layout) -> int:
    records = model.load_jsonl(lay.requirements)
    if not records:
        return _fail("реестр пуст: docs/requirements-registry.jsonl")
    evidence = model.load_jsonl(lay.evidence)
    artifacts_root = Path(args.artifacts_root).resolve() if args.artifacts_root else lay.root
    artifacts = gates.scan_artifacts(artifacts_root)
    registry_rel = lay.requirements.relative_to(artifacts_root).as_posix()
    artifacts.pop(registry_rel, None)
    artifacts = {
        path: ids
        for path, ids in artifacts.items()
        if not path.startswith("docs/registry/")
    }
    findings = gates.drift_gate(records, evidence, artifacts)
    return _print_findings(findings, args.json, "drift")


def cmd_replay(args, lay: Layout) -> int:
    records = model.load_jsonl(lay.requirements)
    evidence = model.load_jsonl(lay.evidence)
    invariants = {
        rec["inv_id"]: rec for rec in model.load_jsonl(lay.invariants) if "inv_id" in rec
    }
    if not evidence:
        return _fail("записей доказательств нет — перезапускать нечего")
    try:
        results, findings = replay.replay_evidence(
            records, evidence, invariants, lay.root, only_req=args.req
        )
    except replay.IntegrityError as exc:
        print(f"отказ: {exc}", file=sys.stderr)
        return replay.INTEGRITY_EXIT
    if args.json:
        print(
            json.dumps(
                {"results": results, "findings": [f.as_dict() for f in findings]},
                ensure_ascii=False,
                indent=1,
            )
        )
    else:
        for item in results:
            mark = "ok " if item["match"] else "НЕ СХОДИТСЯ"
            print(
                f"{mark} {item['req_id']} / {item['inv_id']} / {item['transition']}: "
                f"в записи {item['expected']}, сейчас {item['actual']}"
            )
        for finding in findings:
            print(finding.line())
    return 1 if gates.has_block(findings) else 0


def cmd_status(args, lay: Layout) -> int:
    spans = model.load_jsonl(lay.spans)
    verdicts = model.load_jsonl(lay.verdicts)
    records = model.load_jsonl(lay.requirements)
    evidence = model.load_jsonl(lay.evidence)
    live = model.live_requirements(records)
    by_status: dict[str, int] = {}
    for rec in live.values():
        by_status[str(rec.get("status"))] = by_status.get(str(rec.get("status")), 0) + 1
    print(f"корень: {lay.root}")
    print(f"спанов: {len(spans)}, вердиктов: {len(verdicts)}")
    print(f"требований (живых ревизий): {len(live)} {by_status}")
    print(f"доказательств: {len(evidence)}")
    print(f"инвариантов: {len(model.load_jsonl(lay.invariants))}")
    if spans:
        covered = {
            v.get("span_id")
            for v in verdicts
            if v.get("span_sha256")
        }
        hit = sum(1 for s in spans if s.get("span_id") in covered)
        print(f"покрытие спанов: {hit}/{len(spans)}")
    return 0


# ------------------------------------------------------------------- сборка


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grace.py", description="Реестр требований GRACE: спаны, дрейф, чекеры"
    )
    parser.add_argument("--root", default=".", help="корень проверяемого проекта")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("parse", help="источники → спаны")

    v = sub.add_parser("verdict", help="вердикт по спану")
    v.add_argument("--span-id", required=True)
    v.add_argument("--kind", required=True, choices=_CHOICES_NON_REQ)
    v.add_argument("--quote")
    v.add_argument("--note")
    v.add_argument("--by", required=True)

    a = sub.add_parser("add-req", help="спан → требование")
    a.add_argument("--span-id", required=True)
    a.add_argument("--kind", default="requirement", choices=("requirement", "constraint"))
    a.add_argument("--strength", default="must", choices=model.STRENGTHS)
    a.add_argument("--status", default="elicited", choices=model.STATUSES)
    a.add_argument("--req-id")
    a.add_argument("--owner")
    a.add_argument("--deadline")
    a.add_argument("--by", required=True)

    r = sub.add_parser("revise", help="новая ревизия требования")
    r.add_argument("--req", required=True)
    r.add_argument("--status", choices=model.STATUSES)
    r.add_argument("--owner")
    r.add_argument("--deadline")
    r.add_argument("--superseded-by")
    r.add_argument("--by", required=True)

    i = sub.add_parser("invariant-add", help="инвариант с переходами")
    i.add_argument("--inv")
    i.add_argument("--req", required=True)
    i.add_argument("--predicate", required=True)
    i.add_argument("--transitions", required=True, help="через запятую")
    i.add_argument("--checker-version", default="1")
    i.add_argument("--kind", default="semantic", choices=("analytic", "semantic"))
    i.add_argument("--fa", type=float, help="доля ложных приёмок на замере")
    i.add_argument("--fr", type=float, help="доля ложных отклонений на замере")
    i.add_argument("--n", type=int, help="размер замера")
    i.add_argument("--by", required=True)

    e = sub.add_parser("evidence", help="запись доказательства")
    e.add_argument("--req", required=True)
    e.add_argument("--inv", required=True)
    e.add_argument("--transition", required=True)
    e.add_argument("--result", required=True, choices=("pass", "fail"))
    e.add_argument("--defeater", required=True)
    e.add_argument("--detail")
    e.add_argument("--code-root")
    e.add_argument("--by", required=True)

    m = sub.add_parser("measure", help="замер предиката на посаженных дефектах")
    m.add_argument("--inv", required=True)
    m.add_argument("--bench", help="набор дефектов, по умолчанию bench/bench.json")
    m.add_argument("--predicate", help="кандидат вместо зарегистрированного предиката")
    m.add_argument("--transition")
    m.add_argument("--out", help="записать отчёт в файл")
    m.add_argument("--json", action="store_true")
    m.add_argument("--by", required=True)

    c = sub.add_parser("coverage", help="гейт покрытия спанов")
    c.add_argument("--json", action="store_true")

    d = sub.add_parser("drift", help="гейт дрейфа")
    d.add_argument("--json", action="store_true")
    d.add_argument("--artifacts-root")

    p = sub.add_parser("replay", help="перезапуск чекеров")
    p.add_argument("--req")
    p.add_argument("--json", action="store_true")

    sub.add_parser("status", help="сводка")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    lay = Layout(args.root)
    handlers = {
        "parse": cmd_parse,
        "verdict": cmd_verdict,
        "add-req": cmd_add_req,
        "revise": cmd_revise,
        "invariant-add": cmd_invariant_add,
        "evidence": cmd_evidence,
        "measure": cmd_measure,
        "coverage": cmd_coverage,
        "drift": cmd_drift,
        "replay": cmd_replay,
        "status": cmd_status,
    }
    try:
        return handlers[args.cmd](args, lay)
    except (ValueError, FileNotFoundError) as exc:
        return _fail(str(exc))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
