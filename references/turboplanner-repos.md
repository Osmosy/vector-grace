# Репозитории автора GRACE (Владимир Иванов)

## GitHub

- **TurboPlanner** — https://github.com/TurboPlanner (организация, 4 репо, 21 фолловер)
- **Rai220** — https://github.com/Rai220/my-health-public (генетический консультант)

## Репо TurboPlanner

| Репо | Описание | Статус |
|------|----------|--------|
| worker | "# worker" | заготовка, 1 коммит |
| images | JS, GPLv3 | заготовка |
| ai_tests | Python, 1★ | **рабочий журнал задач** |
| imagen-openrouter | форк, 12★ | генератор изображений |

## ai_tests — Ключевое репо

Рабочий журнал автора: Task → Agent → Report + Code. Минималистичный GRACE без XML-тегов.

Файлы:
- auth.md — задача на WebAuthn-фикс (человек пишет контракт)
- intel.md — задача на OpenVINO + NPU
- npu_test_report.md — отчёт агента о тесте NPU
- test_npu.py, test_qwen_npu.py, diagnose_npu.py — код от агента
- disable_hybrid_webauthn.py/bat — скрипты от агента

Паттерн:
1. Человек пишет Task с контрактом (requirements + steps)
2. Агент выполняет → генерирует Report + Code
3. Человек ревьюит отчёт

На основе этого создан навык `agent-task-journal` и репо ~/projects/agent-tasks/.

## Железо автора

Intel Core Ultra 9 285H + NPU (AI Boost) + Arc 140T (16GB) + RTX 5080.
NPU тестировался с Phi-3-mini-4k через OpenVINO GenAI.

## Дата наблюдения

2026-06-28. Репо молодые, автор активно экспериментирует.
Стоит перепроверить через месяц — worker может вырасти в GRACE-харнес.
