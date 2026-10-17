"""Прогон, который пишет ТОЛЬКО журнал: из него агент должен уметь заключить о надёжности.

Флаг --orphan-amount добавляет в журнал поле orphan_amount: критерий сохранения суммы
становится проверяемым. Без флага — журнал неполон, и критерий обязан получить статус
"непроверяемо", а не "ok".

Запуск:  python3 run_log.py [--orphan-amount]
Опорный разбор: ../../references/diagnostics-over-tests-dirty-data.md
"""
from pathlib import Path
import json
import sqlite3
import sys
import time

HERE = Path(__file__).resolve().parent
CID = "c-9f1a"

ORDERS = [
    ("O1", "42", 100.0), ("O2", "42", 50.0), ("O3", "7", 300.0), ("O4", " 42", 25.0),
    ("O5", "77", 500.0), ("O6", "9", 40.0), ("O7", "42", 10.0), ("O8", "7", 5.0),
]
DIM = [("42", "ACME"), ("42", "ACME"), ("7", "Beta"), ("9", "Gamma")]


def event(fh, **kwargs):
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "cid": CID}
    rec.update(kwargs)
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    with_orphan_amount = "--orphan-amount" in sys.argv

    con = sqlite3.connect(":memory:")
    con.execute("create table o(order_id text, customer_id text, amount real)")
    con.execute("create table c(customer_id text, name text)")
    con.executemany("insert into o values(?,?,?)", ORDERS)
    con.executemany("insert into c values(?,?)", DIM)

    matched = [o for o in ORDERS if any(o[1] == c[0] for c in DIM)]
    orphans = [o for o in ORDERS if not any(o[1].strip().lower() == c[0].strip().lower() for c in DIM)]
    hygiene = [o for o in ORDERS if o[1] != o[1].strip()]
    dup = sorted({c[0] for c in DIM if sum(1 for x in DIM if x[0] == c[0]) > 1})
    rows = con.execute(
        "select o.customer_id, c.name, sum(o.amount) from o join c on o.customer_id = c.customer_id"
        " group by 1, 2 order by 1"
    ).fetchall()

    join_event = {
        "stage": "join", "block": "JOIN_STAGE",
        "rows_in": len(ORDERS), "rows_out": len(matched),
        "orphan_keys": [o[0] for o in orphans],
        "key_hygiene_suspects": [o[1] for o in hygiene],
    }
    if with_orphan_amount:
        join_event["orphan_amount"] = round(sum(o[2] for o in orphans), 2)

    with (HERE / "run.jsonl").open("w") as fh:
        event(fh, stage="source.orders", block="LOAD_ORDERS",
              rows_in=len(ORDERS), sum_in=round(sum(o[2] for o in ORDERS), 2))
        event(fh, stage="source.dim", block="LOAD_DIM",
              rows_in=len(DIM), dim_duplicate_keys=dup)
        event(fh, **join_event)
        event(fh, stage="agg", block="AGG_STAGE", rows_out=len(rows),
              sum_out=round(sum(r[2] for r in rows), 2),
              offenders=[{"key": r[0], "name": r[1], "revenue": r[2]} for r in rows])
        event(fh, stage="write", block="WRITE_REPORT", file="report.csv", report_rows=len(rows))

    print("журнал записан: run.jsonl" + (" (с полем orphan_amount)" if with_orphan_amount else " (без orphan_amount)"))


if __name__ == "__main__":
    main()
