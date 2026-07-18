# Database

NIRA stores canonical state in `<state-dir>/runtime.db` using SQLite. There is no cloud synchronization.

| Table | Data |
| --- | --- |
| `conversations` / `conversation_messages` | local session metadata and transcript |
| `vector_store` | text, metadata, and optional embeddings |
| `knowledge_graph` | extracted relationships |
| `workflow_memory` | execution traces and success |
| `error_memory` | failed-task output |
| `research_memory` | topics, summaries, concepts, references |
| `performance_metrics` | label, duration, success, timestamp |

Conversation deletion removes messages and then the parent conversation. Markdown export occurs only at a user-selected path. Interaction-training JSONL is disabled by default. Permission decisions are bounded in memory and deliberately omit arguments.

## Limitations

The canonical store is not encrypted and has no formal migration/version framework. Protect the state directory using operating-system access controls. Before changing schemas, add versioned migrations, backup/restore tests, foreign-key enforcement, retention settings, and corruption recovery.
