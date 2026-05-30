# GRACE — Graph-RAG Anchored Code Engineering: Полное руководство

> Источник: https://github.com/osovv/grace-marketplace (v3.10.0)
> Автор: Vladimir Ivanov (@turboplanner)
> Лицензия: MIT

---

## Проблема, которую решает GRACE

LLM теряют контекст между сессиями. Без структуры:
- Не знают, какие модули существуют и как они связаны
- Генерируют код, который дублирует или противоречит существующему
- Не могут трассировать баги по кодовой базе
- Дрейфуют от оригинальной архитектуры со временем

---

## Шесть базовых принципов GRACE

### 1. Никогда не пиши код без контракта
До генерации любого модуля → MODULE_CONTRACT с PURPOSE, SCOPE, INPUTS, OUTPUTS.
Контракт — источник истины. Код реализует контракт, не наоборот.

### 2. Семантическая разметка — не комментарии
`// START_BLOCK_NAME` и `// END_BLOCK_NAME` — навигационные якоря для RAG и attention anchors для контекстного управления LLM. Это несущая структура.

### 3. Граф знаний всегда актуален
`docs/knowledge-graph.xml` — единая карта проекта. Добавил модуль → добавь в граф. Добавил зависимость → добавь CrossLink. Граф никогда не дрейфует от реальности.

### 4. Синтез сверху вниз
Строгий пайплайн генерации:
```
Requirements → Technology → Development Plan → Verification Plan → Module Contracts → Code + Tests
```
Никогда не прыгать в код. Если требования неясны — остановись и уточни.

### 5. Верификация — это архитектура
Тесты, трейсы, лог-маркеры — не финальная обработка. Это часть архитектурного чертежа. Если другой агент не может верифицировать или дебажить модуль по оставленным артефактам — модуль не закончен.

### 6. Управляемая автономность (PCAM)
- **Purpose**: определяется контрактом (ЧТО строить)
- **Constraints**: определяется development plan (ГРАНИЦЫ)
- **Autonomy**: агент выбирает КАК реализовать
- **Metrics**: контракт + верификационные артефакты говорят, готово ли

Свобода в КАК, но не в ЧТО. Если контракты кажутся неверными — предложи изменение, не отклоняйся молча.

---

## Четыре взаимосвязанных системы GRACE

```
Knowledge Graph (docs/knowledge-graph.xml)
    ↓  карты модули, зависимости, публичные интерфейсы
Module Contracts (MODULE_CONTRACT в каждом файле)
    ↓  определяет ЧТО делает каждый модуль
Semantic Markup (START_BLOCK / END_BLOCK в коде)
    ↓  делает код навигабельным с гранулярностью ~500 токенов
Verification Plan (docs/verification-plan.xml)
    ↓  определяет КАК доказывается корректность через тесты, трейсы, логи
Operational Packets (docs/operational-packets.xml)
    ↓  стандартизирует пакеты выполнения, дельты, передачу отказов
```

---

## Основные артефакты GRACE

| Артефакт | Роль |
|----------|------|
| `docs/requirements.xml` | Намерения продукта, скоуп, юзкейсы |
| `docs/technology.xml` | Стек, инструменты, ограничения, рантайм, тестирование |
| `docs/development-plan.xml` | Модули, контракты, порядок реализации, фазы, потоки |
| `docs/verification-plan.xml` | Верификационные записи, тест-команды, сценарии, маркеры |
| `docs/knowledge-graph.xml` | Карта модулей, зависимости, публичные аннотации, навигация |
| `docs/operational-packets.xml` | Шаблоны ExecutionPacket, GraphDelta, VerificationDelta, FailurePacket |

**Публичные/Shared vs Файловые/Local:**

| Где | Что |
|-----|-----|
| Shared XML | Публичные контракты модулей, публичные интерфейсы, зависимости, верификация |
| File-local markup | MODULE_CONTRACT, MODULE_MAP, CHANGE_SUMMARY, function contracts, semantic blocks |

Правило: `grace module show` = публичная истина, `grace file show` = файл-локальная истина.

---

## Семантическая разметка (Semantic Markup)

### Уровень модуля (начало каждого файла)

```
// FILE: path/to/file.ext
// VERSION: 1.0.0
// START_MODULE_CONTRACT
//   PURPOSE: [Что делает модуль — одно предложение]
//   SCOPE: [Какие операции включены]
//   DEPENDS: [Список зависимостей по M-xxx ID]
//   LINKS: [Ссылки на узлы графа знаний]
//   ROLE: [RUNTIME | TEST | BARREL | CONFIG | TYPES | SCRIPT]
//   MAP_MODE: [EXPORTS | LOCALS | SUMMARY | NONE]
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   exportedSymbol - краткое описание
// END_MODULE_MAP
```

### Уровень функции

```
// START_CONTRACT: functionName
//   PURPOSE: [Что делает — одно предложение]
//   INPUTS: { paramName: Type - описание }
//   OUTPUTS: { ReturnType - описание }
//   SIDE_EFFECTS: [Какое внешнее состояние модифицирует]
//   LINKS: [Связанные модули/функции через граф знаний]
// END_CONTRACT: functionName
```

### Уровень блока кода (внутри функций)

```
// START_BLOCK_VALIDATE_INPUT
// ... код ...
// END_BLOCK_VALIDATE_INPUT
```

### Правила гранулярности

1. ~500 токенов на блок. Слишком большой — модель теряет локальность. Слишком маленький — разметка становится шумом.
2. Имена блоков уникальны внутри файла.
3. Каждый `START_BLOCK_X` → парный `END_BLOCK_X`.
4. Имена блоков описывают ЧТО, а не КАК.

### Логирование

Все важные логи привязаны к семантическим блокам:
```
logger.info(`[ModuleName][functionName][BLOCK_NAME] message`, {
  correlationId,
  stableField: value,
});
```
Это создаёт прямую связь от рантайм-логов к блокам исходного кода.

---

## Knowledge Graph

### Структура

```xml
<KnowledgeGraph>
  <Project NAME="project-name" VERSION="1.0.0">
    <keywords>keyword1, keyword2</keywords>
    <annotation>Описание проекта для LLM domain activation</annotation>

    <M-CONFIG NAME="Config" TYPE="UTILITY" STATUS="implemented">
      <purpose>Конфигурация приложения</purpose>
      <path>src/config/index.ts</path>
      <depends>none</depends>
      <verification-ref>V-M-CONFIG</verification-ref>
      <annotations>
        <fn-loadConfig PURPOSE="Load and validate config" />
        <type-AppConfig PURPOSE="Configuration type definition" />
        <export-config PURPOSE="Singleton config instance" />
      </annotations>
    </M-CONFIG>

    <CrossLink from="M-DB" to="M-CONFIG" relation="reads-config" />
  </Project>
</KnowledgeGraph>
```

### Уникальные теги — не генерические!

❌ `<Module ID="M-CONFIG">...</Module>` → closing-tag polysemy, LLM теряет контекст
✅ `<M-CONFIG>...</M-CONFIG>` → семантический аккумулятор, `</M-CONFIG>` однозначно

| Сущность | Плохо | Правильно |
|----------|-------|-----------|
| Module | `<Module ID="M-CONFIG">` | `<M-CONFIG NAME="Config" TYPE="UTILITY">` |
| Phase | `<Phase number="1">` | `<Phase-1 name="Foundation">` |
| Flow | `<Flow ID="DF-SEARCH">` | `<DF-SEARCH NAME="...">` |
| Функция | `<function name="search">` | `<fn-search .../>` |
| Тип | `<type name="SearchResult">` | `<type-SearchResult .../>` |

**Почему:** Уникальные токены служат «аккумуляторами» — закрывающий `</M-CONFIG>` реактивирует все семантические ассоциации с `<M-CONFIG>`. Генерический `</Module>` заставляет LLM разрешать неоднозначность, тратя attention capacity.

---

## Contract-Driven Development

### Поток разработки

```
Requirements → Architecture → Verification Plan → Module Contracts → Function Contracts → Code + Tests
```

Никогда не перескакивать уровни. Если требования неясны — остановись.

### PCAM (Governed Autonomy)

| Аспект | Откуда | Значение |
|--------|--------|----------|
| **P**urpose | Контракт | ЧТО строить |
| **C**onstraints | Development plan | ГРАНИЦЫ |
| **A**utonomy | Агент решает | КАК реализовать |
| **M**etrics | Контракт + верификация | Готово ли? |

### Правила модификации контрактов

1. Прочитай MODULE_CONTRACT перед редактированием файла
2. Обнови MODULE_MAP при изменении публичных/локальных символов
3. Обнови knowledge-graph.xml при изменении модулей/зависимостей
4. Обнови verification-plan.xml при изменении тестов/маркеров
5. Добавь CHANGE_SUMMARY после фикса багов
6. Никогда не удаляй семантическую разметку
7. Предлагай изменение контракта, не отклоняйся молча
8. Используй осмысленные имена и конкретные PURPOSE

---

## Verification-Driven Development

Верификация в GRACE отвечает на четыре вопроса:
1. Выдала ли система правильный результат?
2. Следовала ли она допустимому пути выполнения?
3. Может ли другой агент дебажить провал по оставленным артефактам?
4. Безопасен ли модуль для длинных автономных прогонов?

### Три слоя верификации

1. **Детерминистические ассерты** — стабильные выходы, return values, state transitions
2. **Trace/log ассерты** — пути выполнения, branch decisions, retries, failure handling
3. **Integration/smoke проверки** — end-to-end viability

### Уровни исполнения

- **Module level**: typecheck, lint, unit tests, локальные ассерты (worker)
- **Wave level**: integration checks для затронутых поверхностей (post-wave)
- **Phase level**: full suite, full integrity audit, final reconciliation

### Autonomy Gate

Перед отправкой модуля в длинный автономный прогон:
1. Существует V-M-xxx запись для модуля?
2. Есть хотя бы одна module-local команда?
3. Названы success и failure сценарии?
4. Required log markers / trace assertions делают дивергенцию наблюдаемой?
5. Wave-level / phase-level follow-up назван?
6. Операционные пакеты захватывают assumptions, stop conditions, next action?

---

## Operational Packets

### ExecutionPacket

Шаблон для передачи контекста worker-агенту:
- Module ID, purpose, target paths, write scope
- Preferred stack excerpt from technology.xml
- Module contract excerpt
- Graph entry excerpt
- Dependency contract summaries
- Verification excerpt (commands, scenarios, markers, test files)
- Assumptions, stop conditions, retry budget

### GraphDelta

Предложение по обновлению knowledge-graph.xml:
- Public interface changes only
- New/removed CrossLinks
- New/removed annotations

### VerificationDelta

Предложение по обновлению verification-plan.xml:
- New/changed test files
- New/changed commands
- New/changed required markers
- Gate follow-up notes

### FailurePacket

При провале верификации:
- Какой сценарий провалился
- Ожидаемый evidence vs наблюдаемый
- Первая расходящаяся функция/блок
- Предложенное следующее действие

---

## Semantic Anchoring

GRACE предполагает, что агенты работают лучше, когда код и артефакты несут доменное значение напрямую:

- ✅ `CustomerProfile`, `ArchiveDatabase`, `ValidateInput`, `BLOCK_ASSIGN_TITLE`
- ❌ Абстрактные placeholder'ы, непрозрачные ID

Сохраняй PURPOSE, SCOPE и scenario текст достаточно конкретным, чтобы описывать трансформацию, а не просто файловую границу.

---

## Семантическая привязка (Semantic Anchoring)

GRACE предполагает, что агенты работают лучше, когда код и артефакты несут доменное значение напрямую. Это не заменяет контракты — это делает контракты проще для точного исполнения агентами.

### Научное обоснование: хрупкость LLM-текста и перплексия

Почему семантическая разметка в коде объективно лучше внешних Markdown-файлов — не вопрос эстетики. Это следствие фундаментального свойства LLM:

**LLM-текст — не просто слова.** Это ключи к векторным комбинациям в embedding-пространстве, где закодировано больше семантики, чем видно на поверхности. Когда одна LLM читает текст другой LLM, она воспринимает «родные» паттерны, заточенные под Attention. Когда человек редактирует этот текст — он разрушает скрытые сигналы.

Подробнее: `references/perplexity-metric.md` и `references/llm-text-brittleness-and-perplexity.md` (в репозитории agents-best-practices).

**Ключевые работы:**
- arXiv 2502.11779v2 — Self-Aligned Perplexity
- «LLMs Show Surface-Form Brittleness Under Paraphrase Stress Tests»
- «Language Models Transmit Behavioural Traits Through Hidden Signals in Data»

**Следствия для GRACE:**
1. Инлайн-разметка сохраняет исходную семантическую когерентность
2. Внешние Markdown-файлы деградируют понимание — текст «причёсан» человеком
3. RAG/MCP, разрезающие документацию, разрушают когерентность
4. Никогда не перефразируй сгенерированный LLM контракт/блок
5. Вэньянь-промптинг не случаен — доказуем через перплексию

---

## Типы модулей GRACE

| Type | Описание |
|------|----------|
| ENTRY_POINT | Где начинается исполнение (CLI, HTTP handler, event listener) |
| CORE_LOGIC | Бизнес-правила и доменная логика |
| DATA_LAYER | Персистенция, запросы, кеширование |
| UI_COMPONENT | Элементы UI |
| UTILITY | Общие хелперы, конфигурация, логирование |
| INTEGRATION | Адаптеры внешних сервисов |

---

## Типичный Workflow

1. `$grace-init` — создать docs/ структуру и AGENTS.md
2. Заполнить `requirements.xml` и `technology.xml` вместе с агентом
3. `$grace-plan` — архитектура модулей, контракты, потоки, зависимости
4. `$grace-verification` — тесты, трейсы, log-driven evidence
5. `$grace-execute` — последовательная генерация с ревью и коммитами
6. `$grace-multiagent-execute` — параллельные волны с controller-managed sync
7. `$grace-refactor` — переименование/перемещение/разделение без drift
8. `$grace-refresh` — синхронизация графа и верификации после ручных изменений
9. `$grace-fix error-description` — дебаг через семантическую навигацию
10. `$grace-status` — отчёт о здоровье проекта
11. `$grace-ask` — Q&A по артефактам проекта

---

## Execution Profiles (multiagent)

### `safe`
- Approval на каждую волну
- Contract + verification review для каждого модуля
- Targeted graph sync + full refresh на границах фаз

### `balanced` (default)
- Один approval на исполнение upfront
- Compact execution packets вместо полных XML
- Module-local verification + scoped gate reviews

### `fast`
- Только для зрелых кодовых баз с сильной верификацией
- Минимальный контекст для точного scope исполнения
- Batch integrity audit на границах фаз

---

## Commit Conventions

### Implementation commits
```
grace(MODULE_ID): краткое описание того, что сделано

Фаза N, Шаг order
Module: module name (module path)
Contract: one-line purpose from development-plan.xml
```

### Shared artifact commits
```
grace(meta): sync после MODULE_ID
```

### Phase completion
```
grace(plan): mark Phase N "phase name" as done
```

### Worker commit bodies
Обязаны перечислять конкретные файлы/функции/экспорты, которые изменились.
Запрещены: «harden X», «add Y evidence», «enforce Z».
Правильно: «catch ENOENT in loadPivvConfig and throw CONFIG_NOT_FOUND»

---

## Ключевое

> GRACE — процесс-первичен, не промпт-первичен. Делай больше работы до запуска, чтобы у агента было меньше неоднозначности при исполнении.

> Давай агенту именованные контракты, потоки, маркеры и чекпоинты вместо абстрактных призывов.

> Относись к автономности как к управляемому режиму исполнения, который должен пройти явный readiness gate.

Из комментария автора (Владимир Иванов):
- Текущая версия GRACE отличается от статей — автоматический цикл тестирования для автономных агентов
- LDD (Log-Driven Development) — «зомби режим» агентов требует другой разметки логов
- «ИИ развивается революционно, а не эволюционно — что-то нужно пересмотреть после мощных апгрейдов вендоров LLM»
- В разработке: адаптация под китайские LLM и Enterprise-стандарты документации для кодовых баз от 1M+ строк

---

## GRACE 2.0 (пререлиз, май 2026)

> Ключевые изменения от автора. Доступно клиентам в приватном репозитории.

### 1. Doxygen — штатная ИИ-документация для Python

Python — самый запущенный стек для инлайн-документации ИИ-агентов:
- Docstrings плохо подходят для каузального чтения после якоря
- Нет штатных средств для кастомных карточек контрактов (нужны поля для AI-агентов, а не просто аргументы и description)
- Необходимо добавлять новые поля для AI-агентов работы с кодом

**Почему Doxygen:**
- **Скорость**: ~50 000 строк кода/мин с эффективным кешированием. Проверен на кодовых базах в несколько миллионов строк
- **XML для ИИ**: штатный XML-вывод с мелкой структурой и связями. Агенты изучают обзор по XML, потом навигируют к файлам. JSON-простыни генерируют галлюцинации на больших контекстах — XML побит мелко и со связями, это качественно лучше
- **Множество выгрузок**: веб-сайт документации, RTF, LaTeX для полиграфического качества схем, Call Graph
- **Обратная связь**: Doxygen выводит агенту на консоль, что не так с разметкой — в отличие от графов, собранных промптами
- **Аналоги**: JSDoc (JS), rustdoc (Rust), DocFX (.NET) — схожие функции, но не всегда с XML-выводом
- **Для Python это «космический уровень» после docstrings**

### 2. Замена графа по коду → XML от Doxygen + GREP-хинты

Проблема: клиенты собирали граф по коду промптами — работает на порядки медленнее Doxygen и даёт слабую обратную связь о нарушении разметки.

**GREP-хинты для Lighting-внимания китайских моделей:**
- В промты прошиты новые якоря для Lighting-внимания (DeepSeek V4, GLM-5)
- Агенту не обязательно лезть в XML-документацию — он может «грепаться» через десятки и сотни модулей разом
- **Критический инсайт о «зомби-режиме»**: автономные агенты завязаны на GREP в выученных траекториях — это высший приоритет. Вы можете упрашивать запустить хитрый MCP или считать хитрый XML, но агент всё равно пойдёт «грепаться», так как только так может висеть на стабильной траектории
- **Решение**: не бороться с GREP, а возглавить — подложить специальные поисковые GREP-теги для фичи «семантический срез через 1000 модулей разом»

### 3. «Вэньянь-промптинг» — сжатие описаний в ~5 раз

Автор добавил крайне экономичные по токенам промпт-формулировки:
- Оптимизированы под паттерны внимания китайских LLM (DeepSeek V4, GLM-5)
- Называет их «заклятиями» — требуют тестирования
- Сжатие описаний примерно в 5 раз по сравнению с обычным промптингом

### Когда обновляться до 2.0

| Ситуация | Рекомендация |
|----------|-------------|
| Проект на Python | Doxygen вместо docstrings, обязательная XML-генерация |
| Китайские модели (DeepSeek V4, GLM-5) | GREP-хинты критичны для корректной навигации |
| Кодовая база >100K строк | Doxygen + GREP-теги масштабируются лучше ручного графа |
| «Зомби-режим» автономных агентов | LDD-разметка логов, старая не работает |
| Нужна обратная связь по разметке | Doxygen выводит ошибки на консоль агенту |