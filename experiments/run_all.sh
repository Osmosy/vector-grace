#!/usr/bin/env bash
# Прогон всех экспериментов репозитория.
# Ожидаемые результаты — в experiments/README.md, опорные разборы — в references/.
set -u
cd "$(dirname "$0")" || exit 1

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "phantom-join: демо (happy-path тесты на повреждённых данных)"
python3 phantom-join/demo.py

hr "phantom-join: журнал без orphan_amount + оценка по критериям"
python3 phantom-join/run_log.py && python3 phantom-join/evaluate.py

hr "phantom-join: журнал с orphan_amount + оценка по критериям"
python3 phantom-join/run_log.py --orphan-amount && python3 phantom-join/evaluate.py

hr "model-probe: как модель пишет модуль сама"
python3 model-probe/analyze_probe.py
