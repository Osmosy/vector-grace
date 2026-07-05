# Vector Grace 2.0

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
