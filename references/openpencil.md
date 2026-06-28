# OpenPencil — AI-native design tool (Figma alternative)

**Repo:** https://github.com/ZSeven-W/openpencil
**Stars:** 3509, open-source

## What it is

AI-native vector design tool with built-in MCP server and concurrent Agent Teams.
Prompt → design system → layout → code. Design-as-code.

## Why relevant to GRACE

- Design-to-code pipeline: openpencil → HTML → html-video
- MCP-first architecture — agents control design directly
- .pen files version-controlled in git — fits GRACE contract-first approach
- Compatible with design-md (DESIGN.md token spec)
- Replaces Figma in agent workflows

## Key features

- Built-in MCP server (connect Claude Code, Codex, Hermes)
- Concurrent Agent Teams — multiple agents work on same canvas
- Multi-model — can use different models for different design tasks
- Image generation — in-style, in-context illustrations
- Figma import — reads Figma frames
- Stock photo integration

## Integration with our stack

```
openpencil (design) → html/claude-design (markup) → html-video (MP4)
                      → design-md (token spec)
```

Skills in our ecosystem:
- openpencil (this one)
- html, html-diagram, html-plan
- claude-design, design-md, design-md-references
- popular-web-designs
- html-video (nexu-io)

## Date noted

2026-06-28
