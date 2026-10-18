# TDFlow: 68.0% с самотестами против 94.3% с человеческими — и почему авторство не важно

**Дата записи:** 2026-10-18
**Источник (эссе пользователя):** «тесты ИИ — мусор, человеческие дают +27.8% на SWE-Bench; TDFlow решает 68.0% против 94.3%».
**Первоисточники (проверены):**
- `aclanthology.org/2026.eacl-long.70` — **TDFlow: Agentic Workflows for Test Driven Development** (Kevin Han, Siddharth Maddikayala, Tim Knappe, Om Patel, Austen Liao, Amir Barati Farimani), EACL 2026 Long Papers, pp. 1511–1527, Рабат, март 2026.
- `arXiv:2510.23761` v2 (2026-01-22) — та же работа, полный текст; PDF с ACL Anthology не докачался (обрывается на 16 КБ), числа сверены по arXiv.

## Числа (Table 1, Table 2)

SWE-Bench Lite, human-written tests:
- TDFlow 88.8% ($1.51 за задачу) против Agentless 61.0% ($0.53) — **+27.8 п.п.** к next best.

SWE-Bench Verified:
| режим | pass rate | стоимость |
|---|---:|---:|
| human-written tests | 94.3% | $1.01 |
| human-written, без Debug-субагента | 87.2% | $0.73 |
| LLM-generated tests | 68.0% | $4.12 |

- 800 прогонов, test hacking найден в 7 случаях (0.9%), засчитаны как провалы.
- Субагенты: Generate Tests — Claude 4 Sonnet; Explore Files, Revise Patch, Debug One — GPT-5.
- Внутреннее расхождение: в вводном тексте стоит 69.8%, в Table 2 — 68.0%.

## Ключевая условность (её легко пропустить)

Раздел 4.2 «The final hurdle to human-level accuracy lies in test generation»:

> «whether or not the reproduction test is written by a human or an LLM doesn't matter for downstream test resolution performance so long as the test truly tests for reproduction behavior».

Раздел 5 Discussion:

> «results in a 93.3% pass rate when using GPT-5 – highlighting that there is no fundamental difference between LLM-generated tests and human-written tests as long as the overall reproduction behavior is the same».

93.3% получены на подмножестве инстансов с **BTR = 0** (Bad Test Rate — доля неуспешных repro-тестов; успешный = падает до gold-патча и проходит после). Против 94.3% с человеческими — разница 1 п.п., паритет.

Авторы прямо называют лечение: «Long horizon reinforcement learning post-training specifically targeting test generation tasks is a promising route». То есть текущее ограничение техническое, а не принципиальная неспособность LLM выражать intent.

## Где эссе перегибает

- «+27.8% относительно тестов самого агента» — нет: +27.8 п.п. против Agentless на Lite. Human vs self-generated — 94.3% против 68.0% на Verified (26.3 п.п.), другое сравнение и другой датасет.
- «Тесты ИИ — мусор» — сильнее данных: 68.0% выше большинства baseline-систем. Точнее: LLM редко генерируют корректные repro-тесты, и это ограничивает автономный ремонт.
- «TDFlow — улучшенный TDD» — по механике это test resolution (patch propose/revise/debug против заданных тестов), а не red-green-refactor.
- «Тесты — передача intent» — в статье такого нет (слово intent встречается один раз, в другом смысле). Интерпретация правдоподобная, но не из данных.

## Практика

Человеческий тест ценен как независимый оракул, а не «потому что человек». Но BTR считается по gold-патчу, которого в реальной нерешённой задаче нет — поэтому в проде отфильтровать некорректные самотесты нечем. Отсюда практическое правило: самотесты не считать оракулом, пока нет внешнего источника ожидаемого поведения.

Смежное: `agent-tests-do-not-change-outcomes.md` (объём самотестов не меняет исход), `kun-chen-tdd-and-ground-truth.md` (TDD с самотестами −3.6 п.п.), `building-to-the-test.md` (агент оптимизирует наблюдаемый сигнал).
