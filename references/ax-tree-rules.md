# GRACE AX Tree Rules

Правило из памяти пользователя (подтверждено и расширено):

UI для ИИ = семантические теги (не div onClick), именованные контролы (не пустые textbox), явные состояния (aria-expanded).

## Проверка качества AX Tree

- `browser_snapshot` не должен показывать `generic` на месте кнопок
- Каждый `textbox` должен иметь имя (label)
- Каждое интерактивное состояние должно быть эксплицитно (aria-expanded, aria-selected, aria-checked)
- Плохой AX Tree = недоступный UI одновременно для людей, агентов и RL-обучения

## Правило из GRACE

Required before UI verification: run `browser_snapshot` and fix any:
- `generic` without semantics
- `textbox` without name
- missing states

See main SKILL.md for the full GRACE methodology.
