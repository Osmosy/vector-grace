"""Детерминированная атомизация источников на спаны.

Спан — диапазон байт исходного файла, а не суждение модели. Всё, что
производится дальше (вердикт, требование, доказательство), ссылается на
(file, sha256 файла, [start, end], sha256 спана) и никогда — на пересказ.

Модуль не знает про LLM и не читает ничего, кроме байтов. Поэтому покрытие
спанов считается механически: джойн спанов с вердиктами, без модели в контуре.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterator

# Нормативная лексика RFC 2119/8174 плюс русские эквиваленты. Регистр не важен:
# в заметках пишут строчными. Это предфильтр, а не классификатор — он только
# помечает спан, который нельзя молча записать в background.
_OBLIGATION = re.compile(
    "|".join(
        [
            r"\b(?:must|shall|should|required|mandatory)\b",
            r"\b(?:must|shall|should)\s+not\b",
            r"\b(?:at\s+least|at\s+most|no\s+less\s+than|no\s+more\s+than)\s+\d",
            r"(?:не\s+должен|не\s+должна|не\s+должно|не\s+должны)\b",
            r"\b(?:должен|должна|должно|должны)\b",
            r"\bобязан\w*\b",
            r"\bзапрещ\w*\b",
            r"\bнельзя\b",
            r"\bне\s+менее\s+\d",
            r"\bне\s+более\s+\d",
            r"\bне\s+позднее\s+\d",
        ]
    ),
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    sha256: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def span_id(file: str, span_sha: str) -> str:
    """Идентификатор спана привязан к содержимому, а не к позиции.

    Правка соседнего абзаца не должна обнулять вердикт по этому. Если текст
    спана изменился, id меняется, старый вердикт перестаёт покрывать что-либо
    и попадает в отчёт как устаревший.
    """
    return f"{file}#{span_sha[:16]}"


def atomize(data: bytes) -> list[Span]:
    """Абзац = спан. Пустые строки разделяют, перевод строки в конец не входит."""
    spans: list[Span] = []
    start: int | None = None
    end: int | None = None
    pos = 0
    for raw in data.splitlines(keepends=True):
        body = raw.rstrip(b"\r\n")
        if body.strip():
            if start is None:
                start = pos
            end = pos + len(body)
        elif start is not None:
            assert end is not None
            spans.append(Span(start, end, sha256_bytes(data[start:end])))
            start = end = None
        pos += len(raw)
    if start is not None and end is not None:
        spans.append(Span(start, end, sha256_bytes(data[start:end])))
    return spans


def obligations(text: str) -> list[str]:
    """Найденные модальные конструкции, нормализованные, без повторов."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _OBLIGATION.finditer(text):
        hit = " ".join(match.group(0).split()).lower()
        if hit not in seen:
            seen.add(hit)
            out.append(hit)
    return out


def records(data: bytes, file: str) -> Iterator[dict]:
    """Записи spans.jsonl для одного источника. Это кэш, его можно пересобрать."""
    file_sha = sha256_bytes(data)
    for span in atomize(data):
        yield {
            "span_id": span_id(file, span.sha256),
            "file": file,
            "file_sha256": file_sha,
            "span": [span.start, span.end],
            "sha256": span.sha256,
            "text": data[span.start : span.end].decode("utf-8"),
        }
