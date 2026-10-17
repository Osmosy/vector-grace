"""Оценка надёжности ТОЛЬКО по журналу и критериям — без доступа к исходным данным.

Если для критерия в журнале нет нужных полей, критерий получает статус
"непроверяемо" (а не "ok"). Список непроверяемых критериев и есть бэклог
наблюдаемости: не хватает поля в контексте — критерий слепой.

Запуск:  python3 evaluate.py
Опорный разбор: ../../references/diagnostics-over-tests-dirty-data.md
"""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent

REQUIRED = {
    "crit.completeness.join": [("source.orders", ["rows_in"]), ("join", ["rows_out", "orphan_keys"])],
    "crit.fanout.dim": [("source.dim", ["dim_duplicate_keys"])],
    "crit.sum.invariance": [("source.orders", ["sum_in"]), ("agg", ["sum_out"]), ("join", ["orphan_amount"])],
    "crit.key.hygiene": [("join", ["key_hygiene_suspects"])],
    "crit.evidence.sample": [("agg", ["offenders"])],
}


def load_events():
    ev = {}
    with (HERE / "run.jsonl").open() as fh:
        for line in fh:
            rec = json.loads(line)
            ev.setdefault(rec["stage"], {}).update(rec)
    return ev


def main():
    criteria = json.load((HERE / "criteria.json").open())["criteria"]
    ev = load_events()
    tol = 1e-6
    rows, unverifiable, alarms = [], [], 0

    def val(stage, field):
        return ev.get(stage, {}).get(field)

    for crit in criteria:
        cid = crit["id"]
        missing = [f"{s}.{f}" for s, fields in REQUIRED[cid] for f in fields if val(s, f) is None]
        if missing:
            rows.append(("непроверяемо", cid, "нет полей: " + ", ".join(missing)))
            unverifiable.append(cid)
            continue

        if cid == "crit.completeness.join":
            ok = val("join", "rows_out") >= val("source.orders", "rows_in") - len(val("join", "orphan_keys"))
            why = (f"rows_in={val('source.orders','rows_in')} rows_out={val('join','rows_out')} "
                   f"orphans={val('join','orphan_keys')}")
        elif cid == "crit.fanout.dim":
            dup = val("source.dim", "dim_duplicate_keys")
            ok, why = len(dup) == 0, f"дубли в справочнике: {dup}"
        elif cid == "crit.sum.invariance":
            expected = val("source.orders", "sum_in") - val("join", "orphan_amount")
            ok = abs(val("agg", "sum_out") - expected) <= tol
            why = (f"sum_in={val('source.orders','sum_in')} orphan_amount={val('join','orphan_amount')} "
                   f"ожидалось={round(expected, 2)} sum_out={val('agg','sum_out')}")
        elif cid == "crit.key.hygiene":
            susp = val("join", "key_hygiene_suspects")
            ok, why = len(susp) == 0, f"подозрительные ключи: {[repr(x) for x in susp]}"
        else:  # crit.evidence.sample
            ok, why = val("agg", "offenders") is not None, f"срез offenders: {val('agg','offenders')}"

        alarms += 0 if ok else 1
        rows.append(("ok" if ok else "ALARM", cid, why))

    width = max(len(r[2]) for r in rows)
    print(f"{'signal':13} {'criterion':24} почему")
    for signal, cid, why in rows:
        print(f"{signal:13} {cid:24} {why}")

    print(f"\nтревог: {alarms} | непроверяемо: {len(unverifiable)} {unverifiable or ''}")
    if unverifiable:
        print("бэклог наблюдаемости: добавить в журнал поля для " + ", ".join(unverifiable))
    print("вердикт приёмки:", "НЕ ПРИНЯТО" if alarms else ("требует наблюдаемости" if unverifiable else "принято"))


if __name__ == "__main__":
    main()
