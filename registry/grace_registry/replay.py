"""Перезапуск чекеров: приёмка — исполнение предиката, а не чтение лога.

Проверяющий не может править ни код, ни предикат: версия чекера закреплена
хэшем в записи инварианта и в записи доказательства. Совпадение хэшей —
условие запуска; расхождение — отказ (IntegrityError), а не «прогнали и ладно».

Сила берётся из маленького доверенного ядра: исполняемого предиката. Два
мнения LLM (генератор и ревьюер) цепочки доказательств не образуют.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from . import gates, model, spans as spans_mod

INTEGRITY_EXIT = 3


class IntegrityError(RuntimeError):
    """Проверку запускать нельзя: версия чекера или инвариант не те."""


def code_hash(root, includes: tuple[str, ...] | None = None) -> str:
    """Один хэш на дерево кода: отсортированные (путь, sha256) файлов."""
    root_path = Path(root)
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
    digests: list[tuple[str, str]] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root_path)
        if any(part in skip for part in rel.parts[:-1]):
            continue
        if includes and path.suffix not in includes:
            continue
        digests.append((rel.as_posix(), spans_mod.sha256_file(path)))
    payload = "".join(f"{name}\0{digest}\n" for name, digest in digests)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_checker(
    predicate, code_root, transition: str, timeout: int = 300
) -> dict:
    """Предикат обязан напечатать JSON {"ok": bool, "detail": str}."""
    try:
        proc = subprocess.run(
            [sys.executable, str(predicate), "--root", str(code_root), "--transition", transition],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": f"таймаут {timeout} с", "exit": None}
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    if not lines:
        return {
            "ok": False,
            "detail": f"чекер ничего не напечатал (stderr: {proc.stderr.strip()[:200]})",
            "exit": proc.returncode,
        }
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return {
            "ok": False,
            "detail": f"не JSON: {lines[-1][:200]}",
            "exit": proc.returncode,
        }
    ok = bool(payload.get("ok")) and proc.returncode in (0, 1)
    return {
        "ok": ok,
        "detail": str(payload.get("detail", "")),
        "exit": proc.returncode,
    }


def replay_evidence(
    requirements: list[dict],
    evidence: list[dict],
    invariants: dict[str, dict],
    code_root,
    only_req: str | None = None,
) -> tuple[list[dict], list[gates.Finding]]:
    """Перезапуск по (req_id, code_hash) со сверкой с записанным результатом.

    Возвращает (результаты прогонов, находки). IntegrityError — запускать
    нельзя; это отдельный код выхода, чтобы «чекер подменили» не выглядело
    как обычное падение проверки.
    """
    live = model.live_requirements(requirements)
    results: list[dict] = []
    findings: list[gates.Finding] = []

    # Журнал append-only: одну и ту же пару (req_id, inv_id, переход) могли
    # перевыпустить (новая версия чекера, другой результат). Приёмка перезапускает
    # актуальную запись, а не первую попавшуюся.
    latest: dict[tuple[str, str, str], dict] = {}
    for ev in evidence:
        key = (
            str(ev.get("req_id")),
            str(ev.get("inv_id")),
            str(ev.get("transition")),
        )
        latest[key] = ev
    evidence = list(latest.values())

    for ev in evidence:
        rid = str(ev.get("req_id"))
        if only_req and rid != only_req:
            continue
        rec = live.get(rid)
        if rec is None:
            findings.append(
                gates.Finding(
                    "orphaned_evidence",
                    gates.BLOCK,
                    "перезапускать нечего: требование не найдено",
                    {"req_id": rid},
                )
            )
            continue
        if ev.get("req_hash") != rec.get("req_hash"):
            findings.append(
                gates.Finding(
                    "stale_evidence",
                    gates.BLOCK,
                    "доказательство относится к прежней версии требования",
                    {"req_id": rid},
                )
            )
            continue

        inv_id = str(ev.get("inv_id"))
        inv = invariants.get(inv_id)
        if inv is None:
            findings.append(
                gates.Finding(
                    "missing_invariant",
                    gates.BLOCK,
                    "инвариант не найден: перезапуск невозможен",
                    {"req_id": rid, "inv_id": inv_id},
                )
            )
            continue

        transitions = inv.get("transitions") or []
        if not transitions:
            raise IntegrityError(
                f"{inv_id}: инвариант без списка переходов — это снимок, а не свойство системы"
            )
        transition = str(ev.get("transition") or "")
        if transition not in transitions:
            raise IntegrityError(
                f"{inv_id}: переход {transition!r} не входит в объявленный список {transitions}"
            )

        predicate = Path(inv.get("predicate", {}).get("path", ""))
        if not predicate.is_absolute():
            predicate = Path(code_root) / predicate
        if not predicate.exists():
            raise IntegrityError(f"{inv_id}: файл предиката не найден: {predicate}")
        actual = spans_mod.sha256_file(predicate)
        declared = inv.get("predicate", {}).get("sha256")
        recorded = ev.get("checker_sha256")
        if not (actual == declared == recorded):
            raise IntegrityError(
                f"{inv_id}: версия чекера не та "
                f"(файл {actual[:12]}, инвариант {str(declared)[:12]}, доказательство {str(recorded)[:12]})"
            )
        if ev.get("checker_version") != inv.get("checker_version"):
            raise IntegrityError(
                f"{inv_id}: версия инварианта {inv.get('checker_version')}, "
                f"в доказательстве {ev.get('checker_version')}"
            )

        outcome = run_checker(predicate, code_root, transition)
        expected = ev.get("result")
        got = "pass" if outcome["ok"] else "fail"
        results.append(
            {
                "req_id": rid,
                "inv_id": inv_id,
                "transition": transition,
                "code_hash": ev.get("code_hash"),
                "expected": expected,
                "actual": got,
                "detail": outcome["detail"],
                "match": expected == got,
            }
        )
        if expected != got:
            findings.append(
                gates.Finding(
                    "replay_mismatch",
                    gates.BLOCK,
                    f"перезапуск дал {got}, в записи {expected}: {outcome['detail'][:160]}",
                    {"req_id": rid, "inv_id": inv_id, "transition": transition},
                )
            )
    return results, findings
