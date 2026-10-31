"""Чекер перехода retry_on_upload.

Предикат — маленькое доверенное ядро: его не правит ни кодирующий агент, ни
ревьюер, а версия закреплена sha256 в инварианте и в записи доказательства.
Протокол: JSON {"ok": bool, "detail": str} в stdout, код выхода 0/1.
"""
import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--root", required=True)
parser.add_argument("--transition", required=True)
args = parser.parse_args()

target = Path(args.root) / "src" / "upload.py"
source = target.read_text("utf-8") if target.is_file() else ""
ok = "range(attempts)" in source and "except OSError" in source
print(
    json.dumps(
        {
            "ok": ok,
            "detail": f"{args.transition}: повтор при сбое на месте"
            if ok
            else f"{args.transition}: в {target} нет повтора при сбое",
        },
        ensure_ascii=False,
    )
)
sys.exit(0 if ok else 1)
