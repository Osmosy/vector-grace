#!/usr/bin/env bash
# Три гейта на мини-проекте. Ожидается: coverage 0, drift 0, replay 0.
# Ломается намеренно: уберите range(attempts) из src/upload.py — replay вернёт 1.
set -u
cd "$(dirname "$0")"
grace() { python3 ../../grace.py --root . "$@"; }

rc=0
for gate in coverage drift replay; do
    if ! grace "$gate"; then
        echo "ГЕЙТ $gate: код $?"
        rc=1
    fi
done
exit "$rc"
