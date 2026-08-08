# Управляемая компактизация контекста

> Сессия 2026-08-08. Источник: анализ Hermes Agent context_compressor.py + методология пользователя.

## Проблема автосжатия

Автоматическая компактизация (batch compaction) — универсальный summary-промпт, который срабатывает по threshold (по умолчанию 50% context window). Для 1M контекста — ~500K.

Критические недостатки:

1. **Потеря акцентов.** Универсальный промпт не знает иерархии значимости. Сохраняет «всё поровну», теряя степени важности.

2. **Низкая степень сжатия.** Подробные summary дают 1:4 вместо достижимых 1:10 с релевантным контекстом.

3. **Самоликвидация документации.** После summary оригинальная сессия и её отчёт исчезают. Session reports — исторический источник, summary их уничтожает.

4. **Потеря ручных указаний.** 2-3 предложения пользователя о том, что важно для следующего агента — самая ценная часть. Универсальный промпт её не сохраняет адекватно.

## Промпт Claude Code (для сравнения)

Claude Code использует структурированный summary-промпт с 9 секциями: Primary Request, Key Technical Concepts, Files and Code Sections, Errors and fixes, Problem Solving, All user messages, Pending Tasks, Current Work, Optional Next Step.

Источник: https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/agent-prompt-conversation-summarization.md

Это один из лучших summary-промптов, но фундаментальный недостаток — универсальность = потеря акцентов.

## Hermes: лучше Claude Code, но та же проблема

Hermes Agent (context_compressor.py) имеет улучшения:

1. **Reference-only инструкция.** Summary помечен `[CONTEXT COMPACTION — REFERENCE ONLY]` — модель явно инструктирована не выполнять задачи из summary, только как background reference.

2. **Защита user-сообщений.** В micro-compaction пользовательские сообщения никогда не summarises, всегда verbatim.

3. **Auxiliary model.** Отдельный провайдер/модель для summarization (дешёвая/быстрая), не основная модель.

4. **Small-context floor.** Модели < 512K получают threshold 75% вместо 50%, чтобы не компактиить каждые 1-2 хода.

5. **Proactive prune.** Ранняя обрезка tool outputs (без LLM) до threshold, с gate на минимум reclaim.

6. **Focus topic.** `/compress focus [topic]` — summarizer сохраняет контекст по теме детально, остальное жмёт агрессивнее.

Но фундаментальная проблема та же: batch compaction сжимает middle вслепую, без классификации что важно, что в хранилище, что можно убрать.

## Архитектура Hermes: два режима компактизации

### Batch compaction (по умолчанию)

- Триггер: threshold_percent = 0.50 (50% context window)
- Алгоритм: prune tool results → protect head (system prompt + первые 3 сообщения) → protect tail (~20% threshold) → summarize middle через auxiliary LLM
- Для моделей < 512K: floor 75%
- Per-model override: `compression.model_thresholds`
- micro_compact: false (off по умолчанию)

### Micro-compaction (опционально)

- `compression.micro_compact: true`
- После каждого хода поглощает один exchange (assistant + tool results) в rolling summary
- Контекст остаётся плоским (~22% occupancy вместо sawtooth)
- Но: ломает prompt cache каждый ход (переписывает историю)
- На провайдерах с глубоким cache-дисконтом — может стоить дороже чем batch

### Конфигурация

```yaml
compression:
  enabled: true
  threshold: 0.50              # триггер batch
  threshold_tokens: null       # абсолютный cap
  target_ratio: 0.20           # tail budget = 20% от threshold
  protect_last_n: 20
  protect_first_n: 3
  micro_compact: false
  micro_compact_every_n_turns: 1
  proactive_prune_tokens: 0    # ранняя обрезка tool outputs
  proactive_prune_min_reclaim_tokens: 4096
  idle_compact_after_seconds: 0
  model_thresholds: {}         # per-model override

auxiliary:
  compression:
    provider: auto
    model: ''                  # пусто = авто-выбор
```

Threshold можно повышать: `hermes config set compression.threshold 0.70` — больше пространства для длинных сессий, но больше tail budget и latency.

## Многоуровневая стратегия (альтернатива автосжатию)

Вместо одного «compress» — 4 уровня:

### Уровень 1: Code docs (восстанавливается, не хранить в контексте)

AGENTS.md, inline комментарии, README. Агент re-read'ит при необходимости. Не нужен в контексте постоянно. Claude Code после compact читает «жадно» — code docs восстанавливают ~90% контекста.

### Уровень 2: Session reports (сохранить в хранилище, убрать из контекста)

После итерации: рефлексия → документ → файл в long_memory/archive/daily/. Оригинальная сессия остаётся в SQLite (session_search). Из контекста можно убрать.

### Уровень 3: Memory (факты и акценты — всегда в контексте)

2-3 предложения ручных указаний → MEMORY.md. Compact, всегда в system prompt. Не нужно summarise — уже сжато до сути.

### Уровень 4: Skills (процедуры — on-demand)

Отработанный workflow → навык. Не в контексте, пока не нужен. Progressive disclosure: skills_list (~3K токенов) → skill_view (полный) → reference files.

## Управляемая компактизация (оркестратор)

Агент сам определяет момент, сохраняет важный контекст в многоуровневую память, затем запускает компактизацию.

### Триггеры

1. Завершена итерация — естественный разрыв
2. Контекст >35% — не ждать 50%
3. Накопилось много tool outputs
4. Смена темы — прошлая итерация в архив

### Процесс

СОХРАНИТЬ → СЖАТЬ → ПРОВЕРИТЬ.

1. **Рефлексия** — что сделано, что важно, какие ошибки
2. **Проверка хранилища** — Hindsight recall, long_memory/, session_search (не дублировать)
3. **Сохранение** — по уровням: MEMORY.md (факты), Hindsight retain (решения), long_memory/decisions/ (дата+контекст), long_memory/archive/daily/ (session report), skill_manage (процедуры)
4. **Session Report** — файл с акцентами пользователя дословно
5. **/compress focus** — направляет summarizer на текущую задачу
6. **Верификация** — проверить что важное на месте после сжатия

### Принципы

- Сохранить → сжать → проверить. Не наоборот.
- Не дублировать: проверь хранилище перед сохранением.
- Code docs > session report для технического контекста.
- Ручные акценты пользователя — самая ценная часть, сохранить дословно.
- Tool outputs — не сохранять, они восстанавливаются re-read'ом.
- Проактивно: агент сам предлагает, не ждёт threshold.
- Честно: если нечего сохранять — сказать, не выдумывать.

## Память Hermes (5 слоёв)

| Слой | Что | Механизм |
|------|-----|----------|
| System Passport | Железо, модели, навыки, проекты | ~/.hermes/SYSTEM_PASSPORT.md, systemd timer 1x/день |
| Operational | Контекст событий, сессии | Context-mode MCP, session DB (SQLite + FTS5) |
| Long-term | Вечные факты, решения, проекты, архив | ~/.hermes/long_memory/ (core/decisions/projects/archive) |
| Knowledge Base | Векторный поиск, индексация | ctx_index, ctx_search, Ollama embeddings, Hindsight |
| Consolidation | Авто-проверки, рефлексия | systemd timers, Hindsight reflect, Hermes cron |

Hindsight (bank "hermes"): recall (<1s, поиск), retain (~20-40s, сохранение), reflect (~30s, синтез).

Разделение: компактное+всегда-нужное → Hermes native memory. Объёмное+событийное → Hindsight. Файлы → long_memory/.

## Связанные навыки

- `hermes-skills-system` — система навыков (установка, создание, hub, bundles, /learn)
- `session-documentation-ritual` — методология документирования (почему автосжатие плохо)
- `managed-compaction` — оркестратор компактизации (когда, как, куда сохранять, потом сжать)
- `long-term-memory` — 5-слойная архитектура памяти
- `hindsight-memory-practice` — recall/retain/reflect