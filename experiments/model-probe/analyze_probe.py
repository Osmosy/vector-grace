"""Разбор пробы: как модель пишет модуль сама, без указаний про контракты и секции.

Считает по файлу probe_taskqueue.py: строки, модульный докстринг, секционные
комментарии, функции и долю функций с докстрингом.

Запуск:  python3 analyze_probe.py
Опорный разбор: ../../references/sft-code-training-and-module-contracts.md
"""
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
TARGET = HERE / "probe_taskqueue.py"


def main():
    lines = TARGET.read_text(encoding="utf-8").split("\n")
    body = "\n".join(lines)

    module_docstring = lines[0].strip().startswith('"""') or lines[0].strip().startswith("'''")
    sections = [
        line.strip() for line in lines
        if re.match(r"\s*#\s*(-{2,}|={2,}|#{1,})", line) or re.match(r"\s*#\s*[А-ЯA-Z][^.!?]{3,45}$", line)
    ]

    defs = [(i, m.group(1)) for i, m in
            ((i, re.match(r"\s*def (\w+)", line)) for i, line in enumerate(lines)) if m]
    documented = []
    for i, name in defs:
        for j in range(i + 1, min(i + 3, len(lines))):
            stripped = lines[j].strip()
            if not stripped:
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                documented.append(name)
            break

    print(f"файл: {TARGET.name}")
    print(f"строк: {len(lines)}")
    print(f"модульный докстринг: {'есть' if module_docstring else 'нет'}")
    print(f"секционных комментариев: {len(sections)}")
    for s in sections:
        print("   ", s)
    print(f"функций (def): {len(defs)} | с докстрингом: {len(documented)} "
          f"({round(100 * len(documented) / max(1, len(defs)))} %)")
    print("   документированы:", ", ".join(documented) or "—")
    print(f"классы: {re.findall(r'^class (\w+)', body, re.M)}")
    print(f"тестовый код в модуле: {'есть' if ('def test_' in body or 'assert ' in body) else 'нет'}")


if __name__ == "__main__":
    main()
