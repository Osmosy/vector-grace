#!/usr/bin/env python3
"""Запуск без установки: python3 registry/grace.py --root <проект> <команда>.

Зависимостей нет, только stdlib (проверено на Python 3.14).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grace_registry.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
