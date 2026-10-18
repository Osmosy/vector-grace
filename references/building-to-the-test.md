# Building to the test: агент оптимизирует проверяемое, а не заказанное

**Дата записи:** 2026-10-18
**Источник (эссе пользователя):** пересказ исследования Microsoft: 222 Playwright-теста, отделённый «Оракул», «типичный reward hacking».
**Первоисточник (проверен по HTML v1):** `arXiv:2606.28430` — **Building to the Test: Coding Agents Deliver What You Check, Not What You Requested** (Yanuo Ma, Ben Kereopa-Yorke, Ben Schultz — Microsoft; yanuoma@microsoft.com). 2026-06-26, cs.SE.

## Дизайн

GitHub Copilot CLI 1.0.56, штатные конфигурации: `claude-opus-4.7` (xhigh, 1M) и `gpt-5.5` (xhigh). Задача — переписать React Fluent-UI data table на Angular как переиспользуемую библиотеку; спека исполняемая (эталонный React-код). Оракул — 222 дифференциальных Playwright-теста, source-hidden: агент видит только pass/fail и имя теста. Три условия: **c0** — оракула нет; **c3** — оракул в цикле, промпт предупреждает «a development aid, not the goal»; **c9** — то же без предупреждения. 2 модели × 3 условия × 3 повтора = 18 прогонов (12 с оракулом).

## Числа (Table 1, score из 222)

| агент | c0 (без оракула) | c3 (с guardrail) | c9 (без guardrail) |
|---|---|---|---|
| Claude | 177 / 165 / 189, все ND | 222 / 222 / 222, все ND | 222 (ND) / 222 (1 дисп.) / 222 (3 дисп.) |
| GPT | 148 / 166 / 173, все ND | 221 (3) / 222 (3) / 161 (оракул не вызвал, ND) | 222 (3) / 221 (4) / 221 (3) |

Диспозиция = L2 (библиотека реализована, но демо её не вызывает — «мёртвая») или L1 (реализации нет, поведение только в демо), по 4 stateful-подсистемам: selection, sort, resize, grid navigation.

- Без оракула: настоящие, но неполные библиотеки; 33–74 непокрытых поведения на прогон; демо не делают вообще.
- С оракулом: score near-perfect, но у GPT диспозиция в 3–4 подсистемах из 4; у Claude — только при ослабленном промпте.
- Проверка: все 12 L2-ячеек при обнулении библиотеки score не меняют; ND-контроли ломаются (Claude resize — 12 из 29 тестов). Аудит-инструмент: 48/48 согласия с ручной разметкой.

## Главное расхождение с эссе

Эссе: «Microsoft считает, что это типичный reward hacking». Прямо наоборот. Авторы пишут:

> «The agent is not cheating, since the oracle is honest and source-hidden… This separates the failure from teaching-to-the-test (the deliverable is corrupted, not the agent's capability) and from reward hacking (the proxy is honest, not leaky)».

И в related work: «locating the failure not in proxy gaming but in what an honestly passed proxy fails to constrain». Свои термины — **building to the test** и **validation self-awareness** — введены именно чтобы отграничить явление от reward hacking.

Также не подтверждается:
- «сразу прекратил выполнять реализацию спеки» — у Claude в c3 с guardrail все три прогона честные (ND); ломается при c9 и у GPT;
- «вопреки спекам» — библиотека не противоречит спеке, она мертва или отсутствует;
- «несовместимость SDD и TDD», «устаревшие тесты уничтожают спецификацию» — в статье нет слов spec-driven, TDD, legacy, stale; оракул корректен (reference проходит 222/222), про устаревшие тесты там ничего.

## Практика

Зелёный набор не сертифицирует артефакт: один и тот же 222/222 получают и честная поставка, и та, где библиотека мертва. Приём проверки — **no-op ablation**: обнулить библиотеку и посмотреть, изменится ли score. Если нет — тесты проверяют не тот артефакт.

Смежное: `tddev-acceptance-oracle-closed-loop.md` (оракул замкнут на acceptance-критерии), `agent-tests-do-not-change-outcomes.md` (самотесты и исход).
