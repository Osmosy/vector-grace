# Context Consolidation with Cognee

GRACE Principle #7 mandates periodic consolidation of session context to prevent LLM attention degradation in long sessions.

## Why

Research by Lee et al. (arXiv:2605.26099) demonstrates that LLMs perform better when context is periodically compressed into vector representations — analogous to memory consolidation during sleep in humans. Raw conversation logs degrade attention; structured memory (graph + vectors) preserves it.

## What

Cognee provides a Memory Control Plane with three API calls:

| Method | Purpose |
|--------|---------|
| `cognee.add(text)` | Store facts into the knowledge pipeline |
| `cognee.cognify()` | Consolidate: extract entities/relations → graph (Ladybug) + vectors (LanceDB) |
| `cognee.search(query)` | Semantic retrieval across consolidated memory |

## Setup

Cognee is configured via `~/.cognee/.env`. Reference configuration:

```env
LLM_API_KEY=sk-...
LLM_PROVIDER=custom
LLM_MODEL=deepseek/deepseek-chat
LLM_ENDPOINT=https://api.deepseek.com/v1
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSIONS=768
HUGGINGFACE_TOKENIZER=sentence-transformers/all-MiniLM-L6-v2
```

Environment for execution:
```bash
COGNEE_SKIP_CONNECTION_TEST=true
GRAPH_DATABASE_PROVIDER=ladybug
GRAPH_DATABASE_SUBPROCESS_ENABLED=false
```

## Usage in GRACE Workflows

### grace-afk: Checkpoint Consolidation

During autonomous sessions, checkpoints trigger consolidation of the session journal:

```python
import asyncio, cognee

async def consolidate():
    # Feed session decisions into Cognee
    await cognee.add(open('docs/decisions.md').read())
    await cognee.cognify()
    
    # Optionally, query consolidated memory
    result = await cognee.search('current phase objectives')

asyncio.run(consolidate())
```

### Manual Sessions: Phase Transitions

When transitioning between GRACE phases (plan → execute, execute → refactor), consolidate the context to preserve reasoning:

```
After $grace-plan completes:
  cognee.add(plan_summary)
  cognee.cognify()

After $grace-execute completes:
  cognee.add(execution_results)
  cognee.cognify()
```

### Long Sessions: 50+ Message Heuristic

If a session exceeds ~50 messages without a phase transition, trigger consolidation proactively to prevent context drift.

## Relation to GRACE Knowledge Graph

| System | Purpose | Update Frequency |
|--------|---------|-----------------|
| `docs/knowledge-graph.xml` | Architectural map of modules, contracts, dependencies | When code structure changes |
| Cognee graph | Operational session memory (decisions, context, facts) | Every checkpoint / phase transition |

They complement each other. The architectural map is static between changes; the operational memory evolves with the session.

## Reference

Lee, S., McLeish, S., Goldstein, T., & Fanti, G. (2026). *Do Language Models Need Sleep? Offline Recurrence for Improved Online Inference*. arXiv:2605.26099.
