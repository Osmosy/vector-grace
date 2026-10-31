"""Тесты реестра: спаны, схема, покрытие, три класса дрейфа, перезапуск чекеров.

Запуск: python3 -m unittest discover -s registry/tests -t registry -v
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grace_registry import cli, gates, measure, model, replay, spans  # noqa: E402

BY = "agent:test/1"


def run_cli(root: Path, *argv: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = cli.main(["--root", str(root), *argv])
    return code, buf.getvalue()


def make_project(tmp: Path) -> Path:
    (tmp / "docs" / "registry").mkdir(parents=True, exist_ok=True)
    (tmp / "notes").mkdir(exist_ok=True)
    (tmp / "notes" / "chat-2026-10-30.md").write_text(
        "Клиент: нужен экспорт отчёта в CSV.\n"
        "\n"
        "Не менее 3 повторов при сбое выгрузки.\n"
        "\n"
        "Остальное — фон, обсуждали отпуска.\n",
        encoding="utf-8",
    )
    (tmp / "docs" / "registry" / "sources.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "file": "notes/chat-2026-10-30.md",
                        "channel": "chat",
                        "speaker": "клиент",
                        "date": "2026-10-30",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return tmp


def write_checker(root: Path, body: str = "True", name: str = "check_retry.py") -> str:
    (root / "checkers").mkdir(exist_ok=True)
    path = root / "checkers" / name
    path.write_text(
        "import argparse, json\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('--root')\n"
        "p.add_argument('--transition')\n"
        "a = p.parse_args()\n"
        f"print(json.dumps({{'ok': {body}, 'detail': 'переход ' + str(a.transition)}}))\n",
        encoding="utf-8",
    )
    return path.relative_to(root).as_posix()


def make_requirement(rid: str = "REQ-0001", **over) -> dict:
    raw = "Не менее 3 повторов при сбое выгрузки."
    rec = {
        "req_id": rid,
        "rev": 1,
        "source": {
            "file": "notes/a.md",
            "sha256": "a" * 64,
            "span": [0, len(raw.encode())],
            "channel": "chat",
            "speaker": "клиент",
            "date": "2026-10-30",
        },
        "raw_text": raw,
        "req_hash": model.req_hash(raw),
        "kind": "requirement",
        "strength": "must",
        "status": "elicited",
        "supersedes": None,
        "superseded_by": None,
        "invariants": [],
        "owner": None,
        "deadline": None,
    }
    rec.update(over)
    return rec


def make_evidence(rec: dict, **over) -> dict:
    ev = {
        "req_id": rec["req_id"],
        "req_hash": rec["req_hash"],
        "inv_id": "INV-0001",
        "transition": "retry_on_upload",
        "checker": "checkers/check_retry.py",
        "checker_sha256": "b" * 64,
        "checker_version": "1",
        "code_hash": "c" * 64,
        "result": "pass",
        "defeater": "если при двух сбоях подряд повторов нет",
    }
    ev.update(over)
    return ev


class TestAtomize(unittest.TestCase):
    def test_offsets_and_hashes(self):
        data = "A one.\nB two.\n\nC three.\n".encode()
        result = spans.atomize(data)
        self.assertEqual(len(result), 2)
        self.assertEqual((result[0].start, result[0].end), (0, 13))
        self.assertEqual(data[result[0].start : result[0].end], b"A one.\nB two.")
        self.assertEqual((result[1].start, result[1].end), (15, 23))
        self.assertEqual(result[0].sha256, spans.sha256_bytes(b"A one.\nB two."))

    def test_crlf(self):
        data = b"A.\r\n\r\nB.\r\n"
        result = spans.atomize(data)
        self.assertEqual([data[s.start : s.end] for s in result], [b"A.", b"B."])

    def test_no_trailing_newline(self):
        data = b"one\n\ntwo"
        result = spans.atomize(data)
        self.assertEqual([data[s.start : s.end] for s in result], [b"one", b"two"])

    def test_empty(self):
        self.assertEqual(spans.atomize(b"\n\n  \n"), [])

    def test_obligations(self):
        self.assertIn("не менее 3", spans.obligations("Не менее 3 повторов"))
        self.assertIn("должен", spans.obligations("Сервис должен отвечать"))
        self.assertTrue(spans.obligations("This must work"))
        self.assertEqual(spans.obligations("должность менеджера"), [])
        self.assertEqual(spans.obligations("Возможно, обсудим позже"), [])

    def test_page_spans(self):
        data = (
            "intro\n\n## Слайд 1 — Раз\nтекст 1\n\n## Слайд 2 — Два\n| a | 1 |\n"
        ).encode()
        recs = list(spans.records(data, "deck.md", split="pages"))
        self.assertEqual([r["page"] for r in recs], [1, 2])
        self.assertTrue(recs[0]["text"].startswith("## Слайд 1"))
        self.assertEqual(
            data[recs[1]["span"][0] : recs[1]["span"][1]].decode(), recs[1]["text"]
        )
        self.assertTrue(recs[1]["text"].endswith("| a | 1 |"))

    def test_span_id_is_content_addressed(self):
        data = b"one\n\ntwo\n"
        first = list(spans.records(data, "f.md"))
        shifted = list(spans.records(b"zero\n\n" + data, "f.md"))
        self.assertEqual(first[1]["span_id"].split("#")[1], shifted[2]["span_id"].split("#")[1])


class TestModel(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(model.problems(make_requirement()), [])

    def test_paraphrase_detected(self):
        rec = make_requirement(raw_text="Три повтора")
        self.assertTrue(any("req_hash" in p for p in model.problems(rec)))

    def test_span_length_mismatch(self):
        rec = make_requirement()
        rec["source"]["span"] = [0, 5]
        self.assertTrue(any("длина" in p for p in model.problems(rec)))

    def test_open_requires_owner_and_deadline(self):
        rec = make_requirement(status="open", kind="question", strength=None)
        problems = model.problems(rec)
        self.assertTrue(any("owner" in p for p in problems))
        self.assertTrue(any("deadline" in p for p in problems))

    def test_strength_only_on_requirement(self):
        rec = make_requirement(kind="background", strength="must")
        self.assertTrue(any("strength" in p for p in model.problems(rec)))

    def test_next_id_and_live_revision(self):
        recs = [make_requirement("REQ-0007")]
        self.assertEqual(model.next_req_id(recs), "REQ-0008")
        revised = dict(recs[0], rev=2, status="superseded", superseded_by="REQ-0009")
        self.assertEqual(model.live_requirements(recs + [revised])["REQ-0007"]["rev"], 2)


class TestCoverage(unittest.TestCase):
    def setUp(self):
        self.data = "Нужен экспорт.\n\nНе менее 3 повторов.\n".encode()
        self.records = list(spans.records(self.data, "n.md"))

    def verdict(self, index: int, kind: str) -> dict:
        rec = self.records[index]
        return {
            "span_id": rec["span_id"],
            "span_sha256": rec["sha256"],
            "kind": kind,
        }

    def codes(self, findings):
        return sorted({f.code for f in findings})

    def test_uncovered_span_blocks(self):
        findings = gates.coverage_gate(self.records, [self.verdict(0, "requirement")])
        self.assertEqual(self.codes(findings), ["uncovered_span"])
        self.assertTrue(gates.has_block(findings))

    def test_hidden_obligation(self):
        findings = gates.coverage_gate(
            self.records, [self.verdict(0, "background"), self.verdict(1, "background")]
        )
        self.assertIn("hidden_obligation", self.codes(findings))
        self.assertTrue(gates.has_block(findings))

    def test_background_without_obligation_is_fine(self):
        findings = gates.coverage_gate(
            self.records, [self.verdict(0, "background"), self.verdict(1, "requirement")]
        )
        self.assertEqual(findings, [])

    def test_verdict_for_old_text_does_not_cover(self):
        stale = dict(self.verdict(0, "requirement"), span_sha256="0" * 64)
        findings = gates.coverage_gate(self.records, [stale, self.verdict(1, "requirement")])
        self.assertIn("uncovered_span", self.codes(findings))

    def test_orphan_verdict_is_warning(self):
        verdicts = [self.verdict(0, "background"), self.verdict(1, "requirement")]
        verdicts.append({"span_id": "gone#deadbeef", "span_sha256": "1" * 64, "kind": "background"})
        findings = gates.coverage_gate(self.records, verdicts)
        self.assertEqual(self.codes(findings), ["stale_verdict"])
        self.assertFalse(gates.has_block(findings))


class TestDrift(unittest.TestCase):
    def test_clean(self):
        rec = make_requirement()
        findings = gates.drift_gate([rec], [make_evidence(rec)])
        self.assertEqual(findings, [])

    def test_three_classes(self):
        a = make_requirement("REQ-0001")
        b = make_requirement("REQ-0002")
        c = make_requirement(
            "REQ-0003", status="superseded", superseded_by="REQ-0004"
        )
        evidence = [
            make_evidence(a, req_hash="d" * 64),  # stale
            make_evidence(c),  # orphaned: требование выведено
        ]
        findings = gates.drift_gate([a, b, c], evidence)
        codes = {f.code for f in findings}
        self.assertIn("stale_evidence", codes)
        self.assertIn("unproven_requirement", codes)  # b без evidence
        self.assertIn("orphaned_evidence", codes)
        self.assertTrue(gates.has_block(findings))

    def test_defeater_required(self):
        rec = make_requirement()
        findings = gates.drift_gate([rec], [make_evidence(rec, defeater="")])
        self.assertIn("undefeatable_evidence", {f.code for f in findings})

    def test_failing_evidence_is_unproven(self):
        rec = make_requirement()
        findings = gates.drift_gate([rec], [make_evidence(rec, result="fail")])
        self.assertIn("unproven_requirement", {f.code for f in findings})

    def test_open_without_owner_blocks(self):
        # open без владельца и срока — не «отложенный пункт», а нарушение схемы.
        rec = make_requirement(
            status="open", kind="question", strength=None, owner="", deadline=""
        )
        findings = gates.drift_gate([rec], [])
        codes = {f.code for f in findings}
        self.assertIn("invalid_record", codes)
        self.assertTrue(gates.has_block(findings))

    def test_source_span_stale_and_orphan(self):
        rec = make_requirement()
        index = {"deck.md#aaa": {"span_id": "deck.md#aaa", "sha256": "b" * 64}}
        span_ref = {
            "span_id": "deck.md#aaa", "file": "deck.md", "page": 5,
            "span": [0, 10], "span_sha256": "b" * 64,
        }
        ev = make_evidence(rec, source_span=span_ref)
        self.assertEqual(gates.drift_gate([rec], [ev], None, index), [])
        stale = make_evidence(rec, source_span=dict(span_ref, span_sha256="c" * 64))
        self.assertIn(
            "stale_source_span", {f.code for f in gates.drift_gate([rec], [stale], None, index)}
        )
        gone = make_evidence(rec, source_span=dict(span_ref, span_id="deck.md#bbb"))
        self.assertIn(
            "orphaned_source_span", {f.code for f in gates.drift_gate([rec], [gone], None, index)}
        )

    def test_artifact_reference_orphan(self):
        rec = make_requirement()
        findings = gates.drift_gate(
            [rec], [make_evidence(rec)], {"src/app.py": {"REQ-0099", "REQ-0001"}}
        )
        self.assertEqual([f.where.get("req_id") for f in findings], ["REQ-0099"])

    def test_scan_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("# см. REQ-0001 и REQ-0002\n")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "x.py").write_text("# REQ-0003\n")
            found = gates.scan_artifacts(root)
        self.assertEqual(found, {"src/app.py": {"REQ-0001", "REQ-0002"}})


class TestReplay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.predicate = write_checker(self.root)
        self.rec = make_requirement()
        self.inv = {
            "inv_id": "INV-0001",
            "req_id": "REQ-0001",
            "transitions": ["retry_on_upload"],
            "predicate": {
                "path": self.predicate,
                "sha256": spans.sha256_file(self.root / self.predicate),
            },
            "checker_version": "1",
        }
        self.ev = make_evidence(
            self.rec, checker=self.predicate, checker_sha256=self.inv["predicate"]["sha256"]
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_match(self):
        results, findings = replay.replay_evidence(
            [self.rec], [self.ev], {"INV-0001": self.inv}, self.root
        )
        self.assertEqual(findings, [])
        self.assertTrue(results[0]["match"])
        self.assertEqual(results[0]["actual"], "pass")

    def test_result_mismatch(self):
        write_checker(self.root, body="False")
        ev = dict(
            self.ev,
            checker_sha256=spans.sha256_file(self.root / self.predicate),
            result="pass",
        )
        inv = dict(
            self.inv,
            predicate={"path": self.predicate, "sha256": ev["checker_sha256"]},
        )
        results, findings = replay.replay_evidence([self.rec], [ev], {"INV-0001": inv}, self.root)
        self.assertFalse(results[0]["match"])
        self.assertEqual([f.code for f in findings], ["replay_mismatch"])

    def test_tampered_checker_refused(self):
        (self.root / self.predicate).write_text("print('{}')\n", encoding="utf-8")
        with self.assertRaises(replay.IntegrityError):
            replay.replay_evidence([self.rec], [self.ev], {"INV-0001": self.inv}, self.root)

    def test_snapshot_invariant_refused(self):
        inv = dict(self.inv, transitions=[])
        with self.assertRaises(replay.IntegrityError):
            replay.replay_evidence([self.rec], [self.ev], {"INV-0001": inv}, self.root)

    def test_wrong_transition_refused(self):
        ev = dict(self.ev, transition="что_то_другое")
        with self.assertRaises(replay.IntegrityError):
            replay.replay_evidence([self.rec], [ev], {"INV-0001": self.inv}, self.root)


class TestMeasure(unittest.TestCase):
    def test_counts_and_false_accept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "m.py").write_text("GOOD\n", encoding="utf-8")
            (root / "bench").mkdir()
            (root / "bench" / "clean.py").write_text("GOOD\n", encoding="utf-8")
            (root / "bench" / "bad.py").write_text("BAD\n", encoding="utf-8")
            (root / "bench" / "ok.py").write_text("GOOD  # правка без дефекта\n", encoding="utf-8")
            (root / "checkers").mkdir()
            predicate = root / "checkers" / "check_good.py"
            predicate.write_text(
                "import argparse, json\n"
                "p = argparse.ArgumentParser()\n"
                "p.add_argument('--root'); p.add_argument('--transition')\n"
                "a = p.parse_args()\n"
                "from pathlib import Path\n"
                "src = Path(a.root) / 'src' / 'm.py'\n"
                "ok = 'GOOD' in src.read_text('utf-8')\n"
                "print(json.dumps({'ok': ok, 'detail': 'good' if ok else 'bad'}))\n",
                encoding="utf-8",
            )
            bench = {
                "clean": "src/m.py",
                "clean_source": "bench/clean.py",
                "mutants": [
                    {"name": "пропал GOOD", "class": "потерянная ветка отказа", "file": "bench/bad.py"},
                    {"name": "правка без дефекта", "class": "подменённый коэффициент", "file": "bench/ok.py"},
                ],
            }
            report = measure.measure(predicate, root, bench, "t")
        self.assertTrue(report["clean_ok"])
        self.assertEqual(report["false_reject"], 0.0)
        self.assertEqual(report["mutants"], 2)
        self.assertEqual(report["detected"], 1)
        self.assertEqual(report["false_accept"], 0.5)
        self.assertEqual(report["by_class"]["подменённый коэффициент"]["detected"], 0)

    def test_empty_bench_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bench.json"
            path.write_text(json.dumps({"clean": "src/m.py", "mutants": []}), encoding="utf-8")
            with self.assertRaises(measure.BenchError):
                measure.load_bench(path)


class TestCliEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_project(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_cycle(self):
        code, out = run_cli(self.root, "parse")
        self.assertEqual(code, 0, out)
        self.assertIn("всего спанов: 3", out)
        span_ids = [s["span_id"] for s in model.load_jsonl(self.root / "docs/registry/spans.jsonl")]

        code, out = run_cli(self.root, "coverage")
        self.assertEqual(code, 1)
        self.assertIn("uncovered_span", out)

        # Спан 0 и 2 — не требования; спан 1 — требование must.
        self.assertEqual(run_cli(self.root, "verdict", "--span-id", span_ids[0], "--kind", "background", "--by", BY)[0], 0)
        self.assertEqual(run_cli(self.root, "verdict", "--span-id", span_ids[2], "--kind", "background", "--by", BY)[0], 0)
        code, out = run_cli(self.root, "coverage")
        self.assertEqual(code, 1)
        self.assertIn("uncovered_span", out)

        code, out = run_cli(
            self.root, "add-req", "--span-id", span_ids[1], "--strength", "must", "--by", BY
        )
        self.assertEqual(code, 0, out)
        rec = model.load_jsonl(self.root / "docs/requirements-registry.jsonl")[0]
        span = model.load_jsonl(self.root / "docs/registry/spans.jsonl")[1]
        self.assertEqual(rec["raw_text"], span["text"])  # дословно, без нормализации

        code, out = run_cli(self.root, "coverage")
        self.assertEqual(code, 0, out)
        self.assertIn("ЧИСТО", out)

        code, out = run_cli(self.root, "drift")
        self.assertEqual(code, 1)
        self.assertIn("unproven_requirement", out)

        predicate = write_checker(self.root)
        code, out = run_cli(
            self.root,
            "invariant-add",
            "--req", "REQ-0001",
            "--predicate", predicate,
            "--transitions", "retry_on_upload,retry_exhausted",
            "--by", BY,
        )
        self.assertEqual(code, 0, out)

        code, out = run_cli(
            self.root,
            "evidence",
            "--req", "REQ-0001",
            "--inv", "INV-0001",
            "--transition", "retry_on_upload",
            "--result", "pass",
            "--defeater", "если повторов нет при двух сбоях подряд",
            "--by", BY,
        )
        self.assertEqual(code, 0, out)

        code, out = run_cli(self.root, "drift")
        self.assertEqual(code, 0, out)
        code, out = run_cli(self.root, "replay")
        self.assertEqual(code, 0, out)
        self.assertIn("ok  REQ-0001", out)

        # Выводим требование из реестра — доказательство обязано стать сиротой.
        code, out = run_cli(
            self.root, "revise", "--req", "REQ-0001", "--superseded-by", "REQ-0002", "--by", BY
        )
        self.assertEqual(code, 0, out)
        code, out = run_cli(self.root, "drift")
        self.assertEqual(code, 1)
        self.assertIn("orphaned_evidence", out)

    def test_measure_recorded_and_evidence_carries_it(self):
        run_cli(self.root, "parse")
        span_ids = [
            s["span_id"]
            for s in model.load_jsonl(self.root / "docs/registry/spans.jsonl")
        ]
        for sid in (span_ids[0], span_ids[2]):
            run_cli(self.root, "verdict", "--span-id", sid, "--kind", "background", "--by", BY)
        run_cli(self.root, "add-req", "--span-id", span_ids[1], "--by", BY)
        predicate = write_checker(self.root)
        run_cli(self.root, "invariant-add", "--req", "REQ-0001", "--predicate", predicate,
                "--transitions", "retry_on_upload", "--by", BY)

        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "bench").mkdir()
        (self.root / "bench" / "mutant.py").write_text("x = 2\n", encoding="utf-8")
        (self.root / "bench" / "bench.json").write_text(
            json.dumps(
                {
                    "clean": "src/app.py",
                    "mutants": [
                        {"name": "коэффициент", "class": "подменённый коэффициент",
                         "file": "bench/mutant.py"}
                    ],
                }
            ),
            encoding="utf-8",
        )

        code, out = run_cli(self.root, "measure", "--inv", "INV-0001", "--by", BY)
        # Предикат не читает код и всегда зелёный: дефект обязан остаться незамеченным.
        self.assertEqual(code, 0, out)
        self.assertIn("обнаружено 0 из 1", out)
        self.assertIn("пропуск 1.0", out)

        code, out = run_cli(self.root, "evidence", "--req", "REQ-0001", "--inv", "INV-0001",
                            "--transition", "retry_on_upload", "--result", "pass",
                            "--defeater", "повторов нет при двух сбоях", "--by", BY)
        self.assertEqual(code, 0, out)
        record = model.load_jsonl(self.root / "docs/registry/evidence.jsonl")[-1]
        self.assertIsNotNone(record["measured"])
        self.assertEqual(record["measured"]["false_accept"], 1.0)
        self.assertEqual(record["measured"]["mutants"], 1)

    def test_stale_cache_blocks_coverage(self):
        run_cli(self.root, "parse")
        span_ids = [s["span_id"] for s in model.load_jsonl(self.root / "docs/registry/spans.jsonl")]
        for sid, kind in ((span_ids[0], "background"), (span_ids[1], "requirement"),
                          (span_ids[2], "background")):
            run_cli(self.root, "verdict", "--span-id", sid, "--kind", kind, "--by", BY)
        self.assertEqual(run_cli(self.root, "coverage")[0], 0)
        (self.root / "notes" / "chat-2026-10-30.md").write_text(
            "Клиент: нужен экспорт отчёта в CSV и в XLSX.\n", encoding="utf-8"
        )
        code, out = run_cli(self.root, "coverage")
        self.assertEqual(code, 1)
        self.assertIn("stale_span_cache", out)

    def test_open_verdict_requires_verbatim_quote(self):
        run_cli(self.root, "parse")
        span_id = model.load_jsonl(self.root / "docs/registry/spans.jsonl")[0]["span_id"]
        code, _ = run_cli(
            self.root, "verdict", "--span-id", span_id, "--kind", "open",
            "--quote", "пересказ своими словами", "--by", BY,
        )
        self.assertEqual(code, 2)
        code, _ = run_cli(
            self.root, "verdict", "--span-id", span_id, "--kind", "open",
            "--quote", "Клиент: нужен экспорт", "--by", BY,
        )
        self.assertEqual(code, 0)

    def test_tampered_checker_exit_3(self):
        run_cli(self.root, "parse")
        span_ids = [s["span_id"] for s in model.load_jsonl(self.root / "docs/registry/spans.jsonl")]
        for sid, kind in ((span_ids[0], "background"), (span_ids[2], "background")):
            run_cli(self.root, "verdict", "--span-id", sid, "--kind", kind, "--by", BY)
        run_cli(self.root, "add-req", "--span-id", span_ids[1], "--by", BY)
        predicate = write_checker(self.root)
        run_cli(self.root, "invariant-add", "--req", "REQ-0001", "--predicate", predicate,
                "--transitions", "retry_on_upload", "--by", BY)
        run_cli(self.root, "evidence", "--req", "REQ-0001", "--inv", "INV-0001",
                "--transition", "retry_on_upload", "--result", "pass",
                "--defeater", "повторов нет при двух сбоях", "--by", BY)
        (self.root / predicate).write_text("print('{}')\n", encoding="utf-8")
        code, out = run_cli(self.root, "replay")
        self.assertEqual(code, 3, out)


if __name__ == "__main__":
    unittest.main()
