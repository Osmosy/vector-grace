# Vector Grace 2.0

[![Ecosystem: Vector](https://img.shields.io/badge/Ecosystem-Vector-blue.svg)](https://osmosy.github.io/)

![Vector Grace](assets/logo.png)

**GRACE (Graph-RAG Anchored Code Engineering)** — методология навигации LLM-агентов по кодовой базе через контракты, семантическую разметку и граф знаний. Собрано по крупицам в Telegram-канале «AI Projects» Владимира Иванова.

## Что внутри

| Файл | Содержание |
|------|-----------|
| `SKILL.md` | Ядро GRACE — workflow, PCAM, уникальные теги, Controller/Worker, профили |
| `references/grace-methodology-guide.md` | Полное руководство (~24K) |
| `references/agent-project-viability.md` | Pre-check: когда GRACE применим |
| `references/ax-tree-rules.md` | Семантический AX Tree для UI |
| `references/deepseek-math-analysis.md` | GRACE глазами математика (5 принципов, AAG, Belief State) |
| `references/perplexity-metric.md` | Self-Aligned Perplexity как научная метрика |
| `references/grep-all-you-need.md` | PwC: grep > векторный поиск на всех LLM |
| `references/latent-reasoning-foundation.md` | Wang (2026): LLM Reasoning Is Latent + Berdoz et al. (ICML 2026): Reasoning Structure — теоретическое основание GRACE |
| `references/hidden-training-formats.md` | Скрытые форматы обучения LLM |
| `references/html-docs-for-ai-agents.md` | HTML-документация для AI-агентов — почему HTML побеждает Markdown (эссе Владимира Иванова) |
| `references/fastcontext-slm-explorer.md` | FastContext от Microsoft — SLM для поиска в кодовых базах, отделение exploration от solving (эссе Владимира Иванова) |
| `references/prompt-engineering-gpt55-outcome-first.md` | Промпт-инжиниринг для GPT-5.5 — outcome-first подход, personality, retrieval budget, валидация (разбор Пименова) |
| `references/comfyui-dit-artifact-cleanup.md` | ComfyUI DiT artifact cleanup |
| `references/indra-ocr-cpu.md` | Indra OCR (1M параметров, ONNX, без GPU): проверено на нашем слайде 154 — 404 мс/страница и все 18 чисел, но четыре с дефектом формата; где годится, а где нет, и лицензионное ограничение весов |

### Тестирование, надёжность и диагностика агентов

| Файл | Содержание |
|------|-----------|
| `references/kun-chen-tdd-and-ground-truth.md` | ProgramBench: forced TDD против свободного подхода (192 парные задачи, pass 52.4 → 48.8 %, стоимость +55 %, входные токены +112 %) и переход агентов на ground truth вместо тестов |
| `references/unit-test-only-reward-degradation.md` | PreciseCoder: unit-test-only GRPO учит править больше (3.94 → 8.28 строки) и галлюцинировать баги в корректном коде (no-op 30.8 → 20.5 %) |
| `references/rl-training-semantic-signals.md` | На какой сигнал реально обучены кодирующие модели: MiMo-V2.6, GLM-5, DeepSeek DSec — reward hacking как отдельная инженерия, рубрики критика поверх тестов, обнуление подтверждённых хак-наград |
| `references/ebt-evidence-based-testing.md` | Доказательное тестирование из life-critical стандартов: DO-178C (71 цель уровня A, 30 with independence; трассируемость к требованиям), IEC 62304, Common Criteria EAL, формальные методы от Floyd и Hoare до B-метода и Météor |
| `references/sft-code-training-and-module-contracts.md` | Классический SFT кодирующих моделей (Code Llama, self-instruct: тесты как фильтр датасета) и сдвиг к контрактам на модуль вместо контрактов на функцию |
| `references/grace-tests-as-logs-and-evidence.md` | Тесты как наполнение логов и доказательства по пунктам спеки (бремя доказательства, evidence-ассерт в журнале, невыдумываемость доказательства) |
| `references/agentic-e2e-vs-scripted-tests.md` | Скриптовые E2E против агентского тестирования через MCP как пользователя; баланс алгоритмических и агентских проверок |
| `references/diagnostics-over-tests-dirty-data.md` | Диагностика важнее ритуалов: грязные данные, фантомные записи и выпадения на JOIN (шесть зелёных тестов при повреждённом выходе), LDD — критерии надёжности как часть контекста |
| `references/anthropic-code-review-pipeline.md` | Конвейер ревью Anthropic при агентском коде: Find → Verify → Rank → Post, риск-классы человеческого одобрения, очередь слияния против актуального main, «инцидент → тест проверяющего агента»; отдельно — что подтверждено документацией, а что только пересказами, и где промо сглаживает факты |
| `experiments/` | Воспроизводимые прогоны к разборам: `phantom-join/` (журнал + критерии + оценка в трёх состояниях), `model-probe/` (как модель пишет модуль сама). Запуск: `bash experiments/run_all.sh` |
| `skills/grace/grace-diagnostics/SKILL.md` | Навык: диагностика в первую очередь — критерии надёжности в журнале, три состояния вердикта, evidence по пунктам спеки (остальные навыки — в `skills/`) |

## Ключевые принципы

1. **Примат замысла** — разработка с формальных XML-артефактов
2. **Синтез по чертежу** — код = compile(DevelopmentPlan.xml)
3. **Дуальность разметки** — якоря = шаблон + навигационная карта
4. **Grep-first** — векторный поиск проигрывает grep (PwC, 2026)
5. **Наблюдаемость** — belief state LLM → верифицируемый артефакт

## Основание

- Автор: Владимир Иванов (Telegram-канал «AI Projects»)
- GRACE 2.0: Doxygen для Python, Wenyan-prompting, GREP-hints
- Подтверждено исследованиями: ETH Zurich (AGENTS.md −3%), PwC (grep > vector)
