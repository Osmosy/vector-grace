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


_PAGE_HEADING = re.compile(r"(?m)^##[ \t]+(?:Слайд|Slide|Страница|Page)[ \t]+(\d+)[^\n]*$")
_TABLE_ROW = re.compile(r"(?m)^\|[^\n]*\|[ \t]*$")


def page_spans(data: bytes) -> list[tuple[int, Span]]:
    """Спан = страница колоды. Колоды режутся по заголовкам, а не по абзацам."""
    text = data.decode("utf-8")
    marks = [(int(m.group(1)), m.start()) for m in _PAGE_HEADING.finditer(text)]
    out: list[tuple[int, Span]] = []
    for index, (page, start_char) in enumerate(marks):
        end_char = marks[index + 1][1] if index + 1 < len(marks) else len(text)
        chunk = text[start_char:end_char].rstrip("\n")
        start = len(text[:start_char].encode("utf-8"))
        end = start + len(chunk.encode("utf-8"))
        out.append((page, Span(start, end, sha256_bytes(data[start:end]))))
    return out


def row_spans(data: bytes) -> list[tuple[int, Span]]:
    """Спан = строка markdown-таблицы, с номером страницы, на которой она стоит.

    Нужен, когда требование — конкретный факт строки, а не страница целиком: иначе
    несколько требований с одной страницы делят один raw_text, и реестр перестаёт
    различать, какое из них доказано. Строки-разделители шапки (`|---|---|`) пропускаются.
    """
    text = data.decode("utf-8")
    pages = [(int(m.group(1)), m.start()) for m in _PAGE_HEADING.finditer(text)]
    out: list[tuple[int, Span]] = []
    for match in _TABLE_ROW.finditer(text):
        chunk = match.group(0)
        cells = chunk.strip().strip("|")
        if not cells or set(cells.replace("|", "")) <= set("-: "):
            continue
        page = 0
        for number, position in pages:
            if position <= match.start():
                page = number
        start = len(text[: match.start()].encode("utf-8"))
        end = start + len(chunk.encode("utf-8"))
        out.append((page, Span(start, end, sha256_bytes(data[start:end]))))
    return out


def records(data: bytes, file: str, split: str = "paragraph") -> Iterator[dict]:
    """Записи spans.jsonl для одного источника. Это кэш, его можно пересобрать."""
    file_sha = sha256_bytes(data)
    if split == "pages":
        pairs = page_spans(data)
    elif split == "rows":
        pairs = row_spans(data)
    elif split == "paragraph":
        pairs = [(None, span) for span in atomize(data)]
    else:
        raise ValueError(f"неизвестная разбивка: {split}")
    for page, span in pairs:
        record = {
            "span_id": span_id(file, span.sha256),
            "file": file,
            "file_sha256": file_sha,
            "span": [span.start, span.end],
            "sha256": span.sha256,
            "text": data[span.start : span.end].decode("utf-8"),
        }
        if page is not None:
            record["page"] = page
        yield record
