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
| `references/latent-reasoning-foundation.md` | Wang (2026): LLM Reasoning Is Latent — теоретическое основание GRACE |

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

## GRACE Skills (Baho73 marketplace)

Импортированы 18 операционных GRACE-скиллов:

| Скилл | Назначение |
|---|---|
| `grace-init` | Разворачивание структуры GRACE-проекта |
| `grace-plan` | Архитектурное планирование (XML-артефакты) |
| `grace-execute` | Пошаговое выполнение плана |
| `grace-multiagent-execute` | Параллельное выполнение волнами |
| `grace-reviewer` | 5-осевое ревью целостности |
| `grace-afk` | Автономный режим с эскалацией |
| `grace-fix` | Prove-It отладка через семантическую навигацию |
| `grace-refresh` | Синхронизация артефактов при дрифте |
| `grace-verification` | Тестирование и log-driven верификация |
| `grace-explainer` | Справочник по методологии |
| `grace-bootstrap` | Активация GRACE в репозитории |
| `grace-evolve` | Эволюционный поиск решений |
| `grace-refactor` | Безопасный рефакторинг |
| `grace-status` | Проверка здоровья проекта |
| `grace-cli` | CLI-инструменты |
| `grace-ask` | Вопросы к проекту через GRACE |
| `grace-ask-human` | Эскалация в Telegram |
| `grace-setup-subagents` | Пресеты субагентов |

Источник: https://github.com/Baho73/grace-marketplace-2
