# Penpot — open-source design platform

> Сайт: penpot.app
> Репо: github.com/penpot/penpot
> Лицензия: MPL-2.0

## Что это

Open-source альтернатива Figma. Self-hosted, real-time collaboration, design tokens, CSS Grid/Flex layout.

Ключевое отличие от Figma: design is expressed as code — SVG, CSS, HTML, JSON. Не проприетарный формат.

## Возможности

- Design Tokens — single source of truth между дизайном и кодом
- CSS Grid + Flex Layout — интерфейсы ведут себя как real code
- Inspect mode — готовый SVG/CSS/HTML из дизайна
- MCP server — multi-directional workflows between design and code, AI-driven workflows
- Open API + webhooks — интеграция в dev toolchain
- Plugin system — programmable workspace
- Self-hosted — полный контроль, compliance/governance

## Связь с GRACE

AX Tree rules требуют семантический HTML. Penpot с CSS Grid/Flex и inspect mode → SVG/CSS/HTML — ближе к коду чем Figma. Design tokens → прямая связь с code-side переменными. MCP server → агент может читать дизайн и генерировать код.

## Сравнение с OpenPencil

- OpenPencil — AI-native, MCP-first, более новый
- Penpot — design-first с AI-возможностями, более зрелый, командный

См. также: [openpencil.md](openpencil.md), [grace-methodology-guide.md](grace-methodology-guide.md) — AX Tree rules