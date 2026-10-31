"""Замер предиката на посаженных дефектах.

Предикат — классификатор, у него две ошибки: пропуск дефекта и отклонение
корректного кода. Второе в автоматическом конвейере дороже: агент начнёт
«чинить» правильно работающий код и уведёт дерево от рабочего состояния.

Поэтому до того, как на инвариант обопрётся приёмка, нужны числа: доля
обнаруженных дефектов по классам и доля ложных отклонений на чистом коде.
Неизмеренный предикат — это null в полях замера, а не ноль: ноль был бы
утверждением о качестве проверки.
"""
from __future__ import annotations

import contextlib
import json
import shutil
import tempfile
from pathlib import Path

from . import replay, spans as spans_mod

_IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", "*.pyc", "node_modules", ".venv", "venv", "dist", "build"
)


class BenchError(ValueError):
    """Набор дефектов не годен: нечего измерять или некуда подставлять."""


def load_bench(path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise BenchError(f"нет набора дефектов: {p}")
    bench = json.loads(p.read_text("utf-8"))
    if not bench.get("clean"):
        raise BenchError("bench: не указан clean — файл, который подменяем")
    mutants = bench.get("mutants") or []
    if not mutants:
        raise BenchError("bench: пустой список mutants — измерять нечего")
    for mutant in mutants:
        if not mutant.get("file") or not mutant.get("class"):
            raise BenchError("bench: у каждого дефекта нужны file и class")
    return bench


@contextlib.contextmanager
def _staged(root: Path, target: str | None = None, source: Path | None = None):
    """Копия проекта с подменённым файлом: чистый прогон и каждый дефект — изолированно."""
    with tempfile.TemporaryDirectory(prefix="grace-bench-") as tmp:
        staged = Path(tmp) / "root"
        shutil.copytree(root, staged, ignore=_IGNORE)
        if target is not None and source is not None:
            dest = staged / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        yield staged


def measure(
    predicate,
    code_root,
    bench: dict,
    transition: str,
    timeout: int = 300,
) -> dict:
    root = Path(code_root)
    target = str(bench["clean"])
    clean_source = bench.get("clean_source")
    clean_path = root / clean_source if clean_source else None

    with _staged(root, target, clean_path) as staged:
        clean = replay.run_checker(predicate, staged, transition, timeout=timeout)
    clean_ok = bool(clean["ok"])

    results: list[dict] = []
    for mutant in bench["mutants"]:
        with _staged(root, target, root / mutant["file"]) as staged:
            outcome = replay.run_checker(predicate, staged, transition, timeout=timeout)
        results.append(
            {
                "name": mutant.get("name") or mutant["file"],
                "class": mutant["class"],
                "detected": not outcome["ok"],
                "detail": outcome["detail"][:200],
            }
        )

    by_class: dict[str, dict] = {}
    for item in results:
        bucket = by_class.setdefault(item["class"], {"n": 0, "detected": 0})
        bucket["n"] += 1
        bucket["detected"] += 1 if item["detected"] else 0

    total = len(results)
    detected = sum(1 for item in results if item["detected"])
    return {
        "checker": str(predicate),
        "checker_sha256": spans_mod.sha256_file(predicate),
        "transition": transition,
        "clean_ok": clean_ok,
        "false_reject": 0.0 if clean_ok else 1.0,
        "clean_runs": 1,
        "clean_detail": clean["detail"][:200],
        "mutants": total,
        "detected": detected,
        "false_accept": round((total - detected) / total, 3) if total else None,
        "by_class": by_class,
        "results": results,
    }
