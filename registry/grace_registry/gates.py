"""Гейты: покрытие спанов и три класса дрейфа.

Оба гейта механические: только джойны и сравнения хэшей. Ни один из них не
спрашивает модель «правильно ли понято» — такой вопрос неопровержим и потому
не является проверкой.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import model, spans as spans_mod

BLOCK = "block"
WARN = "warn"

_ARTIFACT_EXT = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt",
    ".sql", ".md", ".xml", ".yaml", ".yml", ".json", ".jsonl", ".toml",
    ".c", ".h", ".cpp", ".cs", ".rb", ".php", ".sh",
}
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".hermes",
}
_REQ_REF = re.compile(r"\bREQ-\d{4,}\b")


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    where: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "where": self.where,
        }

    def line(self) -> str:
        loc = ", ".join(f"{k}={v}" for k, v in self.where.items())
        return f"[{self.severity.upper():5}] {self.code}: {self.message}" + (
            f"  ({loc})" if loc else ""
        )


def has_block(findings: list[Finding]) -> bool:
    return any(f.severity == BLOCK for f in findings)


# ---------------------------------------------------------------- покрытие


def coverage_gate(span_records: list[dict], verdicts: list[dict]) -> list[Finding]:
    """Каждый спан каждого источника имеет вердикт; модальный спан не в фоне.

    Вердикт покрывает спан только при совпадении span_id и sha256 спана.
    Если текст изменился, вердикт перестаёт покрывать — это и есть повторная
    экстракция, а не потеря работы.
    """
    findings: list[Finding] = []
    latest: dict[str, dict] = {}
    for verdict in verdicts:
        sid = verdict.get("span_id")
        if isinstance(sid, str):
            latest[sid] = verdict  # append-only: последняя запись выигрывает

    current: set[str] = set()
    for span in span_records:
        sid = str(span.get("span_id") or "")
        current.add(sid)
        verdict = latest.get(sid)
        where = {"file": span.get("file"), "span": span.get("span"), "span_id": sid}
        if verdict is None:
            findings.append(
                Finding("uncovered_span", BLOCK, "спан без вердикта", where)
            )
            continue
        if verdict.get("span_sha256") != span.get("sha256"):
            findings.append(
                Finding(
                    "uncovered_span",
                    BLOCK,
                    "вердикт относится к другой версии текста спана",
                    where,
                )
            )
            continue
        kind = verdict.get("kind")
        if kind in ("background", "duplicate"):
            modal = spans_mod.obligations(span.get("text") or "")
            if modal:
                findings.append(
                    Finding(
                        "hidden_obligation",
                        BLOCK,
                        f"спан помечен {kind}, но несёт модальность: {', '.join(modal)}",
                        {**where, "kind": kind, "modal": modal},
                    )
                )
    for sid in sorted(set(latest) - current):
        findings.append(
            Finding(
                "stale_verdict",
                WARN,
                "вердикт не соответствует ни одному текущему спану (текст изменился или удалён)",
                {"span_id": sid, "kind": latest[sid].get("kind")},
            )
        )
    return findings


# ------------------------------------------------------------------- дрейф


def drift_gate(
    requirements: list[dict],
    evidence: list[dict],
    artifacts: dict[str, set[str]] | None = None,
    span_index: dict[str, dict] | None = None,
) -> list[Finding]:
    """Три класса: устаревшее доказательство, недоказанное требование, осиротевшее.

    Плюс два поля, без которых запись доказательства декоративна: defeater и
    список переходов (переходы проверяются в replay, здесь — только defeater).
    """
    findings: list[Finding] = []
    live = model.live_requirements(requirements)

    for rid, rec in sorted(live.items()):
        for problem in model.problems(rec):
            findings.append(
                Finding(
                    "invalid_record",
                    BLOCK,
                    f"{rid}: {problem}",
                    {"req_id": rid, "rev": rec.get("rev")},
                )
            )

    by_req: dict[str, list[dict]] = {}
    for ev in evidence:
        by_req.setdefault(str(ev.get("req_id")), []).append(ev)

    for rid, rec in sorted(live.items()):
        status = rec.get("status")
        current = rec.get("req_hash")
        evs = by_req.get(rid, [])
        if status in model.BLOCKING_STATUSES:
            if not evs:
                findings.append(
                    Finding(
                        "unproven_requirement",
                        BLOCK,
                        "требование в силе, evidence[] пуст",
                        {"req_id": rid, "status": status},
                    )
                )
                continue
            fresh = [ev for ev in evs if ev.get("req_hash") == current]
            if not fresh:
                findings.append(
                    Finding(
                        "unproven_requirement",
                        BLOCK,
                        "все доказательства относятся к прежней версии требования",
                        {"req_id": rid, "evidence": len(evs)},
                    )
                )
            elif not any(ev.get("result") == "pass" for ev in fresh):
                findings.append(
                    Finding(
                        "unproven_requirement",
                        BLOCK,
                        "актуальные доказательства не проходят",
                        {"req_id": rid, "evidence": len(fresh)},
                    )
                )
    for ev in evidence:
        rid = str(ev.get("req_id"))
        rec = live.get(rid)
        if rec is None:
            findings.append(
                Finding(
                    "orphaned_evidence",
                    BLOCK,
                    "доказательство ссылается на требование, которого нет в реестре",
                    {"req_id": rid, "inv_id": ev.get("inv_id")},
                )
            )
            continue
        if rec.get("status") in model.DEAD_STATUSES:
            findings.append(
                Finding(
                    "orphaned_evidence",
                    BLOCK,
                    f"требование {rec.get('status')}, а доказательство живо и считается выполненным",
                    {"req_id": rid, "status": rec.get("status")},
                )
            )
            continue
        if ev.get("req_hash") != rec.get("req_hash"):
            findings.append(
                Finding(
                    "stale_evidence",
                    BLOCK,
                    "evidence.req_hash не совпадает с текущим хэшем требования",
                    {"req_id": rid, "inv_id": ev.get("inv_id")},
                )
            )
        if not ev.get("defeater"):
            findings.append(
                Finding(
                    "undefeatable_evidence",
                    BLOCK,
                    "у записи доказательства нет defeater — назовите наблюдение, которое её опровергнет",
                    {"req_id": rid, "inv_id": ev.get("inv_id")},
                )
            )
        source = ev.get("source_span")
        if source and span_index is not None:
            current_span = span_index.get(str(source.get("span_id")))
            where = {
                "req_id": rid,
                "file": source.get("file"),
                "page": source.get("page"),
            }
            if current_span is None:
                findings.append(
                    Finding(
                        "orphaned_source_span",
                        BLOCK,
                        "спан источника исчез: страница пересобрана или удалена",
                        where,
                    )
                )
            elif current_span.get("sha256") != source.get("span_sha256"):
                findings.append(
                    Finding(
                        "stale_source_span",
                        BLOCK,
                        "текст страницы источника изменился после доказательства",
                        where,
                    )
                )

    for path, ids in sorted((artifacts or {}).items()):
        for rid in sorted(ids):
            rec = live.get(rid)
            if rec is None:
                findings.append(
                    Finding(
                        "orphaned_reference",
                        BLOCK,
                        "код или тесты ссылаются на требование, которого нет в реестре",
                        {"req_id": rid, "file": path},
                    )
                )
            elif rec.get("status") in model.DEAD_STATUSES:
                findings.append(
                    Finding(
                        "orphaned_reference",
                        BLOCK,
                        f"код или тесты ссылаются на требование со статусом {rec.get('status')}",
                        {"req_id": rid, "file": path, "status": rec.get("status")},
                    )
                )
    return findings


def scan_artifacts(
    root, skip_dirs: set[str] | None = None, max_bytes: int = 2_000_000
) -> dict[str, set[str]]:
    """Ссылки на REQ-ID в коде, тестах и документах проекта."""
    root_path = Path(root)
    skip = _SKIP_DIRS | (skip_dirs or set())
    found: dict[str, set[str]] = {}
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix not in _ARTIFACT_EXT:
            continue
        rel = path.relative_to(root_path)
        if any(part in skip for part in rel.parts[:-1]):
            continue
        try:
            if path.stat().st_size > max_bytes:
                continue
            text = path.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        ids = set(_REQ_REF.findall(text))
        if ids:
            found[rel.as_posix()] = ids
    return found
