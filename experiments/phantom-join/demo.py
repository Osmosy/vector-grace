"""Демо: грязные данные + наивная трансформация + полностью зелёные happy-path тесты.

Что показывает: набор тестов может быть зелёным 6 из 6, пока выход повреждён —
выпадение на JOIN (сирота, ключ с пробелом) и фантомные записи (дубль в справочнике
размножает агрегат).

Запуск:  python3 demo.py
Опорный разбор: ../../references/diagnostics-over-tests-dirty-data.md
"""
from pathlib import Path
import csv
import sqlite3

HERE = Path(__file__).resolve().parent

ORDERS = [
    ("O1", "42", 100.0), ("O2", "42", 50.0), ("O3", "7", 300.0), ("O4", " 42", 25.0),
    ("O5", "77", 500.0), ("O6", "9", 40.0), ("O7", "42", 10.0), ("O8", "7", 5.0),
]
DIM = [("42", "ACME"), ("42", "ACME"), ("7", "Beta"), ("9", "Gamma")]


def write_sources():
    with (HERE / "orders.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["order_id", "customer_id", "amount"])
        w.writerows(ORDERS)
    with (HERE / "customers.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "name"])
        w.writerows(DIM)


def transform():
    """Наивная трансформация: INNER JOIN без нормализации ключей и без дедупликации справочника."""
    con = sqlite3.connect(":memory:")
    con.execute("create table o(order_id text, customer_id text, amount real)")
    con.execute("create table c(customer_id text, name text)")
    con.executemany("insert into o values(?,?,?)", ORDERS)
    con.executemany("insert into c values(?,?)", DIM)
    return con.execute(
        "select o.customer_id, c.name, sum(o.amount) from o join c on o.customer_id = c.customer_id"
        " group by 1, 2 order by 1"
    ).fetchall()


def happy_path_tests(rows):
    """Типичный happy-path набор: проверяет форму и факт наличия, а не сверку вход-выход."""
    return [
        ("файл отчёта создан", (HERE / "report.csv").exists()),
        ("отчёт не пустой", len(rows) > 0),
        ("нет пустых выручек", all(r[2] is not None for r in rows)),
        ("все ключи есть в справочнике", all(any(r[0] == c[0] for c in DIM) for r in rows)),
        ("выручка положительна", all(r[2] > 0 for r in rows)),
        ("ACME в отчёте есть", any(r[1] == "ACME" for r in rows)),
    ]


def main():
    write_sources()
    rows = transform()
    with (HERE / "report.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "name", "revenue"])
        w.writerows(rows)

    print("=== happy-path тесты ===")
    for name, ok in happy_path_tests(rows):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")

    matched = [o for o in ORDERS if any(o[1] == c[0] for c in DIM)]
    orphans = [o for o in ORDERS if not any(o[1].strip().lower() == c[0].strip().lower() for c in DIM)]
    hygiene = [o for o in ORDERS if o[1] != o[1].strip()]
    dup = sorted({c[0] for c in DIM if sum(1 for x in DIM if x[0] == c[0]) > 1})
    truth = sum(o[2] for o in ORDERS)
    reported = sum(r[2] for r in rows)
    acme_truth = sum(o[2] for o in ORDERS if o[1] == "42")

    print("\n=== что ушло на выход ===")
    for r in rows:
        print("   ", ",".join(str(x) for x in r))

    print("\n=== что было в данных на самом деле ===")
    print(f"   сопоставлено буквальным JOIN: {len(matched)} из {len(ORDERS)}")
    print(f"   потеряно на JOIN: {len(ORDERS) - len(matched)} заказа на {truth - sum(o[2] for o in matched)}")
    print(f"   сироты (нет в справочнике даже с нормализацией): {[(o[0], o[1], o[2]) for o in orphans]}")
    print(f"   ключи с нарушенной гигиеной: {[(o[0], repr(o[1]), o[2]) for o in hygiene]}")
    print(f"   дубли в справочнике: {dup} -> завышение по ACME x{len([c for c in DIM if c[0] == '42'])}")
    print(f"   ACME: истина {acme_truth} против {[r[2] for r in rows if r[1] == 'ACME'][0]} в отчёте")
    print(f"   итог: истина {truth} против {reported} в отчёте, дельта {reported - truth}")


if __name__ == "__main__":
    main()
