"""Записи реестра требований: схема, проверки, append-only ревизии.

Авторитетно в записи ровно одно поле — дословный raw_text со спановой
привязкой. Остальное производно. Запись не редактируется: изменение — новая
ревизия с ребром supersedes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CHANNELS = ("chat", "letter", "document", "call")
KINDS = (
    "requirement",
    "constraint",
    "question",
    "decision",
    "background",
    "duplicate",
    "open",
    # определение: запись реестра, которая задаёт термины (легенда вердиктов, шкалы).
    # Живая, со спановой привязкой и доказательствами, но обязательством не является:
    # продуктового обещания не несёт, поэтому в счёте «доказано N из M» не участвует.
    "definition",
)
# виды, которые несут обещание и потому обязаны быть доказаны
OBLIGATION_KINDS = ("requirement", "constraint")
STRENGTHS = ("must", "should", "may")
STATUSES = ("elicited", "assumed", "open", "rejected", "superseded")
# Статусы, для которых пустое evidence[] — блокирующая находка.
BLOCKING_STATUSES = ("elicited", "assumed")
# Статусы, при которых ссылки на требование в коде/тестах считаются осиротевшими.
DEAD_STATUSES = ("rejected", "superseded")

REQ_ID = re.compile(r"^REQ-\d{4,}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def req_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def load_jsonl(path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    for lineno, line in enumerate(p.read_text("utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{p}:{lineno}: битая строка JSONL: {exc}") from exc
    return out


def append_jsonl(path, record: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def problems(record: dict) -> list[str]:
    """Нарушения схемы записи требования. Пусто — запись годна."""
    out: list[str] = []
    rid = record.get("req_id")
    if not isinstance(rid, str) or not REQ_ID.match(rid):
        out.append(f"req_id не по схеме REQ-NNNN: {rid!r}")
    if not isinstance(record.get("rev"), int) or record["rev"] < 1:
        out.append("rev должен быть целым >= 1")

    source = record.get("source") or {}
    if not isinstance(source, dict):
        out.append("source должен быть объектом")
        source = {}
    if not source.get("file"):
        out.append("source.file пуст")
    if not _HEX64.match(str(source.get("sha256", ""))):
        out.append("source.sha256 не sha256 (64 hex)")
    span = source.get("span")
    if (
        not isinstance(span, list)
        or len(span) != 2
        or not all(isinstance(x, int) for x in span)
        or not (0 <= span[0] < span[1])
    ):
        out.append("source.span должен быть [int,int], start < end")
    if source.get("channel") not in CHANNELS:
        out.append(f"source.channel вне {CHANNELS}: {source.get('channel')!r}")
    if not source.get("speaker"):
        out.append("source.speaker пуст")
    if not source.get("date"):
        out.append("source.date пуст")

    raw = record.get("raw_text")
    if not isinstance(raw, str) or not raw.strip():
        out.append("raw_text пуст")
        raw = ""
    if raw and record.get("req_hash") != req_hash(raw):
        out.append("req_hash не совпадает с sha256(raw_text)")
    if raw and isinstance(span, list) and len(span) == 2 and all(
        isinstance(x, int) for x in span
    ):
        if span[1] - span[0] != len(raw.encode("utf-8")):
            out.append("длина source.span не равна длине raw_text в байтах")

    kind = record.get("kind")
    if kind not in KINDS:
        out.append(f"kind вне {KINDS}: {kind!r}")
    if kind in ("requirement", "constraint"):
        if record.get("strength") not in STRENGTHS:
            out.append(f"strength вне {STRENGTHS}: {record.get('strength')!r}")
    elif record.get("strength") is not None:
        out.append("strength задан у записи, где его быть не должно")

    status = record.get("status")
    if status not in STATUSES:
        out.append(f"status вне {STATUSES}: {status!r}")
    if status == "open":
        if not record.get("owner"):
            out.append("open без owner")
        if not record.get("deadline"):
            out.append("open без deadline")
    if record.get("superseded_by") and status != "superseded":
        out.append("superseded_by задан, а status не superseded")
    if status == "superseded" and not record.get("superseded_by"):
        out.append("status superseded, а superseded_by пуст")
    for inv in record.get("invariants") or []:
        if not re.match(r"^INV-\d{4,}$", str(inv)):
            out.append(f"invariants: {inv!r} не INV-NNNN")
    return out


def live_requirements(records: list[dict]) -> dict[str, dict]:
    """Последняя ревизия по каждому req_id — то, что действует сейчас."""
    best: dict[str, dict] = {}
    for rec in records:
        rid = rec.get("req_id")
        if not isinstance(rid, str):
            continue
        cur = best.get(rid)
        if cur is None or int(rec.get("rev", 1)) > int(cur.get("rev", 1)):
            best[rid] = rec
    return best


def next_inv_id(records: list[dict]) -> str:
    """Следующий номер инварианта — по максимуму, а не по длине списка.

    Номер по длине выдаёт уже занятые id, если журнал когда-либо чистили или читали
    частично: два разных инварианта получают один id, и доказательства склеиваются.
    """
    top = 0
    for rec in records:
        inv = str(rec.get("inv_id") or "")
        if inv.startswith("INV-") and inv[4:].isdigit():
            top = max(top, int(inv[4:]))
    return f"INV-{top + 1:04d}"


def next_req_id(records: list[dict]) -> str:
    top = 0
    for rec in records:
        rid = rec.get("req_id")
        if isinstance(rid, str) and REQ_ID.match(rid):
            top = max(top, int(rid.split("-")[1]))
    return f"REQ-{top + 1:04d}"
